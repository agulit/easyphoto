"""Main application window."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QKeySequence,
    QPixmap,
)
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from seephoto.cache import PixmapCache
from seephoto.display_loader import DisplayResult, load_for_display, load_raw_preview
from seephoto.drop_handler import (
    accept_file_drag,
    mime_has_urls,
    paths_from_drop,
    pick_open_path,
)
from seephoto.filmstrip import ThumbnailStrip
from seephoto.formats import is_raw_path
from seephoto.gallery import list_images, neighbor
from seephoto.loader import LoadError
from seephoto.actions import (
    copy_pixmap_to_clipboard,
    crop_pixmap,
    delete_file_with_confirm,
    print_pixmap,
    save_pixmap_as,
)
from seephoto.crop_dialog import CropDialog
from seephoto.image_info import PropertiesDialog
from seephoto.toolbar import PhotoToolbar
from seephoto.viewer import _NAV_KEYS
from seephoto.viewer_pane import ViewerPane

_DISPLAY_MAX = 3840


def _screen_max_edge() -> int:
    from PySide6.QtWidgets import QApplication

    screen = QApplication.primaryScreen()
    if screen is None:
        return _DISPLAY_MAX
    size = screen.size() * screen.devicePixelRatio()
    edge = int(max(size.width(), size.height()) * 1.25)
    return max(1920, min(edge, _DISPLAY_MAX))


class _Phase1Worker(QThread):
    """极速 Phase-1：提取 RAW 内嵌 JPEG 预览（~50ms）或直接加载普通图片。"""

    preview_ready = Signal(int, object, object, object)   # gen, path, pixmap, meta
    finished_ok   = Signal(int, object, object, object)   # gen, path, pixmap, meta（非RAW直接在此完成）
    finished_err  = Signal(int, str)                      # gen, message

    def __init__(self, gen: int, path: Path, max_edge: int) -> None:
        super().__init__()
        self._gen = gen
        self._path = path
        self._max_edge = max_edge

    def run(self) -> None:
        if self.isInterruptionRequested():
            return
        try:
            if is_raw_path(self._path):
                # RAW：先提取内嵌预览给 UI，Phase-2 再精解
                preview = load_raw_preview(self._path, self._max_edge)
                if not self.isInterruptionRequested():
                    if preview:
                        self.preview_ready.emit(
                            self._gen, self._path,
                            QPixmap.fromImage(preview.image), preview,
                        )
            else:
                # 普通图片：Phase-1 直接完整加载，不需要 Phase-2
                result = load_for_display(self._path, self._max_edge)
                if not self.isInterruptionRequested():
                    self.finished_ok.emit(
                        self._gen, self._path,
                        QPixmap.fromImage(result.image), result,
                    )
        except LoadError as exc:
            self.finished_err.emit(self._gen, str(exc))
        except Exception:
            self.finished_err.emit(self._gen, f"加载失败: {self._path.name}")


class _Phase2Worker(QThread):
    """后台 Phase-2：RAW 完整精解（慢，但用户已经有预览可以浏览）。"""

    finished_ok = Signal(int, object, object, object)   # gen, path, pixmap, meta
    finished_err = Signal(int, str)

    def __init__(self, gen: int, path: Path, max_edge: int) -> None:
        super().__init__()
        self._gen = gen
        self._path = path
        self._max_edge = max_edge

    def run(self) -> None:
        if self.isInterruptionRequested():
            return
        try:
            result = load_for_display(self._path, self._max_edge)
            if not self.isInterruptionRequested():
                self.finished_ok.emit(
                    self._gen, self._path,
                    QPixmap.fromImage(result.image), result,
                )
        except LoadError as exc:
            self.finished_err.emit(self._gen, str(exc))
        except Exception:
            pass   # Phase-2 失败不弹窗，预览已经够用


# 向后兼容别名（PrefetchWorker 仍在用）
LoadWorker = _Phase1Worker


class PrefetchWorker(QThread):
    def __init__(self, path: Path, max_edge: int, cache: PixmapCache) -> None:
        super().__init__()
        self._path = path
        self._max_edge = max_edge
        self._cache = cache

    def run(self) -> None:
        key = self._path.resolve()
        if self._cache.get(key):
            return
        try:
            result = load_for_display(self._path, self._max_edge)
            pixmap = QPixmap.fromImage(result.image)
            self._cache.put(key, pixmap, result)
        except Exception:
            pass


class DropMixin:
    """Shared drag/drop handlers."""

    def _host_window(self) -> "MainWindow":
        return self.window()  # type: ignore[return-value]

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if mime_has_urls(event):
            accept_file_drag(event)
        else:
            super().dragEnterEvent(event)  # type: ignore[misc]

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if mime_has_urls(event):
            accept_file_drag(event)
        else:
            super().dragMoveEvent(event)  # type: ignore[misc]

    def dropEvent(self, event: QDropEvent) -> None:
        win = self._host_window()
        if hasattr(win, "_handle_file_drop"):
            win._handle_file_drop(event)
        else:
            event.ignore()


class DropStatusBar(DropMixin, QStatusBar):
    pass


class DropRoot(DropMixin, QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Root")
        self.setAcceptDrops(True)


class HintOverlay(DropMixin, QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("OverlayPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAcceptDrops(True)

        # 外层 layout：居中放置内容卡片
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 内容卡片 widget
        card = QWidget()
        card.setObjectName("HintCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("易图")
        title.setObjectName("HintTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        sub = QLabel(
            "拖放图片或文件夹到窗口（黑色区域均可）\n"
            "+ / − 或滚轮缩放 · ← → 切换图片 · 点击底部缩略图\n"
            "0 适应窗口 · 1 实际像素 · F11 全屏 · Esc 退出全屏"
        )
        sub.setObjectName("HintSub")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)

        badges_row = QHBoxLayout()
        badges_row.setSpacing(8)
        badges_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for text in ("JPEG PNG WebP", "NEF ARW CR2", "DNG RAF ORF", "DJI RAW"):
            badge = QLabel(text)
            badge.setObjectName("Badge")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badges_row.addWidget(badge)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.open_file_btn = QPushButton("打开图片")
        self.open_file_btn.setObjectName("GhostBtn")
        self.open_dir_btn = QPushButton("打开文件夹")
        self.open_dir_btn.setObjectName("GhostBtn")
        btn_row.addWidget(self.open_file_btn)
        btn_row.addWidget(self.open_dir_btn)

        layout.addWidget(title, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addLayout(badges_row)
        layout.addSpacing(8)
        layout.addLayout(btn_row)

        outer.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)


class MainWindow(QMainWindow):
    def __init__(self, initial: Path | None = None) -> None:
        super().__init__()
        from seephoto import APP_NAME, version_short

        self._app_title = f"{APP_NAME} {version_short()}"
        self.setWindowTitle(self._app_title)
        self.setMinimumSize(960, 640)
        self.resize(1280, 800)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # 窗口图标（标题栏 + 任务栏）
        import sys as _sys
        from PySide6.QtGui import QIcon
        _base = Path(getattr(_sys, "_MEIPASS", Path(__file__).parent.parent))
        for _name in ("icon.ico", "app_icon.png"):
            _ip = _base / "assets" / _name
            if _ip.exists():
                self.setWindowIcon(QIcon(str(_ip)))
                break

        self.setAcceptDrops(True)

        self._drop_root = DropRoot()
        self.setCentralWidget(self._drop_root)
        layout = QVBoxLayout(self._drop_root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.viewer = ViewerPane()
        layout.addWidget(self.viewer, 1)
        self.canvas = self.viewer.canvas

        self._menu_bar = self._build_menu(self._drop_root)
        self._menu_bar.setAcceptDrops(False)
        layout.insertWidget(0, self._menu_bar)

        self.toolbar = PhotoToolbar()
        self.toolbar.hide()
        layout.addWidget(self.toolbar)

        self.filmstrip = ThumbnailStrip()
        self.filmstrip.hide()
        layout.addWidget(self.filmstrip)

        self.hint = HintOverlay(self.viewer)
        self.hint.open_file_btn.clicked.connect(self._open_file_dialog)
        self.hint.open_dir_btn.clicked.connect(self._open_dir_dialog)

        self._immersive = False
        self._fs_hint = QLabel("按 Esc 退出全屏", self.viewer)
        self._fs_hint.setStyleSheet(
            "color: rgba(210,210,230,0.9); font-size: 13px; "
            "background: rgba(0,0,0,0.45); padding: 8px 16px; border-radius: 10px;"
        )
        self._fs_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._fs_hint.hide()
        self._fs_hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._position_hint()

        self.toolbar.rotate_left.connect(self.canvas.rotate_left)
        self.toolbar.rotate_right.connect(self.canvas.rotate_right)
        self.toolbar.rotate_left.connect(self._update_status)
        self.toolbar.rotate_right.connect(self._update_status)
        self.toolbar.info_clicked.connect(self._show_properties)
        self.toolbar.crop_clicked.connect(self._crop_image)
        self.toolbar.adjust_clicked.connect(self._adjust_image)
        self.toolbar.fullscreen_clicked.connect(self._toggle_immersive)
        self.toolbar.print_clicked.connect(self._print_image)
        self.toolbar.copy_clicked.connect(self._copy_image)
        self.toolbar.save_as_clicked.connect(self._save_image_as)
        self.toolbar.reveal_folder_clicked.connect(self._reveal_in_folder)
        self.toolbar.delete_clicked.connect(self._delete_image)

        self.viewer.prev_clicked.connect(lambda: self._navigate(-1))
        self.viewer.next_clicked.connect(lambda: self._navigate(1))
        self.filmstrip.image_selected.connect(self._open_path_from_strip)

        self._status = DropStatusBar()
        self.setStatusBar(self._status)

        self._current: Path | None = None
        self._images: list[Path] = []
        self._load_gen: int = 0               # 每次 _load() 递增，旧结果一律丢弃
        self._p1: _Phase1Worker | None = None  # Phase-1 worker（快速预览）
        self._p2: _Phase2Worker | None = None  # Phase-2 worker（RAW 精解）
        self._zombies: list[QThread] = []      # 已被放弃但仍在跑的 worker，防止被 GC
        self._prefetch_workers: list[PrefetchWorker] = []
        self._loading_path: Path | None = None
        self._pending_path: Path | None = None
        self._max_edge = _screen_max_edge()
        self._cache = PixmapCache(max_items=20)
        self._display_meta: DisplayResult | None = None

        self.canvas.zoom_changed.connect(self._update_status)

        # 拖放：对窗口内所有控件统一开启，由本窗口 eventFilter 处理
        self._install_drop_on_all()

        # 键盘导航：用 ApplicationShortcut QShortcut，比任何 widget keyPress 更早触发
        # 这是解决 QGraphicsView 吞掉 ←→ 键的唯一可靠方式
        self._setup_nav_shortcuts()

        if initial:
            self._open_path(initial)

    def _setup_nav_shortcuts(self) -> None:
        from PySide6.QtGui import QShortcut

        ctx = Qt.ShortcutContext.ApplicationShortcut
        for key, delta in (
            (Qt.Key.Key_Left,  -1),
            (Qt.Key.Key_Right,  1),
            (Qt.Key.Key_Up,    -1),
            (Qt.Key.Key_Down,   1),
        ):
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(ctx)
            sc.activated.connect(
                (lambda d: lambda: (
                    self._navigate(d) if not self._in_dialog() else None
                ))(delta)
            )

    def _install_drop_on_all(self) -> None:
        """Enable drops and install this filter on every widget in the window."""
        from PySide6.QtWidgets import QAbstractScrollArea
        targets = [self] + list(self.findChildren(QWidget))
        for w in targets:
            w.setAcceptDrops(True)
            w.installEventFilter(self)
        # viewport is a separate child not always found by findChildren on the view
        vp = self.canvas.viewport()
        vp.setAcceptDrops(True)
        vp.installEventFilter(self)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # 把标题栏也变黑（需在窗口显示后调用才有 HWND）
        try:
            from seephoto.win_utils import apply_dark_titlebar
            apply_dark_titlebar(int(self.winId()))
        except Exception:
            pass

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_hint()

    def handle_dropped_paths(self, paths: list[Path]) -> None:
        target = pick_open_path(paths)
        if not target:
            self._status.showMessage("未识别拖入的文件", 4000)
            return
        self._status.showMessage(f"正在打开 {target.name}…", 3000)
        target = Path(target)
        if target.is_dir():
            images = list_images(target)
            if images:
                self._open_path(images[0])
            else:
                QMessageBox.information(self, "易图", "文件夹中没有支持的图片。")
            return
        self._open_path(target)

    def _do_drag_enter(self, event) -> bool:
        if mime_has_urls(event):
            accept_file_drag(event)
            return True
        return False

    def eventFilter(self, watched, event) -> bool:
        t = event.type()
        if t == QEvent.Type.DragEnter:
            if mime_has_urls(event):
                accept_file_drag(event)
                return True
        elif t == QEvent.Type.DragMove:
            if mime_has_urls(event):
                accept_file_drag(event)
                return True
        elif t == QEvent.Type.Drop:
            if mime_has_urls(event):
                self._handle_file_drop(event)
                return True

        if (
            event.type() == QEvent.Type.KeyPress
            and self.isActiveWindow()
            and not self._in_dialog()
        ):
            key = event.key()
            if key in _NAV_KEYS:
                delta = -1 if key in (Qt.Key.Key_Left, Qt.Key.Key_Up) else 1
                self._navigate(delta)
                return True
        return super().eventFilter(watched, event)

    def _in_dialog(self) -> bool:
        from PySide6.QtWidgets import QApplication

        active = QApplication.activeModalWidget()
        return active is not None and active is not self

    def _build_menu(self, parent: QWidget) -> QMenuBar:
        bar = QMenuBar(parent)
        bar.setObjectName("AppMenuBar")

        file_menu = bar.addMenu("文件")
        for label, slot, shortcut in (
            ("打开图片…", self._open_file_dialog, QKeySequence.StandardKey.Open),
            ("打开文件夹…", self._open_dir_dialog, None),
            ("打开所在文件夹", self._reveal_in_folder, "Ctrl+Shift+E"),
            (None, None, None),
            ("退出", self.close, QKeySequence.StandardKey.Quit),
        ):
            if label is None:
                file_menu.addSeparator()
                continue
            act = QAction(label, self)
            if shortcut:
                act.setShortcut(shortcut)
            act.triggered.connect(slot)
            file_menu.addAction(act)

        view_menu = bar.addMenu("视图")
        for label, slot, key in (
            ("放大", self.canvas.zoom_in, "+"),
            ("缩小", self.canvas.zoom_out, "-"),
            ("适应窗口", self.canvas.fit_to_window, "0"),
            ("实际像素", self.canvas.zoom_actual, "1"),
            ("全屏浏览", self._toggle_immersive, "F11"),
        ):
            act = QAction(label, self)
            act.setShortcut(QKeySequence(key))
            act.triggered.connect(slot)
            view_menu.addAction(act)

        img_menu = bar.addMenu("图片")
        for label, slot, key in (
            ("上一张", lambda: self._navigate(-1), "Left"),
            ("下一张", lambda: self._navigate(1), "Right"),
            (None, None, None),
            ("逆时针旋转", self._rotate_left, "Ctrl+,"),
            ("顺时针旋转", self._rotate_right, "Ctrl+."),
            ("图片信息…", self._show_properties, "Ctrl+I"),
            ("打开所在文件夹", self._reveal_in_folder, "Ctrl+Shift+E"),
            ("明暗与色调…", self._adjust_image, "Ctrl+Shift+L"),
            ("重置调色", self._reset_adjustments, None),
            ("裁剪…", self._crop_image, None),
            ("打印…", self._print_image, "Ctrl+P"),
            ("复制", self._copy_image, "Ctrl+C"),
            ("另存为…", self._save_image_as, "Ctrl+Shift+S"),
            ("删除", self._delete_image, "Del"),
        ):
            if label is None:
                img_menu.addSeparator()
                continue
            act = QAction(label, self)
            if key:
                act.setShortcut(QKeySequence(key))
            act.triggered.connect(slot)
            img_menu.addAction(act)

        help_menu = bar.addMenu("帮助")
        about_act = QAction("关于 易图…", self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)
        help_menu.addSeparator()
        reg_act = QAction("添加到右键菜单", self)
        reg_act.triggered.connect(self._register_context_menu)
        help_menu.addAction(reg_act)
        unreg_act = QAction("从右键菜单移除", self)
        unreg_act.triggered.connect(self._unregister_context_menu)
        help_menu.addAction(unreg_act)

        return bar

    def _position_hint(self) -> None:
        # 让 hint 铺满 viewer 整个区域，内部 layout AlignCenter 负责居中内容
        vw = self.viewer.width()
        vh = self.viewer.height()
        if vw > 0 and vh > 0:
            self.hint.setGeometry(0, 0, vw, vh)
        self.hint.raise_()
        if self._immersive and self._fs_hint and self._fs_hint.isVisible():
            self._show_fs_hint()

    def _show_hint(self, show: bool) -> None:
        self.hint.setVisible(show)
        if not self._immersive:
            self.toolbar.setVisible(not show)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if mime_has_urls(event):
            accept_file_drag(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if mime_has_urls(event):
            accept_file_drag(event)

    def dropEvent(self, event: QDropEvent) -> None:
        self._handle_file_drop(event)

    def _handle_file_drop(self, event: QDropEvent) -> bool:
        paths = paths_from_drop(event)
        if not paths:
            return False
        self.handle_dropped_paths(paths)
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
        return True

    def _open_file_dialog(self) -> None:
        from seephoto.formats import ALL_EXTENSIONS

        patterns = " ".join(f"*{ext}" for ext in sorted(ALL_EXTENSIONS))
        path, _ = QFileDialog.getOpenFileName(
            self,
            "打开图片",
            str(self._current.parent if self._current else Path.home()),
            f"图片文件 ({patterns});;所有文件 (*.*)",
        )
        if path:
            self._open_path(Path(path))

    def _open_dir_dialog(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "打开文件夹",
            str(self._current.parent if self._current else Path.home()),
        )
        if path:
            images = list_images(Path(path))
            if images:
                self._open_path(images[0])
            else:
                QMessageBox.information(self, "易图", "该文件夹中没有支持的图片。")

    def _reveal_in_folder(self) -> None:
        if not self._current or not self._current.is_file():
            self._status.showMessage("请先打开一张图片", 3000)
            return
        from seephoto.actions import reveal_file_in_folder

        if reveal_file_in_folder(self._current, self):
            self._status.showMessage(
                f"已在文件夹中定位：{self._current.name}", 3000
            )

    def _open_path_from_strip(self, path: Path) -> None:
        path = Path(path).resolve()
        if self._current and path == self._current.resolve():
            return
        self._load(path)

    def _open_path(self, path: Path) -> None:
        path = Path(path).resolve()
        if path.is_dir():
            images = list_images(path)
            if not images:
                QMessageBox.information(self, "易图", "该文件夹中没有支持的图片。")
                return
            path = images[0]

        self._images = list_images(path.parent)
        self._cache.clear()
        self.filmstrip.set_images(self._images, path)
        self.viewer.set_navigation_visible(len(self._images) > 1)
        self._load(path)

    def _abandon_workers(self) -> None:
        """中断正在运行的 Phase-1/2 worker，结果将因 gen 不匹配而丢弃。"""
        # 清理已完成的僵尸
        self._zombies = [w for w in self._zombies if w.isRunning()]
        for w in (self._p1, self._p2):
            if w and w.isRunning():
                w.requestInterruption()
                self._zombies.append(w)
        self._p1 = None
        self._p2 = None

    def _load(self, path: Path) -> None:
        path = path.resolve()
        self._abandon_workers()
        self._pending_path = None
        self._loading_path = path
        self._load_gen += 1
        gen = self._load_gen

        self.filmstrip.set_current(path)

        cached = self._cache.get(path)
        if cached:
            pixmap, meta = cached
            self._show_image(path, pixmap, meta)
            self._prefetch_neighbors()
            return

        self._status.showMessage(f"正在加载 {path.name}…")
        self._p1 = _Phase1Worker(gen, path, self._max_edge)
        self._p1.preview_ready.connect(self._on_preview)
        self._p1.finished_ok.connect(self._on_p1_done)
        self._p1.finished_err.connect(self._on_load_error)
        self._p1.start()

    def _show_image(
        self,
        path: Path,
        pixmap: QPixmap,
        meta: DisplayResult,
        *,
        is_preview: bool = False,
    ) -> None:
        resolved = path.resolve()
        same_file = self._current is not None and self._current == resolved
        self._current = resolved
        self._display_meta = meta
        self.canvas.set_pixmap(
            pixmap,
            (meta.original_width, meta.original_height),
            reset_view=not same_file,
        )
        self._show_hint(False)
        if not self._immersive:
            self.toolbar.show()
            self.filmstrip.show()
            self._menu_bar.show()
            self.statusBar().show()
            self.viewer.set_navigation_visible(len(self._images) > 1)
        self._update_status(is_preview=is_preview)
        self.setWindowTitle(f"{path.name} — 易图")

    @Slot(int, object, object, object)
    def _on_preview(self, gen: int, path: Path, pixmap: QPixmap, meta: DisplayResult) -> None:
        """Phase-1 RAW 内嵌 JPEG 就绪，立刻显示预览；启动 Phase-2 精解。"""
        if gen != self._load_gen:
            return   # 用户已翻到别的图，丢弃
        resolved = Path(path).resolve()
        self._show_image(resolved, pixmap, meta, is_preview=True)
        # 立刻在后台开始精解（用户已经能看到预览了）
        self._p2 = _Phase2Worker(gen, resolved, self._max_edge)
        self._p2.finished_ok.connect(self._on_p2_done)
        self._p2.finished_err.connect(lambda g, m: None)   # 精解失败静默，预览已够用
        self._p2.start()

    @Slot(int, object, object, object)
    def _on_p1_done(self, gen: int, path: Path, pixmap: QPixmap, meta: DisplayResult) -> None:
        """Phase-1 对非 RAW 文件直接完成加载。"""
        if gen != self._load_gen:
            return
        resolved = Path(path).resolve()
        self._cache.put(resolved, pixmap, meta)
        self._show_image(resolved, pixmap, meta)
        self._prefetch_neighbors()

    @Slot(int, object, object, object)
    def _on_p2_done(self, gen: int, path: Path, pixmap: QPixmap, meta: DisplayResult) -> None:
        """Phase-2 RAW 精解完成，静默替换画面（用户感知不到闪烁）。"""
        if gen != self._load_gen:
            return
        resolved = Path(path).resolve()
        self._cache.put(resolved, pixmap, meta)
        self._show_image(resolved, pixmap, meta)
        self._prefetch_neighbors()

    # 保留旧方法名以兼容 _on_loaded 处可能残留的引用
    def _on_loaded(self, *_args) -> None:
        pass

    def _prefetch_neighbors(self) -> None:
        if not self._current:
            return
        self._prefetch_workers = [w for w in self._prefetch_workers if w.isRunning()]
        for delta in (-1, 1):
            nxt = neighbor(self._images, self._current, delta)
            if not nxt or self._cache.get(nxt):
                continue
            worker = PrefetchWorker(nxt, self._max_edge, self._cache)
            worker.start()
            self._prefetch_workers.append(worker)

    @Slot(int, str)
    def _on_load_error(self, gen: int, message: str) -> None:
        if gen != self._load_gen:
            return
        self._status.showMessage(message, 5000)
        QMessageBox.warning(self, "易图", message)

    def _navigate(self, delta: int) -> None:
        if not self._current:
            return
        nxt = neighbor(self._images, self._current, delta)
        if nxt and nxt.resolve() != self._current.resolve():
            self._load(nxt)

    def _update_status(self, *, is_preview: bool = False) -> None:
        if not self._current:
            self._status.clearMessage()
            return
        meta = self._display_meta
        if meta:
            ow, oh = meta.original_width, meta.original_height
            dw, dh = meta.display_width, meta.display_height
            if (ow, oh) != (dw, dh):
                size_str = f"{ow}×{oh} (显示 {dw}×{dh})"
            else:
                size_str = f"{ow}×{oh}"
        else:
            w, h = self.canvas.pixmap_size()
            size_str = f"{w}×{h}"
        cur = self._current.resolve()
        idx = self._images.index(cur) + 1 if cur in self._images else 0
        total = len(self._images)
        zoom = self.canvas.zoom_factor() * 100
        raw_tag = "RAW" if is_raw_path(self._current) else self._current.suffix.upper().lstrip(".")
        pos = f"{idx}/{total}" if total else ""
        rot = self.canvas.rotation_angle()
        rot_str = f"  ·  旋转 {rot}°" if rot else ""
        adj = self.canvas.adjust_params()
        adj_str = "  ·  已调色" if not adj.is_default() else ""
        preview_str = "  ·  ⏳ 精解中…" if is_preview else ""
        self._status.showMessage(
            f"{self._current.name}  ·  {size_str}  ·  {zoom:.0f}%  ·  {raw_tag}{rot_str}{adj_str}  ·  {pos}{preview_str}"
        )

    def _rotate_left(self) -> None:
        self.canvas.rotate_left()
        self._update_status()

    def _rotate_right(self) -> None:
        self.canvas.rotate_right()
        self._update_status()

    def _show_about(self) -> None:
        from seephoto.about_dialog import AboutDialog
        dlg = AboutDialog(self)
        dlg.exec()

    def _register_context_menu(self) -> None:
        import sys

        if sys.platform != "win32":
            QMessageBox.information(self, "易图", "右键菜单仅支持 Windows。")
            return
        try:
            from seephoto.shell_register import is_registered, register

            if is_registered():
                QMessageBox.information(
                    self, "易图", "右键菜单已注册，在图片文件上右键即可看到「用易图打开」。"
                )
                return
            register()
            QMessageBox.information(
                self,
                "易图",
                "已添加到右键菜单。\n\n在任意支持的图片文件上右键，选择「用易图打开」即可。",
            )
        except Exception as exc:
            QMessageBox.warning(self, "易图", f"注册失败：{exc}")

    def _unregister_context_menu(self) -> None:
        import sys

        if sys.platform != "win32":
            return
        try:
            from seephoto.shell_register import is_registered, unregister

            if not is_registered():
                QMessageBox.information(self, "易图", "当前未注册右键菜单。")
                return
            unregister()
            QMessageBox.information(self, "易图", "已从右键菜单移除。")
        except Exception as exc:
            QMessageBox.warning(self, "易图", f"移除失败：{exc}")

    def _show_properties(self) -> None:
        if not self._current:
            return
        dlg = PropertiesDialog(self._current, self)
        dlg.exec()

    def _reset_adjustments(self) -> None:
        from seephoto.adjustments import AdjustParams

        if not self.canvas.source_pixmap():
            self._status.showMessage("请先打开图片", 3000)
            return
        self.canvas.set_adjust_params(AdjustParams())
        self._update_status()
        self._status.showMessage("已重置调色", 2500)

    def _toggle_immersive(self) -> None:
        if self._immersive:
            self._exit_immersive()
        else:
            self._enter_immersive()

    def _enter_immersive(self) -> None:
        pm = self.canvas.current_pixmap()
        if not pm or pm.isNull():
            self._status.showMessage("请先打开图片", 3000)
            return
        self._immersive = True
        self._menu_bar.hide()
        self.toolbar.hide()
        self.filmstrip.hide()
        self.statusBar().hide()
        self.hint.hide()
        self.viewer.set_navigation_visible(False)
        self.showFullScreen()
        self.canvas.fit_to_window()
        self._show_fs_hint()
        self.viewer.setFocus()

    def _exit_immersive(self) -> None:
        if not self._immersive and not self.isFullScreen():
            return
        self._immersive = False
        self._fs_hint.hide()
        self.showNormal()
        self._menu_bar.show()
        if self._current:
            self.toolbar.show()
            self.filmstrip.show()
            self.statusBar().show()
            self.viewer.set_navigation_visible(len(self._images) > 1)
        else:
            self.toolbar.hide()
            self.filmstrip.hide()
            self.statusBar().show()

    def _show_fs_hint(self) -> None:
        self._fs_hint.adjustSize()
        vw, vh = self.viewer.width(), self.viewer.height()
        self._fs_hint.move(
            max(0, (vw - self._fs_hint.width()) // 2),
            max(0, vh - self._fs_hint.height() - 28),
        )
        self._fs_hint.show()
        self._fs_hint.raise_()
        QTimer.singleShot(2800, self._fs_hint.hide)

    def _adjust_image(self) -> None:
        src = self.canvas.source_pixmap()
        if not src or src.isNull():
            self._status.showMessage("请先打开图片", 3000)
            return
        from seephoto.actions import pil_to_pixmap, pixmap_to_pil
        from seephoto.adjust_dialog import AdjustDialog
        from seephoto.adjustments import (
            AdjustParams,
            apply_adjustments_pil,
            downscale_for_preview,
        )

        backup = self.canvas.adjust_params()
        full_pil = pixmap_to_pil(src)
        preview_pil = downscale_for_preview(full_pil, 1200)
        target = (src.width(), src.height())

        def _render(params: AdjustParams, *, full: bool) -> None:
            if params.is_default():
                self.canvas.set_adjust_params(params, rendered=src)
                return
            pil = full_pil if full else preview_pil
            out = apply_adjustments_pil(pil, params)
            pm = pil_to_pixmap(out)
            if not full and (pm.width(), pm.height()) != target:
                pm = pm.scaled(
                    target[0],
                    target[1],
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                    if full
                    else Qt.TransformationMode.FastTransformation,
                )
            self.canvas.set_adjust_params(params, rendered=pm)

        dlg = AdjustDialog(backup, self)
        dlg.params_preview.connect(lambda p: _render(p, full=False))
        dlg.params_final.connect(lambda p: _render(p, full=True))
        if dlg.exec() != QDialog.DialogCode.Accepted:
            _render(backup, full=True)
        else:
            _render(dlg.result_params(), full=True)
        self._update_status()

    def _crop_image(self) -> None:
        pm = self.canvas.current_pixmap()
        if not pm or pm.isNull():
            self._status.showMessage("请先打开图片", 3000)
            return
        dlg = CropDialog(pm, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        rect = dlg.crop_rect()
        if not rect:
            return
        cropped = crop_pixmap(pm, rect)
        self.canvas.set_display_pixmap(cropped)
        self._update_status()
        self._status.showMessage("已应用裁剪（使用「另存为」可保存到文件）", 5000)

    def _print_image(self) -> None:
        pm = self.canvas.current_pixmap()
        if not pm or pm.isNull():
            return
        if print_pixmap(pm, self):
            self._status.showMessage("已发送到打印机", 3000)

    def _copy_image(self) -> None:
        pm = self.canvas.current_pixmap()
        if not pm or pm.isNull():
            return
        copy_pixmap_to_clipboard(pm)
        self._status.showMessage("已复制到剪贴板", 3000)

    def _save_image_as(self) -> None:
        pm = self.canvas.current_pixmap()
        if not pm or pm.isNull() or not self._current:
            return
        default = self._current.stem + "_edited.jpg"
        saved = save_pixmap_as(pm, self, default)
        if saved:
            self._status.showMessage(f"已保存: {saved.name}", 5000)

    def _delete_image(self) -> None:
        if not self._current:
            return
        path = self._current.resolve()
        nxt = neighbor(self._images, path, 1) or neighbor(self._images, path, -1)
        if not delete_file_with_confirm(path, self):
            return
        try:
            idx = self._images.index(path)
            self._images.pop(idx)
        except ValueError:
            pass
        self._cache.clear()
        self.filmstrip.set_images(self._images, nxt)
        self.viewer.set_navigation_visible(len(self._images) > 1)
        if nxt and nxt.exists():
            self._load(nxt)
        else:
            self._current = None
            self.canvas.clear_image()
            self.filmstrip.hide()
            self.toolbar.hide()
            self._show_hint(True)
            self.setWindowTitle(self._app_title)
            self._status.showMessage("已删除", 3000)

    def keyPressEvent(self, event) -> None:
        key = event.key()
        mods = event.modifiers()

        if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal) and mods != Qt.KeyboardModifier.ControlModifier:
            self.canvas.zoom_in()
            event.accept()
            return
        if key == Qt.Key.Key_Minus:
            self.canvas.zoom_out()
            event.accept()
            return
        if key == Qt.Key.Key_0:
            self.canvas.fit_to_window()
            event.accept()
            return
        if key == Qt.Key.Key_1:
            self.canvas.zoom_actual()
            event.accept()
            return
        if key == Qt.Key.Key_Escape and self._immersive:
            self._exit_immersive()
            event.accept()
            return
        if key == Qt.Key.Key_F11:
            self._toggle_immersive()
            event.accept()
            return
        if key == Qt.Key.Key_Delete:
            self._delete_image()
            event.accept()
            return
        if key == Qt.Key.Key_P and mods == Qt.KeyboardModifier.ControlModifier:
            self._print_image()
            event.accept()
            return
        if key == Qt.Key.Key_I and mods == Qt.KeyboardModifier.ControlModifier:
            self._show_properties()
            event.accept()
            return
        if key == Qt.Key.Key_Comma and mods == Qt.KeyboardModifier.ControlModifier:
            self._rotate_left()
            event.accept()
            return
        if key == Qt.Key.Key_Period and mods == Qt.KeyboardModifier.ControlModifier:
            self._rotate_right()
            event.accept()
            return

        super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._abandon_workers()
        for w in self._zombies + self._prefetch_workers:
            if w.isRunning():
                w.requestInterruption()
                w.wait(300)
        super().closeEvent(event)


def create_app():
    from PySide6.QtWidgets import QApplication

    from seephoto.theme import STYLESHEET

    app = QApplication(sys.argv)
    app.setApplicationName("易图")
    app.setOrganizationName("llso")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    return app
