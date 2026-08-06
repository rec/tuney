import os

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication

from tuney.ui import note_button
from tuney.ui.theme import DARK_THEME, LIGHT_THEME

_ = QApplication.instance() or QApplication([])


@pytest.mark.parametrize(
    ('width', 'height', 'text', 'expected'),
    [
        (70, 80, 'C\n a', note_button.MAX_FONT_SIZE),
        (1, 1, 'C\n a', note_button.MIN_FONT_SIZE),
    ],
)
def test_note_font_size_uses_extremes(
    width: int, height: int, text: str, expected: int
) -> None:
    assert note_button._note_font_size(width, height, text) == expected


def test_note_font_size_scales_down_for_small_buttons() -> None:
    font_size = note_button._note_font_size(20, 20, 'C\n a')

    assert note_button.MIN_FONT_SIZE < font_size < note_button.MAX_FONT_SIZE


def test_note_font_size_accounts_for_text_width() -> None:
    assert (
        note_button._note_font_size(70, 80, 'Very long note\n a')
        < note_button.MAX_FONT_SIZE
    )


def test_note_button_minimum_size_allows_small_buttons() -> None:
    assert note_button.MIN_BUTTON_WIDTH == 8
    assert note_button.MIN_BUTTON_HEIGHT == 30


def test_note_button_theme_refresh_preserves_pressed_state() -> None:
    from PySide6.QtWidgets import QGridLayout, QWidget

    parent = QWidget()
    parent.current_theme = LIGHT_THEME
    layout = QGridLayout(parent)
    button = note_button.NoteButton(
        layout, 0, 0, 'a', 'A', 'tooltip', lambda: 0.0, lambda _: None
    )
    button.is_press = True
    light_style = button.styleSheet()

    parent.current_theme = DARK_THEME
    button.refresh_theme()

    assert button.is_press
    assert button.styleSheet() != light_style
    assert DARK_THEME.note_pressed_background in button.styleSheet()
