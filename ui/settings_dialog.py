from __future__ import annotations

import sys
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QCheckBox, QFrame, QWidget,
    QSpacerItem, QSizePolicy, QGraphicsDropShadowEffect,
)
from PySide6.QtGui import (
    QPainter, QColor, QPainterPath, QBrush, QFont,
)
from PySide6.QtCore import Qt, QTimer

from services.secure_storage import SecureStorage



def _pal(dark: bool) -> dict[str, str]:
    if dark:
        return {
            "bg": "#1E1E1E", "surface": "#2A2A2A",
            "text": "#E5E7EB", "muted": "#9CA3AF",
            "accent": "#F59E0B", "border": "#3F3F3F",
            "input_bg": "#333333", "btn_hover": "#374151",
        }
    return {
        "bg": "#F7F6F3", "surface": "#FFFFFF",
        "text": "#111827", "muted": "#6B7280",
        "accent": "#D97706", "border": "#E5E7EB",
        "input_bg": "#F9FAFB", "btn_hover": "#F3F4F6",
    }



class _RoundedDialog(QDialog):
    RADIUS = 16

    def __init__(self, parent: Optional[QWidget], dark: bool) -> None:
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._dark = dark
        self._drag_pos = None

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        p = _pal(self._dark)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), self.RADIUS, self.RADIUS)
        bg = QColor(p["surface"])
        bg.setAlphaF(0.98)
        painter.fillPath(path, QBrush(bg))
        painter.end()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self._drag_pos = None



class SettingsDialog(_RoundedDialog):

    def __init__(
        self,
        parent: Optional[QWidget],
        dark: bool,
        config: dict,
        storage: SecureStorage,
    ) -> None:
        super().__init__(parent, dark)
        self._config = dict(config)
        self._storage = storage
        self._p = _pal(dark)

        self.setFixedWidth(320)
        self.setMinimumHeight(320)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setXOffset(0)
        shadow.setYOffset(8)
        shadow.setColor(QColor(0, 0, 0, 70))
        self.setGraphicsEffect(shadow)

        self._build()
        self._apply_styles()


    def _build(self) -> None:
        p = self._p
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(0)

        header_row = QHBoxLayout()
        title = QLabel("Settings")
        title.setObjectName("dialogTitle")
        close_btn = QPushButton("✕")
        close_btn.setObjectName("closeBtn")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        header_row.addWidget(title)
        header_row.addStretch()
        header_row.addWidget(close_btn)
        root.addLayout(header_row)
        root.addSpacing(20)

        root.addWidget(self._section_label("Monthly Budget (USD)"))
        root.addSpacing(6)
        self._budget_input = QLineEdit()
        self._budget_input.setObjectName("settingInput")
        self._budget_input.setPlaceholderText("e.g. 50.00")
        self._budget_input.setText(str(self._config.get("monthly_budget", "")))
        root.addWidget(self._budget_input)
        root.addSpacing(16)

        has_key = self._storage.has_api_key()
        root.addWidget(self._section_label("API Key"))
        root.addSpacing(6)

        if has_key:
            key_row = QHBoxLayout()
            key_row.setSpacing(8)
            key_status = QLabel("●  Stored securely in keychain")
            key_status.setObjectName("keyStatus")
            reset_btn = QPushButton("Reset")
            reset_btn.setObjectName("dangerBtn")
            reset_btn.setFixedHeight(28)
            reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            reset_btn.clicked.connect(self._reset_api_key)
            key_row.addWidget(key_status)
            key_row.addStretch()
            key_row.addWidget(reset_btn)
            root.addLayout(key_row)
        else:
            self._api_key_input = QLineEdit()
            self._api_key_input.setObjectName("settingInput")
            self._api_key_input.setPlaceholderText("sk-ant-...")
            self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            root.addWidget(self._api_key_input)

        root.addSpacing(16)

        root.addWidget(self._section_label("Refresh Interval"))
        root.addSpacing(6)
        self._interval_combo = QComboBox()
        self._interval_combo.setObjectName("settingCombo")
        intervals = [("30 seconds", 30), ("1 minute", 60), ("2 minutes", 120), ("5 minutes", 300)]
        current_interval = self._config.get("refresh_interval_secs", 60)
        for label, val in intervals:
            self._interval_combo.addItem(label, val)
            if val == current_interval:
                self._interval_combo.setCurrentIndex(self._interval_combo.count() - 1)
        root.addWidget(self._interval_combo)
        root.addSpacing(16)

        self._dark_check = self._toggle_row(root, "Dark Mode", self._config.get("dark_mode", False))
        root.addSpacing(8)
        self._startup_check = self._toggle_row(root, "Launch on Startup",
                                               self._config.get("launch_on_startup", False))
        root.addSpacing(24)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color: {self._p['border']};")
        root.addWidget(div)
        root.addSpacing(16)

        self._save_btn = QPushButton("Save")
        self._save_btn.setObjectName("saveBtn")
        self._save_btn.setFixedHeight(36)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.clicked.connect(self._save)
        root.addWidget(self._save_btn)

        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("statusLabel")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addSpacing(6)
        root.addWidget(self._status_lbl)

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("sectionLabel")
        return lbl

    def _toggle_row(self, layout: QVBoxLayout, text: str, checked: bool) -> QCheckBox:
        row = QHBoxLayout()
        lbl = QLabel(text)
        lbl.setObjectName("toggleLabel")
        cb = QCheckBox()
        cb.setChecked(checked)
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(cb)
        layout.addLayout(row)
        return cb


    def _apply_styles(self) -> None:
        p = self._p
        self.setStyleSheet(f"""
            QDialog {{ background: transparent; }}

            QLabel#dialogTitle {{
                color: {p['text']};
                font-family: 'Inter', sans-serif;
                font-size: 15px;
                font-weight: 600;
            }}
            QPushButton#closeBtn {{
                background: transparent;
                color: {p['muted']};
                border: none;
                font-size: 13px;
                border-radius: 4px;
            }}
            QPushButton#closeBtn:hover {{
                background: {p['btn_hover']};
                color: {p['text']};
            }}
            QLabel#sectionLabel {{
                color: {p['muted']};
                font-family: 'Inter', sans-serif;
                font-size: 11px;
                font-weight: 500;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            QLabel#toggleLabel {{
                color: {p['text']};
                font-family: 'Inter', sans-serif;
                font-size: 13px;
            }}
            QLabel#keyStatus {{
                color: #10B981;
                font-family: 'Inter', sans-serif;
                font-size: 12px;
            }}
            QLineEdit#settingInput {{
                background: {p['input_bg']};
                color: {p['text']};
                border: 1px solid {p['border']};
                border-radius: 8px;
                padding: 8px 12px;
                font-family: 'Inter', sans-serif;
                font-size: 13px;
            }}
            QLineEdit#settingInput:focus {{
                border: 1px solid {p['accent']};
            }}
            QComboBox#settingCombo {{
                background: {p['input_bg']};
                color: {p['text']};
                border: 1px solid {p['border']};
                border-radius: 8px;
                padding: 7px 12px;
                font-family: 'Inter', sans-serif;
                font-size: 13px;
            }}
            QComboBox#settingCombo::drop-down {{ border: none; }}
            QPushButton#saveBtn {{
                background: {p['accent']};
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                font-family: 'Inter', sans-serif;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton#saveBtn:hover {{ background: #B45309; }}
            QPushButton#dangerBtn {{
                background: transparent;
                color: #EF4444;
                border: 1px solid #EF4444;
                border-radius: 6px;
                padding: 2px 10px;
                font-family: 'Inter', sans-serif;
                font-size: 12px;
            }}
            QPushButton#dangerBtn:hover {{ background: #FEF2F2; }}
            QLabel#statusLabel {{
                color: {p['muted']};
                font-family: 'Inter', sans-serif;
                font-size: 12px;
            }}
            QCheckBox {{
                color: {p['text']};
            }}
            QCheckBox::indicator {{
                width: 16px; height: 16px;
                border: 2px solid {p['border']};
                border-radius: 4px;
                background: {p['input_bg']};
            }}
            QCheckBox::indicator:checked {{
                background: {p['accent']};
                border-color: {p['accent']};
                image: none;
            }}
        """)


    def _save(self) -> None:
        budget_text = self._budget_input.text().strip().lstrip("$")
        try:
            budget = float(budget_text)
            if budget < 0:
                raise ValueError
        except ValueError:
            self._set_status("Enter a valid budget amount.", error=True)
            return

        if hasattr(self, "_api_key_input"):
            raw_key = self._api_key_input.text().strip()
            if raw_key:
                try:
                    self._storage.store_api_key(raw_key)
                except Exception as exc:
                    self._set_status(f"Could not save API key: {exc}", error=True)
                    return

        self._config["monthly_budget"] = budget
        self._config["refresh_interval_secs"] = self._interval_combo.currentData()
        self._config["dark_mode"] = self._dark_check.isChecked()
        self._config["launch_on_startup"] = self._startup_check.isChecked()

        self._apply_startup(self._startup_check.isChecked())

        self.accept()

    def _reset_api_key(self) -> None:
        self._storage.delete_api_key()
        self._set_status("API key removed.", error=False)
        QTimer.singleShot(1200, self.reject)

    def _set_status(self, msg: str, error: bool = False) -> None:
        color = "#EF4444" if error else "#10B981"
        self._status_lbl.setStyleSheet(
            f"color: {color}; font-family: 'Inter', sans-serif; font-size: 12px;"
        )
        self._status_lbl.setText(msg)

    def _apply_startup(self, enabled: bool) -> None:
        try:
            if sys.platform == "win32":
                import winreg
                key = r"Software\Microsoft\Windows\CurrentVersion\Run"
                import sys as _sys
                exe = _sys.executable
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0,
                                    winreg.KEY_SET_VALUE) as reg:
                    if enabled:
                        winreg.SetValueEx(reg, "ClaudeBudgetHUD", 0,
                                          winreg.REG_SZ, f'"{exe}"')
                    else:
                        try:
                            winreg.DeleteValue(reg, "ClaudeBudgetHUD")
                        except FileNotFoundError:
                            pass

            elif sys.platform == "darwin":
                import plistlib, os
                plist_path = os.path.expanduser(
                    "~/Library/LaunchAgents/com.ssajaia.claude-budget-hud.plist"
                )
                if enabled:
                    plist = {
                        "Label": "com.ssajaia.claude-budget-hud",
                        "ProgramArguments": [sys.executable],
                        "RunAtLoad": True,
                        "KeepAlive": False,
                    }
                    with open(plist_path, "wb") as f:
                        plistlib.dump(plist, f)
                else:
                    if os.path.exists(plist_path):
                        os.remove(plist_path)

            else:
                # Linux XDG autostart
                import os
                autostart_dir = os.path.expanduser("~/.config/autostart")
                os.makedirs(autostart_dir, exist_ok=True)
                desktop_path = os.path.join(autostart_dir,
                                            "claude-budget-hud.desktop")
                if enabled:
                    with open(desktop_path, "w") as f:
                        f.write(
                            "[Desktop Entry]\n"
                            "Type=Application\n"
                            "Name=Claude Budget HUD\n"
                            f"Exec={sys.executable}\n"
                            "Hidden=false\n"
                            "NoDisplay=false\n"
                            "X-GNOME-Autostart-enabled=true\n"
                        )
                else:
                    if os.path.exists(desktop_path):
                        os.remove(desktop_path)
        except Exception:
            pass  
    def get_config(self) -> dict:
        return self._config
