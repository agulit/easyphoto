"""专业调色面板 — 明暗 / 高光阴影 / 色彩。"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from seephoto.adjustments import AdjustParams


class AdjustDialog(QDialog):
    """params_preview：低分辨率快速预览；params_final：全分辨率（松手 / 确定）。"""

    params_preview = Signal(object)
    params_final = Signal(object)

    _SLIDER_STYLE = """
        QDialog { background: #121218; color: #e8e8ec; }
        QGroupBox {
            color: #a0a0c0; font-size: 12px; font-weight: bold;
            border: 1px solid #2a2a3c; border-radius: 8px;
            margin-top: 10px; padding-top: 14px;
        }
        QGroupBox::title {
            subcontrol-origin: margin; left: 12px; padding: 0 6px;
        }
        QLabel { background: transparent; color: #c8c8d8; font-size: 13px; }
        QLabel#Val { color: #8ab4ff; min-width: 36px; }
        QSlider {
            min-height: 20px;
            max-height: 20px;
        }
        QSlider::groove:horizontal {
            height: 3px; background: #2a2a3c; border-radius: 2px;
        }
        QSlider::handle:horizontal {
            width: 8px; height: 8px;
            margin: -3px 0;
            background: #6b8cff;
            border: 1px solid #5a7ae0;
            border-radius: 4px;
        }
        QSlider::sub-page:horizontal { background: #3d5afe; border-radius: 2px; }
        QPushButton#ResetBtn {
            background: #252535; color: #a0a0b8; border: 1px solid #3a3a50;
            border-radius: 8px; padding: 6px 16px;
        }
        QPushButton#ResetBtn:hover { background: #33334a; color: #fff; }
        QDialogButtonBox QPushButton {
            background: #252535; color: #c0c0d0; border: 1px solid #3a3a50;
            border-radius: 8px; padding: 6px 18px; min-width: 72px;
        }
        QDialogButtonBox QPushButton:hover { background: #33334a; color: #fff; }
        QScrollArea { border: none; background: transparent; }
    """

    def __init__(
        self,
        initial: AdjustParams,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("专业调色")
        self.setModal(True)
        self.setMinimumWidth(440)
        self.resize(460, 520)
        self.setStyleSheet(self._SLIDER_STYLE)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(80)
        self._debounce.timeout.connect(self._emit_preview)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 12)

        hint = QLabel("拖动滑块实时预览；松手后自动清晰。确定保留，取消恢复。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #7070a0; font-size: 12px;")
        root.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setSpacing(8)

        self._sliders: dict[str, tuple[QSlider, QLabel]] = {}

        tone_rows = (
            ("brightness", "亮度", initial.brightness),
            ("contrast", "对比度", initial.contrast),
            ("highlights", "高光", initial.highlights),
            ("shadows", "阴影", initial.shadows),
        )
        color_rows = (
            ("saturation", "饱和度", initial.saturation),
            ("warmth", "色温", initial.warmth),
            ("hue", "色相", initial.hue),
        )

        body_layout.addWidget(self._make_group("明暗", tone_rows))
        body_layout.addWidget(self._make_group("色彩", color_rows))
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        reset_row = QHBoxLayout()
        reset_row.addStretch()
        reset_btn = QPushButton("全部重置")
        reset_btn.setObjectName("ResetBtn")
        reset_btn.clicked.connect(self._reset)
        reset_row.addWidget(reset_btn)
        root.addLayout(reset_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _make_group(self, title: str, rows: tuple) -> QGroupBox:
        box = QGroupBox(title)
        grid = QGridLayout(box)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(20)
        for row, (key, label, val) in enumerate(rows):
            grid.addWidget(QLabel(label), row, 0)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setObjectName("AdjustSlider")
            slider.setRange(-100, 100)
            slider.setValue(val)
            slider.setTracking(True)
            slider.valueChanged.connect(self._on_slider)
            slider.sliderReleased.connect(self._emit_final)
            val_lbl = QLabel(self._fmt(val))
            val_lbl.setObjectName("Val")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(slider, row, 1)
            grid.addWidget(val_lbl, row, 2)
            self._sliders[key] = (slider, val_lbl)
        return box

    @staticmethod
    def _fmt(v: int) -> str:
        return f"{v:+d}" if v else "0"

    def _read_params(self) -> AdjustParams:
        return AdjustParams(
            **{key: sl.value() for key, (sl, _) in self._sliders.items()},
        )

    def _on_slider(self) -> None:
        for slider, val_lbl in self._sliders.values():
            val_lbl.setText(self._fmt(slider.value()))
        self._debounce.start()

    def _emit_preview(self) -> None:
        self.params_preview.emit(self._read_params())

    def _emit_final(self) -> None:
        self._debounce.stop()
        self.params_final.emit(self._read_params())

    def _reset(self) -> None:
        self._debounce.stop()
        for slider, val_lbl in self._sliders.values():
            slider.blockSignals(True)
            slider.setValue(0)
            slider.blockSignals(False)
            val_lbl.setText("0")
        self.params_preview.emit(AdjustParams())
        self.params_final.emit(AdjustParams())

    def _on_ok(self) -> None:
        self._debounce.stop()
        self.params_final.emit(self._read_params())
        self.accept()

    def result_params(self) -> AdjustParams:
        return self._read_params()
