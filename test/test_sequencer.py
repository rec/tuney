from threading import Event
from types import SimpleNamespace

import pytest

from tuney.time.char_press import CharPress
from tuney.time.sequencer import Sequencer


def test_clock_jumps_do_not_change_event_timing(monkeypatch) -> None:
    clock = SimpleNamespace(elapsed=0.0, wall=1000.0)
    waits: list[float] = []
    emitted: list[float] = []

    class Wait(Event):
        def wait(self, timeout: float | None = None) -> bool:
            assert timeout is not None
            assert len(waits) < 4
            waits.append(timeout)
            clock.elapsed += timeout
            clock.wall += 3600 if len(waits) % 2 else -7200
            return False

    monkeypatch.setattr(
        'tuney.time.sequencer.time',
        SimpleNamespace(
            monotonic=lambda: clock.elapsed,
            time=lambda: clock.wall,
        ),
    )
    sequence = Sequencer(
        char_presses=[CharPress('a', time=100), CharPress('a', False, 250)],
        callback=lambda c: emitted.append(clock.elapsed) if c is not None else None,
        stop_event=Wait(),
    )
    sequence.run()
    assert emitted == pytest.approx([0.1, 0.25])
    assert waits == pytest.approx([0.1, 0.1, 0.05])
