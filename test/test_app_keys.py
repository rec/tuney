import subprocess
import sys
from collections.abc import Callable

# We need to run Qt tests in a new process, because you can't really
# bring Qt up and down without side-effects.
# See _test_app_keys.py for the bodies of the functions.


def _in_subprocess(f: Callable[[], None]) -> Callable[[], None]:
    def run() -> None:
        command = f'from test import _test_app_keys; _test_app_keys.{f.__name__}()'
        cmd = sys.executable, '-c', command
        subprocess.run(cmd, check=True, capture_output=True, text=True)

    return run


@_in_subprocess
def test_qt_key_events() -> None:
    pass


@_in_subprocess
def test_macos_option_composed_characters() -> None:
    pass


@_in_subprocess
def test_macos_option_special_keys_remain_ignored() -> None:
    pass


@_in_subprocess
def test_non_macos_alt_characters_remain_ignored() -> None:
    pass


@_in_subprocess
def test_app_event_filter() -> None:
    pass


@_in_subprocess
def test_app_mainloop_exits_on_sigint() -> None:
    pass


@_in_subprocess
def test_application_uses_cross_platform_style() -> None:
    pass


@_in_subprocess
def test_app_activate_and_history() -> None:
    pass


@_in_subprocess
def test_app_imports_and_exports_tuning() -> None:
    pass
