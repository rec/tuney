from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QMessageBox, QProgressDialog

from ..app.export_job import ExportJob

if TYPE_CHECKING:
    from .main_window import MainWindow


class ExportDialog(QProgressDialog):
    def __init__(
        self,
        window: MainWindow,
        path: Path,
        title: str,
        presets: list[str] | None = None,
    ) -> None:
        super().__init__('Preparing export', 'Cancel', 0, 100, window)
        self.main_window = window
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setAutoClose(False)
        self.setAutoReset(False)
        self.setMinimumDuration(0)
        self.job = ExportJob(path, window.app, presets)
        self.polling = False
        window.export_dialog = self
        window._is_saving = True
        self.canceled.connect(self.job.cancel)
        window.qt_app.aboutToQuit.connect(self.shutdown)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(50)
        self.show()

    def poll(self) -> None:
        if self.polling:
            return
        self.polling = True
        try:
            finished = self.job.poll()
            if not finished:
                self.setLabelText(self.job.update.message)
                self.setValue(self.job.update.percent)
                return
            self.timer.stop()
            self.main_window._is_saving = False
            self.main_window._has_focus = False
            self.main_window.export_dialog = None
            self.hide()
            if not self.job.cancelled and self.job.update.error:
                QMessageBox.critical(
                    self.main_window, self.windowTitle(), self.job.update.error
                )
            self.deleteLater()
        finally:
            self.polling = False

    def shutdown(self) -> None:
        self.timer.stop()
        self.job.close()
