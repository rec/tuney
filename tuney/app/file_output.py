from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile


@contextmanager
def atomic_output(path: Path) -> Iterator[Path]:
    """Replace an output only after its writer has finished successfully."""
    with NamedTemporaryFile(
        prefix=f'.{path.stem}-', suffix=path.suffix, dir=path.parent, delete=False
    ) as file:
        temporary = Path(file.name)
    try:
        yield temporary
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
