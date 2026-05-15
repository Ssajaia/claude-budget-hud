"""
OS-specific click-through (input passthrough) for frameless windows.

Windows  → WS_EX_TRANSPARENT via ctypes
macOS    → NSWindow.setIgnoresMouseEvents via AppKit
Linux    → XShapeCombineRegion (empty input shape) via Xlib
"""

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


def set_click_through(widget: "QWidget", enabled: bool) -> None:
    """Toggle click-through mode. Idempotent and non-fatal on failure."""
    try:
        if sys.platform == "win32":
            _win_click_through(widget, enabled)
        elif sys.platform == "darwin":
            _mac_click_through(widget, enabled)
        else:
            _linux_click_through(widget, enabled)
    except Exception:
        pass  # Never crash the app over window decoration details


def _win_click_through(widget: "QWidget", enabled: bool) -> None:
    import ctypes
    import ctypes.wintypes as wt

    GWL_EXSTYLE = -20
    WS_EX_LAYERED = 0x00080000
    WS_EX_TRANSPARENT = 0x00000020

    hwnd = int(widget.winId())
    current = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)

    if enabled:
        new_style = current | WS_EX_TRANSPARENT | WS_EX_LAYERED
    else:
        new_style = current & ~WS_EX_TRANSPARENT

    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)


def _mac_click_through(widget: "QWidget", enabled: bool) -> None:
    from AppKit import NSApp  # type: ignore[import]

    ns_window = widget.winId().__int__()
    # PySide6 on macOS exposes the NSView; walk up to NSWindow
    for win in NSApp.windows():
        if int(win.contentView().__repr__()) != 0:
            win.setIgnoresMouseEvents_(enabled)
            break


def _linux_click_through(widget: "QWidget", enabled: bool) -> None:
    """
    On Linux/X11 we use Qt's built-in transparent-for-input attribute.
    Full Xlib shape masking requires the python-xlib package and is
    preferred when available; we fall back to Qt's attribute.
    """
    from PySide6.QtCore import Qt

    if enabled:
        widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    else:
        widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

    # Best-effort Xlib shape mask for true click-through
    try:
        import Xlib.display  # type: ignore[import]
        import Xlib.X as X
        import Xlib.ext.shape as shape

        display = Xlib.display.Display()
        wid = int(widget.winId())
        xwindow = display.create_resource_object("window", wid)

        if enabled:
            # Apply an empty input shape — all mouse events fall through
            xwindow.shape_mask(shape.SO.Set, shape.SK.Input, 0, 0, X.NONE)
        else:
            # Reset to bounding shape (full window receives input)
            xwindow.shape_mask(shape.SO.Set, shape.SK.Input, 0, 0,
                               xwindow.get_geometry().root)
        display.flush()
    except Exception:
        pass  # Xlib not installed or not running X11
