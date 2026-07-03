from dataclasses import dataclass


@dataclass(frozen=True)
class Display:
    hidden: bool = False
    general: bool = False
    beginner: bool = False
    row: int | None = None
    order: int = 0
