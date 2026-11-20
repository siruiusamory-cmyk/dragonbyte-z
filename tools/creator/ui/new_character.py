"""Make the project's one new character: name, behaviour, size, then draw it."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..model.characters import BEHAVIOURS, FEWEST_FRAMES, MOST_FRAMES, SLOT_TITLES, WALKS
from ..model.project import CreatorError
from .sprite_editor import SpriteEditorPanel

BEHAVIOUR_WORDS = {
    "Stands": ("Stands still on its map. How it looks facing up or left has not been "
               "checked in the running game"),
    "Walks": "Walks around inside its wander box and stops now and then",
}


class NewCharacterPanel(QWidget):
    changed = Signal()
    closed = Signal()

    def __init__(self, maker) -> None:
        super().__init__()
        self.maker = maker
        self.editor: SpriteEditorPanel | None = None

        self.title = QLabel()
        self.undo_button = QPushButton("Undo")
        self.redo_button = QPushButton("Redo")
        self.remove_button = QPushButton("Remove this character")
        back = QPushButton("Back to the library")
        self.template_button = QPushButton("Import sheet template...")
        self.template_button.clicked.connect(self.ask_import_template)
        top = QHBoxLayout()
        top.addWidget(self.title, 1)
        for button in (self.undo_button, self.redo_button, self.template_button,
                       self.remove_button, back):
            top.addWidget(button)

        self.form = QWidget()
        self.name = QLineEdit()
        self.name.setAccessibleName("Name of the new character")
        self.behaviour = QComboBox()
        self.behaviour.setAccessibleName("What it does")
        for behaviour in BEHAVIOURS:
            self.behaviour.addItem(f"{behaviour}: {BEHAVIOUR_WORDS[behaviour]}", behaviour)
        self.size = QComboBox()
        self.size.setAccessibleName("Frame size")
        self.make_button = QPushButton("Make this character")
        fields = QFormLayout(self.form)
        fields.addRow("&Name", self.name)
        fields.addRow("&What it does", self.behaviour)
        fields.addRow("&Frame size", self.size)
        fields.addRow(self.make_button)

        self.tools = QWidget()
        tools = QHBoxLayout(self.tools)
        self.import_buttons = []
        for slot, title in enumerate(SLOT_TITLES):
            button = QPushButton(f"Import a {title} sheet...")
            button.clicked.connect(lambda _checked=False, slot=slot: self.ask_import(slot))
            self.import_buttons.append(button)
            tools.addWidget(button)
        self.walk_frames = QSpinBox()
        self.walk_frames.setRange(FEWEST_FRAMES[1], MOST_FRAMES)
        self.walk_frames.setPrefix("Walk frames for each facing: ")
        tools.addWidget(self.walk_frames)
        self.export_button = QPushButton("Export sheet...")
        self.export_button.clicked.connect(self.ask_export)
        tools.addWidget(self.export_button)
        self.attribution = QLineEdit()
        self.attribution.setPlaceholderText("Who made this art (saved with the character)")
        self.attribution.setAccessibleName("Attribution")
        self.attribution.editingFinished.connect(
            lambda: self._do(lambda: self.maker.set_attribution(self.attribution.text())))
        tools.addWidget(self.attribution, 1)
        self.problems = QLabel()
        self.problems.setWordWrap(True)
        self.problems.setAccessibleName("What is still missing")
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.area = QVBoxLayout()

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.form)
        layout.addWidget(self.tools)
        layout.addLayout(self.area, 1)
        layout.addWidget(self.problems)
        layout.addWidget(self.message)

        back.clicked.connect(self.closed)
        self.undo_button.clicked.connect(lambda: self._do(self.maker.undo))
        self.redo_button.clicked.connect(lambda: self._do(self.maker.redo))
        self.remove_button.clicked.connect(lambda: self._do(self.maker.remove))
        self.behaviour.currentIndexChanged.connect(lambda _index: self._fill_sizes())
        self.make_button.clicked.connect(self.make)
        self.walk_frames.editingFinished.connect(
            lambda: self._do(lambda: self.maker.set_frames(1, self.walk_frames.value())))
        self._fill_sizes()
        self.refresh()

    def _fill_sizes(self) -> None:
        self.size.clear()
        self.size.addItems(self.maker.sizes(self.behaviour.currentData()))

    def _do(self, action) -> bool:
        try:
            action()
        except CreatorError as exc:
            self.message.setText(f"⚠ {exc}")
            return False
        self.message.clear()
        self.refresh()
        self.changed.emit()
        return True

    def make(self) -> bool:
        return self._do(lambda: self.maker.create(
            self.name.text(), self.behaviour.currentData(), self.size.currentText()))

    def import_sheet(self, slot: int, path: Path) -> bool:
        return self._do(lambda: self.maker.import_sheet(slot, Path(path)))

    def ask_import(self, slot: int) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self, f"Import a {SLOT_TITLES[slot]} sheet", "", "PNG pictures (*.png)")
        if path:
            self.import_sheet(slot, Path(path))

    def import_template(self, path: Path) -> bool:
        return self._do(lambda: self.maker.import_template(Path(path)))

    def ask_import_template(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self, "Import sheet template", "", "Sheet templates (*.sprite.toml)")
        if path:
            self.import_template(Path(path))

    def export_sheet(self, folder: Path, replace_files: bool = False) -> bool:
        try:
            written = self.maker.export_sheet(Path(folder), replace_files)
        except CreatorError as exc:
            self.message.setText(f"⚠ {exc}")
            return False
        self.message.setText(f"Exported {written[0].name} and {written[1].name}.")
        return True

    def ask_export(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Export sheet to a folder")
        if not folder:
            return
        try:
            present = [path.name for path in self.maker.export_targets(Path(folder))
                       if path.exists()]
        except CreatorError as exc:
            self.message.setText(f"⚠ {exc}")
            return
        if present and QMessageBox.question(
                self, "Replace files?",
                f"{' and '.join(present)} already in that folder. Replace?"
        ) != QMessageBox.StandardButton.Yes:
            return
        self.export_sheet(Path(folder), bool(present))

    def refresh(self) -> None:
        character = self.maker.character
        self.form.setVisible(character is None)
        self.tools.setVisible(character is not None)
        self.remove_button.setEnabled(character is not None)
        self.undo_button.setEnabled(self.maker.can_undo)
        self.redo_button.setEnabled(self.maker.can_redo)
        if self.editor is not None:
            self.area.removeWidget(self.editor)
            self.editor.deleteLater()
            self.editor = None
        if character is None:
            self.title.setText("Make a new character. A project can have one.")
            self.problems.clear()
            return
        walks = character.behaviour == WALKS
        self.title.setText(f"{character.name}: {character.behaviour.lower()}, frames "
                           f"{character.size}")
        self.attribution.setText(self.maker.attribution())
        self.import_buttons[1].setVisible(walks)
        self.walk_frames.setVisible(walks)
        if walks:
            self.walk_frames.blockSignals(True)
            self.walk_frames.setValue(character.frames[1])
            self.walk_frames.blockSignals(False)
        self.editor = SpriteEditorPanel(self.maker)
        self.editor.closed.connect(self.closed)
        self.editor.changed.connect(self._painted)
        self.area.addWidget(self.editor)
        self._show_problems()

    def _painted(self) -> None:
        self.undo_button.setEnabled(self.maker.can_undo)
        self.redo_button.setEnabled(self.maker.can_redo)
        self._show_problems()
        self.changed.emit()

    def _show_problems(self) -> None:
        found = self.maker.problems()
        self.problems.setText(
            "Still to do before the game can be built:\n" + "\n".join(found) if found
            else "✔ Ready to place on a map and build.")
