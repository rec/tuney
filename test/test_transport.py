import pytest

from tuney.ui.transport import State, _ready_state, _record_state


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
def test_stop_and_clear_buttons_change_transport_state(
    state: State, expected: State
) -> None:
    assert _ready_state(state) == expected
