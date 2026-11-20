"""Notifications discrètes en bas à droite de la fenêtre."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QVBoxLayout, QWidget

from face_analyse.ui import theme

_LEVEL_COLORS = {"info": theme.FG, "success": theme.OK, "warning": theme.WARN, "error": theme.DANGER}


class Toast(QLabel):
    def __init__(self, parent: QWidget, text: str, level: str = "info", duration_ms: int = 3800):
        super().__init__(text, parent)
        self.setWordWrap(True)
        self.setMaximumWidth(380)
        color = _LEVEL_COLORS.get(level, theme.FG)
        self.setStyleSheet(
            f"background: rgba(12,12,12,0.96); color: {color}; border: 1px solid {theme.LINE_2};"
            f"border-left: 2px solid {color}; padding: 10px 14px; border-radius: 4px;"
        )
        self._fx = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._fx)
        self._anim = QPropertyAnimation(self._fx, b"opacity", self)
        self._anim.setDuration(260)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
        QTimer.singleShot(duration_ms, self._fade_out)

    def _fade_out(self):
        self._anim.stop()
        self._anim.setStartValue(self._fx.opacity())
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self.deleteLater)
        self._anim.start()


class ToastHost(QWidget):
    """Conteneur transparent superposé à la fenêtre principale."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 18, 18)
        self._layout.setSpacing(8)
        self._layout.addStretch(1)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        parent.installEventFilter(self)
        self._fit()

    def eventFilter(self, obj, ev):
        if ev.type() == ev.Type.Resize:
            self._fit()
        return False

    def _fit(self):
        self.setGeometry(self.parentWidget().rect())
        self.raise_()

    def show_message(self, text: str, level: str = "info", duration_ms: int = 3800):
        toast = Toast(self, text, level, duration_ms)
        self._layout.addWidget(toast, 0, Qt.AlignmentFlag.AlignRight)
        self.raise_()
