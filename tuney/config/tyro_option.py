from collections.abc import Callable

import tyro


def tyro_option(
    alias: str | None = None,
    name: str | None = None,
    metavar: str | None = None,
    constructor: type | Callable[..., object] | None = None,
    help_behavior_hint: str | Callable[[str], str] | None = None,
) -> object:
    aliases = [alias] if alias is not None else None
    return tyro.conf.arg(
        prefix_name=False,
        aliases=aliases,
        constructor=constructor,
        help_behavior_hint=help_behavior_hint,
        name=name,
        metavar=metavar,
    )
