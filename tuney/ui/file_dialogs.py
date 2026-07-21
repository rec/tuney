from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QFileDialog

if TYPE_CHECKING:
    from .main_window import MainWindow


def get_open_file_name(
    main_window: MainWindow, command: str, title: str, filter_: str
) -> tuple[str, str]:
    result = QFileDialog.getOpenFileName(
        main_window,
        title,
        main_window.app.global_config.directory(command),
        filter_,
    )
    main_window.app.global_config.remember_directory(command, result[0])
    return result


def get_save_file_name(
    main_window: MainWindow, command: str, title: str, filter_: str
) -> tuple[str, str]:
    result = QFileDialog.getSaveFileName(
        main_window,
        title,
        main_window.app.global_config.directory(command),
        filter_,
    )
    main_window.app.global_config.remember_directory(command, result[0])
    return result
