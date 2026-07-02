from __future__ import annotations

import sys


def app_args(argv: list[str], *, frozen: bool) -> list[str]:
    if frozen and len(argv) == 1:
        return [argv[0], '--gui']
    return argv


def main() -> None:
    frozen = bool(getattr(sys, 'frozen', False))
    if frozen:
        from tuney.app_state import install_frozen_excepthook

        install_frozen_excepthook()
    try:
        from tuney.__main__ import main as tuney_main
        from tuney.audio.midi import INTERNAL_LIST_MIDI_OUTPUTS, output_names_json

        if sys.argv[1:] == [INTERNAL_LIST_MIDI_OUTPUTS]:
            print(output_names_json())
            return
        sys.argv = app_args(sys.argv, frozen=frozen)
        tuney_main()
    except Exception as error:
        if not frozen:
            raise
        from tuney.app_state import handle_frozen_exception

        handle_frozen_exception(error)


if __name__ == '__main__':
    main()
