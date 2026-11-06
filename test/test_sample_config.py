from typing import TYPE_CHECKING

from tuney.app.global_config import GlobalConfig

if TYPE_CHECKING:
    from reccy.pytest_plugin import SampleConfigRegression


def test_sample_config(sample_config_regression: 'SampleConfigRegression') -> None:
    sample_config_regression(GlobalConfig)
