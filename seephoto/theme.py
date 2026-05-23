"""Application stylesheet — modern dark UI, non-native Windows chrome."""

STYLESHEET = """
* {
    font-family: "Segoe UI", "Microsoft YaHei UI", "PingFang SC", sans-serif;
}

QMainWindow, QWidget#Root {
    background-color: #121218;
    color: #e8e8ef;
}

QMenuBar, QMenuBar#AppMenuBar {
    background: #1a1a24;
    color: #c8c8d8;
    border-bottom: 1px solid #2a2a38;
    padding: 4px 8px;
    spacing: 6px;
}

QMenuBar::item {
    background: transparent;
    padding: 6px 12px;
    border-radius: 6px;
}

QMenuBar::item:selected {
    background: #2d2d42;
    color: #ffffff;
}

QMenu {
    background: #1e1e2a;
    color: #e0e0ec;
    border: 1px solid #333348;
    border-radius: 8px;
    padding: 6px;
}

QMenu::item {
    padding: 8px 28px 8px 16px;
    border-radius: 6px;
}

QMenu::item:selected {
    background: #3d5afe33;
    color: #ffffff;
}

QStatusBar {
    background: #16161f;
    color: #9090a8;
    border-top: 1px solid #2a2a38;
    font-size: 12px;
    padding: 2px 12px;
}

QToolTip {
    background: #252532;
    color: #f0f0f8;
    border: 1px solid #404058;
    border-radius: 6px;
    padding: 6px 10px;
}

QScrollBar:vertical, QScrollBar:horizontal {
    background: #121218;
    width: 10px;
    height: 10px;
    margin: 0;
}

QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: #3a3a52;
    border-radius: 5px;
    min-height: 24px;
    min-width: 24px;
}

QScrollBar::handle:hover {
    background: #5c6cff;
}

QScrollBar::add-line, QScrollBar::sub-line {
    width: 0;
    height: 0;
}

QWidget#OverlayPanel {
    background: #0e0e14;
}

QWidget#HintCard {
    background: rgba(22, 22, 30, 0.92);
    border: 1px solid #3a3a50;
    border-radius: 14px;
}

QLabel#HintTitle {
    font-size: 22px;
    font-weight: 600;
    color: #f0f0fa;
}

QLabel#HintSub {
    font-size: 13px;
    color: #8888a0;
    line-height: 1.5;
}

QLabel#Badge {
    background: #2a2a3c;
    color: #a8b4ff;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 600;
}

QPushButton#GhostBtn {
    background: #2a2a3c;
    color: #d8d8ec;
    border: 1px solid #404058;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
}

QPushButton#GhostBtn:hover {
    background: #3d5afe;
    border-color: #3d5afe;
    color: #ffffff;
}

QPushButton#GhostBtn:pressed {
    background: #3040c8;
}

QWidget#ViewerPane {
    background: #0e0e14;
}

QPushButton#NavBtn {
    background: rgba(30, 30, 44, 0.75);
    color: #f0f0ff;
    border: 1px solid rgba(120, 130, 200, 0.35);
    border-radius: 12px;
    font-size: 32px;
    font-weight: 300;
    padding: 0 0 4px 0;
}

QPushButton#NavBtn:hover {
    background: rgba(61, 90, 254, 0.92);
    border-color: #5c6cff;
    color: #ffffff;
}

QPushButton#NavBtn:pressed {
    background: #3040c8;
}

QWidget#Filmstrip {
    background: #16161f;
    border-top: 1px solid #2a2a38;
}

QScrollArea#FilmstripScroll {
    background: transparent;
}

QWidget#FilmstripInner {
    background: transparent;
}

QWidget#ThumbCell {
    background: #1e1e2a;
    border: 2px solid transparent;
    border-radius: 8px;
}

QWidget#ThumbCell[selected="true"] {
    background: #252538;
    border: 2px solid #5c6cff;
}

QWidget#ThumbCell:hover {
    background: #2a2a40;
    border: 2px solid #4a58c8;
}

QLabel#ThumbPreview {
    background: #121218;
    border-radius: 4px;
    color: #606078;
    font-size: 11px;
}

QLabel#ThumbCaption {
    color: #8888a0;
    font-size: 10px;
}

QWidget#PhotoToolbar {
    background: #16161f;
    border-top: 1px solid #2a2a38;
    min-height: 56px;
}

QPushButton#ToolBtn {
    background: transparent;
    color: #c8c8e0;
    border: none;
    border-radius: 8px;
    font-size: 26px;
    min-width: 52px;
    min-height: 48px;
    padding: 6px 12px;
}

QPushButton#ToolBtn:hover {
    background: #2d2d42;
    color: #ffffff;
}

QPushButton#ToolBtn:pressed {
    background: #3d5afe;
}

QFrame#ToolSep {
    color: #333348;
    max-width: 1px;
    margin: 6px 4px;
}

QLabel#CropHint {
    color: #9090a8;
    font-size: 13px;
    padding: 8px;
}

QLabel#InfoBody {
    color: #d8d8ec;
    font-size: 13px;
    padding: 12px;
    font-family: "Consolas", "Cascadia Mono", "Microsoft YaHei UI", monospace;
}

QDialog {
    background: #1a1a24;
    color: #e8e8ef;
}

QDialog QScrollArea {
    background: #1a1a24;
    border: none;
}

QDialog QWidget {
    background: #1a1a24;
    color: #e8e8ef;
}

QDialog QDialogButtonBox QPushButton {
    background: #2a2a3c;
    color: #d8d8ec;
    border: 1px solid #404058;
    border-radius: 6px;
    padding: 6px 20px;
    min-width: 80px;
}

QDialog QDialogButtonBox QPushButton:hover {
    background: #3d5afe;
    border-color: #3d5afe;
    color: #ffffff;
}

"""
