import subprocess
import sys
from textwrap import dedent


def test_qt_key_events() -> None:
    _run_app_key_script(
        """
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QKeyEvent

        from tuney.keyboard.char_press import CharPress
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

        from tuney.keyboard.char_press import CharPress
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


def test_app_mainloop_exits_on_sigint() -> None:
    _run_app_key_script(
        """
        import signal

        from tuney.ui import app as app_module
        from tuney.ui.app import App, SIGNAL_POLL_IN_MS

        calls = []
        handlers = []

        class Signal:
            def __init__(self):
                self.callback = None

            def connect(self, callback):
                self.callback = callback

        class FakeTimer:
            def __init__(self, parent):
                calls.append(('timer', parent))
                self.timeout = Signal()

            def start(self, delay):
                calls.append(('start', delay))

            def stop(self):
                calls.append('stop')

            def deleteLater(self):
                calls.append('delete')

        class FakeQtApp:
            def exec(self):
                handlers[-1][1](signal.SIGINT, None)
                calls.append('exec')

            def quit(self):
                calls.append('quit')

        app_module.QTimer = FakeTimer
        app_module.signal.getsignal = lambda signum: 'old'
        app_module.signal.signal = lambda signum, handler: handlers.append(
            (signum, handler)
        )

        app = type(
            'LoopApp',
            (),
            {
                'qt_app': FakeQtApp(),
                'activate': lambda self: calls.append('activate'),
                'close': lambda self: calls.append('close'),
                '_on_sigint': lambda self, signum, frame: App._on_sigint(
                    self, signum, frame
                ),
            },
        )()

        App.mainloop(app)

        assert calls == [
            ('timer', app),
            ('start', SIGNAL_POLL_IN_MS),
            'activate',
            'close',
            'quit',
            'exec',
            'stop',
            'delete',
        ]
        assert handlers[0][0] == signal.SIGINT
        assert callable(handlers[0][1])
        assert handlers[-1] == (signal.SIGINT, 'old')
        """
    )


def test_application_uses_cross_platform_style() -> None:
    _run_app_key_script(
        """
        from tuney.ui.app import _application

        app = _application()

        assert app.applicationName() == 'Tuney'
        assert app.style().objectName().lower() == 'fusion'
        """
    )


def test_app_activate_and_history() -> None:
    _run_app_key_script(
        """
        import os
        import tempfile
        from pathlib import Path

        from tuney.tuney import Tuney
        from tuney.keyboard.char_press import CharPress
        from tuney.ui import app as app_module
        from tuney.ui.app import App, LoopState

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
                self.loop_state = LoopState()
                self._undo_stack = []
                self._redo_stack = []

            @property
            def loop_replay(self):
                return App.loop_replay.fget(self)

            @loop_replay.setter
            def loop_replay(self, loop_replay):
                App.loop_replay.fset(self, loop_replay)

            @property
            def loop_before(self):
                return App.loop_before.fget(self)

            @loop_before.setter
            def loop_before(self, loop_before):
                App.loop_before.fset(self, loop_before)

            @property
            def loop_after(self):
                return App.loop_after.fget(self)

            @loop_after.setter
            def loop_after(self, loop_after):
                App.loop_after.fset(self, loop_after)

            @property
            def loop_tempo(self):
                return App.loop_tempo.fget(self)

            @loop_tempo.setter
            def loop_tempo(self, loop_tempo):
                App.loop_tempo.fset(self, loop_tempo)

            @property
            def randomize_on_each_loop(self):
                return App.randomize_on_each_loop.fget(self)

            @randomize_on_each_loop.setter
            def randomize_on_each_loop(self, randomize_on_each_loop):
                App.randomize_on_each_loop.fset(self, randomize_on_each_loop)

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

            def clear_settings(self):
                App.clear_settings(self)

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

        object.__setattr__(app.tuney, 'max_gap', 3.0)
        object.__setattr__(app.tuney, 'text', [CharPress('a', time=0.0)])
        app.tuney.__dict__.pop('char_presses', None)
        app.loop_replay = True
        app.loop_before = 0.25
        app.loop_after = 0.5
        app.loop_tempo = 2.0
        app.randomize_on_each_loop = True

        app.clear_settings()

        assert app.tuney.max_gap == Tuney().max_gap
        assert app.tuney.char_presses == []
        assert app.tuney.gui
        assert not app.loop_replay
        assert app.loop_before == 0.0
        assert app.loop_after == 0.0
        assert app.loop_tempo == 1.0
        assert not app.randomize_on_each_loop

        with tempfile.TemporaryDirectory() as tmp:
            os.environ['XDG_STATE_HOME'] = tmp
            messages = []

            class FakeMessageBox:
                @staticmethod
                def information(parent, title, text):
                    messages.append((parent, title, text))

            app_module.QMessageBox = FakeMessageBox
            App.on_show_log(app)

            assert messages == [
                (
                    app,
                    'Tuney log',
                    f'Log file:\\n\\n{Path(tmp) / "tuney" / "tuney.txt"}',
                )
            ]
        """
    )


def _run_app_key_script(script: str) -> None:
    subprocess.run(
        [sys.executable, '-c', dedent(script)],
        check=True,
        capture_output=True,
        text=True,
    )
