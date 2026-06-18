import pytest

from tuney.ui.note_button import (
    FONT_SCALING_THRESHOLD,
    MAX_FONT_SIZE,
    MIN_FONT_SIZE,
    _note_font_size,
)


@pytest.mark.parametrize(
    ('width', 'height', 'expected'),
    [
        (70, 80, MAX_FONT_SIZE),
        (60, 60, MAX_FONT_SIZE),
        (48, 80, MAX_FONT_SIZE * 48 // FONT_SCALING_THRESHOLD),
        (80, 48, MAX_FONT_SIZE * 48 // FONT_SCALING_THRESHOLD),
        (20, 20, MIN_FONT_SIZE),
    ],
)
def test_note_font_size_only_scales_below_threshold(
    width: int, height: int, expected: int
) -> None:
    assert _note_font_size(width, height) == expected
