

import sys
import signal

from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PySide6.QtCore import Qt, QTimer

from ui.hud_window import HUDWindow
from services.secure_storage import SecureStorage
from utils.assets import get_icon_pixmap


def build_tray_icon(app: QApplication, window: HUDWindow) -> QSystemTrayIcon:
    tray = QSystemTrayIcon(app)
    tray.setIcon(QIcon(get_icon_pixmap(size=22)))
    tray.setToolTip("Claude Budget HUD")

    menu = QMenu()
    menu.setStyleSheet("""
        QMenu {
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
            padding: 4px;
            font-family: 'Inter', sans-serif;
            font-size: 13px;
            color: #111827;
        }
        QMenu::item { padding: 6px 16px; border-radius: 4px; }
        QMenu::item:selected { background: #F3F4F6; }
        QMenu::separator { height: 1px; background: #E5E7EB; margin: 3px 8px; }
    """)

    show_action = menu.addAction("Show HUD")
    show_action.triggered.connect(window.show_and_raise)

    settings_action = menu.addAction("Settings")
    settings_action.triggered.connect(window.open_settings)

    menu.addSeparator()

    quit_action = menu.addAction("Quit")
    quit_action.triggered.connect(app.quit)

    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: window.show_and_raise()
                           if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
    tray.show()
    return tray


def main() -> None:
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    app.setApplicationName("Claude Budget HUD")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("ssajaia")
    app.setQuitOnLastWindowClosed(False)

    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("Warning: no system tray available on this desktop environment.")

    window = HUDWindow()

    storage = SecureStorage()
    has_key = storage.has_api_key()

    if has_key:
        window.show()
        window.start_polling()
    else:
        window.show()
        QTimer.singleShot(200, window.open_settings)

    tray = build_tray_icon(app, window)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
