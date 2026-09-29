from collections import deque
from collections.abc import Callable
from threading import Lock

INPUT_QUEUE_CAPACITY = 256
INPUT_EVENTS_PER_TICK = 32


class InputQueue[T]:
    def __init__(
        self, capacity: int, is_press: Callable[[T], bool], key: Callable[[T], object]
    ) -> None:
        self.capacity = capacity
        self.is_press = is_press
        self.key = key
        self.items: deque[T] = deque()
        self.lock = Lock()

    def put(self, item: T) -> bool:
        with self.lock:
            if len(self.items) == self.capacity:
                if self.is_press(item):
                    return False
                for index, queued in enumerate(self.items):
                    if self.is_press(queued):
                        del self.items[index]
                        break
                else:
                    for index, queued in enumerate(self.items):
                        if self.key(queued) == self.key(item):
                            del self.items[index]
                            break
                    else:
                        self.items.popleft()
            self.items.append(item)
            return True

    def take(self, limit: int) -> list[T]:
        with self.lock:
            return [self.items.popleft() for _ in range(min(limit, len(self.items)))]

    def clear(self) -> None:
        with self.lock:
            self.items.clear()

    def __len__(self) -> int:
        with self.lock:
            return len(self.items)
