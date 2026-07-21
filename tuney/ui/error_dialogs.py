from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel, QMessageBox

from ..app.platform_info import (
    crash_issue_url,
    error_issue_url,
    instrument,
    log_exception,
    log_path,
    problem_issue_url,
)

if TYPE_CHECKING:
    from .main_window import MainWindow


def on_show_log(main_window: MainWindow, *_: object) -> None:
    QMessageBox.information(
        main_window,
        'Tuney log',
        f'Log file:\n\n{log_path()}',
    )


def on_report_problem(main_window: MainWindow, *_: object) -> None:
    instrument('ui report problem')
    QDesktopServices.openUrl(QUrl(problem_issue_url(log_path())))


def show_restore_error(main_window: MainWindow, error: BaseException) -> None:
    path = log_exception(error)
    dialog = QMessageBox(main_window)
    dialog.setIcon(QMessageBox.Icon.Critical)
    dialog.setWindowTitle('Could not restore saved state')
    dialog.setTextFormat(Qt.TextFormat.RichText)
    url = QUrl.fromLocalFile(str(path)).toString()
    dialog.setText(
        'Tuney could not fully restore its saved state and will continue with '
        'the available settings.<br><br>'
        f'<a href="{url}">Open the log file</a>'
    )
    if label := dialog.findChild(QLabel):
        label.setOpenExternalLinks(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
    report = dialog.addButton('Report Issue', QMessageBox.ButtonRole.ActionRole)
    dialog.exec()
    if dialog.clickedButton() is report:
        QDesktopServices.openUrl(QUrl(error_issue_url(error, path)))


def show_crash_report(main_window: MainWindow) -> None:
    path = log_path()
    reply = QMessageBox.question(
        main_window,
        'File issue?',
        'Tuney appears to have crashed during the previous run.\n\nFile issue?',
    )
    if reply == QMessageBox.StandardButton.Yes:
        QDesktopServices.openUrl(QUrl(crash_issue_url(path)))


def show_audio_error(main_window: MainWindow, error: str) -> None:
    dialog = QMessageBox(main_window)
    dialog.setIcon(QMessageBox.Icon.Critical)
    dialog.setWindowTitle('Audio error')
    dialog.setText(error)
    report = dialog.addButton('Report Issue', QMessageBox.ButtonRole.ActionRole)
    dialog.addButton(QMessageBox.StandardButton.Ok)
    dialog.exec()
    if dialog.clickedButton() is report:
        QDesktopServices.openUrl(QUrl(problem_issue_url(log_path())))
