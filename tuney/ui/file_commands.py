from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import ValidationError
from PySide6.QtCore import QFile, QMimeData, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from ..app.app import (
    dump_data,
    dump_toml,
    load_text_file,
    note_events,
    output_comment,
    restore_data,
    restore_text,
    save,
    save_autosave,
)
from ..app.platform_info import instrument
from ..presets import delete_presets, read_file, write_preset
from .main_menu import OPEN_TEXT_FILE_COMMAND, SAVE_AS_AUDIO_COMMAND, SAVE_COMMAND
from .preset_dialogs import preset_name, selected_preset_names

if TYPE_CHECKING:
    from .main_window import MainWindow

CHAR_PRESSES_MIME = 'application/x-tuney-char-presses+json'


def on_open_text_file(main_window: MainWindow, *_: object) -> None:
    instrument('ui open text file')
    main_window._is_saving = True
    try:
        result = main_window._get_open_file_name(
            OPEN_TEXT_FILE_COMMAND,
            OPEN_TEXT_FILE_COMMAND,
            'Text (*.txt);;All files (*)',
        )
        if filename := result[0]:
            try:
                load_text_file(main_window.app, Path(filename))
            except (OSError, ValueError) as error:
                QMessageBox.critical(main_window, 'Open Text File', str(error))
    finally:
        main_window._is_saving = False
        main_window._has_focus = False


def on_save(main_window: MainWindow, *_: object) -> None:
    instrument('ui save')
    main_window._is_saving = True
    try:
        result = main_window._get_save_file_name(
            SAVE_COMMAND, SAVE_COMMAND, 'TOML (*.toml);;JSON (*.json)'
        )
        if filename := result[0]:
            try:
                save(main_window.app, Path(filename))
            except (OSError, ValueError) as error:
                QMessageBox.critical(main_window, 'Save', str(error))
    finally:
        main_window._is_saving = False
        main_window._has_focus = False


def on_save_as_audio(main_window: MainWindow, *_: object) -> None:
    instrument('ui save as audio')
    main_window._is_saving = True
    try:
        result = main_window._get_save_file_name(
            SAVE_AS_AUDIO_COMMAND,
            SAVE_AS_AUDIO_COMMAND,
            'WAV (*.wav);;All files (*)',
        )
        if filename := result[0]:
            try:
                main_window.app.player.render_file(
                    Path(filename),
                    note_events(main_window.app, main_window.app.player.sample_rate),
                    output_comment(main_window.app),
                )
            except (OSError, RuntimeError, ValueError) as error:
                QMessageBox.critical(main_window, SAVE_AS_AUDIO_COMMAND, str(error))
    finally:
        main_window._is_saving = False
        main_window._has_focus = False


def on_save_preset(main_window: MainWindow, *_: object) -> None:
    instrument('ui save preset')
    if (name := preset_name(main_window)) is None:
        return
    try:
        write_preset(name, dump_data(main_window.app))
    except (OSError, ValueError) as error:
        QMessageBox.critical(main_window, 'Save preset', str(error))
        return
    main_window.ui.rebuild_control_panel()


def on_delete_presets(main_window: MainWindow, *_: object) -> None:
    instrument('ui delete presets')
    if not (names := selected_preset_names(main_window)):
        return
    try:
        main_window.history.checkpoint_undo()
        delete_presets(names)
    except (OSError, ValueError) as error:
        QMessageBox.critical(main_window, 'Delete presets', str(error))
        return
    main_window.ui.rebuild_control_panel()


def on_open_config_folder(main_window: MainWindow, *_: object) -> None:
    instrument('ui open config folder')
    path = config_path(main_window)
    folder = path.expanduser().parent.resolve()
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        QMessageBox.critical(
            main_window,
            'Open enclosing folder for config file',
            f'Could not create {folder}:\n\n{error}',
        )
        return
    if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder))):
        QMessageBox.critical(
            main_window,
            'Open enclosing folder for config file',
            f'Could not open {folder}',
        )


def on_trash_config_file(main_window: MainWindow, *_: object) -> None:
    instrument('ui trash config file')
    path = config_path(main_window).expanduser().resolve()
    if not path.exists():
        QMessageBox.critical(
            main_window,
            'Put Config file in Trash',
            f'Config file does not exist:\n\n{path}',
        )
        return
    if not QFile.moveToTrash(str(path)):
        QMessageBox.critical(
            main_window,
            'Put Config file in Trash',
            f'Could not put config file in Trash:\n\n{path}',
        )


def config_path(main_window: MainWindow) -> Path:
    return main_window.app.config_file or main_window.app._autosave.path


def on_copy_from_state(main_window: MainWindow, *_: object) -> None:
    instrument('ui copy from state')
    main_window.qt_app.clipboard().setText(dump_toml(main_window.app))


def on_paste_into_state(main_window: MainWindow, *_: object) -> None:
    instrument('ui paste into state')
    try:
        main_window.history.checkpoint_undo()
        restore_text(main_window.app, main_window.qt_app.clipboard().text())
    except (ValueError, ValidationError) as error:
        QMessageBox.critical(main_window, 'Paste into state', str(error))
        return
    main_window.ui.rebuild_control_panel()
    main_window.ui.rebuild_note_grid()
    main_window.sync_config_actions()
    main_window.update_text_display()


def on_copy_text(main_window: MainWindow, *_: object) -> None:
    instrument('ui copy text')
    mime = QMimeData()
    mime.setText(main_window.app.display_text)
    mime.setData(
        CHAR_PRESSES_MIME,
        json.dumps([c.model_dump() for c in main_window.app.char_presses]).encode(),
    )
    main_window.qt_app.clipboard().setMimeData(mime)


def on_paste_text(main_window: MainWindow, *_: object) -> None:
    instrument('ui paste text')
    text = main_window.qt_app.clipboard().text()
    if not text:
        return
    main_window.history.checkpoint_undo()
    main_window.app.__dict__['char_presses'] = list(
        main_window.app.text_timings.char_presses(text)
    )
    main_window.app.key_recorder.clear()
    main_window.update_text_display()


def on_load_autosave(main_window: MainWindow, checked: bool) -> None:
    instrument('ui load autosave', checked=checked)
    if checked == main_window.app.load_autosave:
        return
    main_window.history.checkpoint_undo()
    main_window.app.load_autosave = checked


def on_swap_with_autosave(main_window: MainWindow, *_: object) -> None:
    instrument('ui swap with autosave')
    path = main_window.app._autosave.path
    try:
        data = read_file(path)
        type(main_window.app).model_validate(data)
    except (OSError, ValueError, ValidationError) as error:
        QMessageBox.critical(main_window, 'Swap with autosave', str(error))
        return
    try:
        main_window.history.checkpoint_undo()
        main_window.app._autosave.save(
            lambda path: save_autosave(main_window.app, path)
        )
        restore_data(main_window.app, data)
    except (OSError, ValueError, ValidationError) as error:
        QMessageBox.critical(main_window, 'Swap with autosave', str(error))
        return
    main_window.sync_config_actions()
    main_window.ui.rebuild_control_panel()
    main_window.ui.rebuild_note_grid()
    main_window.update_text_display()
