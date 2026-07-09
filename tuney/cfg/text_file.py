from __future__ import annotations

from pathlib import Path

import chardet


def read_text_file(path: Path) -> str:
    data = path.read_bytes()
    encoding = chardet.detect(data).get('encoding')
    if not isinstance(encoding, str):
        raise UnicodeError('could not detect text encoding')
    return data.decode(encoding)
