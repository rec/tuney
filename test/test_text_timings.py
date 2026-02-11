from tuney.time.text_timings import TextTimings


def test_text_timings():
    tt = TextTimings(other={'!': 2000}, random_seed=23)
    # actual = [int(i.time) for i in tt.lines_to_times(TEXT)]
    events = list(tt.events(TEXT))
    text = ''.join(e.data.char for e in events if e.data.is_press)
    begins = [int(e.timestamp) for e in events if e.data.is_press]
    ends = [int(e.timestamp) for e in events if not e.data.is_press]
    assert (text, begins, ends) == ('One, .\nThree!', BEGINS, ENDS)


TEXT = """\
One, 2.

Three!
"""
BEGINS = [0, 107, 165, 208, 587, 798, 1242, 2376, 2541, 2669, 2738, 3035, 3113]
ENDS = [127, 185, 228, 607, 818, 1262, 2396, 2561, 2689, 2758, 3055, 3133, 5229]
