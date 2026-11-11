"""The New Project dialog: pick the ROM, see whether it is the right one, name it."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..model.project import check_rom

ROM_FILTER = "Game Boy Advance ROM (*.gba);;All files (*)"


def _row(field: QLineEdit, button: QPushButton) -> QWidget:
    holder = QWidget()
    layout = QHBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(field, 1)
    layout.addWidget(button)
    return holder


class NewProjectDialog(QDialog):
    def __init__(self, start_directory: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setMinimumWidth(620)
        self.rom = QLineEdit()
        self.rom.setPlaceholderText("Your Dragon Ball Z: Buu's Fury (USA) ROM file")
        self.verdict = QLabel("Choose your Buu's Fury ROM to begin.")
        self.verdict.setWordWrap(True)
        self.verdict.setMinimumHeight(self.verdict.fontMetrics().lineSpacing() * 4)
        self.name = QLineEdit("My Legacy of Goku")
        self.location = QLineEdit(start_directory or str(Path.home() / "Documents" / "DragonByte Z"))
        self.target = QLabel()
        browse_rom = QPushButton("Browse...")
        browse_location = QPushButton("Browse...")

        form = QFormLayout()
        form.addRow("Buu's Fury ROM", _row(self.rom, browse_rom))
        form.addRow("", self.verdict)
        form.addRow("Project name", self.name)
        form.addRow("Save projects in", _row(self.location, browse_location))
        form.addRow("", self.target)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Create Project")
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.buttons)

        browse_rom.clicked.connect(self._browse_rom)
        browse_location.clicked.connect(self._browse_location)
        self.rom.textChanged.connect(self._update)
        self.name.textChanged.connect(self._update)
        self.location.textChanged.connect(self._update)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self._compatible = False
        self._update()

    def rom_path(self) -> Path:
        return Path(self.rom.text().strip())

    def project_name(self) -> str:
        return self.name.text().strip()

    def project_directory(self) -> Path:
        return Path(self.location.text().strip()) / self.project_name()

    def _browse_rom(self) -> None:
        chosen, _ = QFileDialog.getOpenFileName(self, "Choose your Buu's Fury ROM", "", ROM_FILTER)
        if chosen:
            self.rom.setText(chosen)

    def _browse_location(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Save projects in", self.location.text())
        if chosen:
            self.location.setText(chosen)

    def _update(self) -> None:
        text = self.rom.text().strip()
        if text:
            check = check_rom(Path(text))
            self._compatible = check.compatible
            glyph = "✔" if check.compatible else "⚠"
            self.verdict.setText(f"{glyph} {check.title}\n{check.detail}")
        else:
            self._compatible = False
            self.verdict.setText("Choose your Buu's Fury ROM to begin.")
        ready = self._compatible and bool(self.project_name()) and bool(self.location.text().strip())
        self.target.setText(f"The project folder will be {self.project_directory()}" if ready else "")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ready)
