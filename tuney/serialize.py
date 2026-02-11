import dataclasses as dc
from typing import Any


def serialize(x: Any) -> Any:
    if not dc.is_dataclass(x):
        return x

    res = {}
    for f in dc.fields(x):
        v = getattr(x, f.name)
        if not (v == f.default or (s := serialize(v)) in ([], {})):
            res[f.name] = s
    return res
