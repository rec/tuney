import subprocess
import sys
from textwrap import dedent


def test_qt_key_events() -> None:
    _run_app_key_script(
        """
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QKeyEvent

        from tuney.char_press import CharPress
        from tuney.ui import app as app_module
        from tuney.ui.app import App, _event_char

        def key_event(key, text='', modifiers=Qt.KeyboardModifier.NoModifier,
                      event_type=QKeyEvent.Type.KeyPress):
            return QKeyEvent(event_type, key, modifiers, text)

        assert _event_char(key_event(Qt.Key.Key_CapsLock)) == ''
        assert _event_char(key_event(Qt.Key.Key_A, 'a')) == 'a'
        assert _event_char(
            key_event(Qt.Key.Key_A, 'a', Qt.KeyboardModifier.MetaModifier)
        ) == ''
        assert _event_char(key_event(Qt.Key.Key_Backspace)) == '\\b'
        assert _event_char(key_event(Qt.Key.Key_Return)) == '\\n'

        chars = []
        app = type('KeyApp', (), {})()
        app._key_chars = {}
        app.tuney = type('Tuney', (), {'on_char': chars.append})()
        app_module.time.time = iter([100.0, 100.25]).__next__

        App._on_key_event(app, key_event(Qt.Key.Key_A, 'A'), True)
        App._on_key_event(
            app, key_event(Qt.Key.Key_A, event_type=QKeyEvent.Type.KeyRelease), False
        )

        assert chars == [
            CharPress('A', time=100.0),
            CharPress('A', False, time=100.25),
        ]
        """
    )


def test_app_event_filter() -> None:
    _run_app_key_script(
        """
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QKeyEvent

        from tuney.char_press import CharPress
        from tuney.ui import app as app_module
        from tuney.ui.app import App

        def key_event(key, text=''):
            return QKeyEvent(
                QKeyEvent.Type.KeyPress,
                key,
                Qt.KeyboardModifier.NoModifier,
                text,
            )

        chars = []
        app = type('KeyApp', (), {})()
        app._key_chars = {}
        app.focus_in_control_panel = False
        app.tuney = type('Tuney', (), {'on_char': chars.append})()
        app._on_key_event = lambda event, is_press: App._on_key_event(
            app, event, is_press
        )
        app_module.time.time = lambda: 100.0

        assert App.eventFilter(app, app, key_event(Qt.Key.Key_A, 'a'))
        assert chars == [CharPress('a', time=100.0)]

        chars.clear()
        app.focus_in_control_panel = True
        assert not App.eventFilter(app, app, key_event(Qt.Key.Key_A, 'a'))
        assert chars == []
        """
    )


def test_app_activate_and_history() -> None:
    _run_app_key_script(
        """
        from tuney.tuney import Tuney
        from tuney.ui import app as app_module
        from tuney.ui.app import App

        calls = []
        app = type(
            'ActivateApp',
            (),
            {
                'show': lambda self: calls.append('show'),
                'raise_': lambda self: calls.append('raise'),
                'activateWindow': lambda self: calls.append('activate'),
                'setFocus': lambda self: calls.append('focus'),
                '_has_focus': False,
            },
        )()

        App.activate(app)
        assert calls == ['show', 'raise', 'activate', 'focus']
        assert app._has_focus

        class FakeLoop:
            def select(self):
                pass

            def deselect(self):
                pass

        class FakeLayout:
            loop = FakeLoop()
            randomize_on_each_loop = FakeLoop()

            def set_text(self, text):
                pass

            def rebuild_control_panel(self):
                pass

            def rebuild_note_grid(self):
                pass

            def refresh_loop_controls(self):
                pass

            def set_loop_state(self, loop_replay):
                if loop_replay:
                    self.loop.select()
                else:
                    self.loop.deselect()

            def set_randomize_on_each_loop_state(self, randomize_on_each_loop):
                if randomize_on_each_loop:
                    self.randomize_on_each_loop.select()
                else:
                    self.randomize_on_each_loop.deselect()

        class HistoryApp:
            def __init__(self):
                self.tuney = Tuney(max_gap=1.0)
                self.ui = FakeLayout()
                self._loop_replay = False
                self.loop_before = 0.0
                self.loop_after = 0.0
                self.loop_tempo = 1.0
                self.randomize_on_each_loop = False
                self._undo_stack = []
                self._redo_stack = []

            @property
            def loop_replay(self):
                return App.loop_replay.fget(self)

            def _history_state(self):
                return App._history_state(self)

            def _restore_history_state(self, state):
                App._restore_history_state(self, state)

            def record_undo(self):
                App.record_undo(self)

            def on_undo(self):
                App.on_undo(self)

            def on_redo(self):
                App.on_redo(self)

        app = HistoryApp()
        app.record_undo()
        object.__setattr__(app.tuney, 'max_gap', 2.0)
        app.loop_before = 0.5
        app.on_undo()

        assert app.tuney.max_gap == 1.0
        assert app.loop_before == 0.0

        app.on_redo()

        assert app.tuney.max_gap == 2.0
        assert app.loop_before == 0.5
        """
    )


def _run_app_key_script(script: str) -> None:
    subprocess.run(
        [sys.executable, '-c', dedent(script)],
        check=True,
        capture_output=True,
        text=True,
    )
