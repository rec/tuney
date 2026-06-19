import pytest

from tuney.ui.transport import State, _record_state, _stop_state


@pytest.mark.parametrize(
    ('state', 'expected'),
    [
        (State.ready, State.recording),
        (State.recording, State.paused),
        (State.paused, State.recording),
    ],
)
def test_record_button_changes_transport_state(state: State, expected: State) -> None:
    assert _record_state(state) == expected


@pytest.mark.parametrize(
    ('state', 'expected'),
    [
        (State.ready, State.ready),
        (State.recording, State.ready),
        (State.paused, State.ready),
    ],
)
def test_stop_button_changes_transport_state(state: State, expected: State) -> None:
    assert _stop_state(state) == expected
