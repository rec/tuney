from __future__ import annotations

from PySide6.QtCore import QEvent, QRect, QSize, Qt
from PySide6.QtGui import QColor, QEnterEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QSplitter, QSplitterHandle, QWidget

from .theme import Theme, widget_theme


class SpacedSplitter(QSplitter):
    def __init__(
        self,
        orientation: Qt.Orientation,
        parent: QWidget,
        *,
        handle_size: int,
        space_above: int,
        space_below: int,
        color: str = '#9a9a9a',
        hover_color: str = '#707070',
    ) -> None:
        super().__init__(orientation, parent)
        self.handle_size = handle_size
        self.space_above = space_above
        self.space_below = space_below
        self.color = QColor(color)
        self.hover_color = QColor(hover_color)
        self.setChildrenCollapsible(False)
        self.setHandleWidth(handle_size + space_above + space_below)
        self.refresh_theme()

    def createHandle(self) -> QSplitterHandle:
        return _SpacedSplitterHandle(self.orientation(), self)

    def refresh_theme(self, theme: Theme | None = None) -> None:
        theme = theme or widget_theme(self)
        self.color = QColor(theme.border)
        self.hover_color = QColor(theme.disabled_text)
        self.update()


class _SpacedSplitterHandle(QSplitterHandle):
    def __init__(self, orientation: Qt.Orientation, parent: SpacedSplitter) -> None:
        super().__init__(orientation, parent)
        self.hovered = False

    def enterEvent(self, event: QEnterEvent) -> None:
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self.hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        splitter = self._splitter
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().window())
        painter.fillRect(
            self._bar_size(splitter),
            splitter.hover_color if self.hovered else splitter.color,
        )
        painter.end()
        event.accept()

    def sizeHint(self) -> QSize:
        splitter = self._splitter
        size = splitter.handle_size + splitter.space_above + splitter.space_below
        if self.orientation() == Qt.Orientation.Vertical:
            return QSize(1, size)
        return QSize(size, 1)

    @property
    def _splitter(self) -> SpacedSplitter:
        splitter = self.splitter()
        assert isinstance(splitter, SpacedSplitter)
        return splitter

    def _bar_size(self, splitter: SpacedSplitter) -> QRect:
        if self.orientation() == Qt.Orientation.Vertical:
            return QRect(0, splitter.space_above, self.width(), splitter.handle_size)
        return QRect(splitter.space_above, 0, splitter.handle_size, self.height())
