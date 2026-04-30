from __future__ import annotations

import dataclasses as dc
import multiprocessing as mp
import threading
import traceback
from collections.abc import Sequence
from concurrent import futures
from functools import cached_property
from typing import TYPE_CHECKING, Any, NamedTuple, runtime_checkable

from typing_extensions import Protocol

if TYPE_CHECKING:
    from multiprocessing.synchronize import Event


class StoppableFuture(NamedTuple):
    stoppable: Stoppable
    future: futures.Future | None = None

    def stop(self) -> None:
        self.stoppable.stop()


@dc.dataclass  # OK
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


@dc.dataclass(frozen=True)  # OK
class Target:
    function: StoppableFunction
    args: Sequence[Any]
    kwargs: dict[str, Any]
    stoppable: Stoppable

    def __post_init__(self):
        assert callable(self.function), self

    def __call__(self) -> None:
        try:
            self.function(*self.args, stoppable=self.stoppable, **self.kwargs)
        except Exception:
            traceback.print_exc()
            raise


@dc.dataclass(frozen=True)  # OK
class Runner:
    function: StoppableFunction
    use_multiprocessing: bool
    use_pool: bool = False
    max_workers: int = 10

    @cached_property
    def executor(self) -> futures.Executor:
        mp = self.use_multiprocessing
        cls = futures.ThreadPoolExecutor if mp else futures.ProcessPoolExecutor
        return cls(max_workers=self.max_workers)

    def __call__(self, *args: Any, **kwargs: Any) -> StoppableFuture:
        stoppable = Stoppable(
            mp.Event() if self.use_multiprocessing else threading.Event()
        )
        target = Target(
            function=self.function, args=args, kwargs=kwargs, stoppable=stoppable
        )
        if self.use_pool:
            future = self.executor.submit(target)
        else:
            runner = mp.Process if self.use_multiprocessing else threading.Thread
            runner(target=target).start()
            future = None
        return StoppableFuture(stoppable, future)
