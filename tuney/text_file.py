from __future__ import annotations

from pathlib import Path

import chardet


class UnreadableTextFile(ValueError):
    pass


def read_text_file(path: Path) -> str:
    try:
        data = path.read_bytes()
        encoding = chardet.detect(data).get('encoding')
        if not isinstance(encoding, str):
            raise UnicodeError('could not detect text encoding')
        return data.decode(encoding)
    except Exception as error:
        message = f'Could not read text file {path}: unreadable file'
        raise UnreadableTextFile(message) from error
