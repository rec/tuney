from __future__ import annotations

import tempfile
import uuid
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from ..audio.multi_player import MultiPlayer
from ..ui.transport import Action, State


class AudioRecorder(BaseModel):
    path: Path | None = None
    started: bool = False
    comment: Callable[[], str] | None = None

    def on_transport_state(
        self,
        old_state: State,
        state: State,
        action: Action,
        player: MultiPlayer,
        comment_factory: Callable[[], Callable[[], str]],
        path: Path | None = None,
    ) -> bool:
        if action == Action.save:
            if path is None:
                return False
            if old_state == State.recording:
                self.stop(player)
            self.save(path)
        elif action == Action.clear:
            if old_state == State.recording:
                self.stop(player)
            self.clear()
        elif state == State.paused:
            self.stop(player)
        else:
            self.start(player, comment_factory)
        return True

    def start(
        self, player: MultiPlayer, comment_factory: Callable[[], Callable[[], str]]
    ) -> None:
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

    def stop(self, player: MultiPlayer) -> None:
        player.stop_recording()

    def save(self, path: Path) -> None:
        if self.path is None:
            return
        self.path.replace(path)
        self._forget()

    def clear(self) -> None:
        if self.path is not None:
            self.path.unlink(missing_ok=True)
        self._forget()

    def _forget(self) -> None:
        self.path = None
        self.started = False
        self.comment = None
