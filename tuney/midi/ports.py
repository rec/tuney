from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from functools import cache

import mido

from ..app.platform_info import report_error

LIST_MIDI = '--list-midi'
MIDO_NAMES_SCRIPT = (
    'import json, mido; '
    'print(json.dumps([mido.get_input_names(), mido.get_output_names()], indent=2))'
)


@cache
def midi_names() -> list[list[str]]:
    args = (
        [sys.executable, LIST_MIDI]
        if getattr(sys, 'frozen', False)
        else [sys.executable, '-c', MIDO_NAMES_SCRIPT]
    )
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            check=True,
            text=True,
            timeout=5,
        )
        names = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        report_error(f'Could not list MIDI ports: {error}')
        return [[], []]
    if not (
        isinstance(names, list)
        and len(names) == 2
        and all(isinstance(n, list) for n in names)
    ):
        report_error(
            f'Could not list MIDI ports: expected two lists, got {type(names).__name__}'
        )
        return [[], []]
    return [
        [name for name in names[0] if isinstance(name, str)],
        [name for name in names[1] if isinstance(name, str)],
    ]


def midi_names_json() -> str:
    return json.dumps(_direct_midi_names(), indent=2)


def _direct_midi_names() -> list[list[str]]:
    return [
        _direct_port_names(mido.get_input_names, 'inputs'),
        _direct_port_names(mido.get_output_names, 'outputs'),
    ]


def _direct_port_names(names: Callable[[], list[str]], kind: str) -> list[str]:
    try:
        result = names()
    except (OSError, RuntimeError) as error:
        report_error(f'Could not list MIDI {kind}: {error}')
        result = []
    return [name for name in result if isinstance(name, str)]
