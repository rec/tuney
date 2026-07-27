import sys
from pathlib import Path

import tyro
from pydantic import ValidationError

from ..presets import merged_data, read_file, read_preset
from ..ui import startup
from .app import App
from .platform_info import exit_with_message


def main() -> None:
    data = {}
    try:
        app: App = tyro.cli(App, prog='tuney')
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
            app = tyro.cli(App, prog='tuney', default=App(**data))
        result = app.run()
    except (ValidationError, FileExistsError) as e:
        result = e
    if result is None:
        sys.exit()
    exit_with_message(str(result))
