from __future__ import annotations

import sys

from tuney.__main__ import main as tuney_main


def app_args(argv: list[str], *, frozen: bool) -> list[str]:
    if frozen and len(argv) == 1:
        return [argv[0], '--gui']
    return argv


def main() -> None:
    sys.argv = app_args(sys.argv, frozen=bool(getattr(sys, 'frozen', False)))
    tuney_main()


if __name__ == '__main__':
    main()
