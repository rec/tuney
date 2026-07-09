from PySide6.QtCore import Qt
from pytest import MonkeyPatch

from tuney.ui import startup


def test_startup_modifier_detects_shift(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        startup.QApplication,
        'queryKeyboardModifiers',
        lambda: Qt.KeyboardModifier.ShiftModifier,
    )

    assert startup.startup_modifier_held()


def test_startup_modifier_ignores_no_modifier(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        startup.QApplication,
        'queryKeyboardModifiers',
        lambda: Qt.KeyboardModifier.NoModifier,
    )

    assert not startup.startup_modifier_held()
