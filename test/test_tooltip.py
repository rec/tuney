from __future__ import annotations

import os
from enum import StrEnum, auto

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from pydantic import BaseModel

from tuney.config.tuney import Tuney
from tuney.mapper.mapper import Mapper
from tuney.scale.scale import Scale
from tuney.scale.tuning import Tuning
from tuney.ui import control_panel, control_panel_visibility
from tuney.ui.layout import REPLAY_TOOLTIPS
from tuney.ui.tooltip import Tooltip
from tuney.ui.transport import TOOLTIPS


class TooltipEnum(StrEnum):
    # Alpha tooltip text
    # with preserved line break
    alpha = auto()
    beta = auto()


class _Widget:
    def __init__(self, *children: _Widget) -> None:
        self.children = list(children)

    def winfo_children(self) -> list[_Widget]:
        return self.children


def test_field_help_uses_tyro_help_text() -> None:
    assert control_panel._field_help(Tuney, 'max_gap') == (
        'Maximum silent gap to keep in recordings, in seconds'
    )
    assert control_panel._field_help(Scale, 'note_names') == 'The base note names'


def test_field_name_is_used_when_help_is_missing() -> None:
    assert control_panel._field_hover_text(Mapper, 'map') == 'map'


def test_enum_hover_text_uses_member_comment_or_name() -> None:
    assert control_panel._enum_hover_text(TooltipEnum.alpha) == (
        'Alpha tooltip text\nwith preserved line break'
    )
    assert control_panel._enum_hover_text(TooltipEnum.beta) == 'beta'


def test_enum_radio_buttons_have_member_tooltips() -> None:
    from PySide6.QtWidgets import QApplication, QRadioButton, QWidget

    _ = QApplication.instance() or QApplication([])
    parent = QWidget()
    panel = control_panel.ControlPanel(parent, Tuning())
    radios = panel.findChildren(QRadioButton)

    assert {
        radio.text(): [
            tooltip.text for tooltip in radio.children() if isinstance(tooltip, Tooltip)
        ]
        for radio in radios
        if radio.text() in {'computed', 'table', 'ratios'}
    } == {
        'computed': ['computed'],
        'table': ['table'],
        'ratios': ['ratios'],
    }


def test_hover_text_rewraps_lines_and_preserves_paragraphs() -> None:
    assert control_panel._rewrap_hover_text(
        'first line\nsecond line\n\nnext paragraph'
    ) == ('first line second line\n\nnext paragraph')
    assert control_panel._field_hover_text(Scale, 'notes').count('\n') == 2


def test_tooltips_bind_only_to_leaf_widgets() -> None:
    first, second = _Widget(), _Widget()
    root = _Widget(_Widget(first), second)

    assert control_panel._field_widgets(root) == [first, second]


def test_field_widgets_walks_qt_leaf_widgets() -> None:
    from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

    _ = QApplication.instance() or QApplication([])
    first, second = QWidget(), QWidget()
    root = QWidget()
    middle = QWidget(root)
    layout = QVBoxLayout(root)
    middle_layout = QVBoxLayout(middle)
    middle_layout.addWidget(first)
    layout.addWidget(middle)
    layout.addWidget(second)

    assert control_panel._field_widgets(root) == [first, second]


def test_all_visible_fields_have_hover_text() -> None:
    root = Tuney()
    controls = list(control_panel._general_controls(root))

    def walk(data: BaseModel) -> None:
        controls.extend(
            (data, name)
            for name in control_panel_visibility._visible_control_names(data)
        )
        for name in control_panel_visibility._visible_child_names(data):
            walk(getattr(data, name))

    walk(root)

    assert [
        f'{type(data).__name__}.{name}'
        for data, name in controls
        if control_panel._field_help(type(data), name) is None
    ] == []


def test_transport_button_tooltips_cover_all_buttons() -> None:
    assert TOOLTIPS == {
        'record': 'Record',
        'stop': 'Stop',
        'save': 'Save',
        'clear': 'Clear',
    }


def test_replay_bar_tooltips_cover_all_widgets() -> None:
    assert REPLAY_TOOLTIPS == {
        'replay': 'Play recorded text, or stop playback',
        'randomize': 'Randomize time for the recorded text',
        'loop': 'Repeat replay until stopped',
        'loop_clock': 'Elapsed time in the current replay loop',
        'master_gain': 'Playback volume',
        'help': 'Help',
    }
