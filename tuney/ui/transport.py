from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from . import Action, State, StateChange
from .tooltip import Tooltip

IMAGE_SIZE = 22
BUTTON_SIZE = 32
FLASH_INTERVAL_MS = 1000
RED = '#d02020'
GREY = '#a0a0a0'
BLACK = '#101010'
HOVER_STYLE = 'QPushButton:hover { background: #d8d8d8; }'
TOOLTIPS = {
    'record': 'Record',
    'stop': 'Stop',
    'save': 'Save',
    'clear': 'Clear',
}


class Transport(QWidget):
    def __init__(
        self,
        parent: QWidget,
        callback: Callable[[StateChange], bool],
        hover_time: Callable[[], float],
    ) -> None:
        super().__init__(parent)
        self.callback = callback
        self.hover_time = hover_time
        self._state = State.ready
        self._flash_on = False
        self._flash_timer = QTimer(self)
        self._flash_timer.timeout.connect(self._flash_record)
        self.record_icon = _circle(RED)
        self.disabled_stop_icon = _square(GREY)
        self.stop_icon = _square(BLACK)
        self.pause_icon = _pause(RED)
        self.save_icon = _save(BLACK)
        self.disabled_save_icon = _save(GREY)
        self.clear_icon = _cross(BLACK)
        self.disabled_clear_icon = _cross(GREY)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.record = _button(self.record_icon, self._on_record)
        self.stop = _button(self.disabled_stop_icon, self._on_stop)
        self.save = _button(self.disabled_save_icon, self._on_save)
        self.clear = _button(self.disabled_clear_icon, self._on_clear)
        for button in [self.record, self.stop, self.save, self.clear]:
            layout.addWidget(button)
        self._add_tooltips()
        self._configure_buttons()

    @property
    def state(self) -> State:
        return self._state

    def _on_record(self) -> None:
        self._set_state(_record_state(self.state), Action.record)

    def _on_stop(self) -> None:
        self._set_state(State.paused, Action.stop)

    def _on_save(self) -> None:
        self._set_state(_ready_state(self.state), Action.save)

    def _on_clear(self) -> None:
        self._set_state(_ready_state(self.state), Action.clear)

    def _set_state(self, state: State, action: Action) -> None:
        if state == self.state:
            return
        change = StateChange(old_state=self.state, state=state, action=action)
        if not self.callback(change):
            return
        self._state = state
        self._configure_buttons()

    def _configure_buttons(self) -> None:
        if self.state == State.recording:
            self._start_flashing()
        else:
            self._stop_flashing()
            self.record.setIcon(self.record_icon)

        recording = self.state == State.recording
        self.stop.setIcon(self.stop_icon if recording else self.disabled_stop_icon)
        self.stop.setEnabled(recording)
        ready = self.state == State.ready
        self.save.setIcon(self.disabled_save_icon if ready else self.save_icon)
        self.save.setEnabled(not ready)
        self.clear.setIcon(self.disabled_clear_icon if ready else self.clear_icon)
        self.clear.setEnabled(not ready)

    def _start_flashing(self) -> None:
        if self._flash_timer.isActive():
            return
        self._flash_on = True
        self.record.setIcon(self.pause_icon)
        self._flash_timer.start(FLASH_INTERVAL_MS)

    def _stop_flashing(self) -> None:
        self._flash_timer.stop()
        self._flash_on = False

    def _flash_record(self) -> None:
        if self.state != State.recording:
            self._stop_flashing()
            return
        self._flash_on = not self._flash_on
        self.record.setIcon(self.pause_icon if self._flash_on else self.record_icon)

    def _add_tooltips(self) -> None:
        Tooltip(self.record, TOOLTIPS['record'], self.hover_time)
        Tooltip(self.stop, TOOLTIPS['stop'], self.hover_time)
        Tooltip(self.save, TOOLTIPS['save'], self.hover_time)
        Tooltip(self.clear, TOOLTIPS['clear'], self.hover_time)


def _button(icon: QIcon, callback: Callable[[], None]) -> QPushButton:
    button = QPushButton()
    button.setIcon(icon)
    button.setIconSize(QSize(IMAGE_SIZE, IMAGE_SIZE))
    button.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
    button.setStyleSheet(HOVER_STYLE)
    button.clicked.connect(callback)
    return button


def _record_state(state: State) -> State:
    return State.paused if state == State.recording else State.recording


def _ready_state(state: State) -> State:
    return State.ready if state != State.ready else state


def _circle(color: str) -> QIcon:
    pixmap = _blank_pixmap()
    painter = QPainter(pixmap)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(3, 3, 18, 18)
    painter.end()
    return QIcon(pixmap)


def _square(color: str) -> QIcon:
    pixmap = _blank_pixmap()
    painter = QPainter(pixmap)
    painter.fillRect(4, 4, 16, 16, QColor(color))
    painter.end()
    return QIcon(pixmap)


def _pause(color: str) -> QIcon:
    pixmap = _blank_pixmap()
    painter = QPainter(pixmap)
    painter.fillRect(5, 3, 5, 18, QColor(color))
    painter.fillRect(14, 3, 5, 18, QColor(color))
    painter.end()
    return QIcon(pixmap)


def _save(color: str) -> QIcon:
    pixmap = _blank_pixmap()
    painter = QPainter(pixmap)
    pen = QPen(QColor(color), 2)
    painter.setPen(pen)
    painter.drawRect(4, 3, 16, 18)
    painter.drawRect(7, 5, 9, 6)
    painter.fillRect(14, 5, 3, 6, QColor(color))
    painter.drawRect(8, 15, 8, 6)
    painter.drawLine(10, 17, 14, 17)
    painter.end()
    return QIcon(pixmap)


def _cross(color: str) -> QIcon:
    pixmap = _blank_pixmap()
    painter = QPainter(pixmap)
    painter.setPen(QPen(QColor(color), 4))
    painter.drawLine(5, 5, 18, 18)
    painter.drawLine(18, 5, 5, 18)
    painter.end()
    return QIcon(pixmap)


def _blank_pixmap() -> QPixmap:
    pixmap = QPixmap(IMAGE_SIZE, IMAGE_SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    return pixmap
