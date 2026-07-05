from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

STARTUP_FILE_SKIP_MODIFIERS = (
    Qt.KeyboardModifier.ShiftModifier
    | Qt.KeyboardModifier.ControlModifier
    | Qt.KeyboardModifier.AltModifier
    | Qt.KeyboardModifier.MetaModifier
)


def startup_modifier_held() -> bool:
    _ = QApplication.instance() or QApplication([])
    return bool(QApplication.keyboardModifiers() & STARTUP_FILE_SKIP_MODIFIERS)
