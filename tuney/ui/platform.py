from __future__ import annotations


def command_key(platform: str) -> str:
    return 'Command' if platform == 'darwin' else 'Ctrl'
