from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from PySide6 import QtWidgets
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices

from ..app import platform_info

if TYPE_CHECKING:
    from .main_window import MainWindow


class ProblemReportOptions(NamedTuple):
    include_log: bool
    include_snapshot: bool


def on_show_log(main_window: MainWindow, *_: object) -> None:
    QtWidgets.QMessageBox.information(
        main_window,
        'Tuney log',
        f'Log file:\n\n{platform_info.log_path()}',
    )


def on_report_problem(main_window: MainWindow, *_: object) -> None:
    platform_info.instrument('ui report problem')
    if (options := report_problem_options(main_window)) is None:
        return
    snapshot_path = None
    if options.include_snapshot:
        try:
            snapshot_path = save_problem_snapshot(main_window)
        except OSError as error:
            QtWidgets.QMessageBox.warning(
                main_window, 'Could not save snapshot', str(error)
            )
    QDesktopServices.openUrl(
        QUrl(
            platform_info.problem_issue_url(
                platform_info.log_path(),
                include_log=options.include_log,
                snapshot_path=snapshot_path,
            )
        )
    )


def report_problem_options(main_window: MainWindow) -> ProblemReportOptions | None:
    dialog = QtWidgets.QDialog(main_window)
    dialog.setWindowTitle('Report a problem')

    include_log = QtWidgets.QPushButton('Include log?', dialog)
    include_log.setCheckable(True)
    include_log.setChecked(False)
    include_snapshot = QtWidgets.QPushButton('Include snapshot?', dialog)
    include_snapshot.setCheckable(True)
    include_snapshot.setChecked(False)

    toggle_layout = QtWidgets.QHBoxLayout()
    toggle_layout.addWidget(include_log)
    toggle_layout.addWidget(
        QtWidgets.QLabel(
            'Turn this on if the problem just happened a few seconds ago', dialog
        )
    )
    snapshot_layout = QtWidgets.QHBoxLayout()
    snapshot_layout.addWidget(include_snapshot)
    snapshot_layout.addWidget(
        QtWidgets.QLabel('Save a picture of the Tuney window', dialog)
    )

    buttons = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.StandardButton.Yes
        | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
        dialog,
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)

    layout = QtWidgets.QVBoxLayout(dialog)
    layout.addWidget(QtWidgets.QLabel('Open an issue on Github?', dialog))
    layout.addLayout(toggle_layout)
    layout.addLayout(snapshot_layout)
    layout.addWidget(buttons)

    if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
        return None
    return ProblemReportOptions(
        include_log=include_log.isChecked(),
        include_snapshot=include_snapshot.isChecked(),
    )


def save_problem_snapshot(main_window: MainWindow) -> Path:
    path = problem_snapshot_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not main_window.ui.grab().save(str(path), 'PNG'):
        raise OSError(f'Could not save snapshot {path}')
    return path


def problem_snapshot_path() -> Path:
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    return platform_info.app_state_dir() / 'snapshots' / f'tuney-{timestamp}.png'


def show_restore_error(main_window: MainWindow, error: BaseException) -> None:
    path = platform_info.log_exception(error)
    dialog = QtWidgets.QMessageBox(main_window)
    dialog.setIcon(QtWidgets.QMessageBox.Icon.Critical)
    dialog.setWindowTitle('Could not restore saved state')
    dialog.setTextFormat(Qt.TextFormat.RichText)
    url = QUrl.fromLocalFile(str(path)).toString()
    dialog.setText(
        'Tuney could not fully restore its saved state and will continue with '
        'the available settings.<br><br>'
        f'<a href="{url}">Open the log file</a>'
    )
    if label := dialog.findChild(QtWidgets.QLabel):
        label.setOpenExternalLinks(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
    report = dialog.addButton(
        'Report Issue', QtWidgets.QMessageBox.ButtonRole.ActionRole
    )
    dialog.exec()
    if dialog.clickedButton() is report:
        QDesktopServices.openUrl(QUrl(platform_info.error_issue_url(error, path)))


def show_crash_report(main_window: MainWindow) -> None:
    path = platform_info.log_path()
    main_window.show()
    main_window.raise_()
    main_window.activateWindow()
    dialog = QtWidgets.QMessageBox(main_window)
    dialog.setIcon(QtWidgets.QMessageBox.Icon.Question)
    dialog.setWindowTitle('File issue?')
    dialog.setText(
        'Tuney appears to have crashed during the previous run.\n\nFile issue?'
    )
    dialog.setStandardButtons(
        QtWidgets.QMessageBox.StandardButton.Yes
        | QtWidgets.QMessageBox.StandardButton.No
    )
    dialog.setDefaultButton(QtWidgets.QMessageBox.StandardButton.Yes)
    dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    reply = dialog.exec()
    if reply == QtWidgets.QMessageBox.StandardButton.Yes:
        QDesktopServices.openUrl(QUrl(platform_info.crash_issue_url(path)))


def show_audio_error(main_window: MainWindow, error: str) -> None:
    dialog = QtWidgets.QMessageBox(main_window)
    dialog.setIcon(QtWidgets.QMessageBox.Icon.Critical)
    dialog.setWindowTitle('Audio error')
    dialog.setText(error)
    report = dialog.addButton(
        'Report Issue', QtWidgets.QMessageBox.ButtonRole.ActionRole
    )
    dialog.addButton(QtWidgets.QMessageBox.StandardButton.Ok)
    dialog.exec()
    if dialog.clickedButton() is report:
        QDesktopServices.openUrl(
            QUrl(platform_info.problem_issue_url(platform_info.log_path()))
        )
