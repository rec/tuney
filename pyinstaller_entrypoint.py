from __future__ import annotations

import sys

from tuney.__main__ import main as tuney_main
from tuney.audio.midi import INTERNAL_LIST_MIDI_OUTPUTS, output_names_json


def app_args(argv: list[str], *, frozen: bool) -> list[str]:
    if frozen and len(argv) == 1:
        return [argv[0], '--gui']
    return argv


def main() -> None:
    if sys.argv[1:] == [INTERNAL_LIST_MIDI_OUTPUTS]:
        print(output_names_json())
        return
    sys.argv = app_args(sys.argv, frozen=bool(getattr(sys, 'frozen', False)))
    tuney_main()


if __name__ == '__main__':
    main()
