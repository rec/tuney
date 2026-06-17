from tkinter import Misc
from typing import cast

from tuney.ui.app import APP_NAME, set_app_name


class FakeTk:
    def __init__(self) -> None:
        self.app_name = ''

    def call(self, *args: str) -> str:
        if args == ('tk', 'appname'):
            return self.app_name
        assert args == ('tk', 'appname', APP_NAME)
        self.app_name = APP_NAME
        return self.app_name


class FakeApp:
    def __init__(self) -> None:
        self.tk = FakeTk()


def test_set_app_name():
    app = FakeApp()

    set_app_name(cast(Misc, app))

    assert app.tk.call('tk', 'appname') == APP_NAME
