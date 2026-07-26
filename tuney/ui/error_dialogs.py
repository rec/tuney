from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

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
    if (include_log := report_problem_include_log(main_window)) is None:
        return
    QDesktopServices.openUrl(
        QUrl(problem_issue_url(log_path(), include_log=include_log))
    )


def report_problem_include_log(main_window: MainWindow) -> bool | None:
    dialog = QDialog(main_window)
    dialog.setWindowTitle('Report a problem')

    include_log = QPushButton('Include log?', dialog)
    include_log.setCheckable(True)
    include_log.setChecked(False)

    toggle_layout = QHBoxLayout()
    toggle_layout.addWidget(include_log)
    toggle_layout.addWidget(
        QLabel('Turn this on if the problem just happened a few seconds ago', dialog)
    )

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.Cancel,
        dialog,
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)

    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel('Open an issue on Github?', dialog))
    layout.addLayout(toggle_layout)
    layout.addWidget(buttons)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return include_log.isChecked()


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
    main_window.show()
    main_window.raise_()
    main_window.activateWindow()
    dialog = QMessageBox(main_window)
    dialog.setIcon(QMessageBox.Icon.Question)
    dialog.setWindowTitle('File issue?')
    dialog.setText(
        'Tuney appears to have crashed during the previous run.\n\nFile issue?'
    )
    dialog.setStandardButtons(
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    dialog.setDefaultButton(QMessageBox.StandardButton.Yes)
    dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    reply = dialog.exec()
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
