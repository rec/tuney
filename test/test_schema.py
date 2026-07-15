import inspect
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel

from tuney.config.simplify_data_class import simplify_data_class
from tuney.config.tuney import Tuney

MARKDOWN_PATH = Path('schema.md')
OMIT = (
    'extra_settings',
    'clip_off',
    'dither_off',
    'never_drop_input',
    'prime_output_buffers_using_stream_callback',
)

MARKDOWN_TEMPLATE = """\
# Tuney data classes

```
{}
```
"""


def find_models(m: type[BaseModel]) -> Iterable[type[BaseModel]]:
    yield m

    for f in m.model_fields.values():
        annotations = (a := f.annotation), *getattr(a, '__args__', ())
        for a in annotations:
            if isinstance(a, type) and issubclass(a, BaseModel):
                yield from find_models(a)


def test_schema(file_regression) -> None:
    files = {inspect.getfile(m): None for m in find_models(Tuney)}
    data = simplify_data_class(files, remove=OMIT)
    file_regression.check(MARKDOWN_TEMPLATE.format(data), fullpath=MARKDOWN_PATH)
