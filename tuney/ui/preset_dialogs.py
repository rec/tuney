from __future__ import annotations

from PySide6 import QtWidgets

from ..presets import user_preset_names


def preset_name(parent: QtWidgets.QWidget) -> str | None:
    name, accepted = QtWidgets.QInputDialog.getText(
        parent, 'Save preset', 'Preset name:'
    )
    name = name.strip()
    return name if accepted and name else None


def test_sheet_preset_names(parent: QtWidgets.QWidget) -> list[str]:
    return selected_preset_names(
        parent,
        title='Save test sheet',
        prompt='Select presets to render:',
        empty_title='Save test sheet',
        empty_text='There are no user presets.',
    )


def selected_preset_names(
    parent: QtWidgets.QWidget,
    title: str = 'Delete presets',
    prompt: str = 'Select presets to delete:',
    empty_title: str = 'Delete presets',
    empty_text: str = 'There are no user presets.',
) -> list[str]:
    names = user_preset_names()
    if not names:
        QtWidgets.QMessageBox.information(parent, empty_title, empty_text)
        return []

    dialog = QtWidgets.QDialog(parent)
    dialog.setWindowTitle(title)
    layout = QtWidgets.QVBoxLayout(dialog)
    layout.addWidget(QtWidgets.QLabel(prompt, dialog))

    presets = QtWidgets.QListWidget(dialog)
    presets.setSelectionMode(
        QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
    )
    presets.addItems(names)
    layout.addWidget(presets)

    buttons = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.StandardButton.Ok
        | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
        dialog,
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
        return []
    return [i.text() for i in presets.selectedItems()]
