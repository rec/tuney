import numpy as np
import pytest
from tuney.audio.oscillator_player import OscillatorPlayer, Sound


def render_chunked(chunk_size: int, num_chunks: int, sound: Sound) -> np.ndarray:
    """Render audio chunk by chunk the way the app does it."""
    player = OscillatorPlayer(sound=sound, oscillator_name='sine')
    buffers = []
    for _ in range(num_chunks):
        out = np.zeros((chunk_size, 1), dtype=np.float32)
        player._fill(out)
        player.chunk_count += 1
        player.frame_size = chunk_size
        buffers.append(out.copy())
    return np.concatenate(buffers).flatten()


def render_direct(chunk_size: int, num_chunks: int, sound: Sound) -> np.ndarray:
    """Render the same audio in one shot as ground truth."""
    total_samples = chunk_size * num_chunks
    period = float(sound.period)
    ratio = float(2 * np.pi) / period
    wave = np.sin(np.linspace(0, total_samples * ratio, total_samples, endpoint=False))
    wave = wave * float(sound.gain)
    return wave.astype(np.float32)


def test_sine_continuity():
    """Chunked rendering should match direct rendering with no discontinuities."""
    chunk_size = 1024
    num_chunks = 8
    sound = Sound(fade_in_samples=0, fade_out_samples=0)

    chunked = render_chunked(chunk_size, num_chunks, sound)
    direct = render_direct(chunk_size, num_chunks, sound)

    assert np.allclose(chunked, direct, atol=1e-5), \
        "Chunked audio does not match direct rendering — discontinuity detected!"
