import subprocess
import sys

# We need to run Qt tests in a new process, because you can't really
# bring Qt up and down without side-effects.
# See _test_app_keys.py for the bodies of the functions.


def test_app_keys() -> None:
    _run_app_key_scripts(
        'test_qt_key_events',
        'test_macos_option_composed_characters',
        'test_macos_option_special_keys_remain_ignored',
        'test_non_macos_alt_characters_remain_ignored',
        'test_app_event_filter',
        'test_application_uses_cross_platform_style',
        'test_app_mainloop_exits_on_sigint',
        'test_loop_state_restoration_does_not_retoggle_checkboxes',
        'test_app_activate_and_history',
        'test_app_reports_problem',
        'test_app_imports_and_exports_tuning',
        'test_file_dialogs_remember_last_directories',
        'test_app_saves_audio_from_current_text',
        'test_app_cancels_test_sheet_without_preset_selection',
        'test_app_saves_test_sheet_from_current_text',
        'test_app_saves_and_deletes_presets',
        'test_close_releases_audio_before_closing_player',
    )


def _run_app_key_scripts(*names: str) -> None:
    command = f'from test import _test_app_keys; _test_app_keys.run({list(names)!r})'
    cmd = sys.executable, '-c', command
    subprocess.run(cmd, check=True, capture_output=True, text=True)
