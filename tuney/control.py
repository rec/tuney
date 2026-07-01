from dataclasses import dataclass


@dataclass(frozen=True)
class Control:
    hidden: bool = False
    general: bool = False
    beginner: bool = False
    row: int | None = None
    order: int = 0


def control(
    *,
    hidden: bool = False,
    general: bool = False,
    beginner: bool = False,
    row: int | None = None,
    order: int = 0,
) -> Control:
    return Control(
        hidden=hidden,
        general=general,
        beginner=beginner,
        row=row,
        order=order,
    )
