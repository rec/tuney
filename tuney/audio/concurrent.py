from __future__ import annotations

import multiprocessing as mp
import threading
import traceback
from collections.abc import Sequence
from concurrent import futures
from functools import cached_property
from multiprocessing.synchronize import Event as MpEvent
from typing import Any, NamedTuple, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import Protocol


class StoppableFuture(NamedTuple):
    stoppable: Stoppable
    future: futures.Future | None = None

    def stop(self) -> None:
        self.stoppable.stop()


class Stoppable(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    event: MpEvent | threading.Event = Field(default_factory=threading.Event)

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


class Target(BaseModel, frozen=True):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    function: StoppableFunction
    args: Sequence[Any]
    kwargs: dict[str, Any]
    stoppable: Stoppable

    def model_post_init(self, __context: Any) -> None:
        assert callable(self.function), self

    def __call__(self) -> None:
        try:
            self.function(*self.args, stoppable=self.stoppable, **self.kwargs)
        except Exception:
            traceback.print_exc()
            raise


class Runner(BaseModel, frozen=True):
    model_config = ConfigDict(arbitrary_types_allowed=True)

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
            event=mp.Event() if self.use_multiprocessing else threading.Event()
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
