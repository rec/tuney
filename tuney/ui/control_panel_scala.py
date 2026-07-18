from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QLineEdit, QWidget

from ..app.platform_info import instrument
from ..scale.ratios import Ratios
from ..scale.scala_browser import ScalaTrie, scala_trie
from ..scale.tuning import Tuning, Type

if TYPE_CHECKING:
    from ..app.app import App


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
        self.setStyleSheet(
            'QLineEdit {'
            'selection-color: #909090;'
            'selection-background-color: transparent;'
            '}'
        )

    @cached_property
    def trie(self) -> ScalaTrie:
        instrument('scala browser trie load start')
        return scala_trie()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if event.text().isalnum() and len(event.text()) == 1:
            self._type(event.text().casefold())
        elif key == Qt.Key.Key_Left:
            self.index = max(0, self.index - 1)
        elif key == Qt.Key.Key_Right:
            self.index = (
                len(self.text())
                if self.completion()
                else min(len(self.text()), self.index + 1)
            )
        elif key in {Qt.Key.Key_Up, Qt.Key.Key_Down}:
            self._cycle(1 if key == Qt.Key.Key_Down else -1)
        elif key in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            self.load(self)
        else:
            super().keyPressEvent(event)
            return
        self._sync()
        event.accept()

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

    def _sync(self) -> None:
        self.setCursorPosition(self.index)
        if self.index < len(self.text()):
            self.setSelection(self.index, len(self.text()) - self.index)
        self.setToolTip(scala_browser_tooltip(self.trie, self.text()))
        if (completion := self.completion()) and self.index == len(self.text()):
            self._audition(completion[1])
        else:
            self.restore_audition()

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
    return ratios.name.removesuffix('.scl') if ratios else ''


def loaded_scala_description(app: App | None) -> str:
    ratios = loaded_scala_ratios(app)
    return ratios.desc if ratios else ''


def loaded_scala_ratios(app: App | None) -> Ratios | None:
    if app is None or app.tuning.type != Type.ratios:
        return None
    return app.tuning.ratios
