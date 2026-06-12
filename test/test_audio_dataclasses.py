import threading

import numpy as np

from tuney.audio.concurrent import Runner, Stoppable
from tuney.audio.oscillator_player import OscillatorPlayer, Sound
from tuney.audio.sample_data import SampleData


def _stop(stoppable: Stoppable) -> None:
    stoppable.stop()


def test_sample_data_reports_channels_and_cuts_from_center():
    data = np.arange(8).reshape((4, 2))
    sample_data = SampleData(data=data, samplerate=2)

    device = sample_data.device('speaker')
    cut = sample_data.cut_to(1)

    assert sample_data.channels == 2
    assert device.channels == 2
    assert device.device == 'speaker'
    assert device.samplerate == 2
    np.testing.assert_array_equal(cut.data, data[1:3])


def test_runner_starts_target_with_stoppable():
    runner = Runner(function=_stop, use_multiprocessing=False)
    stoppable_future = runner()
    assert stoppable_future.stoppable.event.wait(1)

    assert stoppable_future.future is None
    assert not stoppable_future.stoppable.is_running


def test_stoppable_wait_blocks_until_stop():
    stoppable = Stoppable()
    waiter = threading.Thread(target=stoppable.wait)

    waiter.start()
    stoppable.stop()
    waiter.join(timeout=1)
    assert not waiter.is_alive()


def test_oscillator_player_fill_advances_frame_counters():
    player = OscillatorPlayer(
        oscillator_name='sine',
        sound=Sound(period=8, fade_in_samples=0, fade_out_samples=0),
    )
    out = np.zeros((4, 1))

    assert player.fill(out, frame_size=4)
    assert player.chunk_count == 1
    assert player.frame_count == 4
    assert player.frame_size == 4
    assert np.any(out)
