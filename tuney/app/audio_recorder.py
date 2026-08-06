from __future__ import annotations

import tempfile
import uuid
from collections.abc import Callable
from pathlib import Path
from shutil import move

from pydantic import BaseModel

from ..audio.player import Player
from ..ui.state import Action, State, StateChange
from .platform_info import instrument


class AudioRecorder(BaseModel):
    path: Path | None = None
    started: bool = False
    comment: Callable[[], str] | None = None

    def on_transport_state(
        self,
        change: StateChange,
        player: Player,
        comment_factory: Callable[[], Callable[[], str]],
        path: Path | None = None,
    ) -> bool:
        instrument(
            'audio recorder transport',
            old_state=change.old_state,
            state=change.state,
            action=change.action,
        )
        if change.action == Action.save:
            if path is None:
                return False
            if change.old_state == State.recording:
                self.stop(player)
            self.save(path)
        elif change.action == Action.clear:
            if change.old_state == State.recording:
                self.stop(player)
            self.clear()
        elif change.action == Action.stop:
            if change.old_state == State.recording:
                self.stop(player)
        elif change.state == State.paused:
            self.stop(player)
        else:
            self.start(player, comment_factory)
        return True

    def start(
        self, player: Player, comment_factory: Callable[[], Callable[[], str]]
    ) -> None:
        instrument('audio recorder start', has_path=self.path is not None)
        if self.path is None:
            self.path = Path(tempfile.gettempdir()) / f'tuney-{uuid.uuid4()}.wav'
            self.path.touch()
            self.comment = comment_factory()
        assert self.path is not None
        player.start_recording(
            self.path,
            self.comment,
            append=self.started,
        )
        self.started = True

    def stop(self, player: Player) -> None:
        instrument('audio recorder stop')
        player.stop_recording()

    def save(self, path: Path) -> None:
        instrument('audio recorder save', path=path)
        if self.path is None:
            return
        move(self.path, path)
        self._forget()

    def clear(self) -> None:
        instrument('audio recorder clear')
        if self.path is not None:
            self.path.unlink(missing_ok=True)
        self._forget()

    def _forget(self) -> None:
        self.path = None
        self.started = False
        self.comment = None
