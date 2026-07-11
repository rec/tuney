from __future__ import annotations

from pathlib import Path


def startup_modifier_held() -> bool:
    return _MODIFIER_HELD


def set_gui(gui: bool) -> None:
    if not gui:
        return

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    global _MODIFIER_HELD

    _ = QApplication.instance() or QApplication([])
    _MODIFIER_HELD = bool(
        (
            Qt.KeyboardModifier.ShiftModifier
            | Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.MetaModifier
        )
        & QApplication.queryKeyboardModifiers()
    )


autosave_file: Path | None = None
_MODIFIER_HELD = False
# The reason for this single, evil global is that we don't want to even try to
# load anything to do with PySide6 if --gui is false: on a headless system
# this might crash Python.
