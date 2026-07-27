from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QInputDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from ..presets import user_preset_names


def preset_name(parent: QWidget) -> str | None:
    name, accepted = QInputDialog.getText(parent, 'Save preset', 'Preset name:')
    name = name.strip()
    return name if accepted and name else None


def test_sheet_preset_names(parent: QWidget) -> list[str]:
    return selected_preset_names(
        parent,
        title='Save test sheet',
        prompt='Select presets to render:',
        empty_title='Save test sheet',
        empty_text='There are no user presets.',
    )


def selected_preset_names(
    parent: QWidget,
    title: str = 'Delete presets',
    prompt: str = 'Select presets to delete:',
    empty_title: str = 'Delete presets',
    empty_text: str = 'There are no user presets.',
) -> list[str]:
    names = user_preset_names()
    if not names:
        QMessageBox.information(parent, empty_title, empty_text)
        return []

    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel(prompt, dialog))

    presets = QListWidget(dialog)
    presets.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    presets.addItems(names)
    layout.addWidget(presets)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        dialog,
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return []
    return [i.text() for i in presets.selectedItems()]
