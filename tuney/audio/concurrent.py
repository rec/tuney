from __future__ import annotations

import threading

from pydantic import BaseModel, ConfigDict, Field


class Stoppable(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    event: threading.Event = Field(default_factory=threading.Event)

    @property
    def is_running(self) -> bool:
        return not self.event.is_set()

    def stop(self) -> None:
        self.event.set()

    def wait(self) -> None:
        self.event.wait()
