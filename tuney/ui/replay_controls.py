from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..app.platform_info import instrument
from . import Action, StateChange
from .main_menu import SAVE_AUDIO_COMMAND

if TYPE_CHECKING:
    from .main_window import MainWindow


def on_transport_state(main_window: MainWindow, change: StateChange) -> bool:
    instrument(
        'ui transport state',
        old_state=change.old_state,
        state=change.state,
        action=change.action,
    )
    filename = ''
    if change.action == Action.save:
        main_window._is_saving = True
        try:
            result = main_window._get_save_file_name(
                SAVE_AUDIO_COMMAND,
                SAVE_AUDIO_COMMAND,
                'WAV (*.wav)',
            )
            filename = result[0]
        finally:
            main_window._is_saving = False
            main_window._has_focus = False
    path = Path(filename) if filename else None
    return main_window.app.audio_recorder.on_transport_state(
        change,
        main_window.app.player,
        main_window.app.output_comment,
        path,
    )


def is_replaying(main_window: MainWindow) -> bool:
    return main_window._is_replaying


def set_is_replaying(main_window: MainWindow, is_replaying: bool) -> None:
    if main_window._is_replaying != is_replaying:
        instrument('ui replay state', is_replaying=is_replaying)
        main_window._is_replaying = is_replaying
        main_window.ui.set_replay_state(is_replaying)
        main_window.app.on_replay()


def on_replay(main_window: MainWindow, *_: object) -> None:
    instrument('ui replay button')
    main_window.is_replaying = not main_window.is_replaying


def on_loop_replay(main_window: MainWindow, checked: bool) -> None:
    instrument('ui loop replay', checked=checked)
    if checked != main_window.history.loop_replay:
        main_window.history.checkpoint_undo()
        main_window.history.loop_replay = checked


def on_master_gain(main_window: MainWindow, master_gain: float) -> None:
    instrument('ui master gain', master_gain=master_gain)
    main_window.app.player.set_master_gain(master_gain)


def on_loop_tempo(main_window: MainWindow, tempo: float | str) -> None:
    instrument('ui loop tempo', tempo=tempo)
    try:
        value = float(tempo)
    except ValueError:
        return
    if value > 0 and value != main_window.history.loop_tempo:
        main_window.history.checkpoint_undo()
        main_window.history.loop_tempo = value


def on_loop_before(main_window: MainWindow, before: str) -> None:
    instrument('ui loop before', before=before)
    if (
        value := _float_or_none(before)
    ) is not None and value != main_window.history.loop_before:
        main_window.history.checkpoint_undo()
        main_window.history.loop_before = value


def on_loop_after(main_window: MainWindow, after: str) -> None:
    instrument('ui loop after', after=after)
    if (
        value := _float_or_none(after)
    ) is not None and value != main_window.history.loop_after:
        main_window.history.checkpoint_undo()
        main_window.history.loop_after = value


def on_randomize_on_each_loop(main_window: MainWindow, checked: bool) -> None:
    instrument('ui randomize on each loop', checked=checked)
    if checked != main_window.history.randomize_on_each_loop:
        main_window.history.checkpoint_undo()
        main_window.history.randomize_on_each_loop = checked


def _float_or_none(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None
