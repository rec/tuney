from __future__ import annotations

import json
import random
import string
import tomllib
from pathlib import Path

import tomlkit

from ..audio.player import Player
from ..config.serialize import serialize
from ..config.text_file import read_text_file
from ..presets.preset import is_str_dict, merged_data, read_preset
from ..scale.accidentals import Accidentals
from ..scale.tuning import Computed, Type
from .app_members import AppMembers
from .platform_info import instrument


class AppState(AppMembers):
    def clear(self) -> None:
        instrument('clear')
        main_window = self.__dict__.get('main_window')
        if main_window is None and self.gui:
            main_window = self.main_window
        data = type(self)(gui=self.gui).dump_data()
        if main_window is not None and self.dump_data() != data:
            main_window.history.checkpoint_undo()
        self.restore_data(data)
        self.key_recorder.clear()
        if main_window is not None:
            main_window.ui.rebuild_control_panel()
            main_window.ui.rebuild_note_grid()
            main_window.sync_config_actions()
            main_window.update_text_display()

    def randomize_timing(self) -> None:
        instrument('randomize timing')
        if not (text := self.display_text):
            return
        if self.gui:
            self.main_window.history.checkpoint_undo()
        self.__dict__['char_presses'] = list(self.text_timings.char_presses(text))
        self.key_recorder.clear()
        if self.gui:
            self.main_window.update_text_display()

    def randomize_settings(self, rng: random.Random | None = None) -> None:
        instrument('randomize settings')
        rng = rng or random.Random()
        if self.gui:
            self.main_window.history.checkpoint_undo()
        intervals, notes = rng.choice(SCALE_CHOICES)
        self.scale = type(self.scale).model_validate(
            self.scale.model_dump()
            | {
                'note_names': string.ascii_uppercase,
                'root': rng.choice('ABCDEFG'),
                'begin': 'A',
                'end': 'G',
                'notes': notes,
                'intervals': intervals,
                'accidentals': rng.choice(list(Accidentals)),
                'offset': rng.randint(-12, 12),
            }
        )
        self.tuning = type(self.tuning).model_validate(
            self.tuning.model_dump()
            | {
                'type': Type.computed,
                'computed': Computed(
                    limit=rng.choice([0, 0, 0, 3, 5, 7, 11]),
                    notes_per_octave=sum(intervals),
                    octave_ratio=rng.choice([1.5, 2.0, 2.0, 2.0, 3.0]),
                ),
                'detune': rng.uniform(-50, 50),
                'root_frequency': rng.uniform(220, 660),
                'root_note': rng.randint(48, 72),
            }
        )
        if isinstance(player := self.__dict__.get('player'), Player):
            player.close()
        self.clear_cached_values()
        if self.gui:
            self.main_window.ui.rebuild_control_panel()
            self.main_window.ui.rebuild_note_grid()
            self.send_midi_tuning_dump()

    def load_text_file(self, path: Path) -> None:
        instrument('load text file', path=path)
        text = read_text_file(path)
        if self.gui:
            self.main_window.history.checkpoint_undo()
        self.__dict__['char_presses'] = list(self.text_timings.char_presses(text))
        self.key_recorder.clear()
        if self.gui:
            self.main_window.update_text_display()

    def save(self, path: Path) -> None:
        match path.suffix:
            case '.toml':
                text = self.dump_toml()
            case '.json':
                text = json.dumps(serialize(self.dump_data()), indent=2) + '\n'
            case _:
                raise ValueError(f'Do not understand file {path}')
        path.write_text(text)

    def save_autosave(self, path: Path) -> None:
        data = serialize(self.dump_data())
        if main_window := self.__dict__.get('main_window'):
            from ..ui.history import WindowState

            geometry = main_window.geometry()
            instrument('autosave window geometry', **main_window.geometry_log_data())
            data['loop'] = main_window.history.loop_state.model_dump()
            data['window'] = WindowState(
                x=geometry.x(),
                y=geometry.y(),
                width=geometry.width(),
                height=geometry.height(),
            ).model_dump()
        path.write_text(tomlkit.dumps(data))

    def dump_toml(self) -> str:
        return tomlkit.dumps(serialize(self.dump_data()))

    def restore_text(self, text: str) -> None:
        self.restore_data(_read_state_text(text))

    def apply_preset(self, name: str) -> None:
        instrument('apply preset', name=name)
        char_presses = self.__dict__.get('char_presses')
        data = merged_data(self.model_dump(), read_preset(name), {'preset': name})
        validated = type(self).model_validate(data)
        if isinstance(player := self.__dict__.get('player'), Player):
            player.close()
        for field in type(self).model_fields:
            setattr(self, field, getattr(validated, field))
        self.clear_cached_values()
        if char_presses is not None:
            self.__dict__['char_presses'] = char_presses
        self.send_midi_tuning_dump()

    def restore_data(self, data: dict[str, object]) -> None:
        instrument('restore data start', keys=sorted(data))
        validated = type(self).model_validate(data)
        if isinstance(player := self.__dict__.get('player'), Player):
            player.close()
        for field in type(self).model_fields:
            setattr(self, field, getattr(validated, field))
        self.clear_cached_values()
        self.send_midi_tuning_dump()
        instrument('restore data end')

    def dump_data(self) -> dict[str, object]:
        data = self.model_dump()
        mapper = data.pop('mapper')
        data = {'mapper': mapper, **data}
        if self.char_presses:
            data['text'] = [c.model_dump() for c in self.char_presses]
        return data

    def send_midi_tuning_dump(self) -> None:
        if self.gui and 'main_window' in self.__dict__:
            self.midi.output.send_tuning_dump(self.scale, self.tuning)

    def clear_cached_values(self) -> None:
        keep = {
            'main_window',
            'keyboard_listener',
            'key_recorder',
            'audio_recorder',
        }
        for key in tuple(self.__dict__):
            if key not in keep and key not in type(self).model_fields:
                self.__dict__.pop(key, None)


def _read_state_text(text: str) -> dict[str, object]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as toml_error:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as json_error:
            raise ValueError(
                f'Clipboard does not contain TOML or JSON: {json_error}'
            ) from toml_error
    if not is_str_dict(data):
        raise ValueError('Clipboard does not contain a string dictionary')
    return data


SCALE_CHOICES = [
    ([1] * 12, None),
    ([2, 2, 1, 2, 2, 2, 1], None),
    ([2, 2, 1, 2, 2, 2, 1], 'CDEFGAB'),
    ([2, 2, 3, 2, 3], None),
    ([2, 2, 3, 2, 3], 'CDFGA'),
    ([2, 2, 2, 2, 2, 2], None),
    ([3, 2, 2, 3, 2], None),
]
