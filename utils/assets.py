

from PySide6.QtGui import QPixmap, QPainter, QColor, QPainterPath, QFont, QBrush
from PySide6.QtCore import Qt, QRectF


def get_icon_pixmap(size: int = 64, dark: bool = False) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    accent = QColor("#F59E0B") if dark else QColor("#D97706")
    painter.setBrush(QBrush(accent))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(2, 2, size - 4, size - 4)

    painter.end()
    return pixmap
