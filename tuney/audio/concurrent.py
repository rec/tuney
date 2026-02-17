from __future__ import annotations

import dataclasses as dc
import multiprocessing as mp
import threading
import traceback
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, runtime_checkable

from typing_extensions import Protocol

if TYPE_CHECKING:
    from multiprocessing.synchronize import Event


@dc.dataclass(frozen=True)
class Stoppable:
    event: Event | threading.Event = dc.field(default_factory=threading.Event)

    @property
    def is_running(self) -> bool:
        return not self.event.is_set()

    def stop(self) -> None:
        self.event.set()

    def wait(self) -> None:
        self.event.wait()


@runtime_checkable
class StoppableFunction(Protocol):
    def __call__(self, *args: Any, stoppable: Stoppable, **kwargs: Any) -> None: ...


@contextmanager
def print_exception() -> Generator[None]:
    try:
        yield
    except Exception:
        traceback.print_exc()


@dc.dataclass(frozen=True)
class Target:
    function: StoppableFunction
    args: Sequence[Any]
    kwargs: dict[str, Any]
    stoppable: Stoppable

    def __call__(self) -> None:
        with print_exception():
            self.function(*self.args, stoppable=self.stoppable, **self.kwargs)
        with print_exception():
            self.stoppable.stop()


def start(
    use_multiprocessing: bool, function: StoppableFunction, /, *args: Any, **kwargs: Any
) -> Stoppable:
    stoppable = Stoppable(mp.Event() if use_multiprocessing else threading.Event())
    runner = mp.Process if use_multiprocessing else threading.Thread

    target = Target(function=function, args=args, kwargs=kwargs, stoppable=stoppable)
    runner(target=target).start()
    return stoppable
