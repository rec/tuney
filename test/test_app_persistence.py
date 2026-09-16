import sys
import tomllib
from pathlib import Path

from tuney.app import platform_info
from tuney.app.app import App
from tuney.app.global_config import GlobalConfig
from tuney.audio.player import Player
from tuney.time.char_press import CharPress
from tuney.ui import main_window
from tuney.ui.history import History, LoopState, WindowState
from tuney.ui.main_window import MainWindow, visible_restored_window_state
from tuney.ui.theme import ThemeName

from .app_helpers import (
    _AutosaveWindow,
    _Geometry,
    _ScreenWindow,
    set_autosave_file,
    temporary_path,
)


def test_restore_data_restores_char_presses_and_model_values() -> None:
    app = App(max_gap=1.0, text=[CharPress('a', time=0)])

    app.restore_data(
        {'max_gap': 2.0, 'text': [CharPress('b', time=0).model_dump()]},
    )

    assert app.max_gap == 2.0
    assert app.char_presses == [CharPress('b', time=0)]


def test_restore_data_closes_cached_player(monkeypatch) -> None:
    app = App()
    player = app.player
    closed: list[Player] = []
    monkeypatch.setattr(Player, 'close', lambda self: closed.append(self))

    app.restore_data({'max_gap': 2.0})

    assert closed == [player]
    assert 'player' not in app.__dict__


def test_autosave_path_uses_xdg_state_home(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))

        assert App()._autosave.path == tmp_path / 'tuney' / 'state.toml'


def test_global_config_persists_dialog_directories() -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'global.toml'
        config = GlobalConfig(file=path)

        config.remember_directory('Open Text File', str(tmp_path / 'texts' / 'a.txt'))

        assert GlobalConfig.read(path).directories == {
            'Open Text File': str(tmp_path / 'texts')
        }


def test_global_config_persists_buffer_size() -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'global.toml'
        config = GlobalConfig(file=path)

        assert config.buffer_size == 32
        assert config.increase_buffer_size() == 64
        assert GlobalConfig.read(path).buffer_size == 64


def test_global_config_persists_control_panel_state() -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'global.toml'
        config = GlobalConfig(file=path)
        config.control_panel_sections['Tuney.sound'] = False
        config.control_panel_scroll = 120

        config.save()

        saved = GlobalConfig.read(path)
        assert saved.control_panel_sections == {'Tuney.sound': False}
        assert saved.control_panel_scroll == 120


def test_global_config_persists_theme() -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'global.toml'
        config = GlobalConfig(file=path, theme=ThemeName.dark)

        config.save()

        assert GlobalConfig.read(path).theme == ThemeName.dark


def test_global_config_clamps_saved_buffer_size() -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'global.toml'
        path.write_text('buffer_size = 46624\n')

        assert GlobalConfig.read(path).buffer_size == 4096
        assert tomllib.loads(path.read_text())['buffer_size'] == 4096


def test_global_config_stops_increasing_buffer_size_at_limit() -> None:
    with temporary_path() as tmp_path:
        config = GlobalConfig(buffer_size=4090, file=tmp_path / 'global.toml')

        assert config.increase_buffer_size() == 4096
        assert config.increase_buffer_size() == 4096


def test_configure_logging_sets_frozen_log_path(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        monkeypatch.setattr(sys, 'frozen', True, raising=False)
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
        calls: list[tuple[Path, str]] = []
        monkeypatch.setattr(
            platform_info.logging,
            'configure',
            lambda path, *, service_name: calls.append((path, service_name)),
        )

        platform_info.configure_logging()

        assert calls == [(tmp_path / 'tuney' / 'tuney.log', 'tuney')]


def test_autosave_writes_current_model_without_app_state(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'state.toml'
        set_autosave_file(monkeypatch, path)
        app = App(
            gui=True,
            max_gap=2.0,
            text=[
                CharPress('a', time=0),
                CharPress('a', False, 100),
            ],
        )

        app._autosave.save(lambda path: app.save(path))

        data = tomllib.loads(path.read_text())
    assert data['gui']
    assert data['max_gap'] == 2.0
    assert data['text'] == [
        {'char': 'a', 'is_press': True, 'time': 0},
        {'char': 'a', 'is_press': False, 'time': 100},
    ]
    assert 'autosave_file' not in data
    assert 'is_replaying' not in data
    assert 'loop_replay' not in data


def test_autosave_writes_loop_state_and_geometry_window_state(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'state.toml'
        set_autosave_file(monkeypatch, path)
        app = App(gui=True, max_gap=2.0)
        history = type(
            'History',
            (),
            {
                'loop_state': LoopState(
                    replay=True,
                    before=0.5,
                    after=0.25,
                    tempo=2.0,
                    randomize_on_each_loop=True,
                )
            },
        )()
        window = _AutosaveWindow(history)
        app.__dict__['main_window'] = window

        app._autosave.save(app.save_autosave)

        data = tomllib.loads(path.read_text())

    assert {'x': window.x(), 'y': window.y()} == {'x': 33, 'y': 44}
    assert data['max_gap'] == 2.0
    assert data['loop'] == {
        'replay': True,
        'before': 0.5,
        'after': 0.25,
        'tempo': 2.0,
        'randomize_on_each_loop': True,
    }
    assert data['window'] == {'x': 10, 'y': 20, 'width': 640, 'height': 480}


def test_main_window_geometry_log_data_records_direct_and_geometry_values() -> None:
    window = _AutosaveWindow(object())

    assert MainWindow.geometry_log_data(window) == {
        'direct': {'x': 33, 'y': 44, 'width': 660, 'height': 500},
        'geometry': {'x': 10, 'y': 20, 'width': 640, 'height': 480},
        'frame_geometry': {'x': 9, 'y': 19, 'width': 642, 'height': 482},
        'normal_geometry': {'x': 11, 'y': 21, 'width': 638, 'height': 478},
        'window_state': 'window state',
        'is_maximized': False,
        'is_minimized': False,
        'is_full_screen': False,
    }


def test_restore_autosave_restores_gui_state_without_explicit_startup_data(
    monkeypatch,
) -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'state.toml'
        set_autosave_file(monkeypatch, path)
        saved = App(
            gui=True,
            max_gap=2.0,
            text=[
                CharPress('a', time=0),
                CharPress('a', False, 100),
            ],
        )
        saved._autosave.save(saved.save)
        app = App(gui=True)

        app._autosave.restore(app)

        assert app.max_gap == 2.0
        assert app.char_presses == [
            CharPress('a', time=0),
            CharPress('a', False, 100),
        ]


def test_restore_autosave_restores_loop_state(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'state.toml'
        set_autosave_file(monkeypatch, path)
        path.write_text(
            'gui = true\n'
            '\n'
            '[loop]\n'
            'replay = true\n'
            'before = 0.5\n'
            'after = 0.25\n'
            'tempo = 2.0\n'
            'randomize_on_each_loop = true\n'
            '\n'
            '[window]\n'
            'x = 10\n'
            'y = 20\n'
            'width = 640\n'
            'height = 480\n'
        )
        app = App(gui=True)

        error = app._autosave.restore(app)
        history = History(type('Window', (), {'app': app})())

    assert error is None
    assert history.loop_state == LoopState(
        replay=True,
        before=0.5,
        after=0.25,
        tempo=2.0,
        randomize_on_each_loop=True,
    )
    assert app.__dict__['_autosave_window_state'] == WindowState(
        x=10, y=20, width=640, height=480
    )


def test_main_window_restores_autosaved_window_state(monkeypatch) -> None:
    monkeypatch.setattr(main_window.QtWidgets.QApplication, 'instance', lambda: None)
    app = App(gui=True)
    app.__dict__['_autosave_window_state'] = WindowState(
        x=10, y=20, width=640, height=480
    )
    window = type(
        'Window',
        (),
        {
            'app': app,
            'set_geometry': None,
            'enforce_count': 0,
            '_restored_window_state': None,
            'x': lambda self: 0,
            'y': lambda self: 0,
            'width': lambda self: 0,
            'height': lambda self: 0,
            'geometry': lambda self: _Geometry(x=0, y=0, width=0, height=0),
            'frameGeometry': lambda self: _Geometry(x=0, y=0, width=0, height=0),
            'normalGeometry': lambda self: _Geometry(x=0, y=0, width=0, height=0),
            'windowState': lambda self: 'window state',
            'isMaximized': lambda self: False,
            'isMinimized': lambda self: False,
            'isFullScreen': lambda self: False,
            'setGeometry': lambda self, *args: setattr(self, 'set_geometry', args),
            'enforce_minimum_size': lambda self: setattr(
                self, 'enforce_count', self.enforce_count + 1
            ),
            'geometry_log_data': MainWindow.geometry_log_data,
            '_apply_restored_window_state': MainWindow._apply_restored_window_state,
        },
    )()

    MainWindow._restore_window_state(window)

    assert window.set_geometry == (10, 20, 640, 480)
    assert window.enforce_count == 1
    assert window._restored_window_state == WindowState(
        x=10, y=20, width=640, height=480
    )
    assert '_autosave_window_state' not in app.__dict__


def test_restored_window_state_keeps_menu_reachable() -> None:
    state = WindowState(x=10, y=-80, width=640, height=480)

    visible = visible_restored_window_state(_ScreenWindow(top=0), state)

    assert visible == WindowState(x=10, y=0, width=640, height=480)


def test_restored_window_state_keeps_visible_top_edge() -> None:
    state = WindowState(x=10, y=25, width=640, height=480)

    visible = visible_restored_window_state(_ScreenWindow(top=0), state)

    assert visible is state


def test_restore_autosave_skips_when_startup_modifier_is_held(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'state.toml'
        set_autosave_file(monkeypatch, path)
        saved = App(gui=True, max_gap=2.0)
        saved._autosave.save(saved.save)
        app = App(gui=True)
        monkeypatch.setattr(
            'tuney.presets.autosave.startup_modifier_held', lambda: True
        )

        app._autosave.restore(app)

        assert app.max_gap == App().max_gap


def test_restore_autosave_skips_when_saved_state_disables_autosave(
    monkeypatch,
) -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'state.toml'
        set_autosave_file(monkeypatch, path)
        saved = App(gui=True, max_gap=2.0, load_autosave=False)
        saved._autosave.save(saved.save)
        app = App(gui=True, max_gap=3.0)

        app._autosave.restore(app)

        assert app.max_gap == App().max_gap
        assert not app.load_autosave


def test_restore_autosave_ignores_invalid_state_file(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'state.toml'
        set_autosave_file(monkeypatch, path)
        path.write_text('max_gap =')
        app = App(gui=True)

        error = app._autosave.restore(app)

        assert app.max_gap == App().max_gap
    assert error is not None
    assert f'Could not restore {path}' in str(error)


def test_restore_autosave_defaults_invalid_fields(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'state.toml'
        set_autosave_file(monkeypatch, path)
        path.write_text('max_gap = "bad"\nhover_time = 2.0\n')
        app = App(gui=True)

        error = app._autosave.restore(app)

        assert app.max_gap == App().max_gap
        assert app.hover_time == 2.0
    assert error is not None
    assert f'Could not restore fields from {path}' in str(error)
    assert 'max_gap' in str(error)


def test_restore_autosave_defaults_invalid_nested_scale(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'state.toml'
        set_autosave_file(monkeypatch, path)
        path.write_text(
            '\n'.join(
                [
                    'hover_time = 2.0',
                    '[scale]',
                    'note_names = "AB"',
                    'root = "C"',
                    'begin = "A"',
                    'end = "B"',
                ]
            )
        )
        app = App(gui=True)

        error = app._autosave.restore(app)

        assert app.hover_time == 2.0
        assert app.scale == App().scale
    assert error is not None
    assert f'Could not restore fields from {path}' in str(error)
    assert 'root must be present in note_names' in str(error)


def test_restore_autosave_defaults_empty_ratios(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'state.toml'
        set_autosave_file(monkeypatch, path)
        path.write_text(
            '\n'.join(
                [
                    '[tuning]',
                    'type = "ratios"',
                    '[tuning.ratios]',
                    'text = ""',
                ]
            )
        )
        app = App(gui=True)

        error = app._autosave.restore(app)

        assert app.tuning.ratios is None
        assert app.tuning(69) == 440
    assert error is not None
    assert f'Could not restore fields from {path}' in str(error)
    assert 'No tuning ratios configured' in str(error)


def test_restore_autosave_does_not_override_explicit_text(monkeypatch) -> None:
    with temporary_path() as tmp_path:
        path = tmp_path / 'state.toml'
        set_autosave_file(monkeypatch, path)
        saved = App(gui=True, text=[CharPress('a', time=0)])
        saved._autosave.save(saved.save)
        app = App(gui=True, text='b')

        app._autosave.restore(app)

        assert app.display_text == 'b'
