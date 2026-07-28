from __future__ import annotations

import sys
from functools import cached_property
from typing import TYPE_CHECKING

from PySide6.QtCore import QElapsedTimer, QSignalBlocker, Qt, QTimer
from PySide6.QtGui import QFont, QResizeEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDial,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..app.platform_info import instrument, trace
from ..audio.device import device_names
from ..midi.ports import midi_names
from . import constants, control_panel
from .control_panel import ControlPanel
from .control_panel_layout import _FlowLayout
from .main_window import MainWindow
from .note_button import MIN_BUTTON_HEIGHT, MIN_FONT_SIZE, NoteButton, _note_font_size
from .platform import command_key
from .splitter import SpacedSplitter
from .theme import replay_style
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
    'replay': 'Play recorded text, or stop playback',
    'randomize': 'Randomize time for the recorded text',
    'loop': 'Repeat replay until stopped',
    'loop_clock': 'Elapsed time in the current replay loop',
    'master_gain': 'Playback volume',
    'help': 'Help',
}
MASTER_GAIN_SCALE = 100
MASTER_GAIN_DECIMALS = 4
MASTER_GAIN_INCREMENT = 0.01
LOOP_TEMPO_MINIMUM = 0.01
LOOP_TEMPO_MAXIMUM = 100.0
LOOP_TEMPO_INCREMENT = 0.01
LOOP_TEMPO_DECIMALS = 2
NOTE_FONT_REFRESH_DELAY_MS = 50

WIDTH, HEIGHT = 70, 80

if TYPE_CHECKING:
    from ..app.app import App


class Layout(QWidget):
    def __init__(self, main_window: MainWindow) -> None:
        instrument('layout init start')
        super().__init__(main_window)
        self.setEnabled(False)
        self.hide()
        width = WIDTH * main_window.columns
        height = (
            HEIGHT * main_window.rows
            + TEXT_BOX_HEIGHT
            + CONTROL_PANEL_HEIGHT
            + LOOP_CONTROLS_HEIGHT
        )
        main_window.resize(width, height)

        self.main_window = main_window
        self._note_font_refresh_pending = False
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.root = QVBoxLayout(self)
        self.root.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.root.setContentsMargins(
            constants.PAD, constants.PAD, constants.PAD, constants.PAD
        )
        self.root.setSpacing(constants.QUARTER)
        _ = self.splitter
        _ = self.control_panel
        _ = self.text_area
        _ = self.stats_frame
        _ = self.text_stack
        _ = self.replay_frame
        _ = self.loop_controls
        _ = self.note_grid_widget
        self.splitter.setSizes(
            [
                CONTROL_PANEL_HEIGHT,
                TEXT_BOX_HEIGHT + REPLAY_FRAME_HEIGHT + LOOP_CONTROLS_HEIGHT,
                max(NOTE_GRID_HEIGHT * main_window.rows, NOTE_GRID_HEIGHT),
            ]
        )
        self.set_text(main_window.app.display_text)
        self.update_minimum_height()
        QTimer.singleShot(0, self.finish_startup_layout)
        instrument('layout init end')

    def finish_startup_layout(self) -> None:
        instrument('layout startup build start')
        self.control_panel.rebuild()
        self.rebuild_note_grid()
        self.root.activate()
        self.splitter.updateGeometry()
        self.setEnabled(True)
        self.show()
        self.main_window.qt_app.processEvents()
        self.refresh_note_button_fonts()
        self.main_window.setFocus(Qt.FocusReason.OtherFocusReason)
        instrument('layout startup build end')

    def set_text(self, s: str) -> None:
        trace('layout set text', length=len(s))
        self.text_stack.setCurrentWidget(self.textbox)
        self.textbox.setPlainText(s)
        self.textbox.moveCursor(self.textbox.textCursor().MoveOperation.End)
        self.count_label.setText(f'Chars: {len(s)}')

    def set_text_timings(self, rows: list[list[str]]) -> None:
        trace('layout set text timings', rows=len(rows))
        self.text_stack.setCurrentWidget(self.text_timings)
        self.text_timings.blockSignals(True)
        self.text_timings.setRowCount(len(rows))
        for row, values in enumerate(rows):
            for column, value in enumerate(values):
                self.text_timings.setItem(row, column, QTableWidgetItem(value))
        self.text_timings.blockSignals(False)
        self.count_label.setText(f'Notes: {len(rows)}')

    def set_active_text_timing(self, index: int | None) -> None:
        self.text_timings.clearSelection()
        if index is None or index < 0 or index >= self.text_timings.rowCount():
            return
        self.text_timings.selectRow(index)
        if item := self.text_timings.item(index, 0):
            self.text_timings.scrollToItem(
                item, QAbstractItemView.ScrollHint.PositionAtCenter
            )

    def on_text_timing_changed(self, item: QTableWidgetItem) -> None:
        self.main_window.on_text_timing_changed(item.row(), item.column(), item.text())

    def set_play_cursor(self, index: int | None) -> None:
        trace('layout set play cursor', index=index)
        if index is None:
            if self.text_stack.currentWidget() is not self.textbox:
                return
            index = len(self.textbox.toPlainText())
        cursor = self.textbox.textCursor()
        cursor.setPosition(max(0, min(index, len(self.textbox.toPlainText()))))
        self.textbox.setTextCursor(cursor)
        self.textbox.ensureCursorVisible()
        self.textbox.setFocus(Qt.FocusReason.OtherFocusReason)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.schedule_note_button_font_refresh()

    def schedule_note_button_font_refresh(self) -> None:
        if self.__dict__.get('_note_font_refresh_pending', False):
            return
        self._note_font_refresh_pending = True
        QTimer.singleShot(NOTE_FONT_REFRESH_DELAY_MS, self._refresh_note_button_fonts)

    def _refresh_note_button_fonts(self) -> None:
        self._note_font_refresh_pending = False
        self.refresh_note_button_fonts()

    def refresh_note_button_fonts(self) -> None:
        buttons = list(self.__dict__.get('note_buttons', {}).values())
        if not buttons:
            return
        instrument('layout refresh note button fonts', buttons=len(buttons))
        font_size = max(
            MIN_FONT_SIZE,
            min(_note_font_size(i.width(), i.height(), i.note_name) for i in buttons),
        )
        for button in buttons:
            button.set_note_font_size(font_size)

    def update_minimum_height(self) -> None:
        self.main_window.minimum_content_height = _minimum_program_height(
            self.main_window.rows, self.splitter.handleWidth()
        )
        self.main_window.enforce_minimum_size()

    @cached_property
    def splitter(self) -> SpacedSplitter:
        splitter = SpacedSplitter(
            Qt.Orientation.Vertical,
            self,
            handle_size=6,
            space_above=10,
            space_below=10,
        )
        splitter.refresh_theme(self.main_window.current_theme)
        self.root.addWidget(splitter, stretch=1)
        return splitter

    @cached_property
    def control_panel(self) -> ControlPanel:
        panel = ControlPanel(
            self,
            self.main_window.app,
            CONTROL_PANEL_HEIGHT,
            self.main_window.app,
            build=False,
            eager_modes=False,
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
        instrument('layout refresh devices')
        device_names.cache_clear()
        midi_names.cache_clear()
        for option_control in self.control_panel.option_controls:
            option_control.refresh()

    def refresh_midi_devices(self) -> None:
        instrument('layout refresh midi devices')
        for option_control in self.control_panel.option_controls:
            option_control.refresh()

    def rebuild_control_panel(self) -> None:
        instrument('layout rebuild control panel start')
        self.control_panel.rebuild()
        instrument('layout rebuild control panel end')

    def refresh_loop_controls(self) -> None:
        _set_entry_text(self.loop_before, str(self.main_window.history.loop_before))
        _set_entry_text(self.loop_after, str(self.main_window.history.loop_after))
        _set_spin_value(self.loop_tempo, self.main_window.history.loop_tempo)

    def set_randomize_on_each_loop_state(self, randomize_on_each_loop: bool) -> None:
        self.randomize_on_each_loop.setChecked(randomize_on_each_loop)

    def set_loop_state(self, loop_replay: bool) -> None:
        self.loop.setChecked(loop_replay)

    def set_replay_state(self, is_replaying: bool) -> None:
        self.replay.setText('Stop' if is_replaying else 'Play')
        self.replay.setStyleSheet(
            replay_style(self.main_window.current_theme, is_replaying)
        )
        if not is_replaying:
            self.stop_loop_clock()

    def refresh_theme(self) -> None:
        if 'control_panel' in self.__dict__:
            self.control_panel.refresh_theme()
        if 'note_buttons' in self.__dict__:
            for button in self.note_buttons.values():
                button.refresh_theme()
        if 'transport' in self.__dict__:
            self.transport.refresh_theme()
        if 'replay' in self.__dict__:
            self.set_replay_state(self.main_window.is_replaying)
        if 'splitter' in self.__dict__:
            self.splitter.refresh_theme(self.main_window.current_theme)
            self.splitter.update()
            for i in range(self.splitter.count()):
                self.splitter.handle(i).update()

    def start_loop_clock(self) -> None:
        if 'loop_clock' not in self.__dict__:
            return
        self.loop_clock_elapsed.start()
        self.set_loop_clock(0)
        self.loop_clock_timer.start(100)

    def stop_loop_clock(self) -> None:
        if 'loop_clock_timer' in self.__dict__:
            self.loop_clock_timer.stop()
        if 'loop_clock' in self.__dict__:
            self.set_loop_clock(0)

    def refresh_loop_clock(self) -> None:
        self.set_loop_clock(self.loop_clock_elapsed.elapsed())

    def set_loop_clock(self, elapsed_ms: int) -> None:
        total_tenths = max(0, elapsed_ms // 100)
        minutes, tenths = divmod(total_tenths, 600)
        seconds, tenths = divmod(tenths, 10)
        self.loop_clock.setText(f'{minutes}:{seconds:02}.{tenths}')

    @cached_property
    def loop_clock_elapsed(self) -> QElapsedTimer:
        return QElapsedTimer()

    @cached_property
    def loop_clock_timer(self) -> QTimer:
        timer = QTimer(self)
        timer.timeout.connect(self.refresh_loop_clock)
        return timer

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
        textbox.setCursorWidth(2)
        textbox.setReadOnly(True)
        return textbox

    @cached_property
    def text_timings(self) -> QTableWidget:
        text_timings = QTableWidget(0, 3, self.text_area)
        text_timings.setMinimumHeight(40)
        text_timings.setFont(QFont(FONT_FAMILY, FONT_SIZE))
        text_timings.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        text_timings.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        text_timings.setHorizontalHeaderLabels(['Character', 'Delay', 'Hold'])
        text_timings.itemChanged.connect(self.on_text_timing_changed)
        return text_timings

    @cached_property
    def text_stack(self) -> QStackedWidget:
        stack = QStackedWidget(self.text_area)
        stack.addWidget(self.textbox)
        stack.addWidget(self.text_timings)
        self.text_area_layout.addWidget(stack, stretch=1)
        return stack

    @cached_property
    def replay_frame(self) -> QWidget:
        frame = QWidget(self.text_area)
        frame.setMinimumHeight(REPLAY_FRAME_HEIGHT)
        layout = _FlowLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        self.transport = Transport(
            frame,
            self.main_window.on_transport_state,
            lambda: self.main_window.app.hover_time,
        )
        layout.addWidget(self.transport)

        def hover_time() -> float:
            return self.main_window.app.hover_time

        self.replay = QPushButton('Play', frame)
        self.replay.setFixedSize(90, 32)
        self.replay.setFont(QFont(FONT_FAMILY, FONT_SIZE))
        self.replay.clicked.connect(self.main_window.on_replay)
        Tooltip(self.replay, REPLAY_TOOLTIPS['replay'], hover_time)
        layout.addWidget(self.replay)
        self.randomize = QPushButton('Randomize time', frame)
        self.randomize.setFixedWidth(116)
        self.randomize.clicked.connect(self.main_window.on_randomize_timing)
        Tooltip(self.randomize, REPLAY_TOOLTIPS['randomize'], hover_time)
        layout.addWidget(self.randomize)
        self.loop = QCheckBox('Loop', frame)
        self.loop.toggled.connect(self.main_window.on_loop_replay)
        Tooltip(self.loop, REPLAY_TOOLTIPS['loop'], hover_time)
        layout.addWidget(self.loop)
        gain = QWidget(frame)
        gain_layout = QHBoxLayout(gain)
        gain_layout.setContentsMargins(0, 0, 0, 0)
        gain_layout.setSpacing(6)
        self.master_gain = QDial(gain)
        self.master_gain.setFixedSize(34, 34)
        self.master_gain.setRange(0, 200)
        self.master_gain.setValue(
            round(self.main_window.app.sound.master_gain * MASTER_GAIN_SCALE)
        )
        self.master_gain.setNotchesVisible(True)
        self.master_gain.setObjectName('master_gain_dial')
        Tooltip(self.master_gain, REPLAY_TOOLTIPS['master_gain'], hover_time)
        gain_layout.addWidget(self.master_gain)
        self.master_gain_value = QDoubleSpinBox(gain)
        self.master_gain_value.setObjectName('master_gain')
        self.master_gain_value.setDecimals(MASTER_GAIN_DECIMALS)
        self.master_gain_value.setSingleStep(MASTER_GAIN_INCREMENT)
        self.master_gain_value.setRange(0, 2)
        self.master_gain_value.setValue(self.main_window.app.sound.master_gain)
        self.master_gain_value.setFixedWidth(74)
        Tooltip(self.master_gain_value, REPLAY_TOOLTIPS['master_gain'], hover_time)
        gain_layout.addWidget(self.master_gain_value)
        self.master_gain.valueChanged.connect(self._on_master_gain_dial)
        self.master_gain_value.valueChanged.connect(self._on_master_gain_value)
        layout.addWidget(gain)
        self.help = QPushButton('?', frame)
        self.help.setFixedSize(32, 32)
        self.help.setFont(QFont(FONT_FAMILY, 18))
        Tooltip(self.help, REPLAY_TOOLTIPS['help'], hover_time)
        self.help.clicked.connect(self.main_window.on_help)
        layout.addWidget(self.help)
        self.text_area_layout.addWidget(frame)
        self.set_replay_state(False)
        return frame

    def _on_master_gain_dial(self, value: int) -> None:
        gain = value / MASTER_GAIN_SCALE
        with QSignalBlocker(self.master_gain_value):
            self.master_gain_value.setValue(gain)
        self.main_window.on_master_gain(gain)

    def _on_master_gain_value(self, gain: float) -> None:
        with QSignalBlocker(self.master_gain):
            self.master_gain.setValue(round(gain * MASTER_GAIN_SCALE))
        self.main_window.on_master_gain(gain)

    @cached_property
    def loop_controls(self) -> QWidget:
        frame = QWidget(self.text_area)
        frame.setMinimumHeight(LOOP_CONTROLS_HEIGHT)
        layout = _FlowLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        def labeled_entry(label: str, value: float) -> QLineEdit:
            group = QWidget(frame)
            group_layout = QHBoxLayout(group)
            group_layout.setContentsMargins(0, 0, 0, 0)
            group_layout.setSpacing(4)
            group_layout.addWidget(QLabel(label, group))
            entry = QLineEdit(str(value), group)
            entry.setFixedWidth(48)
            group_layout.addWidget(entry)
            layout.addWidget(group)
            return entry

        self.loop_before = labeled_entry('Before', self.main_window.history.loop_before)
        self.loop_before.editingFinished.connect(
            lambda: self.main_window.on_loop_before(self.loop_before.text())
        )
        self.loop_after = labeled_entry('After', self.main_window.history.loop_after)
        self.loop_after.editingFinished.connect(
            lambda: self.main_window.on_loop_after(self.loop_after.text())
        )
        tempo = QWidget(frame)
        tempo_layout = QHBoxLayout(tempo)
        tempo_layout.setContentsMargins(0, 0, 0, 0)
        tempo_layout.setSpacing(4)
        tempo_layout.addWidget(QLabel('Tempo', tempo))
        self.loop_tempo = QDoubleSpinBox(tempo)
        self.loop_tempo.setLocale(control_panel.NUMERIC_LOCALE)
        self.loop_tempo.setRange(LOOP_TEMPO_MINIMUM, LOOP_TEMPO_MAXIMUM)
        self.loop_tempo.setSingleStep(LOOP_TEMPO_INCREMENT)
        self.loop_tempo.setDecimals(LOOP_TEMPO_DECIMALS)
        self.loop_tempo.setValue(self.main_window.history.loop_tempo)
        self.loop_tempo.setFixedWidth(64)
        tempo_layout.addWidget(self.loop_tempo)
        layout.addWidget(tempo)
        self.loop_tempo.editingFinished.connect(
            lambda: self.main_window.on_loop_tempo(self.loop_tempo.value())
        )
        self.randomize_on_each_loop = QCheckBox('Randomize each loop', frame)
        self.randomize_on_each_loop.toggled.connect(
            self.main_window.on_randomize_on_each_loop
        )
        layout.addWidget(self.randomize_on_each_loop)
        self.loop_clock = QLabel('0:00.0', frame)
        self.loop_clock.setObjectName('loop_clock')
        self.loop_clock.setFont(QFont(FONT_FAMILY, FONT_SIZE))
        self.loop_clock.setFixedWidth(56)
        Tooltip(
            self.loop_clock,
            REPLAY_TOOLTIPS['loop_clock'],
            lambda: self.main_window.app.hover_time,
        )
        layout.addWidget(self.loop_clock)
        self.text_area_layout.addWidget(frame)
        return frame

    @cached_property
    def note_grid_widget(self) -> QWidget:
        widget = QWidget(self)
        widget.setMinimumHeight(_note_grid_minimum_height(self.main_window.rows))
        self.note_grid = QGridLayout(widget)
        self.note_grid.setContentsMargins(0, 0, 0, 0)
        self.note_grid.setSpacing(constants.QUARTER)
        self.splitter.addWidget(widget)
        return widget

    @cached_property
    def note_buttons(self) -> dict[str, NoteButton]:
        it = self.main_window.app.note_labels.items()
        buttons = {}
        for i, (char, text) in enumerate(it):
            buttons[char] = self._note_frame(i, char, text)
        for char, button in self.note_button_cache.items():
            if char not in buttons:
                button.hide()
                button.is_press = False
        return buttons

    @cached_property
    def note_button_cache(self) -> dict[str, NoteButton]:
        return {}

    def rebuild_note_grid(self) -> None:
        instrument('layout rebuild note grid start')
        self.main_window.app.__dict__.pop('note_labels', None)
        self.__dict__.pop('note_buttons', None)
        _clear_grid(self.note_grid)
        try:
            has_note_buttons = self.main_window.app.scale.note_count > 0
        except (AssertionError, ValueError, ZeroDivisionError):
            has_note_buttons = False
        if has_note_buttons:
            n = len(self.main_window.app.note_labels)
            self.main_window.columns = max(1, int(n**0.5 + 0.999999))
            self.main_window.rows = max(
                1, (n + self.main_window.columns - 1) // self.main_window.columns
            )
            self.note_grid_widget.setMinimumHeight(
                _note_grid_minimum_height(self.main_window.rows)
            )
            self.update_minimum_height()
            _ = self.note_buttons
        self.refresh_note_button_fonts()
        instrument('layout rebuild note grid end', has_note_buttons=has_note_buttons)

    def _note_frame(self, i: int, char: str, text: str) -> NoteButton:
        row, column = divmod(i, self.main_window.columns)
        if char not in self.note_button_cache:
            self.note_button_cache[char] = NoteButton(
                self.note_grid,
                row,
                column,
                char,
                text,
                _note_tooltip_text(self.main_window.app, char, text),
                lambda: self.main_window.app.hover_time,
                self.main_window.app.on_char,
            )
        button = self.note_button_cache[char]
        button.set_note(text)
        button.set_tooltip_text(_note_tooltip_text(self.main_window.app, char, text))
        button.show()
        self.note_grid.addWidget(button, row, column)
        return button


def _set_entry_text(entry: QLineEdit, text: str) -> None:
    entry.setText(text)


def _set_spin_value(spin: QDoubleSpinBox, value: float) -> None:
    with QSignalBlocker(spin):
        spin.setValue(value)


def _clear_grid(layout: QGridLayout) -> None:
    while layout.count():
        layout.takeAt(0)


def _note_grid_minimum_height(rows: int) -> int:
    return max(MIN_BUTTON_HEIGHT * rows, MIN_BUTTON_HEIGHT)


def _minimum_program_height(rows: int, splitter_handle_width: int) -> int:
    return (
        constants.PAD * 2
        + CONTROL_PANEL_HEIGHT
        + TEXT_BOX_HEIGHT
        + REPLAY_FRAME_HEIGHT
        + LOOP_CONTROLS_HEIGHT
        + _note_grid_minimum_height(rows)
        + splitter_handle_width * 2
    )


def _note_tooltip_text(app: App, char: str, text: str) -> str:
    note_number = app.mapper.char_to_number[char]
    frequency = app.scale.frequency(app.tuning, note_number)
    return f'{text}\n{frequency:.6g} Hz'
