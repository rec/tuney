from io import BytesIO

import numpy as np
import pytest
import soundfile
from enge.synth import VoiceRenderer
from pytest_regressions.file_regression import FileRegressionFixture
from ufor.oscillator import Waveform

from tuney.audio.mixer import Mixer, NotePress
from tuney.audio.oscillator import Oscillator
from tuney.audio.polyphony import Polyphony
from tuney.audio.sound import Binaural
from tuney.audio.voice import Voice


@pytest.mark.parametrize('binaural', [False, True], ids=['mono', 'binaural'])
@pytest.mark.parametrize('scenario', ['early_release', 'fractional_hold', 'immediate'])
def test_shared_envelope_preserves_tuney_audio(
    file_regression: FileRegressionFixture, scenario: str, binaural: bool
) -> None:
    voice = Voice(
        frequency=100,
        gain=0.37,
        sample_rate=48000,
        fade_in=0 if scenario == 'immediate' else 0.2,
        fade_out=0 if scenario == 'immediate' else 0.05003125,
        minimum_note_time=0.10003125 if scenario == 'fractional_hold' else 0,
        oscillator=Oscillator(waveform=Waveform.sine),
        binaural=Binaural(enable=binaural, frequency=20, width=0.3),
    )
    frames = np.arange(48000)
    release = max(1200, voice.minimum_note_time * 48000)
    attack = (
        np.ones(48000)
        if voice.fade_in == 0
        else np.clip(frames / (voice.fade_in * 48000), 0, 1)
    )
    if voice.fade_out == 0:
        envelope = attack * (frames < release)
    else:
        captured = min(1, release / (voice.fade_in * 48000))
        envelope = np.where(
            frames < release,
            attack,
            captured * np.clip(1 - (frames - release) / (voice.fade_out * 48000), 0, 1),
        )
    if binaural:
        low = np.sin(2 * np.pi * frames * 90 / 48000)
        high = np.sin(2 * np.pi * frames * 110 / 48000)
        expected = np.column_stack([0.65 * low + 0.35 * high, 0.35 * low + 0.65 * high])
    else:
        expected = np.sin(2 * np.pi * frames * 100 / 48000)[:, None]
    expected *= envelope[:, None] * voice.gain

    outputs: list[np.ndarray] = []
    for block in (997, 1024):
        state = VoiceRenderer.start(voice.definition)
        chunks: list[np.ndarray] = []
        start = 0
        while start < 48000:
            if start == 1200:
                assert state.release()
                assert not state.release()
            end = min(start + block, 1200 if start < 1200 else 48000)
            chunks.append(state.render(end - start))
            start = end
        actual = np.concatenate(chunks).reshape(48000, -1)
        assert state.complete
        assert np.all(np.isfinite(actual))
        np.testing.assert_allclose(actual, expected, atol=1e-10, rtol=1e-9)
        outputs.append(actual)
    np.testing.assert_allclose(outputs[0], outputs[1], atol=1e-12, rtol=1e-12)
    wav = BytesIO()
    soundfile.write(wav, outputs[0], 48000, format='WAV', subtype='PCM_16')
    file_regression.check(wav.getvalue(), binary=True, extension='.wav')


@pytest.mark.parametrize('channels', [1, 3])
def test_binaural_output_conversion_keeps_tuney_channel_policy(
    file_regression: FileRegressionFixture, channels: int
) -> None:
    voice = Voice(
        frequency=100,
        fade_in=0,
        oscillator=Oscillator(waveform=Waveform.sine),
        binaural=Binaural(enable=True, frequency=20, width=-0.4),
    )
    mixer = Mixer(voice_maker=lambda _: voice, polyphony=Polyphony(headroom=1))
    mixer.apply(NotePress(0))
    actual = mixer.render(48000, channels=channels)
    frames = np.arange(48000)
    low = np.sin(2 * np.pi * frames * 90 / 48000)
    high = np.sin(2 * np.pi * frames * 110 / 48000)
    signal = (low + high) / 2 if channels == 1 else 0.3 * low + 0.7 * high
    expected = np.repeat(signal[:, None], channels, axis=1)
    np.testing.assert_allclose(actual, expected, atol=1e-10, rtol=1e-9)
    saved = actual.copy()
    mixer.render(128, channels=channels)
    np.testing.assert_array_equal(actual, saved)
    wav = BytesIO()
    soundfile.write(wav, actual, 48000, format='WAV', subtype='PCM_16')
    file_regression.check(wav.getvalue(), binary=True, extension='.wav')


@pytest.mark.parametrize('binaural', [False, True], ids=['square', 'binaural_sync'])
def test_shared_phase_preserves_edges_and_binaural_onset(
    file_regression: FileRegressionFixture, binaural: bool
) -> None:
    voice = Voice(
        frequency=100,
        fade_in=0,
        oscillator=Oscillator(waveform=Waveform.sine if binaural else Waveform.square),
        binaural=Binaural(enable=binaural, frequency=20),
    )
    mixer = Mixer(
        voice_maker=lambda _: voice,
        synchronize_oscillators=binaural,
        polyphony=Polyphony(headroom=1),
    )
    mixer.render(1257)
    mixer.apply(NotePress(0))
    audio = np.concatenate(
        [mixer.render(min(997, 48000 - i), channels=2) for i in range(0, 48000, 997)]
    )
    frames = np.arange(48000)
    if binaural:
        # Preserve Tuney's onset convention: the shared sample-position origin
        # wraps at the base note period before initializing both oscillators.
        positions = frames + 1257 % 480
        expected = np.sin(2 * np.pi * positions[:, None] * np.array([90, 110]) / 48000)
    else:
        expected = np.repeat(
            np.where(frames % 480 < 240, 1.0, -1.0)[:, None], 2, axis=1
        )
    np.testing.assert_allclose(audio, expected, atol=1e-10, rtol=1e-9)
    wav = BytesIO()
    soundfile.write(wav, audio / 2, 48000, format='WAV', subtype='PCM_16')
    file_regression.check(wav.getvalue(), binary=True, extension='.wav')
