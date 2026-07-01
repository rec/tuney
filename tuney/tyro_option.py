from typing import Any

import tyro


def tyro_option(**kwargs: Any) -> Any:
    return tyro.conf.arg(prefix_name=False, **kwargs)
