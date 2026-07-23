from __future__ import annotations

from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from ..config.annotations import Display, Numeric
from .control_panel_metadata import _annotation_types

ENTRY_CHAR_WIDTH = 10
EDITOR_HORIZONTAL_PADDING = 8
SPIN_BUTTON_WIDTH = 34
LABEL_PADDING = 8
MIN_EDITOR_WIDTH = 72
MIN_TEXT_EDITOR_WIDTH = 160


def _display_label(name: str) -> str:
    if name.isupper():
        return name
    return name.replace('_', ' ').capitalize()


def _configure_label(label: QLabel) -> None:
    label.setObjectName('control_label')
    width = label.fontMetrics().horizontalAdvance(label.text()) + LABEL_PADDING
    label.setMinimumWidth(width)
    label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)


def _configure_editor(widget: QWidget, width: int | None = None) -> None:
    widget.setObjectName('control_editor')
    if width:
        widget.setFixedWidth(width)
        widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    else:
        widget.setMinimumWidth(max(MIN_TEXT_EDITOR_WIDTH, MIN_EDITOR_WIDTH))
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


def _configure_flexible_editor(widget: QWidget, width: int | None = None) -> None:
    widget.setObjectName('control_editor')
    widget.setMinimumWidth(MIN_EDITOR_WIDTH)
    if width is not None:
        widget.setMaximumWidth(width)
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


def _entry_width(
    name: str,
    annotation: object,
    display: Display | None = None,
    numeric: Numeric | None = None,
) -> int | None:
    display = display or Display()
    numeric = numeric or Numeric()
    if width := numeric.width:
        return width * ENTRY_CHAR_WIDTH + EDITOR_HORIZONTAL_PADDING
    if width := display.width:
        return width * ENTRY_CHAR_WIDTH + EDITOR_HORIZONTAL_PADDING

    types = _annotation_types(annotation)
    if str in types:
        return None
    if int in types and float not in types and bool not in types:
        return 4 * ENTRY_CHAR_WIDTH
    if float in types:
        return (4 if numeric.inc == 0.01 else 6) * ENTRY_CHAR_WIDTH
    return None
