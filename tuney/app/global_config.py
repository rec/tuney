from __future__ import annotations

import tomllib
from functools import cached_property
from pathlib import Path

import tomlkit
from pydantic import BaseModel, Field, field_validator

from .platform_info import app_config_dir, report_error

GLOBAL_CONFIG_FILE = 'global.toml'
BUFFER_SIZE_MIN = 32
BUFFER_SIZE_MAX = 4096
BUFFER_SIZE_INCREMENT = 32


class GlobalConfig(BaseModel):
    directories: dict[str, str] = Field(default_factory=dict)
    buffer_size: int = BUFFER_SIZE_MIN
    file: Path | None = Field(default=None, exclude=True)

    @cached_property
    def path(self) -> Path:
        return self.file or app_config_dir() / GLOBAL_CONFIG_FILE

    @classmethod
    def read(cls, path: Path | None = None) -> GlobalConfig:
        file = path or app_config_dir() / GLOBAL_CONFIG_FILE
        if not file.exists():
            return cls(file=file)
        try:
            data = tomllib.loads(file.read_text())
            config = cls.model_validate(data | {'file': file})
            if data.get('buffer_size') != config.buffer_size:
                try:
                    config.save()
                except OSError as error:
                    report_error(f'Could not save global config {file}: {error}')
            return config
        except (OSError, ValueError) as error:
            report_error(f'Could not read global config {file}: {error}')
            return cls(file=file)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            tomlkit.dumps(
                {'directories': self.directories, 'buffer_size': self.buffer_size}
            )
        )

    def directory(self, name: str) -> str:
        return self.directories.get(name, '')

    def remember_directory(self, name: str, filename: str) -> None:
        if not filename:
            return
        self.directories[name] = str(Path(filename).parent)
        try:
            self.save()
        except OSError as error:
            report_error(f'Could not save global config {self.path}: {error}')

    def increase_buffer_size(self) -> int:
        self.buffer_size = min(
            self.buffer_size + BUFFER_SIZE_INCREMENT, BUFFER_SIZE_MAX
        )
        try:
            self.save()
        except OSError as error:
            report_error(f'Could not save global config {self.path}: {error}')
        return self.buffer_size

    @field_validator('buffer_size', mode='before')
    @classmethod
    def _validate_buffer_size(cls, value: object) -> object:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return min(max(value, BUFFER_SIZE_MIN), BUFFER_SIZE_MAX)
        return value
