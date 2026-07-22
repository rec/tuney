from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from functools import cache

import mido

from ..app.platform_info import report_error

INTERNAL_LIST_MIDI_INPUTS = '--internal-list-midi-inputs'
INTERNAL_LIST_MIDI_OUTPUTS = '--internal-list-midi-outputs'
MIDO_INPUT_NAMES_SCRIPT = 'import json, mido; print(json.dumps(mido.get_input_names()))'
MIDO_OUTPUT_NAMES_SCRIPT = (
    'import json, mido; print(json.dumps(mido.get_output_names()))'
)


@cache
def input_names() -> list[str]:
    return _port_names(INTERNAL_LIST_MIDI_INPUTS, MIDO_INPUT_NAMES_SCRIPT, 'inputs')


@cache
def output_names() -> list[str]:
    return _port_names(INTERNAL_LIST_MIDI_OUTPUTS, MIDO_OUTPUT_NAMES_SCRIPT, 'outputs')


def output_names_json() -> str:
    return _direct_port_names(mido.get_output_names, 'outputs')


def input_names_json() -> str:
    return _direct_port_names(mido.get_input_names, 'inputs')


def _port_names(internal_command: str, script: str, kind: str) -> list[str]:
    args = (
        [sys.executable, internal_command]
        if getattr(sys, 'frozen', False)
        else [sys.executable, '-c', script]
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
        report_error(f'Could not list MIDI {kind}: {error}')
        return []
    if not isinstance(names, list):
        report_error(
            f'Could not list MIDI {kind}: expected list, got {type(names).__name__}'
        )
        return []
    return [name for name in names if isinstance(name, str)]


def _direct_port_names(names: Callable[[], list[str]], kind: str) -> str:
    try:
        result = names()
    except (OSError, RuntimeError) as error:
        report_error(f'Could not list MIDI {kind}: {error}')
        result = []
    return json.dumps([name for name in result if isinstance(name, str)])
