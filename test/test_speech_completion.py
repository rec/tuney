from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile

from tuney.app.app import App
from tuney.audio.engine import AudioEngine, PlaySpeech, StopAll
from tuney.audio.mixer import Mixer
from tuney.audio.player import Player
from tuney.audio.speech import SpeechPlayback, SpeechRequest
from tuney.audio.voice import Voice
from tuney.time.char_press import CharPress
from tuney.time.sequencer import Sequencer


def test_audio_export_finishes_speech_after_notes(
    monkeypatch, tmp_path: Path, file_regression
) -> None:
    requests: list[SpeechRequest] = []

    def speech(request: SpeechRequest) -> SpeechPlayback:
        requests.append(request)
        return SpeechPlayback(data=np.ones((72_001, 1)), level=request.level)

    monkeypatch.setattr('tuney.app.app_playback.render_speech', speech)
    path = tmp_path / 'spoken.wav'
    App(
        output=path,
        silent=True,
        use_speech=True,
        speech_level=0.25,
        text=[CharPress('a', time=0), CharPress('a', False, 100)],
    ).run_cli()
    assert requests[0].sample_rate == 48_000
    assert requests[0].phrases[0].text == 'a'
    audio, rate = soundfile.read(path)
    assert rate == 48_000
    assert len(audio) == 72_001
    np.testing.assert_array_equal(audio[48_000:], np.full(24_001, 0.25))
    wav = BytesIO()
    soundfile.write(wav, audio, rate, format='WAV', subtype='PCM_16')
    file_regression.check(wav.getvalue(), binary=True, extension='.wav')


@pytest.mark.parametrize('finish_speech', [False, True])
def test_live_completion_preserves_speech_but_explicit_stop_cancels(
    finish_speech: bool, file_regression
) -> None:
    engine = AudioEngine(mixer=Mixer(voice_maker=lambda _: Voice()))
    engine.submit(
        PlaySpeech(speech=SpeechPlayback(data=np.full((48_000, 1), 0.25), level=1))
    )
    engine.submit(StopAll(finish_speech=finish_speech))
    first, second = np.zeros((24_000, 1)), np.zeros((24_000, 1))
    engine.callback(first, len(first), None, None)
    assert engine.playback_complete.is_set() is not finish_speech
    engine.callback(second, len(second), None, None)
    assert engine.playback_complete.is_set()
    wav = BytesIO()
    soundfile.write(
        wav, np.concatenate([first, second]), 48_000, format='WAV', subtype='PCM_16'
    )
    file_regression.check(wav.getvalue(), binary=True, extension='.wav')


@pytest.mark.parametrize('loop', [False, True])
@pytest.mark.parametrize('replaced', [False, True])
def test_replay_waits_for_speech_before_stopping_or_looping(
    monkeypatch, loop: bool, replaced: bool
) -> None:
    app = App(gui=True, use_speech=True, text='a')
    callbacks: list[Callable[[], None]] = []
    calls: list[str] = []
    window = SimpleNamespace(
        is_replaying=True,
        history=SimpleNamespace(loop_replay=loop),
        after=lambda delay, callback: callbacks.append(callback),
    )
    app.__dict__['main_window'] = window
    app.__dict__['player'] = SimpleNamespace(
        engine=SimpleNamespace(stream=SimpleNamespace(active=True)),
        stop_all=lambda finish_speech=False: calls.append(
            'drain' if finish_speech else 'stop'
        ),
    )
    monkeypatch.setattr(App, 'on_replay', lambda _: calls.append('loop'))
    monkeypatch.setattr(App, 'replay_char_presses', lambda _: [CharPress('a')])
    speech = SpeechPlayback(data=np.ones((48_000, 1)), level=1)
    app.key_recorder.speech = speech
    app.key_recorder.finish_replay(app)
    assert window.is_replaying
    assert calls == ['drain']
    if replaced:
        app.key_recorder.sequencer = Sequencer(char_presses=[], callback=lambda _: None)
    speech.position = 48_000
    callbacks.pop()()
    if replaced:
        assert calls == ['drain']
        assert window.is_replaying
        return
    assert calls == (['drain', 'loop'] if loop else ['drain', 'stop'])
    assert window.is_replaying is loop


def test_cli_starts_speech_and_preserves_it_on_normal_completion(monkeypatch) -> None:
    calls: list[object] = []
    monkeypatch.setattr(
        Player, 'start_speech', lambda self, *args: calls.append(args[0])
    )
    monkeypatch.setattr(
        Player,
        'stop_all',
        lambda self, finish_speech=False: calls.append(finish_speech),
    )
    monkeypatch.setattr(Player, 'wait', lambda self: None)
    monkeypatch.setattr(Player, 'close', lambda self: None)
    monkeypatch.setattr(Sequencer, 'run', lambda self: None)
    App(text='a', use_speech=True).run_cli()
    assert calls[0][0].text == 'a'
    assert calls[1] is True
