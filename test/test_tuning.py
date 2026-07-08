import pytest
from pydantic import ValidationError

from tuney.scale.ratios import Ratios
from tuney.scale.tuning import Tuning


def test_tuning_rejects_table_and_ratios() -> None:
    with pytest.raises(ValidationError, match='only one explicit tuning source'):
        Tuning(table=[440], ratios=Ratios(ratios=[2]))


def test_tuning_uses_table_when_present() -> None:
    assert not Tuning(table=[440]).ratios.ratios
    assert Tuning(table=[440])(0) == 440


def test_tuning_uses_computed_when_ratios_are_empty() -> None:
    assert Tuning()(69) == 440
