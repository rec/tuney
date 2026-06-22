from enum import StrEnum, auto


class State(StrEnum):
    ready = auto()
    recording = auto()
    paused = auto()


class Action(StrEnum):
    record = auto()
    save = auto()
    clear = auto()
