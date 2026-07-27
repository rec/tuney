from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer
from PySide6.QtWidgets import QLabel, QWidget

from .theme import tooltip_style, widget_theme


class Tooltip(QObject):
    def __init__(
        self,
        widget: QWidget,
        text: str,
        hover_time: Callable[[], float],
    ) -> None:
        super().__init__(widget)
        self.widget = widget
        self.text = text
        self.hover_time = hover_time
        self.window: QLabel | None = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._show)
        widget.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.widget and event.type() == QEvent.Type.Enter:
            self._schedule()
        elif watched is self.widget and event.type() in {
            QEvent.Type.Leave,
            QEvent.Type.MouseButtonPress,
        }:
            self._hide()
        return super().eventFilter(watched, event)

    def _schedule(self) -> None:
        self._hide()
        self.timer.start(round(self.hover_time() * 1000))

    def _show(self) -> None:
        self.window = QLabel(self.text, self.widget, Qt.WindowType.ToolTip)
        self.window.setWordWrap(True)
        self.window.setStyleSheet(tooltip_style(widget_theme(self.widget)))
        self.window.setMaximumWidth(320)
        point = self.widget.mapToGlobal(QPoint(0, self.widget.height() + 4))
        self.window.move(point)
        self.window.show()

    def _hide(self) -> None:
        self.timer.stop()
        if self.window is not None:
            self.window.close()
            self.window.deleteLater()
            self.window = None
