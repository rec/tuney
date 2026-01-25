from tuney.text_timings import TextTimings

TEXT = """\
One, two.

Three!
"""


def test_text_timings():
    tt = TextTimings(other={"!": 2000}, seed=23)
    # actual = [int(i.time) for i in tt.lines_to_times(TEXT)]
    letters, times = zip(*tt.lines_to_times(TEXT))
    text = "".join(letters)
    times = [int(i) for i in times]
    assert text == "One, two.\nThree!"
    assert times == [
        127,
        77,
        62,
        399,
        231,
        164,
        153,
        184,
        448,
        1088,
        317,
        97,
        116,
        169,
        61,
        2104,
    ]
