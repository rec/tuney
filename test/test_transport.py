import pytest

from tuney.ui import Action, State
from tuney.ui.transport import Transport, _ready_state, _record_state


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


def test_stop_button_pauses_without_saving() -> None:
    changes: list[tuple[State, Action]] = []
    transport = type(
        'FakeTransport',
        (),
        {'_set_state': lambda self, state, action: changes.append((state, action))},
    )()

    Transport._on_stop(transport)

    assert changes == [(State.paused, Action.stop)]
