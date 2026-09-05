import sys
from pathlib import Path
from typing import Annotated

import tyro
from pydantic import ValidationError
from reccy.runtime import logging

from ..midi.ports import midi_names_json
from ..presets.preset import merged_data, read_file, read_preset
from ..ui import startup
from . import platform_info
from .app import App

CLI_DESCRIPTION = (
    'Turn text into music. Use positional `TEXT` to play characters as notes, then '
    'tune the scale, audio, MIDI, and timing from the same config model.'
)
LOGGER = logging.get_logger(__name__)


def main() -> None:
    platform_info.configure_logging()
    LOGGER.info('Tuney starting')
    data = {}
    try:
        list_midi, app = parse_cli()
        if list_midi:
            print(midi_names_json())
            sys.exit()
        startup.set_gui(app.gui)

        if startup.startup_modifier_held():
            update = {'config_file': None, 'preset': None}
            app = app.model_copy(update=update)
        elif app.config_file or app.preset:
            if app.preset:
                data = merged_data(
                    data, read_preset(app.preset), {'preset': app.preset}
                )
            if app.config_file:
                assert isinstance(app.config_file, Path)
                data = merged_data(data, read_file(app.config_file))
            list_midi, app = parse_cli(App(**data))
            if list_midi:
                print(midi_names_json())
                sys.exit()
        result = app.run()
    except (ValidationError, FileExistsError) as e:
        result = e
    if result is None:
        sys.exit()
    platform_info.exit_with_message(str(result))


def parse_cli(default: App | None = None) -> tuple[bool, App]:
    default = default or App()

    def cli(
        list_midi: Annotated[
            tyro.conf.FlagCreatePairsOff[bool],
            tyro.conf.arg(help='List MIDI input and output ports as JSON.'),
        ] = False,
        app: Annotated[App, tyro.conf.arg(name='')] = default,
    ) -> tuple[bool, App]:
        return list_midi, app

    return tyro.cli(cli, prog='tuney', description=CLI_DESCRIPTION)
