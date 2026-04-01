import numpy as np
import pytest
from tuney.audio.oscillator_player import OscillatorPlayer, Sound, _fade

SAMPLE_RATE = 48_000


def render_chunked(chunk_size: int, num_chunks: int, sound: Sound) -> np.ndarray:
    player = OscillatorPlayer(sound=sound, oscillator_name='sine')
    buffers = []
    for _ in range(num_chunks):
        out = np.zeros((chunk_size, 1), dtype=np.float32)
        player._fill(out)
        player.chunk_count += 1
        player.frame_size = chunk_size
        buffers.append(out.flatten().copy())
    return np.concatenate(buffers)


def render_direct(chunk_size: int, num_chunks: int, sound: Sound) -> np.ndarray:
    total_samples = chunk_size * num_chunks
    period = float(sound.period)
    ratio = float(2 * np.pi) / period
    wave = np.sin(
        np.linspace(0, total_samples * ratio, total_samples, endpoint=False)
    ).astype(np.float32)

    fade_in = float(sound.fade_in_samples)
    if fade_in > 0:
        for i in range(num_chunks):
            frame_count = i * chunk_size
            if frame_count < fade_in:
                chunk = wave[i * chunk_size:(i + 1) * chunk_size]
                _fade(chunk, frame_count / fade_in, chunk_size / fade_in)

    return wave


@pytest.mark.parametrize("fade_samples", [0, int(SAMPLE_RATE * 0.2)])
def test_sine_continuity(fade_samples):
    chunk_size = 1024
    num_chunks = 20
    sound = Sound(fade_in_samples=fade_samples, fade_out_samples=fade_samples)

    chunked = render_chunked(chunk_size, num_chunks, sound)
    direct = render_direct(chunk_size, num_chunks, sound)

    assert np.allclose(chunked, direct, atol=1e-5)