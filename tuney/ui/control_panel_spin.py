from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QSpinBox, QWidget

from ..config.annotations import Numeric


class _NumericDoubleSpinBox(QDoubleSpinBox):
    def __init__(self, parent: QWidget, numeric: Numeric) -> None:
        super().__init__(parent)
        self.numeric = numeric

    def stepBy(self, steps: int) -> None:
        modified_steps = _modified_steps(steps)
        if not self.numeric.log:
            self.setValue(self.numeric.step(self.value(), modified_steps))
            return
        value = self.value()
        if value <= 0:
            assert self.numeric.min is not None
            value = self.numeric.min
        self.setValue(self.numeric.step(value, modified_steps))


class _NumericSpinBox(QSpinBox):
    def stepBy(self, steps: int) -> None:
        self.setValue(round(self.value() + self.singleStep() * _modified_steps(steps)))


def _modified_steps(steps: int) -> float:
    modifiers = QApplication.keyboardModifiers()
    if modifiers & Qt.KeyboardModifier.AltModifier:
        return steps / 10
    if modifiers & Qt.KeyboardModifier.ShiftModifier:
        return steps * 10
    return steps
