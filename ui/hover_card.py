"""Hover glow helper for CardWidget-like widgets.

Provides a simple function to attach a QGraphicsDropShadowEffect to a widget
and install an event filter to toggle the glow on enter/leave. This keeps
the glow implementation centralized so it can be applied to any widget
created dynamically (not just subclasses).
"""
from typing import Optional
from PySide6.QtCore import QObject, QEvent
from PySide6.QtWidgets import QGraphicsDropShadowEffect
from PySide6.QtGui import QColor


class _HoverEventFilter(QObject):
    def __init__(self, shadow: QGraphicsDropShadowEffect, parent=None):
        super().__init__(parent)
        self._shadow = shadow

    def eventFilter(self, watched, event):
        # Toggle the graphics effect on enter/leave
        if event.type() == QEvent.Type.Enter:
            try:
                watched.setGraphicsEffect(self._shadow)
            except Exception:
                pass
            return False
        if event.type() == QEvent.Type.Leave:
            try:
                watched.setGraphicsEffect(None)
            except Exception:
                pass
            return False
        return False


def apply_hover_glow(widget, color: Optional[str] = None, blur_radius: int = 24, alpha: int = 160):
    """Attach a hover glow effect to a widget.

    Args:
        widget: QWidget to attach the hover glow to
        color: Optional hex color string for the glow (e.g. '#7C3AED')
        blur_radius: Blur radius for the glow
        alpha: Alpha (0-255) for the glow color
    """
    try:
        if color is None:
            # Default to a semi-transparent purple if no color provided
            color = "#7C3AED"

        qcolor = QColor(color)
        qcolor.setAlpha(alpha)

        shadow = QGraphicsDropShadowEffect(widget)
        shadow.setBlurRadius(blur_radius)
        shadow.setOffset(0, 0)
        shadow.setColor(qcolor)

        # Install event filter to toggle the effect
        filt = _HoverEventFilter(shadow, widget)
        widget.installEventFilter(filt)

        # Store references to avoid GC
        widget._hover_shadow = shadow
        widget._hover_event_filter = filt
    except Exception:
        # Best-effort: if graphics effects aren't available, silently skip
        pass
