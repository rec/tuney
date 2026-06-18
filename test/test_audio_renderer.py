from collections.abc import Callable
from io import BytesIO
from typing import Any

import numpy as np
import pytest
import soundfile
from pytest_regressions.file_regression import FileRegressionFixture
from sounddevice import CallbackStop, PortAudioError

from tuney.audio import engine as engine_module
from tuney.audio.engine import AudioEngine, StopAll
from tuney.audio.mixer import Mixer, NotePress
from tuney.audio.multi_player import MultiPlayer
from tuney.audio.oscillator import Oscillator, Waveform
from tuney.audio.renderer import OfflineRenderer
from tuney.audio.voice import Voice, VoiceState

SAMPLE_RATE = 48_000
SAMPLE_COUNT = SAMPLE_RATE


def _sound(note_number: int) -> Voice:
    return Voice(
        frequency=220 * 2 ** (note_number / 12),
        fade_in=0.1,
        fade_out=0.1,
        oscillator=Oscillator(waveform=Waveform.sine),
        sample_rate=SAMPLE_RATE,
    )


def _renderer(sound: Callable[[int], Voice] = _sound) -> OfflineRenderer:
    return OfflineRenderer(mixer=Mixer(sound=sound))


def _render_scenario(name: str, block_size: int = 997) -> np.ndarray:
    renderer = _renderer()
    blocks: list[np.ndarray] = []
    rendered = 0
    block_index = 0
    while rendered < SAMPLE_COUNT:
        frame_size = min(block_size, SAMPLE_COUNT - rendered)
        notes: list[NotePress] = []
        if block_index == 0:
            notes.append(NotePress(note_number=0, is_press=True))
            if name in {'overlap', 'stop_all'}:
                notes.append(NotePress(note_number=7, is_press=True))
        if name == 'envelope' and rendered >= 24_000 > rendered - frame_size:
            notes.append(NotePress(note_number=0, is_press=False))
        if name == 'overlap' and rendered >= 24_000 > rendered - frame_size:
            notes.append(NotePress(note_number=0, is_press=False))
        if name == 'overlap' and rendered >= 36_000 > rendered - frame_size:
            notes.append(NotePress(note_number=7, is_press=False))
        if name == 'stop_all' and rendered >= 24_000 > rendered - frame_size:
            renderer.stop_all()
        blocks.append(renderer.render(notes, frame_size, np.float32))
        rendered += frame_size
        block_index += 1
    return np.concatenate(blocks)


def _wav(audio: np.ndarray) -> bytes:
    output = BytesIO()
    soundfile.write(output, audio, SAMPLE_RATE, format='WAV', subtype='PCM_16')
    return output.getvalue()


@pytest.mark.parametrize(
    'scenario',
    ['phase_continuity', 'envelope', 'overlap', 'stop_all'],
)
def test_audio_rendering(file_regression: FileRegressionFixture, scenario: str) -> None:
    audio = _render_scenario(scenario)

    assert len(audio) == SAMPLE_COUNT
    if scenario == 'phase_continuity':
        np.testing.assert_allclose(
            audio,
            _render_scenario(scenario, 1_024),
            atol=1e-12,
        )
    file_regression.check(_wav(audio), binary=True, extension='.wav')


def test_note_events_reject_repeated_press_and_unmatched_release() -> None:
    renderer = _renderer()
    press = NotePress(note_number=0, is_press=True)
    release = NotePress(note_number=1, is_press=False)

    assert renderer.apply(press)
    assert not renderer.apply(press)
    assert not renderer.apply(release)


def test_callback_records_status_without_printing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    engine = AudioEngine(mixer=_renderer().mixer)

    engine.callback(np.zeros((4, 1)), 4, 0.0, 'underflow')

    assert engine.diagnostics.callback_statuses == ['underflow']
    assert capsys.readouterr().out == ''


class _EngineStream:
    instances: list['_EngineStream'] = []

    def __init__(self, callback: Callable[..., None], **_: Any) -> None:
        self.callback = callback
        self.active = False
        self.closed = False
        self.samplerate = 44_100
        self.instances.append(self)

    def start(self) -> None:
        self.active = True

    def stop(self) -> None:
        self.active = False

    def close(self) -> None:
        self.closed = True


class _FailingEngineStream(_EngineStream):
    def start(self) -> None:
        raise PortAudioError('device unavailable')


def test_stream_failure_is_recorded(monkeypatch) -> None:
    monkeypatch.setattr(engine_module, 'OutputStream', _FailingEngineStream)
    engine = AudioEngine(mixer=_renderer().mixer)

    with pytest.raises(PortAudioError, match='device unavailable'):
        engine.start()

    assert engine.diagnostics.stream_errors == ['device unavailable']


def test_multi_player_uses_one_stream_for_polyphony(monkeypatch) -> None:
    _EngineStream.instances.clear()
    monkeypatch.setattr(engine_module, 'OutputStream', _EngineStream)
    player = MultiPlayer()

    assert player.start(0)
    assert player.start(7)
    assert len(_EngineStream.instances) == 1

    out = np.zeros((128, 1), dtype=np.float32)
    player.engine.callback(out, len(out), None, None)

    assert player.engine.mixer.pressed_notes == [0, 7]
    assert all(
        state.voice.sample_rate == 44_100
        for state in player.engine.mixer.voices.values()
    )


def test_mixer_limits_max_polyphony() -> None:
    voice = Voice(fade_in=0, oscillator=Oscillator(waveform=Waveform.triangle))
    mixer = Mixer(sound=lambda _: voice)
    for note_number in range(mixer.max_polyphony):
        assert mixer.apply(NotePress(note_number=note_number, is_press=True))

    assert not mixer.apply(NotePress(note_number=mixer.max_polyphony, is_press=True))

    out = mixer.render(48_000, np.float32)

    assert np.max(np.abs(out)) <= 1


def test_envelope_duration_is_stable_across_sample_rates_and_blocks() -> None:
    def render(sample_rate: int, block_size: int) -> np.ndarray:
        state = VoiceState(
            voice=Voice(
                frequency=100,
                fade_in=0.1,
                fade_out=0.1,
                oscillator=Oscillator(waveform=Waveform.sine),
                sample_rate=sample_rate,
            )
        )
        release_frame = sample_rate // 10
        sample_count = sample_rate // 5
        blocks: list[np.ndarray] = []
        rendered = 0
        while rendered < sample_count:
            if rendered == release_frame:
                state.release()
            frame_size = min(
                block_size,
                release_frame - rendered if rendered < release_frame else sample_count,
                sample_count - rendered,
            )
            blocks.append(state.render(frame_size))
            rendered += frame_size
        return np.concatenate(blocks)

    at_48_khz = render(48_000, 997)
    at_96_khz = render(96_000, 1_024)

    np.testing.assert_allclose(at_48_khz, at_96_khz[::2], atol=1e-12)


def test_mixer_maps_mono_signal_to_each_channel() -> None:
    mixer = _renderer().mixer
    mixer.apply(NotePress(note_number=0, is_press=True))

    out = mixer.render(48_000, np.float32, channels=3)

    assert out.shape == (48_000, 3)
    np.testing.assert_array_equal(out[:, 0], out[:, 1])
    np.testing.assert_array_equal(out[:, 1], out[:, 2])


def test_engine_applies_stop_all_on_next_block() -> None:
    engine = AudioEngine(mixer=_renderer().mixer)
    engine.submit(NotePress(note_number=0, is_press=True))
    engine.submit(StopAll())
    out = np.zeros((4_800, 1), dtype=np.float32)

    with pytest.raises(CallbackStop):
        engine.callback(out, len(out), None, None)

    assert not engine.mixer.pressed_notes
    assert not engine.mixer.voices


def test_engine_close_does_not_open_unused_stream(monkeypatch) -> None:
    _EngineStream.instances.clear()
    monkeypatch.setattr(engine_module, 'OutputStream', _EngineStream)
    engine = AudioEngine(mixer=_renderer().mixer)

    engine.close()

    assert not _EngineStream.instances


def test_engine_close_closes_existing_stream(monkeypatch) -> None:
    _EngineStream.instances.clear()
    monkeypatch.setattr(engine_module, 'OutputStream', _EngineStream)
    engine = AudioEngine(mixer=_renderer().mixer)

    engine.start()
    engine.close()

    assert _EngineStream.instances[0].closed
