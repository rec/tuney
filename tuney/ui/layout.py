from __future__ import annotations

import sys
from functools import cached_property

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from . import constants
from .control_panel import ControlPanel
from .main_window import MainWindow
from .note_button import NoteButton
from .platform import command_key
from .splitter import SpacedSplitter
from .tooltip import Tooltip
from .transport import Transport

TEXT_BOX_HEIGHT = 120
CONTROL_PANEL_HEIGHT = 270
NOTE_GRID_HEIGHT = 52
REPLAY_FRAME_HEIGHT = 40
LOOP_CONTROLS_HEIGHT = 28
FONT_FAMILY = 'Arial'
FONT_SIZE = 14
COMMAND_KEY = command_key(sys.platform)
REPLAY_TOOLTIPS = {
    'replay': 'Replay recorded text, or stop replaying',
    'randomize': 'Randomize the recorded text timing',
    'loop': 'Repeat replay until stopped',
    'help': 'Help',
}

WIDTH, HEIGHT = 70, 80


class Layout(QWidget):
    def __init__(self, main_window: MainWindow) -> None:
        super().__init__(main_window)
        width = WIDTH * main_window.columns
        height = (
            HEIGHT * main_window.rows
            + TEXT_BOX_HEIGHT
            + CONTROL_PANEL_HEIGHT
            + LOOP_CONTROLS_HEIGHT
        )
        main_window.resize(width, height)

        self.main_window = main_window
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(
            constants.PAD, constants.PAD, constants.PAD, constants.PAD
        )
        self.root.setSpacing(constants.QUARTER)
        _ = self.splitter
        _ = self.control_panel
        _ = self.text_area
        _ = self.stats_frame
        _ = self.textbox
        _ = self.replay_frame
        _ = self.loop_controls
        _ = self.note_grid_widget
        _ = self.note_buttons
        self.splitter.setSizes(
            [
                CONTROL_PANEL_HEIGHT,
                TEXT_BOX_HEIGHT + REPLAY_FRAME_HEIGHT + LOOP_CONTROLS_HEIGHT,
                max(NOTE_GRID_HEIGHT * main_window.rows, NOTE_GRID_HEIGHT),
            ]
        )
        self.set_text(main_window.state.display_text)

    def set_text(self, s: str) -> None:
        self.textbox.setPlainText(s)
        self.textbox.moveCursor(self.textbox.textCursor().MoveOperation.End)
        self.count_label.setText(f'Chars: {len(s)}')

    @cached_property
    def splitter(self) -> SpacedSplitter:
        splitter = SpacedSplitter(
            Qt.Orientation.Vertical,
            self,
            handle_size=6,
            space_above=10,
            space_below=10,
        )
        self.root.addWidget(splitter, stretch=1)
        return splitter

    @cached_property
    def control_panel(self) -> ControlPanel:
        panel = ControlPanel(
            self,
            self.main_window.state.tuney,
            CONTROL_PANEL_HEIGHT,
            self.main_window.state,
        )
        self.splitter.addWidget(panel)
        return panel

    @cached_property
    def text_area(self) -> QWidget:
        frame = QWidget(self)
        self.text_area_layout = QVBoxLayout(frame)
        self.text_area_layout.setContentsMargins(0, 0, 0, 0)
        self.text_area_layout.setSpacing(constants.QUARTER)
        self.splitter.addWidget(frame)
        return frame

    def refresh_devices(self) -> None:
        for option_control in self.control_panel.option_controls:
            option_control.refresh()

    def rebuild_control_panel(self) -> None:
        self.control_panel.rebuild()

    def refresh_loop_controls(self) -> None:
        _set_entry_text(self.loop_before, str(self.main_window.history.loop_before))
        _set_entry_text(self.loop_after, str(self.main_window.history.loop_after))
        _set_entry_text(self.loop_tempo, str(self.main_window.history.loop_tempo))

    def set_randomize_on_each_loop_state(self, randomize_on_each_loop: bool) -> None:
        self.randomize_on_each_loop.setChecked(randomize_on_each_loop)

    def set_loop_state(self, loop_replay: bool) -> None:
        self.loop.setChecked(loop_replay)

    def set_replay_state(self, is_replaying: bool) -> None:
        self.replay.setText('Stop' if is_replaying else 'Replay')
        self.replay.setStyleSheet(
            'background: #b0a8b0;' if is_replaying else 'background: #30a870;'
        )

    @cached_property
    def stats_frame(self) -> QWidget:
        frame = QWidget(self.text_area)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel('Text:', frame)
        font = QFont(FONT_FAMILY, FONT_SIZE)
        font.setBold(True)
        label.setFont(font)
        layout.addWidget(label)
        layout.addStretch()
        self.count_label = QLabel('Chars: 0', frame)
        self.count_label.setFont(QFont(FONT_FAMILY, FONT_SIZE))
        layout.addWidget(self.count_label)
        self.text_area_layout.addWidget(frame)
        return frame

    @cached_property
    def textbox(self) -> QTextEdit:
        textbox = QTextEdit(self.text_area)
        textbox.setMinimumHeight(40)
        textbox.setFont(QFont(FONT_FAMILY, FONT_SIZE))
        textbox.setReadOnly(True)
        self.text_area_layout.addWidget(textbox, stretch=1)
        return textbox

    @cached_property
    def replay_frame(self) -> QWidget:
        frame = QWidget(self.text_area)
        frame.setFixedHeight(REPLAY_FRAME_HEIGHT)
        layout = QGridLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(6)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 1)
        self.transport = Transport(
            frame,
            self.main_window.on_transport_state,
            lambda: self.main_window.state.tuney.hover_time,
        )
        layout.addWidget(self.transport, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)

        def hover_time() -> float:
            return self.main_window.state.tuney.hover_time

        self.replay = QPushButton('Replay', frame)
        self.replay.setFixedSize(156, 36)
        self.replay.setFont(QFont(FONT_FAMILY, 16))
        self.replay.clicked.connect(self.main_window.on_replay)
        Tooltip(self.replay, REPLAY_TOOLTIPS['replay'], hover_time)
        layout.addWidget(self.replay, 0, 1, alignment=Qt.AlignmentFlag.AlignCenter)
        right = QWidget(frame)
        right_layout = QHBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)
        self.randomize = QPushButton('Randomize', frame)
        self.randomize.setFixedWidth(96)
        self.randomize.clicked.connect(self.main_window.on_randomize_timing)
        Tooltip(self.randomize, REPLAY_TOOLTIPS['randomize'], hover_time)
        right_layout.addWidget(self.randomize)
        self.loop = QCheckBox('Loop', frame)
        self.loop.toggled.connect(lambda _: self.main_window.on_loop_replay())
        Tooltip(self.loop, REPLAY_TOOLTIPS['loop'], hover_time)
        right_layout.addWidget(self.loop)
        self.help = QPushButton('?', frame)
        self.help.setFixedSize(34, 34)
        self.help.setFont(QFont(FONT_FAMILY, 18))
        Tooltip(self.help, REPLAY_TOOLTIPS['help'], hover_time)
        self.help.clicked.connect(self.main_window.on_help)
        right_layout.addWidget(self.help)
        layout.addWidget(right, 0, 2, alignment=Qt.AlignmentFlag.AlignRight)
        self.text_area_layout.addWidget(frame)
        self.set_replay_state(False)
        return frame

    @cached_property
    def loop_controls(self) -> QWidget:
        frame = QWidget(self.text_area)
        frame.setFixedHeight(LOOP_CONTROLS_HEIGHT)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        def labeled_entry(label: str, value: float) -> QLineEdit:
            layout.addWidget(QLabel(label, frame))
            entry = QLineEdit(str(value), frame)
            entry.setFixedWidth(48)
            layout.addWidget(entry)
            return entry

        self.loop_before = labeled_entry('Before', self.main_window.history.loop_before)
        self.loop_before.editingFinished.connect(
            lambda: self.main_window.on_loop_before(self.loop_before.text())
        )
        self.loop_after = labeled_entry('After', self.main_window.history.loop_after)
        self.loop_after.editingFinished.connect(
            lambda: self.main_window.on_loop_after(self.loop_after.text())
        )
        self.loop_tempo = labeled_entry('Tempo', self.main_window.history.loop_tempo)
        self.loop_tempo.editingFinished.connect(
            lambda: self.main_window.on_loop_tempo(self.loop_tempo.text())
        )
        self.randomize_on_each_loop = QCheckBox('Randomize each loop', frame)
        self.randomize_on_each_loop.toggled.connect(
            lambda _: self.main_window.on_randomize_on_each_loop()
        )
        layout.addWidget(self.randomize_on_each_loop)
        layout.addStretch()
        self.text_area_layout.addWidget(frame)
        return frame

    @cached_property
    def note_grid_widget(self) -> QWidget:
        widget = QWidget(self)
        widget.setMinimumHeight(
            max(NOTE_GRID_HEIGHT * self.main_window.rows, NOTE_GRID_HEIGHT)
        )
        self.note_grid = QGridLayout(widget)
        self.note_grid.setContentsMargins(0, 0, 0, 0)
        self.note_grid.setSpacing(constants.QUARTER)
        self.splitter.addWidget(widget)
        return widget

    @cached_property
    def note_buttons(self) -> dict[str, NoteButton]:
        it = self.main_window.state.note_labels.items()
        return {k: self._note_frame(i, k, text) for i, (k, text) in enumerate(it)}

    def rebuild_note_grid(self) -> None:
        self.main_window.state.__dict__.pop('note_labels', None)
        self.__dict__.pop('note_buttons', None)
        _clear_grid(self.note_grid)
        try:
            has_note_buttons = self.main_window.state.tuney.sound.scale.note_count > 0
        except (AssertionError, ValueError, ZeroDivisionError):
            has_note_buttons = False
        if has_note_buttons:
            _ = self.note_buttons

    def _note_frame(self, i: int, char: str, text: str) -> NoteButton:
        row, column = divmod(i, self.main_window.columns)
        return NoteButton(
            self.note_grid,
            row,
            column,
            char,
            text,
            self.main_window.state.on_char,
        )


def _set_entry_text(entry: QLineEdit, text: str) -> None:
    entry.setText(text)


def _clear_grid(layout: QGridLayout) -> None:
    while layout.count():
        if (item := layout.takeAt(0)) is None:
            continue
        if (widget := item.widget()) is not None:
            widget.deleteLater()
