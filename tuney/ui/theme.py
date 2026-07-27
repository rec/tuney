from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication, QWidget


class ThemeName(StrEnum):
    light = auto()
    dark = auto()


@dataclass(frozen=True)
class Theme:
    name: ThemeName
    window: str
    base: str
    alternate_base: str
    button: str
    text: str
    disabled_text: str
    border: str
    section: str
    section_title: str
    note_pressed_background: str
    note_pressed_text: str
    note_released_background: str
    note_released_text: str
    transport_hover: str
    transport_icon: str
    transport_disabled_icon: str
    transport_record_icon: str
    replay_active: str
    replay_idle: str
    tooltip_background: str
    tooltip_text: str
    tooltip_border: str
    scala_faded_text: str
    validation_error: str


LIGHT_THEME = Theme(
    name=ThemeName.light,
    window='#f0f0f0',
    base='#f0f0f0',
    alternate_base='#f0f0f0',
    button='#f0f0f0',
    text='#000000',
    disabled_text='#909090',
    border='#c8c8c8',
    section='#f7f7f7',
    section_title='#303030',
    note_pressed_background='#90ee90',
    note_pressed_text='#000000',
    note_released_background='#e5e5e5',
    note_released_text='#000000',
    transport_hover='#d8d8d8',
    transport_icon='#101010',
    transport_disabled_icon='#a0a0a0',
    transport_record_icon='#d02020',
    replay_active='#b0a8b0',
    replay_idle='#30a870',
    tooltip_background='#ffffe0',
    tooltip_text='#000000',
    tooltip_border='#000000',
    scala_faded_text='#909090',
    validation_error='#ff0000',
)
DARK_THEME = Theme(
    name=ThemeName.dark,
    window='#202124',
    base='#25272b',
    alternate_base='#2d3035',
    button='#30343a',
    text='#f1f3f4',
    disabled_text='#9aa0a6',
    border='#5f6368',
    section='#2b2f35',
    section_title='#f1f3f4',
    note_pressed_background='#60d394',
    note_pressed_text='#07130d',
    note_released_background='#3a3f46',
    note_released_text='#f1f3f4',
    transport_hover='#3c424a',
    transport_icon='#f1f3f4',
    transport_disabled_icon='#777d86',
    transport_record_icon='#ff6b6b',
    replay_active='#6f6678',
    replay_idle='#2f9d71',
    tooltip_background='#ffffe0',
    tooltip_text='#000000',
    tooltip_border='#000000',
    scala_faded_text='#9aa0a6',
    validation_error='#ff8a80',
)


def theme_for_name(name: ThemeName | str) -> Theme:
    try:
        theme_name = ThemeName(name)
    except ValueError:
        theme_name = ThemeName.light
    return DARK_THEME if theme_name == ThemeName.dark else LIGHT_THEME


def set_app_theme(app: QApplication, theme: Theme) -> None:
    from PySide6.QtGui import QColor, QPalette

    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(theme.window))
    palette.setColor(QPalette.ColorRole.Base, QColor(theme.base))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(theme.alternate_base))
    palette.setColor(QPalette.ColorRole.Button, QColor(theme.button))
    palette.setColor(QPalette.ColorRole.Text, QColor(theme.text))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(theme.text))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(theme.text))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(theme.tooltip_background))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(theme.tooltip_text))
    app.setPalette(palette)


def widget_theme(widget: QWidget) -> Theme:
    window = widget.window()
    theme = getattr(window, 'current_theme', None)
    if isinstance(theme, Theme):
        return theme
    return LIGHT_THEME


def note_button_style(theme: Theme, pressed: bool) -> str:
    if pressed:
        background = theme.note_pressed_background
        color = theme.note_pressed_text
    else:
        background = theme.note_released_background
        color = theme.note_released_text
    return (
        f'background: {background}; color: {color}; border-radius: 8px; padding: 0px;'
    )


def control_section_style(theme: Theme) -> str:
    return f"""
QFrame#control_section {{
    background: {theme.section};
    border: 1px solid {theme.border};
    border-radius: 4px;
}}
QToolButton#control_section_disclosure {{
    border: none;
    color: {theme.section_title};
    font-weight: 600;
    padding: 2px;
    text-align: left;
}}
"""


def transport_hover_style(theme: Theme) -> str:
    return f'QPushButton:hover {{ background: {theme.transport_hover}; }}'


def replay_style(theme: Theme, is_replaying: bool) -> str:
    background = theme.replay_active if is_replaying else theme.replay_idle
    return f'background: {background}; color: {theme.text};'


def tooltip_style(theme: Theme) -> str:
    return (
        f'background: {theme.tooltip_background}; color: {theme.tooltip_text};'
        f' border: 1px solid {theme.tooltip_border}; padding: 4px 6px;'
    )


def scala_tooltip_style(theme: Theme) -> str:
    return (
        'QLabel {'
        f'background-color: {theme.tooltip_background};'
        f'border: 1px solid {theme.tooltip_border};'
        f'color: {theme.tooltip_text};'
        'padding: 2px;'
        '}'
    )


def scala_completion_style(theme: Theme, faded: bool = False) -> str:
    color = f'color: {theme.scala_faded_text};' if faded else ''
    return (
        'QLineEdit {'
        f'{color}'
        f'selection-color: {theme.scala_faded_text};'
        'selection-background-color: transparent;'
        '}'
    )


def invalid_scale_widget_style(theme: Theme) -> str:
    return f'color: {theme.validation_error};'
