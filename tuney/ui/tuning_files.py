from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox

from ..app.platform_info import instrument
from ..scale.ratios import Ratios
from ..scale.table import Table
from ..scale.tuning import Computed, Tuning, Type
from .main_menu import EXPORT_TUNING_COMMAND, IMPORT_TUNING_COMMAND

if TYPE_CHECKING:
    from .main_window import MainWindow


def on_import_tuning(main_window: MainWindow, *_: object) -> None:
    instrument('ui import tuning')
    main_window._is_saving = True
    try:
        result = main_window._get_open_file_name(
            IMPORT_TUNING_COMMAND,
            'Import tuning',
            'Scala (*.scl);;All files (*)',
        )
        if filename := result[0]:
            try:
                main_window.history.checkpoint_undo()
                main_window._set_tuning(Ratios.read_scala_file(Path(filename)))
            except (OSError, ValueError) as error:
                QMessageBox.critical(main_window, 'Import tuning', str(error))
    finally:
        main_window._is_saving = False
        main_window._has_focus = False


def on_export_tuning(main_window: MainWindow, *_: object) -> None:
    instrument('ui export tuning')
    if (tuning := export_tuning_source(main_window.app.tuning)) is None:
        return

    main_window._is_saving = True
    try:
        result = main_window._get_save_file_name(
            EXPORT_TUNING_COMMAND,
            'Export tuning',
            'Scala (*.scl);;All files (*)',
        )
        if filename := result[0]:
            try:
                ratios = tuning if isinstance(tuning, Ratios) else tuning.as_ratios()
                ratios.write_scala_file(Path(filename))
            except (OSError, ValueError) as error:
                QMessageBox.critical(main_window, 'Export tuning', str(error))
    finally:
        main_window._is_saving = False
        main_window._has_focus = False


def set_tuning(main_window: MainWindow, tuning: Computed | Ratios | Table) -> None:
    instrument('ui set tuning', tuning=type(tuning).__name__)
    data = main_window.app.tuning.model_dump()
    match tuning:
        case Computed():
            data |= {'type': Type.computed, 'computed': tuning}
        case Ratios():
            data |= {'type': Type.ratios, 'ratios': tuning}
        case Table():
            data |= {'type': Type.table, 'table': tuning}
    validated = type(main_window.app.tuning).model_validate(data)
    for field in type(main_window.app.tuning).model_fields:
        setattr(main_window.app.tuning, field, getattr(validated, field))
    main_window.ui.rebuild_control_panel()
    main_window.app.midi.output.send_tuning_dump(
        main_window.app.scale, main_window.app.tuning
    )


def update_export_tuning_action(main_window: MainWindow) -> None:
    main_window.export_tuning_action.setEnabled(
        export_tuning_source(main_window.app.tuning) is not None
    )


def export_tuning_source(tuning: Tuning) -> Computed | Ratios | None:
    match tuning.type:
        case Type.computed:
            return tuning.computed
        case Type.ratios:
            return tuning.ratios
        case Type.table | None:
            return None
