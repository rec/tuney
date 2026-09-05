import pytest
import tyro
from pydantic import ValidationError

from tuney.app.app import App
from tuney.app.text_timing import edit_text_timing
from tuney.audio.device import Device
from tuney.audio.sound import Binaural, Sound
from tuney.audio.speech import SpeechPhrase
from tuney.audio.voice import Voice
from tuney.scale.table import Table
from tuney.scale.tuning import Tuning
from tuney.time.char_press import CharPress
from tuney.time.text_timings import TextTimings
from tuney.ui.history import LoopState


def test_models_normalize_unit_values() -> None:
    app = App(
        max_gap='2 min',
        hover_time='250ms',
        backspace_repeat_delay='1:30',
        device=Device(sample_rate='48kHz'),
        sound=Sound(minimum_note_time='250ms', binaural=Binaural(frequency='0.01kHz')),
        tuning=Tuning(detune='12 cents', root_frequency='0.44kHz'),
        text_timings=TextTimings(space='0.1s', other={'!': '2s'}, timings=['250ms']),
        text=[CharPress('a', time='0.25s')],
    )

    assert app.max_gap == 120.0
    assert app.hover_time == 0.25
    assert app.backspace_repeat_delay == 90.0
    assert app.device.sample_rate == 48_000
    assert app.sound.minimum_note_time == 0.25
    assert app.sound.binaural.frequency == 10.0
    assert app.tuning.detune == 12.0
    assert app.tuning.root_frequency == 440.0
    assert app.text_timings.space == 100.0
    assert app.text_timings.other == {'!': 2000.0}
    assert app.text_timings.timings == [250.0]
    assert app.char_presses == [CharPress('a', time=250.0)]
    assert Voice(frequency='0.44kHz', fade_in='250ms').frequency == 440.0
    assert Voice(fade_in='250ms').fade_in == 0.25
    assert SpeechPhrase(text='a', start='250ms').start == 0.25
    loop = LoopState(before='250ms', after='2min')
    assert loop.before == 0.25
    assert loop.after == 120.0


def test_models_reject_incompatible_unit_values() -> None:
    with pytest.raises(ValidationError):
        Tuning(root_frequency='1s')
    with pytest.raises(ValidationError):
        CharPress('a', time='1Hz')
    with pytest.raises(ValidationError):
        Device(sample_rate='440.5Hz')


def test_cli_normalizes_unit_options() -> None:
    app = tyro.cli(
        App,
        args=[
            '--max-gap',
            '2min',
            '--device.sample-rate',
            '48kHz',
            '-N',
            '250ms',
            '-T',
            '12cents',
            '-U',
            '0.44kHz',
            '--text-timings.space',
            '0.1s',
        ],
    )

    assert app.max_gap == 120.0
    assert app.device.sample_rate == 48_000
    assert app.sound.minimum_note_time == 0.25
    assert app.tuning.detune == 12.0
    assert app.tuning.root_frequency == 440.0
    assert app.text_timings.space == 100.0


def test_text_timing_editor_accepts_unit_values() -> None:
    presses = [CharPress('a', time=0), CharPress('a', False, time=100)]

    edit_text_timing(presses, 0, 1, '0.25s')
    edit_text_timing(presses, 0, 2, '0.5s')

    assert presses == [CharPress('a', time=250), CharPress('a', False, time=750)]


def test_frequency_table_accepts_hertz_quantities() -> None:
    assert Table(text='440Hz; 0.88kHz').values == [440.0, 880.0]
