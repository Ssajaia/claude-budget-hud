"""
Runtime icon generation so the app works without bundled asset files.
A real production build replaces this with a proper icon file.
"""

from PySide6.QtGui import QPixmap, QPainter, QColor, QPainterPath, QFont, QBrush
from PySide6.QtCore import Qt, QRectF


def get_icon_pixmap(size: int = 64, dark: bool = False) -> QPixmap:
    """Generate the Claude-style icon: warm amber circle with 'C'."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Circle background
    accent = QColor("#F59E0B") if dark else QColor("#D97706")
    painter.setBrush(QBrush(accent))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(2, 2, size - 4, size - 4)

    # Letter C
    painter.setPen(QColor("#FFFFFF"))
    font = QFont("Inter", max(size // 3, 8), QFont.Weight.Medium)
    painter.setFont(font)
    painter.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "C")

    painter.end()
    return pixmap
