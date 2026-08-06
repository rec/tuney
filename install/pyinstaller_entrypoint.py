from __future__ import annotations

import sys
from pathlib import Path

from tuney import __main__

SOURCE_ROOT = Path(__file__).resolve().parents[1]
if not getattr(sys, 'frozen', False) and str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from tuney.app import platform_info  # noqa: E402


def app_args(argv: list[str], *, frozen: bool) -> list[str]:
    if frozen and len(argv) == 1:
        return [argv[0], '--gui']
    return argv


def main() -> None:
    frozen = bool(getattr(sys, 'frozen', False))
    if frozen:
        platform_info.start_crash_logging(show_frozen_errors=True)
    try:
        sys.argv = app_args(sys.argv, frozen=frozen)
        __main__.main()
    except Exception as error:
        if not frozen:
            raise
        platform_info.handle_frozen_exception(error)


if __name__ == '__main__':
    main()
