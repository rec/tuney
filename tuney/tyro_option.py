from typing import Any

import tyro


def tyro_option(alias: str | None = None, **kwargs: Any) -> Any:
    aliases = [alias] if alias is not None else None
    return tyro.conf.arg(prefix_name=False, aliases=aliases, **kwargs)
