from pathlib import Path

from pytest_regressions.file_regression import FileRegressionFixture

from tuney.config.simplify_data_class import simplify_data_class


def test_simplify_data_class_simplifies_pydantic_classes_only(
    tmp_path: Path, file_regression: FileRegressionFixture
) -> None:
    path = tmp_path / 'models.py'
    path.write_text(
        """
from functools import cached_property
from typing import Annotated

from pydantic import BaseModel, Field

from tuney.config.display import Hidden


class Plain:
    x: int = 1

    def method(self) -> int:
        return self.x


class First(BaseModel, frozen=True):
    a: Annotated[int, Field(gt=0)] = 1
    b: Annotated[str, Hidden] = 'hide'
    c: float
    f: int = Field(32, gt=0)
    _private: int = 3
    removed: str = 'drop'

    @property
    def prop(self) -> int:
        return self.a

    @cached_property
    def cached(self) -> int:
        return self.a

    def method(self) -> int:
        return self.a

    @classmethod
    def class_method(cls) -> int:
        return 1

    @staticmethod
    def static_method() -> int:
        return 2


class Second(First):
    d: Annotated[int, Hidden] = 2
    e: str = 'keep'
"""
    )

    file_regression.check(
        simplify_data_class([path], remove={'removed'}), extension='.py.out'
    )


def test_simplify_tuney(file_regression: FileRegressionFixture) -> None:
    file_regression.check(
        simplify_data_class(
            [Path('tuney/config/tuney.py'), Path('tuney/scale/tuning.py')]
        ),
        extension='.py.out',
    )
