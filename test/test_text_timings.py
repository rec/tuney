import random

from tuney.time.char_press import CharPress
from tuney.time.sequencer import Sequencer
from tuney.time.text_timings import MAX_GENERATED_SEED, TextTimings


def test_text_timings():
    tt = TextTimings(other={'!': 2000}, seed=23)
    # actual = [int(i.time) for i in tt.lines_to_times(TEXT)]
    cps = list(tt.char_presses(TEXT))
    text = ''.join(e.char for e in cps if e.is_press)
    begins = [int(e.time) for e in cps if e.is_press]
    ends = [int(e.time) for e in cps if not e.is_press]
    assert (text, begins, ends) == ('One, .\nThree!', BEGINS, ENDS)


def test_text_timings_generates_and_stores_seed(
    monkeypatch,
) -> None:
    def randint(start: int, end: int) -> int:
        assert start == 0
        assert end == MAX_GENERATED_SEED
        return MAX_GENERATED_SEED

    monkeypatch.setattr(random, 'randint', randint)
    timings = TextTimings()

    actual = timings.random.random()

    assert timings.seed == MAX_GENERATED_SEED
    assert actual == random.Random(MAX_GENERATED_SEED).random()


def test_text_timings_sorts_overlapping_events() -> None:
    presses = list(TextTimings(seed=23).char_presses('Now is the time'))

    Sequencer(char_presses=presses, callback=lambda _: None)
    assert presses == sorted(presses, key=lambda press: press.time)


def test_sequencer_stop_wakes_waiting_thread() -> None:
    sequencer = Sequencer(
        char_presses=[CharPress('a', time=60_000)],
        callback=lambda _: None,
    )

    thread = sequencer.start()
    sequencer.stop()
    thread.join(timeout=1)

    assert not thread.is_alive()


TEXT = """\
One, 2.

Three!
"""
BEGINS = [0, 107, 165, 208, 587, 798, 1242, 2376, 2541, 2669, 2738, 3035, 3113]
ENDS = [127, 185, 228, 607, 818, 1262, 2396, 2561, 2689, 2758, 3055, 3133, 5229]
