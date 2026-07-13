from __future__ import annotations

from pathlib import Path, PurePosixPath
from zipfile import ZipFile

import chardet
import tomlkit

from tuney.scale.ratios import Ratios

ROOT = Path(__file__).resolve().parent
SCALES_ZIP = ROOT / 'scales.zip'
SCALES_TOML = ROOT / 'scales.toml'


def main() -> None:
    scales = read_scales(SCALES_ZIP)
    SCALES_TOML.write_text(
        tomlkit.dumps({k: v.model_dump() for k, v in scales.items()})
    )


def read_scales(path: Path) -> dict[str, Ratios]:
    result: dict[str, Ratios] = {}
    with ZipFile(path) as archive:
        for name in sorted(i for i in archive.namelist() if i.endswith('.scl')):
            key = PurePosixPath(name).stem
            if key in result:
                raise ValueError(f'Duplicate scale name {key!r}')
            result[key] = scala_text_to_ratios(
                archive.read(name), PurePosixPath(name).name
            )
    return result


def scala_text_to_ratios(data: bytes, name: str = '') -> Ratios:
    text = _decode(data)
    lines = [i.strip() for i in text.splitlines() if not i.startswith('!')]
    while lines and not lines[-1]:
        lines.pop()
    desc, length, *names = lines
    if int(length) != len(names):
        raise ValueError(f'In file {name}: {length=} != {len(names)=}')
    it = (s[0] for n in names if (s := n.split()))
    return Ratios(
        text='; '.join(f'cents({s})' if '.' in s else s for s in it),
        name=name,
        desc=desc,
    )


def _decode(data: bytes) -> str:
    encoding = chardet.detect(data).get('encoding')
    if isinstance(encoding, str):
        try:
            return data.decode(encoding)
        except UnicodeError:
            pass
    return data.decode('latin-1')


if __name__ == '__main__':
    main()
