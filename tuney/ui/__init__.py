from enum import StrEnum, auto

from pydantic import BaseModel


class State(StrEnum):
    ready = auto()
    recording = auto()
    paused = auto()


class Action(StrEnum):
    record = auto()
    save = auto()
    clear = auto()


class StateChange(BaseModel, frozen=True):
    old_state: State
    state: State
    action: Action
