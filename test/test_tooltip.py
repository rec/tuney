from __future__ import annotations

from tkinter import Misc
from typing import cast

from pydantic import BaseModel

from tuney.mapper.mapper import Mapper
from tuney.scale.scale import Scale
from tuney.tuney import Tuney
from tuney.ui.control_panel import (
    _field_help,
    _field_hover_text,
    _field_widgets,
    _general_controls,
    _rewrap_hover_text,
    _visible_child_names,
    _visible_control_names,
)
from tuney.ui.transport import TOOLTIPS


class _Widget:
    def __init__(self, *children: _Widget) -> None:
        self.children = list(children)

    def winfo_children(self) -> list[_Widget]:
        return self.children


def test_field_help_uses_tyro_help_text() -> None:
    assert _field_help(Tuney, 'max_gap') == (
        'Maximum silent gap to keep in recordings, in seconds'
    )
    assert _field_help(Scale, 'alphabet') == 'The base alphabet'


def test_field_name_is_used_when_help_is_missing() -> None:
    assert _field_hover_text(Mapper, 'map') == 'map'


def test_hover_text_rewraps_lines_and_preserves_paragraphs() -> None:
    assert _rewrap_hover_text('first line\nsecond line\n\nnext paragraph') == (
        'first line second line\n\nnext paragraph'
    )
    assert _field_hover_text(Scale, 'notes').count('\n') == 2


def test_tooltips_bind_only_to_leaf_widgets() -> None:
    first, second = _Widget(), _Widget()
    root = _Widget(_Widget(first), second)

    assert _field_widgets(cast(Misc, root)) == [first, second]


def test_all_visible_fields_have_hover_text() -> None:
    root = Tuney()
    controls = list(_general_controls(root))

    def walk(data: BaseModel) -> None:
        controls.extend((data, name) for name in _visible_control_names(data))
        for name in _visible_child_names(data):
            walk(getattr(data, name))

    walk(root)

    assert [
        f'{type(data).__name__}.{name}'
        for data, name in controls
        if _field_help(type(data), name) is None
    ] == []


def test_transport_button_tooltips_cover_all_buttons() -> None:
    assert TOOLTIPS == {
        'record': 'Record',
        'stop': 'Stop',
        'save': 'Save',
        'clear': 'Clear',
    }
