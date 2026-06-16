from tkinter import Tk

from tuney.ui.app import APP_NAME, set_app_name


def test_set_app_name():
    root = Tk()
    try:
        set_app_name(root)

        assert root.tk.call('tk', 'appname') == APP_NAME
    finally:
        root.destroy()
