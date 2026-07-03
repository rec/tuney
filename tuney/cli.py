import sys
from pathlib import Path

import tyro
from pydantic import ValidationError

from .audio.player import Player
from .platform_info import exit_with_message
from .presets import merged_data, read_file, read_preset
from .tuney_state import TuneyState


def cli(cls, prog: str):
    data = {}
    try:
        f = tyro.cli(cls, prog=prog)
        assert hasattr(f, 'config_file')
        assert hasattr(f, 'preset')
        if f.config_file or f.preset:
            if f.preset:
                data = merged_data(data, read_preset(f.preset), {'preset': f.preset})
            if f.config_file:
                assert isinstance(f.config_file, Path)
                data = merged_data(data, read_file(f.config_file))
            default = cls(**data)
            f = tyro.cli(cls, prog=prog, default=default)
        state = TuneyState(f)
        if isinstance(player_data := data.get('player'), dict):
            player_data = {str(key): value for key, value in player_data.items()}
            state.__dict__['player'] = Player.model_validate(
                {**player_data, 'tuning': f.tuning}
            )
        result = state()
    except (ValidationError, FileExistsError) as e:
        if getattr(locals().get('f'), 'verbose', False):
            raise
        result = e
    if result is None:
        sys.exit()
    exit_with_message(str(result))
