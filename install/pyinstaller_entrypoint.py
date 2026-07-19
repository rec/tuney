from __future__ import annotations

import sys
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1]
if not getattr(sys, 'frozen', False) and str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from tuney.__main__ import main as tuney_main  # noqa: E402
from tuney.app.platform_info import (  # noqa: E402
    handle_frozen_exception,
    install_frozen_excepthook,
)
from tuney.audio.midi import (  # noqa: E402
    INTERNAL_LIST_MIDI_INPUTS,
    INTERNAL_LIST_MIDI_OUTPUTS,
    input_names_json,
    output_names_json,
)


def app_args(argv: list[str], *, frozen: bool) -> list[str]:
    if frozen and len(argv) == 1:
        return [argv[0], '--gui']
    return argv


def main() -> None:
    frozen = bool(getattr(sys, 'frozen', False))
    if frozen:
        install_frozen_excepthook()
    try:
        if sys.argv[1:] == [INTERNAL_LIST_MIDI_INPUTS]:
            print(input_names_json())
            return
        if sys.argv[1:] == [INTERNAL_LIST_MIDI_OUTPUTS]:
            print(output_names_json())
            return
        sys.argv = app_args(sys.argv, frozen=frozen)
        tuney_main()
    except Exception as error:
        if not frozen:
            raise
        handle_frozen_exception(error)


if __name__ == '__main__':
    main()
