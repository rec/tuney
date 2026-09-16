import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from PySide6.QtCore import QMimeData

from tuney.app.app import App
from tuney.app.key_recorder import KeyRecorder
from tuney.time.char_press import CharPress
from tuney.ui import startup
from tuney.ui.main_window import MainWindow
from tuney.ui.state import Action, State, StateChange


@contextmanager
def temporary_path() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as directory:
        yield Path(directory)


def on_transport_state(
    app: App,
    old_state: State,
    state: State,
    action: Action,
    path: Path | None = None,
) -> bool:
    return app.audio_recorder.on_transport_state(
        StateChange(old_state=old_state, state=state, action=action),
        app.player,
        lambda: app.output_comment(),
        path,
    )


def recorded_char_press(app: App, c: CharPress) -> CharPress:
    return app.key_recorder.recorded_char_press(c, app.char_presses, app.max_gap)


def set_autosave_file(monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    monkeypatch.setattr(startup, 'autosave_file', path)


class FakeApp:
    is_replaying = False
    is_saving = False
    loop_replay = False
    loop_before = 0.0
    loop_after = 0.0
    loop_tempo = 1.0
    randomize_on_each_loop = False
    has_focus = True
    focus_in_control_panel = False

    def __init__(self) -> None:
        self.after_calls: list[tuple[str, int, object, tuple[object, ...]]] = []
        self.cancelled_after_ids: list[str] = []
        self.undo_count = 0
        self.midi_device_monitor_start_count = 0
        self.history = self

    class layout:
        @staticmethod
        def set_text(_: str) -> None:
            pass

        @staticmethod
        def set_text_timings(_: list[list[str]]) -> None:
            pass

        @staticmethod
        def rebuild_control_panel() -> None:
            pass

        @staticmethod
        def rebuild_note_grid() -> None:
            pass

        @staticmethod
        def set_play_cursor(_: int | None) -> None:
            pass

        @staticmethod
        def set_active_text_timing(_: int | None) -> None:
            pass

        @staticmethod
        def start_loop_clock() -> None:
            pass

    ui = layout

    def update_text_display(self) -> None:
        pass

    def sync_config_actions(self) -> None:
        pass

    def on_midi_output_failed(self, error: str) -> None:
        self.__dict__.setdefault('midi_output_errors', []).append(error)

    def checkpoint_undo(self) -> None:
        self.undo_count += 1

    def recorder_state(self) -> KeyRecorder:
        return KeyRecorder()

    @contextmanager
    def text_edit(
        self, index: int = 0, recorder: KeyRecorder | None = None
    ) -> Iterator[None]:
        self.checkpoint_undo()
        yield

    @staticmethod
    def start() -> None:
        pass

    def start_midi_device_monitor(self) -> None:
        self.midi_device_monitor_start_count += 1

    def sync_midi_device_monitor(self) -> None:
        app = self.__dict__.get('app')
        if app is None or app.midi.input.enable or app.midi.output.enable:
            self.start_midi_device_monitor()

    def after(self, delay: int, callback: object, *args: object) -> str:
        after_id = f'after-{len(self.after_calls)}'
        self.after_calls.append((after_id, delay, callback, args))
        return after_id

    def after_cancel(self, after_id: str) -> None:
        self.cancelled_after_ids.append(after_id)

    @staticmethod
    def on_char(_: CharPress) -> None:
        pass

    @staticmethod
    def on_key(_: CharPress) -> None:
        pass


class _FakeClipboard:
    def __init__(self, text: str = '') -> None:
        self._text = text
        self.mime = None

    def setMimeData(self, mime: object) -> None:
        self.mime = mime

    def mimeData(self) -> QMimeData | None:
        return self.mime

    def text(self) -> str:
        return self._text


class _FakeQtApp:
    def __init__(self, clipboard: _FakeClipboard) -> None:
        self._clipboard = clipboard

    def clipboard(self) -> _FakeClipboard:
        return self._clipboard


class _TextClipboardWindow:
    def __init__(self, app: App, clipboard: _FakeClipboard) -> None:
        self.app = app
        self.qt_app = _FakeQtApp(clipboard)
        self.history = self
        self.undo_count = 0
        self.update_count = 0

    def checkpoint_undo(self) -> None:
        self.undo_count += 1

    @contextmanager
    def text_edit(self) -> Iterator[None]:
        self.checkpoint_undo()
        yield

    def update_text_display(self) -> None:
        self.update_count += 1


class _Geometry:
    def __init__(self, x: int, y: int, width: int, height: int) -> None:
        self._x = x
        self._y = y
        self._width = width
        self._height = height

    def x(self) -> int:
        return self._x

    def y(self) -> int:
        return self._y

    def width(self) -> int:
        return self._width

    def height(self) -> int:
        return self._height


class _Screen:
    def __init__(self, top: int) -> None:
        self.top = top

    def availableGeometry(self) -> _Geometry:
        return _Geometry(x=0, y=self.top, width=1920, height=1080)


class _ScreenWindow:
    def __init__(self, top: int) -> None:
        self._screen = _Screen(top)

    def screen(self) -> _Screen:
        return self._screen


class _AutosaveWindow:
    history: object

    def __init__(self, history: object) -> None:
        self.history = history

    @staticmethod
    def x() -> int:
        return 33

    @staticmethod
    def y() -> int:
        return 44

    @staticmethod
    def width() -> int:
        return 660

    @staticmethod
    def height() -> int:
        return 500

    @staticmethod
    def geometry() -> _Geometry:
        return _Geometry(x=10, y=20, width=640, height=480)

    @staticmethod
    def frameGeometry() -> _Geometry:
        return _Geometry(x=9, y=19, width=642, height=482)

    @staticmethod
    def normalGeometry() -> _Geometry:
        return _Geometry(x=11, y=21, width=638, height=478)

    @staticmethod
    def windowState() -> str:
        return 'window state'

    @staticmethod
    def isMaximized() -> bool:
        return False

    @staticmethod
    def isMinimized() -> bool:
        return False

    @staticmethod
    def isFullScreen() -> bool:
        return False

    geometry_log_data = MainWindow.geometry_log_data


class _ShortcutWindow:
    _key_chars: dict[int, str] = {}

    def __init__(self) -> None:
        self.calls: list[str] = []

    def on_copy_text(self) -> None:
        self.calls.append('copy')

    def on_paste_text(self) -> None:
        self.calls.append('paste')


class _FakeKeyEvent:
    def __init__(self, key: object, modifiers: object) -> None:
        self._key = key
        self._modifiers = modifiers
        self.accepted = False

    @staticmethod
    def isAutoRepeat() -> bool:
        return False

    def key(self) -> object:
        return self._key

    def modifiers(self) -> object:
        return self._modifiers

    def accept(self) -> None:
        self.accepted = True

    def ignore(self) -> None:
        self.accepted = False
