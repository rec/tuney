from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QLayoutItem, QStackedWidget, QWidget


class _FlowLayout(QLayout):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.items: list[QLayoutItem] = []
        self.setSpacing(6)

    def addItem(self, item: QLayoutItem) -> None:
        self.items.append(item)

    def count(self) -> int:
        return len(self.items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        return self.items[index] if 0 <= index < len(self.items) else None

    def takeAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self.items):
            return self.items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientation:
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self.items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(
            margins.left() + margins.right(),
            margins.top() + margins.bottom(),
        )
        return size

    def _layout(self, rect: QRect, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective = rect.adjusted(
            margins.left(), margins.top(), -margins.right(), -margins.bottom()
        )
        x = effective.x()
        y = effective.y()
        line_height = 0
        spacing = self.spacing()
        for item in self.items:
            hint = item.sizeHint()
            next_x = x + hint.width() + spacing
            if x > effective.x() and next_x - spacing > effective.right():
                x = effective.x()
                y += line_height + spacing
                next_x = x + hint.width() + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()


class _CurrentPageStackedWidget(QStackedWidget):
    def sizeHint(self) -> QSize:
        if current := self.currentWidget():
            return current.sizeHint()
        return super().sizeHint()

    def minimumSizeHint(self) -> QSize:
        if current := self.currentWidget():
            return current.minimumSizeHint()
        return super().minimumSizeHint()
