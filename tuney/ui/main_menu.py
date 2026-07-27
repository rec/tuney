from __future__ import annotations

from collections.abc import Callable
from importlib.metadata import version
from typing import TYPE_CHECKING

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMenu, QMenuBar

from ..app.platform_info import instrument

if TYPE_CHECKING:
    from .main_window import MainWindow


def build_menu(window: MainWindow) -> QMenuBar:
    menu = window.menuBar()
    file_menu = menu.addMenu('File')
    edit_menu = menu.addMenu('Edit')
    view_menu = menu.addMenu('View')
    help_menu = menu.addMenu('Help')
    _add_action(edit_menu, 'Undo', UNDO_ACCELERATOR, window.history.undo)
    _add_action(edit_menu, 'Redo', REDO_ACCELERATOR, window.history.redo)
    _add_action(
        edit_menu,
        'Randomize Timing',
        RANDOMIZE_TIMING_ACCELERATOR,
        window.on_randomize_timing,
    )
    _add_action(
        edit_menu,
        'Randomize Settings',
        RANDOMIZE_SETTINGS_ACCELERATOR,
        lambda *_: window.app.randomize_settings(),
    )
    _add_action(edit_menu, 'Clear', CLEAR_ACCELERATOR, window.on_clear)
    _add_action(edit_menu, 'Clear Text', CLEAR_TEXT_ACCELERATOR, window.on_clear_text)
    window.show_text_timings_action = _add_action(
        view_menu,
        'Show Text Timings',
        SHOW_TEXT_TIMINGS_ACCELERATOR,
        window.on_show_text_timings,
    )
    window.show_text_timings_action.setCheckable(True)
    window.show_text_timings_action.setChecked(window.app.show_text_timings)
    window.dark_mode_action = _add_action(
        view_menu, 'Dark Mode', DARK_MODE_ACCELERATOR, window.on_dark_mode
    )
    window.dark_mode_action.setCheckable(True)
    window.dark_mode_action.setChecked(window.current_theme.name == 'dark')
    window.advanced_action = _add_action(
        view_menu, 'Advanced', ADVANCED_ACCELERATOR, window.on_advanced
    )
    window.advanced_action.setCheckable(True)
    window.advanced_action.setChecked(True)
    _add_action(
        file_menu,
        OPEN_TEXT_FILE_COMMAND,
        OPEN_TEXT_FILE_ACCELERATOR,
        window.on_open_text_file,
    )
    _add_action(
        file_menu, 'Save preset...', SAVE_PRESET_ACCELERATOR, window.on_save_preset
    )
    _add_action(
        file_menu,
        'Delete presets...',
        DELETE_PRESETS_ACCELERATOR,
        window.on_delete_presets,
    )
    _add_action(
        file_menu,
        IMPORT_TUNING_COMMAND,
        IMPORT_TUNING_ACCELERATOR,
        window.on_import_tuning,
    )
    window.export_tuning_action = _add_action(
        file_menu,
        EXPORT_TUNING_COMMAND,
        EXPORT_TUNING_ACCELERATOR,
        window.on_export_tuning,
    )
    file_menu.aboutToShow.connect(window._update_export_tuning_action)
    window._update_export_tuning_action()
    _add_action(file_menu, SAVE_COMMAND, SAVE_ACCELERATOR, window.on_save)
    _add_action(
        file_menu,
        SAVE_AS_AUDIO_COMMAND,
        SAVE_AS_AUDIO_ACCELERATOR,
        window.on_save_as_audio,
    )
    _add_action(
        file_menu,
        SAVE_TEST_SHEET_COMMAND,
        SAVE_TEST_SHEET_ACCELERATOR,
        window.on_save_test_sheet,
    )
    _add_action(
        file_menu,
        'Open enclosing folder for config file',
        OPEN_CONFIG_FOLDER_ACCELERATOR,
        window.on_open_config_folder,
    )
    _add_action(
        file_menu,
        'Put Config file in Trash',
        TRASH_CONFIG_FILE_ACCELERATOR,
        window.on_trash_config_file,
    )
    _add_action(
        file_menu,
        'Copy from state',
        COPY_STATE_ACCELERATOR,
        window.on_copy_from_state,
    )
    _add_action(
        file_menu,
        'Paste into state',
        PASTE_STATE_ACCELERATOR,
        window.on_paste_into_state,
    )
    window.load_autosave_action = _add_action(
        file_menu,
        'Load autosave on start',
        LOAD_AUTOSAVE_ACCELERATOR,
        window.on_load_autosave,
    )
    window.load_autosave_action.setCheckable(True)
    window.load_autosave_action.setChecked(window.app.load_autosave)
    _add_action(
        file_menu,
        'Swap with autosave',
        SWAP_AUTOSAVE_ACCELERATOR,
        window.on_swap_with_autosave,
    )
    _add_action(
        file_menu,
        'Refresh Devices',
        REFRESH_DEVICES_ACCELERATOR,
        window.on_refresh_devices,
    )
    _add_action(help_menu, 'Tuney Help', HELP_ACCELERATOR, window.on_help)
    _add_action(
        help_menu, 'Show Log Location', SHOW_LOG_ACCELERATOR, window.on_show_log
    )
    _add_action(
        help_menu,
        'Report a problem...',
        REPORT_PROBLEM_ACCELERATOR,
        window.on_report_problem,
    )
    _add_version_action(help_menu)
    return menu


CLEAR_ACCELERATOR = 'Ctrl+B'
REFRESH_DEVICES_ACCELERATOR = 'Ctrl+D'
SAVE_ACCELERATOR = 'Ctrl+S'
SAVE_AS_AUDIO_ACCELERATOR = 'Ctrl+Alt+E'
SAVE_TEST_SHEET_ACCELERATOR = 'Ctrl+Alt+Shift+E'
UNDO_ACCELERATOR = 'Ctrl+Z'
REDO_ACCELERATOR = 'Ctrl+Y'
RANDOMIZE_TIMING_ACCELERATOR = 'Ctrl+R'
RANDOMIZE_SETTINGS_ACCELERATOR = 'Ctrl+Alt+R'
CLEAR_TEXT_ACCELERATOR = 'Ctrl+Alt+B'
SHOW_TEXT_TIMINGS_ACCELERATOR = 'Ctrl+T'
ADVANCED_ACCELERATOR = 'Ctrl+Alt+A'
DARK_MODE_ACCELERATOR = 'Ctrl+Alt+D'
OPEN_TEXT_FILE_ACCELERATOR = 'Ctrl+O'
SAVE_PRESET_ACCELERATOR = 'Ctrl+P'
DELETE_PRESETS_ACCELERATOR = 'Ctrl+Alt+P'
IMPORT_TUNING_ACCELERATOR = 'Ctrl+I'
EXPORT_TUNING_ACCELERATOR = 'Ctrl+E'
OPEN_CONFIG_FOLDER_ACCELERATOR = 'Ctrl+Alt+O'
TRASH_CONFIG_FILE_ACCELERATOR = 'Ctrl+Alt+Delete'
COPY_STATE_ACCELERATOR = 'Ctrl+Alt+C'
PASTE_STATE_ACCELERATOR = 'Ctrl+Alt+V'
LOAD_AUTOSAVE_ACCELERATOR = 'Ctrl+L'
SWAP_AUTOSAVE_ACCELERATOR = 'Ctrl+Alt+S'
SHOW_LOG_ACCELERATOR = 'Ctrl+Alt+L'
REPORT_PROBLEM_ACCELERATOR = 'Ctrl+Alt+I'
HELP_ACCELERATOR = QKeySequence.StandardKey.HelpContents
OPEN_TEXT_FILE_COMMAND = 'Open Text File'
SAVE_COMMAND = 'Save'
SAVE_AS_AUDIO_COMMAND = 'Save as Audio...'
SAVE_TEST_SHEET_COMMAND = 'Save Test Sheet...'
IMPORT_TUNING_COMMAND = 'Import tuning...'
EXPORT_TUNING_COMMAND = 'Export tuning...'
SAVE_AUDIO_COMMAND = 'Save audio'


def _add_action(
    menu: QMenu,
    text: str,
    shortcut: str | QKeySequence.StandardKey | None,
    callback: Callable[..., object],
) -> QAction:
    action = QAction(text, menu)
    if isinstance(shortcut, QKeySequence.StandardKey):
        action.setShortcuts(shortcut)
    elif shortcut:
        action.setShortcut(shortcut)

    def instrumented_callback(*args: object) -> object:
        instrument('menu action', text=text)
        if action.isCheckable():
            return callback(action.isChecked())
        return callback(*args)

    action.triggered.connect(instrumented_callback)
    menu.addAction(action)
    return action


def _add_version_action(menu: QMenu) -> QAction:
    action = QAction(f'Tuney {version("tuney")}', menu)
    action.setEnabled(False)
    menu.addAction(action)
    return action
