import sys
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace

import numpy as np
import pytest
import sounddevice
import soundfile
from sounddevice import CallbackAbort, PortAudioError

import tuney.audio.device
from tuney.audio import speech
from tuney.audio.device import Device
from tuney.audio.engine import AudioEngine, Configure, PlaySpeech, StopAll, Stream
from tuney.audio.mixer import Mixer, NotePress
from tuney.audio.oscillator import Oscillator, Waveform
from tuney.audio.output_file import AudioFileWriter
from tuney.audio.player import Player
from tuney.audio.polyphony import Polyphony
from tuney.audio.renderer import OfflineRenderer
from tuney.audio.sound import Binaural, Sound
from tuney.audio.speech import SpeechPhrase, SpeechPlayback
from tuney.audio.voice import Voice, VoiceState
from tuney.scale.scale import Scale

SAMPLE_RATE = 48_000
SAMPLE_COUNT = SAMPLE_RATE


def _voice_maker(note_number: int) -> Voice:
    return Voice(
        frequency=220 * 2 ** (note_number / 12),
        fade_in=0.1,
        fade_out=0.1,
        oscillator=Oscillator(waveform=Waveform.sine),
        sample_rate=SAMPLE_RATE,
    )


def _renderer(voice_maker: Callable[[int], Voice] = _voice_maker) -> OfflineRenderer:
    return OfflineRenderer(mixer=Mixer(voice_maker=voice_maker))


def _render_scenario(scenario: str, block_size: int = 997) -> np.ndarray:
    renderer = _renderer()
    blocks: list[np.ndarray] = []
    rendered = 0
    block_index = 0
    while rendered < SAMPLE_COUNT:
        frame_size = min(block_size, SAMPLE_COUNT - rendered)
        notes: list[NotePress] = []
        if block_index == 0:
            notes.append(NotePress(0))
            if scenario in {'overlap', 'stop_all'}:
                notes.append(NotePress(7))
        if scenario == 'envelope' and rendered >= 24_000 > rendered - frame_size:
            notes.append(NotePress(0, False))
        if scenario == 'overlap' and rendered >= 24_000 > rendered - frame_size:
            notes.append(NotePress(0, False))
        if scenario == 'overlap' and rendered >= 36_000 > rendered - frame_size:
            notes.append(NotePress(7, False))
        if scenario == 'stop_all' and rendered >= 24_000 > rendered - frame_size:
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
def test_audio_rendering(file_regression, scenario: str) -> None:
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
    press = NotePress(0)
    release = NotePress(1, False)

    assert renderer.apply(press)
    assert not renderer.apply(press)
    assert not renderer.apply(release)


def test_callback_records_status_without_printing(
    capsys,
) -> None:
    engine = AudioEngine(mixer=_renderer().mixer)

    engine.callback(np.zeros((4, 1)), 4, 0.0, 'underflow')

    assert engine.diagnostics.callback_statuses == ['underflow; buffer_size=32']
    assert capsys.readouterr().out == ''


def test_underflow_increases_buffer_size() -> None:
    buffer_sizes = [32]

    def increase_buffer_size() -> int:
        buffer_sizes[0] += 32
        return buffer_sizes[0]

    engine = AudioEngine(
        mixer=_renderer().mixer,
        buffer_size=buffer_sizes[0],
        increase_buffer_size=increase_buffer_size,
    )

    engine.callback(np.zeros((4, 1)), 4, 0.0, 'output underflow')

    assert engine.buffer_size == 64
    assert engine.diagnostics.callback_statuses == ['output underflow; buffer_size=64']


def test_underflow_logs_buffer_size(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
    monkeypatch.setenv('TUNEY_TRACE', '1')
    engine = AudioEngine(
        mixer=_renderer().mixer,
        buffer_size=32,
        increase_buffer_size=lambda: 64,
    )

    engine.callback(np.zeros((4, 1)), 4, 0.0, 'output underflow')

    assert (
        'output underflow; buffer_size=64'
        in (tmp_path / 'tuney' / 'tuney.txt').read_text()
    )


def test_engine_master_gain_scales_output() -> None:
    engine = AudioEngine(mixer=_renderer().mixer, master_gain=0.25)
    engine.submit(NotePress(0))
    out = np.zeros((128, 1), dtype=np.float32)

    engine.callback(out, len(out), 0.0, None)

    expected = AudioEngine(mixer=_renderer().mixer)
    expected.submit(NotePress(0))
    unscaled = np.zeros((128, 1), dtype=np.float32)
    expected.callback(unscaled, len(unscaled), 0.0, None)
    np.testing.assert_allclose(out, unscaled * 0.25)


def test_engine_master_gain_accepts_integer_output_buffer() -> None:
    engine = AudioEngine(mixer=_renderer().mixer, master_gain=0.25)
    engine.submit(NotePress(0))
    out = np.zeros((128, 1), dtype=np.int16)

    engine.callback(out, len(out), 0.0, None)

    assert out.dtype == np.int16


def test_synchronized_oscillators_use_mixer_frame_count() -> None:
    voice = Voice(
        frequency=480,
        sample_rate=48_000,
        oscillator=Oscillator(waveform=Waveform.sine),
    )
    mixer = Mixer(voice_maker=lambda _: voice, synchronize_oscillators=True)

    mixer.render(125)
    mixer.apply(NotePress(0))

    assert mixer.voices[0].phase == 25


def test_unsynchronized_oscillators_start_at_zero() -> None:
    voice = Voice(
        frequency=480,
        sample_rate=48_000,
        oscillator=Oscillator(waveform=Waveform.sine),
    )
    mixer = Mixer(voice_maker=lambda _: voice)

    mixer.render(125)
    mixer.apply(NotePress(0))

    assert mixer.voices[0].phase == 0


def test_configure_sets_synchronized_oscillators() -> None:
    engine = AudioEngine(mixer=_renderer().mixer)
    engine.submit(
        Configure(
            voice_maker=_voice_maker,
            polyphony=Polyphony(),
            synchronize_oscillators=True,
        )
    )

    engine.callback(np.zeros((4, 1)), 4, 0.0, None)

    assert engine.mixer.synchronize_oscillators


class _EngineStream(Stream):
    instances: list['_EngineStream'] = []

    def __init__(self, callback: Callable[..., None], **_: object) -> None:
        self.callback = callback
        self.active = False
        self.closed = False
        self.samplerate = 44_100
        self.channels = 1
        self.options = _
        self.blocksize = _.get('blocksize')
        self.dtype = _.get('dtype')
        self.device = _.get('device')
        self.latency = 0.01
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


class _FailingOpenStream:
    def __init__(self, **_: object) -> None:
        raise PortAudioError('cannot open device')


class _FailingMixer(Mixer):
    def render(self, *_: object, **__: object) -> np.ndarray:
        raise ValueError('cannot render block')


def test_stream_failure_is_recorded(monkeypatch) -> None:
    _EngineStream.instances.clear()
    monkeypatch.setattr(sounddevice, 'OutputStream', _FailingEngineStream)
    engine = AudioEngine(mixer=_renderer().mixer)

    with pytest.raises(PortAudioError, match='device unavailable'):
        engine.start()

    assert engine.diagnostics.stream_errors == ['device unavailable']
    assert _EngineStream.instances[0].closed
    assert 'stream' not in engine.__dict__


def test_stream_open_failure_leaves_engine_stopped(monkeypatch) -> None:
    monkeypatch.setattr(sounddevice, 'OutputStream', _FailingOpenStream)
    engine = AudioEngine(mixer=_renderer().mixer)

    with pytest.raises(PortAudioError, match='cannot open device'):
        engine.start()

    assert engine.diagnostics.stream_errors == ['cannot open device']
    assert 'stream' not in engine.__dict__


def test_player_rolls_back_failed_stream_open(monkeypatch) -> None:
    monkeypatch.setattr(sounddevice, 'OutputStream', _FailingOpenStream)
    player = Player()

    assert not player.start(0)
    assert not player.pressed_notes
    assert player.engine.diagnostics.stream_errors == ['cannot open device']
    assert 'stream' not in player.engine.__dict__


def test_player_recording_uses_integer_stream_sample_rate(
    monkeypatch, tmp_path
) -> None:
    _EngineStream.instances.clear()
    monkeypatch.setattr(sounddevice, 'OutputStream', _EngineStream)
    sample_rates: list[int] = []

    class Writer:
        def __init__(
            self,
            path: object,
            sample_rate: int,
            channels: int,
            comment: Callable[[], str] | None,
            append: bool,
        ) -> None:
            sample_rates.append(sample_rate)

    monkeypatch.setattr('tuney.audio.player.AudioFileWriter', Writer)
    player = Player()
    player.engine.stream.samplerate = 44_100.0

    player.start_recording(tmp_path / 'out.wav')

    assert sample_rates == [44_100]


def test_callback_failure_is_recorded() -> None:
    engine = AudioEngine(mixer=_FailingMixer(voice_maker=_voice_maker))

    with pytest.raises(CallbackAbort):
        engine.callback(np.zeros((4, 1)), 4, 0.0, None)

    assert engine.diagnostics.take_errors() == ['cannot render block']


def test_engine_records_rendered_callback_block(tmp_path) -> None:
    path = tmp_path / 'out.wav'
    engine = AudioEngine(mixer=_renderer().mixer)
    engine.recorder = AudioFileWriter(path, SAMPLE_RATE, 1)
    engine.submit(NotePress(0))
    out = np.zeros((1_024, 1), dtype=np.float32)

    engine.callback(out, len(out), None, None)
    engine.recorder.close()
    audio, sample_rate = soundfile.read(path, always_2d=True)

    assert sample_rate == SAMPLE_RATE
    assert len(audio) == len(out)
    assert audio.any()


def test_audio_file_writer_appends_to_existing_file(tmp_path) -> None:
    path = tmp_path / 'out.wav'
    first = np.ones((SAMPLE_COUNT, 1), dtype=np.float32) * 0.25
    second = np.ones((SAMPLE_COUNT, 1), dtype=np.float32) * 0.5
    writer = AudioFileWriter(path, SAMPLE_RATE, 1)
    writer.write(first)
    writer.close()

    writer = AudioFileWriter(path, SAMPLE_RATE, 1, append=True)
    writer.write(second)
    writer.close()

    audio, sample_rate = soundfile.read(path, always_2d=True)

    assert sample_rate == SAMPLE_RATE
    assert len(audio) == SAMPLE_COUNT * 2
    np.testing.assert_allclose(audio[:SAMPLE_COUNT], first, atol=1e-4)
    np.testing.assert_allclose(audio[SAMPLE_COUNT:], second, atol=1e-4)


class _UnsupportedCommentFile:
    @property
    def comment(self) -> str:
        return ''

    @comment.setter
    def comment(self, _: str) -> None:
        raise soundfile.LibsndfileError(
            0, 'Error : File type does not support string data.'
        )


class _FailingCommentFile:
    @property
    def comment(self) -> str:
        return ''

    @comment.setter
    def comment(self, _: str) -> None:
        raise soundfile.LibsndfileError(0, 'Error : another failure.')


def test_audio_file_writer_skips_comment_for_unsupported_formats() -> None:
    writer = object.__new__(AudioFileWriter)
    writer.file = _UnsupportedCommentFile()

    writer._set_comment('metadata')


def test_audio_file_writer_raises_unexpected_comment_errors() -> None:
    writer = object.__new__(AudioFileWriter)
    writer.file = _FailingCommentFile()

    with pytest.raises(soundfile.LibsndfileError, match='another failure'):
        writer._set_comment('metadata')


def test_player_uses_one_stream_for_polyphony(monkeypatch) -> None:
    _EngineStream.instances.clear()
    monkeypatch.setattr(sounddevice, 'OutputStream', _EngineStream)
    player = Player()

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


def test_player_steals_oldest_voice_at_max_polyphony(monkeypatch) -> None:
    _EngineStream.instances.clear()
    monkeypatch.setattr(sounddevice, 'OutputStream', _EngineStream)
    player = Player(sound=Sound(polyphony=Polyphony(max_voices=1)))

    assert player.start(0)
    assert player.start(7)

    out = np.zeros((128, 1), dtype=np.float32)
    player.engine.callback(out, len(out), None, None)

    assert player.pressed_notes == [7]
    assert player.engine.mixer.pressed_notes == [7]
    assert player.engine.mixer.voices[0].release_frame is not None
    assert 7 in player.engine.mixer.voices


def test_player_counts_binaural_notes_as_two_voices(monkeypatch) -> None:
    _EngineStream.instances.clear()
    monkeypatch.setattr(sounddevice, 'OutputStream', _EngineStream)
    player = Player(
        sound=Sound(binaural=Binaural(enable=True), polyphony=Polyphony(max_voices=3))
    )

    assert player.start(0)
    assert player.start(7)

    out = np.zeros((128, 2), dtype=np.float32)
    player.engine.callback(out, len(out), None, None)

    assert player.pressed_notes == [7]
    assert player.engine.mixer.pressed_notes == [7]
    assert list(player.engine.mixer.voices) == [7]


def test_player_uses_scale_note_subset_for_frequencies() -> None:
    chromatic = Player(sound=Sound(note_offset=0))
    white_notes = Player(sound=Sound(note_offset=0), scale=Scale(notes='ABCDEFG'))

    assert white_notes.voice_maker(1).frequency == chromatic.voice_maker(2).frequency


def test_player_applies_oscillator_key_scaling_to_voice_gain() -> None:
    player = Player(
        sound=Sound(
            note_offset=0,
            gain=0.25,
            oscillator=Oscillator(key_scale_note=12, key_scale=6),
        )
    )

    assert player.voice_maker(24).gain == pytest.approx(0.25 * 10 ** (6 / 20))


def test_player_forces_stereo_for_binaural_sound() -> None:
    player = Player(sound=Sound(binaural=Binaural(enable=True)))

    assert player.channels == 2
    assert player.engine.device.channels == 2
    assert player.voice_maker(0).binaural.enable
    assert player.engine.master_gain == 1.0


def test_player_updates_cached_engine_channels_for_binaural_sound() -> None:
    player = Player()
    engine = player.engine
    player.sound.binaural.enable = True

    player.sync_engine_device()

    assert player.engine is engine
    assert player.engine.device.channels == 2


def test_player_updates_live_master_gain() -> None:
    player = Player()
    _ = player.engine

    player.set_master_gain(0.5)

    assert player.sound.master_gain == 0.5
    assert player.engine.master_gain == 0.5


def test_player_preserves_live_master_gain_for_binaural_sound() -> None:
    player = Player(sound=Sound(binaural=Binaural(enable=True)))
    _ = player.engine

    player.set_master_gain(0.5)

    assert player.sound.master_gain == 0.5
    assert player.engine.master_gain == 0.5


def test_device_change_restarts_active_stream(monkeypatch) -> None:
    _EngineStream.instances.clear()
    monkeypatch.setattr(sounddevice, 'OutputStream', _EngineStream)
    player = Player()
    player.start(0)
    first = _EngineStream.instances[0]

    player.device.device = 'speaker'
    player.device.notify_change()

    second = _EngineStream.instances[1]
    assert first.closed
    assert second.active
    assert second.options['device'] == 'speaker'
    assert not player.pressed_notes
    assert not player.engine.mixer.voices

    player.device.device = 'headphones'
    player.device.notify_change()

    assert second.closed
    assert _EngineStream.instances[2].active
    assert _EngineStream.instances[2].options['device'] == 'headphones'


def test_duplicate_output_device_name_uses_device_index(monkeypatch) -> None:
    _EngineStream.instances.clear()
    monkeypatch.setattr(sounddevice, 'OutputStream', _EngineStream)
    monkeypatch.setattr(
        tuney.audio.device.sounddevice,
        'query_devices',
        lambda: [
            {'name': 'speaker', 'max_output_channels': 2},
            {'name': 'speaker', 'max_output_channels': 2},
        ],
    )

    def query_device_info(_: object) -> object:
        raise PortAudioError('no host api')

    monkeypatch.setattr(sounddevice, 'query_devices', query_device_info)

    Player(device=Device(device='speaker')).start(0)

    assert _EngineStream.instances[0].options['device'] == 0


def test_player_passes_buffer_size_to_output_stream(monkeypatch) -> None:
    _EngineStream.instances.clear()
    monkeypatch.setattr(sounddevice, 'OutputStream', _EngineStream)

    Player(buffer_size=64).start(0)

    assert _EngineStream.instances[0].options['blocksize'] == 64


def test_stream_logging_includes_device_details(monkeypatch, tmp_path) -> None:
    _EngineStream.instances.clear()
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
    monkeypatch.setenv('TUNEY_TRACE', '1')
    monkeypatch.setattr(sounddevice, 'OutputStream', _EngineStream)
    monkeypatch.setattr(sounddevice, 'default', {'device': [None, 'speaker']})

    def query_devices(device: object = None) -> object:
        if device is None:
            return [{'name': 'speaker', 'max_output_channels': 2}]
        return {'name': device, 'max_output_channels': 2}

    monkeypatch.setattr(sounddevice, 'query_devices', query_devices)

    Player(device=Device(device='speaker', dtype='float32')).start(0)

    log = (tmp_path / 'tuney' / 'tuney.txt').read_text()
    assert "requested_device='speaker'" in log
    assert "resolved_device='speaker'" in log
    assert "dtype='float32'" in log
    assert "sounddevice_defaults={'device': [None, 'speaker']}" in log
    assert "resolved_device_info={'name': 'speaker', 'max_output_channels': 2}" in log
    assert 'latency=0.01' in log


def test_mixer_steals_oldest_voice_at_max_polyphony() -> None:
    voice = Voice(fade_in=0, oscillator=Oscillator(waveform=Waveform.triangle))
    mixer = Mixer(voice_maker=lambda _: voice)
    for note_number in range(mixer.polyphony.max_voices):
        assert mixer.apply(NotePress(note_number))

    assert mixer.apply(NotePress(mixer.polyphony.max_voices))
    assert mixer.pressed_notes == list(range(1, mixer.polyphony.max_voices + 1))
    assert mixer.voices[0].release_frame is not None

    out = mixer.render(48_000, np.float32)

    assert np.all(np.isfinite(out))


def test_mixer_counts_binaural_notes_as_two_voices() -> None:
    voice = Voice(
        fade_in=0,
        oscillator=Oscillator(waveform=Waveform.triangle),
        binaural=Binaural(enable=True),
    )
    mixer = Mixer(voice_maker=lambda _: voice, polyphony=Polyphony(max_voices=3))

    assert mixer.apply(NotePress(0))
    assert mixer.apply(NotePress(7))
    assert mixer.pressed_notes == [7]
    assert mixer.voices[0].release_frame is not None
    assert 7 in mixer.voices


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


def test_voice_holds_early_release_until_minimum_note_time() -> None:
    state = VoiceState(
        voice=Voice(
            fade_in=0,
            fade_out=0,
            minimum_note_time=0.5,
            oscillator=Oscillator(waveform=Waveform.triangle),
            sample_rate=SAMPLE_RATE,
        )
    )

    state.render(1)
    state.release()
    state.render(SAMPLE_RATE // 2 - 2)

    assert not state.complete

    state.render(1)

    assert state.complete


def test_square_wave_renders_with_float_envelope() -> None:
    state = VoiceState(
        voice=Voice(
            fade_in=0.1,
            oscillator=Oscillator(waveform=Waveform.square),
            sample_rate=SAMPLE_RATE,
        )
    )

    out = state.render(128)

    assert out.dtype == float
    assert np.max(np.abs(out)) <= 1


def test_mixer_maps_mono_signal_to_each_channel() -> None:
    mixer = _renderer().mixer
    mixer.apply(NotePress(0))

    out = mixer.render(48_000, np.float32, channels=3)

    assert out.shape == (48_000, 3)
    np.testing.assert_array_equal(out[:, 0], out[:, 1])
    np.testing.assert_array_equal(out[:, 1], out[:, 2])


def test_mixer_maps_binaural_signal_to_mono_channel() -> None:
    voice = Voice(
        oscillator=Oscillator(waveform=Waveform.sine),
        binaural=Binaural(enable=True),
    )
    mixer = Mixer(voice_maker=lambda _: voice)
    mixer.apply(NotePress(0))

    out = mixer.render(4096, np.float32, channels=1)

    assert out.shape == (4096, 1)
    assert np.all(np.isfinite(out))


def test_mixer_does_not_clip_floating_point_output() -> None:
    voice = Voice(
        fade_in=0,
        gain=2,
        oscillator=Oscillator(waveform=Waveform.square),
        sample_rate=SAMPLE_RATE,
    )
    mixer = Mixer(voice_maker=lambda _: voice, polyphony=Polyphony(headroom=1))
    mixer.apply(NotePress(0))

    out = mixer.render(128, np.float32)

    assert out.max() == 2


def test_binaural_voice_splits_frequencies_across_stereo_channels() -> None:
    voice = Voice(
        frequency=100,
        sample_rate=SAMPLE_RATE,
        oscillator=Oscillator(waveform=Waveform.sine),
        binaural=Binaural(enable=True, frequency=20, width=1),
    )
    mixer = Mixer(voice_maker=lambda _: voice)
    mixer.apply(NotePress(0))

    out = mixer.render(SAMPLE_RATE, np.float32, channels=2)

    assert out.shape == (SAMPLE_RATE, 2)
    np.testing.assert_allclose(
        voice.binaural_period_samples,
        [SAMPLE_RATE / 90, SAMPLE_RATE / 110],
    )
    assert not np.allclose(out[:, 0], out[:, 1])


def test_binaural_voice_is_not_changed_by_later_config_edits() -> None:
    binaural = Binaural(enable=True)
    voice = Voice(
        frequency=100,
        sample_rate=SAMPLE_RATE,
        oscillator=Oscillator(waveform=Waveform.sine),
        binaural=binaural,
    )
    state = VoiceState(voice=voice)

    state.render(128)
    binaural.enable = False
    out = state.render(128)

    assert out.shape == (128, 2)


def test_centered_binaural_width_mixes_both_frequencies_to_both_channels() -> None:
    state = VoiceState(
        voice=Voice(
            frequency=100,
            sample_rate=SAMPLE_RATE,
            oscillator=Oscillator(waveform=Waveform.sine),
            binaural=Binaural(enable=True, frequency=20, width=0),
        )
    )

    out = state.render(SAMPLE_RATE)

    assert out.shape == (SAMPLE_RATE, 2)
    np.testing.assert_allclose(out[:, 0], out[:, 1])


def test_engine_applies_stop_all_on_next_block() -> None:
    engine = AudioEngine(mixer=_renderer().mixer)
    engine.submit(NotePress(0))
    engine.submit(StopAll())
    out = np.zeros((4_800, 1), dtype=np.float32)

    engine.callback(out, len(out), None, None)

    assert not engine.mixer.pressed_notes
    assert engine.mixer.voices

    out = np.zeros((24_000, 1), dtype=np.float32)
    engine.callback(out, len(out), None, None)

    assert not engine.mixer.voices
    assert engine.playback_complete.is_set()


def test_engine_mixes_speech_playback() -> None:
    engine = AudioEngine(mixer=_renderer().mixer)
    speech = SpeechPlayback(data=np.ones((8, 1), dtype=np.float32) * 0.25, level=2.0)
    engine.submit(PlaySpeech(speech=speech))
    out = np.zeros((4, 1), dtype=np.float32)

    engine.callback(out, len(out), None, None)

    np.testing.assert_allclose(out, 0.5)
    assert engine.speech is speech


def test_engine_clears_speech_playback_when_complete() -> None:
    engine = AudioEngine(mixer=_renderer().mixer)
    speech = SpeechPlayback(data=np.ones((4, 1), dtype=np.float32), level=1.0)
    engine.submit(PlaySpeech(speech=speech))

    engine.callback(np.zeros((8, 1), dtype=np.float32), 8, None, None)

    assert engine.speech is None


def test_engine_stop_all_clears_speech_playback() -> None:
    engine = AudioEngine(mixer=_renderer().mixer)
    engine.submit(PlaySpeech(speech=SpeechPlayback(data=np.ones((8, 1)), level=1.0)))
    engine.submit(StopAll())

    engine.callback(np.zeros((4, 1)), 4, None, None)

    assert engine.speech is None


def test_speech_renderer_selects_voice(monkeypatch, tmp_path) -> None:
    calls = []

    class Engine:
        def getProperty(self, name: str) -> object:
            if name == 'voices':
                return [
                    SimpleNamespace(id='voice-1', name='First'),
                    SimpleNamespace(id='voice-2', name='Second'),
                ]
            raise AssertionError(name)

        def setProperty(self, name: str, value: object) -> None:
            calls.append((name, value))

        def save_to_file(self, _: str, path: str) -> None:
            Path(path).touch()

        @staticmethod
        def runAndWait() -> None:
            pass

    monkeypatch.setitem(
        sys.modules,
        'pyttsx3',
        SimpleNamespace(init=lambda: Engine()),
    )
    monkeypatch.setattr(
        soundfile,
        'read',
        lambda *_args, **_kwargs: (np.zeros((8, 1)), SAMPLE_RATE),
    )

    speech._render_speech('hello', 50, tmp_path / 'speech.wav', 'Second')

    assert ('voice', 'voice-2') in calls


def test_speech_playback_aligns_phrases_without_stretching(monkeypatch) -> None:
    def render(
        text: str, _rate: int, _path: Path, _voice: str | None
    ) -> speech._SpeechFile | None:
        values = {'a': 1.0, 'b': 2.0}
        return speech._SpeechFile(
            data=np.ones((2, 1), dtype=np.float32) * values[text],
            sample_rate=4,
        )

    monkeypatch.setattr(speech, '_render_speech', render)

    playback = speech.speech_playback(
        [SpeechPhrase(text='a', start=0.0), SpeechPhrase(text='b', start=0.5)],
        sample_rate=4,
        level=1.0,
        voice=None,
    )

    assert playback is not None
    np.testing.assert_allclose(playback.data[:, 0], [1.0, 1.0, 2.0, 2.0])


def test_engine_waits_for_final_audio_block(monkeypatch) -> None:
    _EngineStream.instances.clear()
    monkeypatch.setattr(sounddevice, 'OutputStream', _EngineStream)
    engine = AudioEngine(mixer=_renderer().mixer)
    engine.submit(NotePress(0))
    engine.submit(StopAll())
    engine.start()
    waiting = Event()

    def wait() -> None:
        waiting.set()
        engine.wait()

    thread = Thread(target=wait)
    thread.start()
    waiting.wait()

    assert thread.is_alive()
    assert engine.stream.active

    engine.callback(np.zeros((30_000, 1)), 30_000, None, None)
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert not engine.stream.active


def test_engine_wait_ignores_inactive_stream(monkeypatch) -> None:
    _EngineStream.instances.clear()
    monkeypatch.setattr(sounddevice, 'OutputStream', _EngineStream)
    engine = AudioEngine(mixer=_renderer().mixer)

    _ = engine.stream
    engine.wait()

    assert not engine.stream.active


def test_engine_close_does_not_open_unused_stream(monkeypatch) -> None:
    _EngineStream.instances.clear()
    monkeypatch.setattr(sounddevice, 'OutputStream', _EngineStream)
    engine = AudioEngine(mixer=_renderer().mixer)

    engine.close()

    assert not _EngineStream.instances


def test_engine_close_closes_existing_stream(monkeypatch) -> None:
    _EngineStream.instances.clear()
    monkeypatch.setattr(sounddevice, 'OutputStream', _EngineStream)
    engine = AudioEngine(mixer=_renderer().mixer)

    engine.start()
    engine.close()

    assert _EngineStream.instances[0].closed

    engine.start()

    assert len(_EngineStream.instances) == 2
    assert _EngineStream.instances[1].active
