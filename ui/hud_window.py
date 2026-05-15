"""
HUD Window — the always-on-top floating overlay.

Layout (240 × 80):
  [C icon]  $31.27 left
            This month: $18.73 used
            Updated 12s ago
"""

from __future__ import annotations

import time
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout,
    QGraphicsDropShadowEffect, QApplication,
)
from PySide6.QtGui import (
    QPainter, QColor, QPainterPath, QBrush,
    QKeySequence, QShortcut,
)
from PySide6.QtCore import (
    Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve, Signal, QObject,
)

from services.api_client import fetch_usage_async, UsageSummary, APIError
from services.budget_calculator import BudgetState
from services.secure_storage import SecureStorage
from utils.encryption import load_config, save_config
from utils.os_window_control import set_click_through
from utils.assets import get_icon_pixmap


# ── Thread-safe signal bridge ─────────────────────────────────────────────────

class _Bridge(QObject):
    usage_ready = Signal(object)
    usage_error = Signal(object)


# ── Rounded-corner translucent background widget ──────────────────────────────

class _Panel(QWidget):
    RADIUS = 16

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._dark = False

    def set_dark(self, dark: bool) -> None:
        self._dark = dark
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor("#1E1E1E") if self._dark else QColor("#F7F6F3")
        bg.setAlphaF(0.97)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), self.RADIUS, self.RADIUS)
        painter.fillPath(path, QBrush(bg))
        painter.end()


# ── Main HUD window ───────────────────────────────────────────────────────────

class HUDWindow(QWidget):
    _W = 240
    _H = 80

    def __init__(self) -> None:
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self._W, self._H)

        self._dark: bool = False
        self._pinned: bool = False
        self._dragging: bool = False
        self._drag_offset: QPoint = QPoint()
        self._last_fetch_ts: float = 0.0
        self._fetching: bool = False
        self._last_state: Optional[BudgetState] = None
        self._error_kind: Optional[str] = None

        self._storage = SecureStorage()
        self._config = load_config()
        self._dark = self._config.get("dark_mode", False)

        self._bridge = _Bridge()
        self._bridge.usage_ready.connect(self._on_usage_ready)
        self._bridge.usage_error.connect(self._on_usage_error)

        self._build_ui()
        self._apply_theme()
        self._position_top_right()

        shortcut = QShortcut(QKeySequence("Ctrl+Shift+P"), self)
        shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        shortcut.activated.connect(self.toggle_pin)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)

        self._age_timer = QTimer(self)
        self._age_timer.setInterval(5_000)
        self._age_timer.timeout.connect(self._update_age_label)
        self._age_timer.start()

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 60))
        self._panel.setGraphicsEffect(shadow)

        self.setMouseTracking(True)
        self._panel.setMouseTracking(True)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._panel = _Panel(self)
        self._panel.setGeometry(0, 0, self._W, self._H)

        self._icon_lbl = QLabel(self._panel)
        self._icon_lbl.setFixedSize(28, 28)
        self._icon_lbl.setPixmap(get_icon_pixmap(28, self._dark))

        self._budget_lbl = QLabel("—", self._panel)
        self._budget_lbl.setObjectName("budgetLabel")

        self._sub_lbl = QLabel("This month: —", self._panel)
        self._sub_lbl.setObjectName("subLabel")

        self._age_lbl = QLabel("", self._panel)
        self._age_lbl.setObjectName("ageLabel")

        self._gear_lbl = QLabel("⚙", self._panel)
        self._gear_lbl.setObjectName("gearLabel")
        self._gear_lbl.setFixedSize(18, 18)
        self._gear_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self._gear_lbl.setVisible(False)
        self._gear_lbl.mousePressEvent = lambda _: self.open_settings()

        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(1)
        right_col.addWidget(self._budget_lbl)
        right_col.addWidget(self._sub_lbl)
        right_col.addWidget(self._age_lbl)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.addLayout(right_col)
        top_row.addStretch()
        top_row.addWidget(self._gear_lbl, alignment=Qt.AlignmentFlag.AlignTop)

        root = QHBoxLayout(self._panel)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)
        root.addWidget(self._icon_lbl, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(top_row)

    def _apply_theme(self) -> None:
        dark = self._dark
        self._panel.set_dark(dark)
        self._icon_lbl.setPixmap(get_icon_pixmap(28, dark))

        text_primary = "#E5E7EB" if dark else "#111827"
        text_muted = "#9CA3AF" if dark else "#6B7280"

        self._budget_lbl.setStyleSheet(
            f"color: {text_primary}; font-family: 'Inter', sans-serif; "
            f"font-size: 17px; font-weight: 600; letter-spacing: -0.3px;"
        )
        self._sub_lbl.setStyleSheet(
            f"color: {text_muted}; font-family: 'Inter', sans-serif; "
            f"font-size: 11px; font-weight: 400;"
        )
        self._age_lbl.setStyleSheet(
            f"color: {text_muted}; font-family: 'Inter', sans-serif; "
            f"font-size: 10px; font-weight: 400;"
        )
        self._gear_lbl.setStyleSheet(
            f"color: {text_muted}; font-size: 12px;"
        )

        if self._last_state:
            self._render_state(self._last_state)

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _render_state(self, state: BudgetState) -> None:
        dark = self._dark
        accent_ok = "#F59E0B" if dark else "#D97706"
        accent_err = "#EF4444"
        color = accent_err if state.exceeded else accent_ok

        if state.exceeded:
            self._budget_lbl.setText(f"{state.format_remaining()} over budget")
        else:
            self._budget_lbl.setText(f"{state.format_remaining()} left")

        self._budget_lbl.setStyleSheet(
            f"color: {color}; font-family: 'Inter', sans-serif; "
            f"font-size: 17px; font-weight: 600; letter-spacing: -0.3px;"
        )
        self._sub_lbl.setText(f"This month: {state.format_spent()} used")
        self._error_kind = None

    def _render_error(self, kind: str) -> None:
        text_muted = "#9CA3AF" if self._dark else "#6B7280"
        messages = {
            APIError.NETWORK: "Offline",
            APIError.INVALID_KEY: "Invalid API key",
            APIError.RATE_LIMITED: "Rate limited — retrying",
            APIError.UNKNOWN: "Error fetching usage",
        }
        self._budget_lbl.setText(messages.get(kind, "Error"))
        self._budget_lbl.setStyleSheet(
            f"color: {text_muted}; font-family: 'Inter', sans-serif; "
            f"font-size: 14px; font-weight: 500;"
        )
        self._sub_lbl.setText("")
        self._error_kind = kind

    def _update_age_label(self) -> None:
        if self._last_fetch_ts == 0:
            self._age_lbl.setText("")
            return
        elapsed = int(time.time() - self._last_fetch_ts)
        if elapsed < 60:
            self._age_lbl.setText(f"Updated {elapsed}s ago")
        else:
            self._age_lbl.setText(f"Updated {elapsed // 60}m ago")

    # ── Polling ───────────────────────────────────────────────────────────────

    def start_polling(self) -> None:
        interval_ms = int(self._config.get("refresh_interval_secs", 60)) * 1_000
        self._timer.setInterval(interval_ms)
        self._timer.start()
        self._refresh()

    def _refresh(self) -> None:
        if self._fetching:
            return
        key = self._storage.get_api_key() or ""
        if not key:
            return

        self._fetching = True
        self._pulse_icon()

        fetch_usage_async(
            api_key=key,
            on_success=lambda s: self._bridge.usage_ready.emit(s),
            on_error=lambda e: self._bridge.usage_error.emit(e),
        )

    def _on_usage_ready(self, summary: UsageSummary) -> None:
        self._fetching = False
        self._last_fetch_ts = time.time()
        budget = float(self._config.get("monthly_budget", 0))
        state = BudgetState(monthly_budget=budget, spent=summary.total_cost_usd)
        self._last_state = state
        self._render_state(state)
        self._update_age_label()

    def _on_usage_error(self, error: APIError) -> None:
        self._fetching = False
        self._last_fetch_ts = time.time()
        self._render_error(error.kind)
        self._update_age_label()

    def _pulse_icon(self) -> None:
        anim = QPropertyAnimation(self._icon_lbl, b"windowOpacity")
        anim.setDuration(600)
        anim.setKeyValueAt(0.0, 1.0)
        anim.setKeyValueAt(0.5, 0.4)
        anim.setKeyValueAt(1.0, 1.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    # ── Pin mode ──────────────────────────────────────────────────────────────

    def toggle_pin(self) -> None:
        self._pinned = not self._pinned
        set_click_through(self, self._pinned)
        self._gear_lbl.setVisible(False)

    # ── Settings ──────────────────────────────────────────────────────────────

    def open_settings(self) -> None:
        from ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self, dark=self._dark, config=self._config,
                             storage=self._storage)
        if dlg.exec():
            new_cfg = dlg.get_config()
            save_config(new_cfg)
            self._config = new_cfg

            dark_changed = new_cfg.get("dark_mode", False) != self._dark
            self._dark = new_cfg.get("dark_mode", False)
            if dark_changed:
                self._apply_theme()

            self._timer.stop()
            self.start_polling()

    # ── Window placement ──────────────────────────────────────────────────────

    def _position_top_right(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(geo.right() - self._W - 20, geo.top() + 20)

    def show_and_raise(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    # ── Drag ─────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if self._pinned:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._pinned:
            return
        if self._dragging:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._dragging = False
        super().mouseReleaseEvent(event)

    # ── Hover ─────────────────────────────────────────────────────────────────

    def enterEvent(self, event) -> None:
        if not self._pinned:
            self._gear_lbl.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._gear_lbl.setVisible(False)
        super().leaveEvent(event)

    # ── Fade-in ───────────────────────────────────────────────────────────────

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.setWindowOpacity(0.0)
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(350)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self._fade_anim = anim
