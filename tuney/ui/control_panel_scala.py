from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from typing import TYPE_CHECKING

from PySide6 import QtWidgets
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QFocusEvent, QKeyEvent
from PySide6.QtWidgets import QLabel, QLineEdit, QWidget

from ..app.platform_info import instrument
from ..scale.ratios import Ratios
from ..scale.scala_browser import ScalaTrie, scala_trie
from ..scale.tuning import Tuning, TuningSource
from . import control_panel_sizing
from .control_panel_layout import _add_labeled_control_frame, _parent_layout
from .theme import scala_completion_style, scala_tooltip_style, widget_theme

if TYPE_CHECKING:
    from ..app.app import App
    from .control_panel import ControlPanel


class ScalaBrowserEdit(QLineEdit):
    def __init__(
        self,
        parent: QWidget | None,
        app: App | None,
        load: Callable[[ScalaBrowserEdit], None],
        set_tuning: Callable[[App, Tuning | Ratios], None],
    ) -> None:
        super().__init__(parent)
        self.app = app
        self.load = load
        self.set_tuning = set_tuning
        self.index = 0
        self.audition = app.audition_scala if app is not None else False
        self.original_tuning: Tuning | None = None
        self.tooltip_active = False
        self.setReadOnly(True)
        self.tooltip_label = QLabel('', self, Qt.WindowType.ToolTip)
        self.tooltip_label.setObjectName('scala_browser_active_tooltip')
        self.tooltip_label.setStyleSheet(scala_tooltip_style(widget_theme(self)))
        self.tooltip_label.hide()
        self._set_completion_style()
        self._complete()
        self._sync(select_completion=False)

    @cached_property
    def trie(self) -> ScalaTrie:
        instrument('scala browser trie load start')
        return scala_trie()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if event.text().isalnum() and len(event.text()) == 1:
            self._type(event.text().casefold())
        elif key == Qt.Key.Key_Left:
            self.index = self._previous_choice_index()
        elif key == Qt.Key.Key_Right:
            self.index = self._next_choice_index()
        elif key in {Qt.Key.Key_Up, Qt.Key.Key_Down}:
            self._cycle(1 if key == Qt.Key.Key_Down else -1)
        elif key in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            self.load(self)
        else:
            super().keyPressEvent(event)
            return
        self._sync()
        event.accept()

    def focusInEvent(self, event: QFocusEvent) -> None:
        super().focusInEvent(event)
        self.tooltip_active = True
        self._show_tooltip(self._tooltip_text())

    def focusOutEvent(self, event: QFocusEvent) -> None:
        self.tooltip_active = False
        self.tooltip_label.hide()
        super().focusOutEvent(event)

    def current_prefix(self) -> str:
        return self.text()[: self.index]

    def selected_ratios(self) -> Ratios | None:
        return self.trie.terminal(self.text()) or self.trie.first(self.current_prefix())

    def completion(self) -> tuple[str, Ratios] | None:
        if ratios := self.trie.terminal(self.text()):
            return self.text(), ratios
        return self.trie.first_match(self.current_prefix())

    def set_audition(self, enabled: bool) -> None:
        self.audition = enabled
        self._sync()

    def restore_audition(self) -> None:
        if self.app is not None and self.original_tuning is not None:
            self.set_tuning(self.app, self.original_tuning)
            self.original_tuning = None

    def _type(self, c: str) -> None:
        if c not in self.trie.choices(self.current_prefix()):
            return
        self.setText(self.text()[: self.index] + c)
        self.index += 1
        self._complete()

    def _cycle(self, step: int) -> None:
        choices = self.trie.choices(self.current_prefix())
        if not choices:
            return
        text = self.text()
        current = text[self.index] if self.index < len(text) else ''
        index = choices.index(current) if current in choices else -1
        self._set_current(choices[(index + step) % len(choices)])

    def _set_current(self, c: str) -> None:
        text = self.text()
        prefix = text[: self.index] + c
        match = self.trie.first_match(prefix)
        self.setText(match[0] if match else prefix)

    def _complete(self) -> None:
        if match := self.trie.first_match(self.current_prefix()):
            self.setText(match[0])

    def _previous_choice_index(self) -> int:
        for i in range(self.index - 1, -1, -1):
            if len(self.trie.choices(self.text()[:i])) > 1:
                return i
        return 0

    def _next_choice_index(self) -> int:
        for i in range(self.index + 1, len(self.text())):
            if len(self.trie.choices(self.text()[:i])) > 1:
                return i
        return len(self.text())

    def _sync(self, select_completion: bool = True) -> None:
        self._set_completion_style(faded=not select_completion)
        self.setCursorPosition(self.index)
        if select_completion and self.index < len(self.text()):
            self.setSelection(self.index, len(self.text()) - self.index)
        else:
            self.deselect()
        if self.tooltip_active:
            self._show_tooltip(self._tooltip_text())
        if (completion := self.completion()) and self._completed(completion[1]):
            self._audition(completion[1])
        else:
            self.restore_audition()

    def _show_tooltip(self, text: str | None = None) -> None:
        self.tooltip_label.setText(text if text is not None else self._tooltip_text())
        self.tooltip_label.adjustSize()
        self.tooltip_label.move(
            self.mapToGlobal(self.rect().bottomLeft()) + QPoint(0, 10)
        )
        self.tooltip_label.show()
        self.tooltip_label.raise_()

    def _tooltip_text(self) -> str:
        return scala_browser_tooltip(self.trie, self.text())

    def _set_completion_style(self, faded: bool = False) -> None:
        self.setStyleSheet(scala_completion_style(widget_theme(self), faded))

    def _completed(self, ratios: Ratios) -> bool:
        stem = ratios.name.removesuffix('.scl').casefold()
        return self.index == len(self.text()) or self.index >= len(stem)

    def _audition(self, ratios: Ratios) -> None:
        if self.app is None or not self.audition:
            self.restore_audition()
            return
        if self.original_tuning is not None:
            return
        self.original_tuning = self.app.tuning.model_copy(deep=True)
        self.set_tuning(self.app, ratios)


def scala_browser_tooltip(trie: ScalaTrie, prefix: str) -> str:
    if ratios := trie.first(prefix):
        return ratios.desc
    return prefix


def loaded_scala_name(app: App | None) -> str:
    ratios = loaded_scala_ratios(app)
    return ratios.name if ratios else ''


def loaded_scala_description(app: App | None) -> str:
    ratios = loaded_scala_ratios(app)
    return ratios.desc if ratios else ''


def loaded_scala_ratios(app: App | None) -> Ratios | None:
    if app is None or app.tuning.type != TuningSource.ratios:
        return None
    return app.tuning.ratios


def add_scala_browser_control(
    parent: QWidget,
    control_panel: ControlPanel,
    set_tuning: Callable[[App, Tuning | Ratios], None],
) -> None:
    frame, layout, _ = _add_labeled_control_frame(parent, 'scala')
    app = control_panel.app
    entry = ScalaBrowserEdit(
        frame,
        app,
        lambda e: _load_scala_browser_tuning(e, control_panel, set_tuning),
        set_tuning,
    )
    control_panel_sizing._configure_editor(
        entry, 12 * control_panel_sizing.ENTRY_CHAR_WIDTH
    )
    entry.setObjectName('scala_browser')
    layout.addWidget(entry)
    if app is not None:
        checkbox = QtWidgets.QCheckBox('audition', frame)
        checkbox.setChecked(app.audition_scala)

        def update(checked: bool) -> None:
            app.audition_scala = checked
            entry.set_audition(checked)

        checkbox.toggled.connect(update)
        layout.addWidget(checkbox)
    name = QLineEdit(loaded_scala_name(app), frame)
    name.setReadOnly(True)
    control_panel_sizing._configure_editor(
        name, 7 * control_panel_sizing.ENTRY_CHAR_WIDTH
    )
    name.setObjectName('tuning_name')
    layout.addWidget(name)
    description = QLineEdit(loaded_scala_description(app), frame)
    description.setReadOnly(True)
    control_panel_sizing._configure_flexible_editor(
        description, 120 * control_panel_sizing.ENTRY_CHAR_WIDTH
    )
    description.setObjectName('tuning_description')
    layout.addWidget(description)
    _parent_layout(parent).addWidget(frame)


def _load_scala_browser_tuning(
    entry: ScalaBrowserEdit,
    control_panel: ControlPanel,
    set_tuning: Callable[[App, Tuning | Ratios], None],
) -> None:
    if (ratios := entry.selected_ratios()) is None:
        return
    parent = entry.parentWidget()
    assert parent is not None
    if (
        QtWidgets.QMessageBox.question(
            parent,
            'Load Scala tuning',
            f'Load {ratios.name}?',
        )
        != QtWidgets.QMessageBox.StandardButton.Yes
    ):
        return
    app = control_panel.app
    assert app is not None
    entry.restore_audition()
    app.main_window.history.checkpoint_undo()
    set_tuning(app, ratios)
    _set_loaded_scala_fields(control_panel, ratios)
    app.main_window.ui.rebuild_control_panel()


def _set_loaded_scala_fields(control_panel: ControlPanel, ratios: Ratios) -> None:
    if name := control_panel.findChild(QLineEdit, 'tuning_name'):
        name.setText(ratios.name)
    if description := control_panel.findChild(QLineEdit, 'tuning_description'):
        description.setText(ratios.desc)
