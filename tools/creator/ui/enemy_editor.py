"""The Enemies tab: the game's own enemy types and the project's own.

The left side lists the game's types with how many placements use each, and the
project's types beside them. The right side is read-only for a game type and a
form for a project type: the name it keeps, the type it behaves like, the four
statistics a record offers, the look the game draws it with, and where it is
used. Placing an enemy is done in Maps.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..model.enemies import NO_LOOK_NOTE, EnemyStudio, donor_label
from ..model.project import CreatorError

KEY = Qt.ItemDataRole.UserRole
FIELDS = (
    ("hp", "Hit points"),
    ("experience", "Experience"),
    ("strength", "Strength"),
    ("endurance", "Endurance"),
)
NOTE = "A project enemy does not appear in the game's appearance panel."
NOTHING_USES_IT = "No map places it yet."


def slug(text: str) -> str:
    """A type name the project accepts: small letters, digits, - and _."""
    return "-".join(text.lower().split())


class EnemyEditor(QWidget):
    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.studio: EnemyStudio | None = None
        self.key = ""
        self.messages: list[str] = []
        self.pick_name = self._ask_name
        self.pick_donor = self._ask_donor
        self._inputs: dict[str, QSpinBox] = {}

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search enemy types...")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Search enemy types")
        self.search.textChanged.connect(lambda _text: self._filter())
        self.game_header = QLabel("Game enemies (read-only)")
        self.game_list = QListWidget()
        self.game_list.setAccessibleName("Game enemies")
        self.game_list.currentItemChanged.connect(self._game_chosen)
        self.pool = QLabel()
        self.list = QListWidget()
        self.list.setAccessibleName("Your enemies")
        self.list.currentItemChanged.connect(self._mine_chosen)
        left = QWidget()
        column = QVBoxLayout(left)
        column.addWidget(self.search)
        column.addWidget(self.game_header)
        column.addWidget(self.game_list, 1)
        column.addWidget(self.pool)
        column.addWidget(self.list, 1)
        for label, action in (("New enemy...", self.new_enemy), ("Duplicate", self.duplicate),
                              ("Rename...", self.rename), ("Delete", self.delete)):
            button = QPushButton(label)
            button.clicked.connect(action)
            column.addWidget(button)

        self.title = QLabel("Choose an enemy type.")
        self.title.setWordWrap(True)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setAccessibleName("About this game enemy")
        self.name = QLabel()
        self.based_on = QLabel()
        self.behaves = QLabel()
        self.look = QComboBox()
        self.look.setAccessibleName("Look")
        self.used = QLabel()
        self.used.setWordWrap(True)
        self.used.setAccessibleName("Used on")
        self.form_host = QWidget()
        form = QFormLayout(self.form_host)
        form.addRow("Name", self.name)
        form.addRow("Based on", self.based_on)
        form.addRow("Behaviour", self.behaves)
        for field, label in FIELDS:
            box = QSpinBox()
            box.setAccessibleName(label)
            self._inputs[field] = box
            form.addRow(label, box)
        form.addRow("Look", self.look)
        form.addRow("Used on", self.used)
        self.apply_button = QPushButton("Apply changes")
        self.apply_button.clicked.connect(self.apply)
        self.note = QLabel(NOTE)
        self.note.setWordWrap(True)
        self.note.setAccessibleName("Note about the appearance panel")
        self.look_note = QLabel()
        self.look_note.setWordWrap(True)
        self.look_note.setAccessibleName("About this enemy's look")
        self.problem = QLabel()
        self.problem.setWordWrap(True)
        self.problem.setAccessibleName("Problems with this enemy type")
        right = QWidget()
        detail = QVBoxLayout(right)
        detail.addWidget(self.title)
        detail.addWidget(self.summary)
        detail.addWidget(self.form_host)
        detail.addWidget(self.look_note)
        detail.addWidget(self.apply_button)
        detail.addWidget(self.problem)
        detail.addWidget(self.note)
        detail.addStretch(1)

        splitter = QSplitter()
        for widget in (left, right):
            splitter.addWidget(widget)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([360, 700])
        QHBoxLayout(self).addWidget(splitter)

    def set_project(self, directory: Path, rom_path: Path) -> None:
        self.studio = EnemyStudio(directory, rom_path)
        self.key = ""
        self.problem.setText("")
        self.refresh()

    def tell(self, text: str) -> None:
        self.messages.append(text)
        self.problem.setText("⚠ " + text)

    def _try(self, action) -> bool:
        try:
            action()
        except CreatorError as exc:
            self.tell(str(exc))
            return False
        self.problem.setText("")
        self.refresh()
        self.changed.emit()
        return True

    def apply_pending(self) -> bool:
        return True

    def refresh(self) -> None:
        """Read the enemy types again from the project and redraw everything."""
        if self.studio is None:
            return
        self._fill_lists()
        self._show()

    def _fill_lists(self) -> None:
        if self.studio is None:
            return
        try:
            game = self.studio.game()
            mine = self.studio.project()
            used, total = self.studio.pool
        except CreatorError as exc:
            self.tell(str(exc))
            return
        self._fill(self.game_list, [(row.key, f"{row.key}   {row.uses} placement(s)")
                                    for row in game])
        self._fill(self.list, [(row.key, row.name + ("   ● used" if row.used_on else ""))
                               for row in mine])
        self.pool.setText(f"Your enemies ({used} of {total})")
        self._filter()

    def _fill(self, widget: QListWidget, rows: list[tuple[str, str]]) -> None:
        widget.blockSignals(True)
        widget.clear()
        for key, title in rows:
            item = QListWidgetItem(title)
            item.setData(KEY, key)
            widget.addItem(item)
            if key == self.key:
                widget.setCurrentItem(item)
        widget.blockSignals(False)

    def _filter(self) -> None:
        needle = self.search.text().strip().lower()
        for widget in (self.game_list, self.list):
            for row in range(widget.count()):
                item = widget.item(row)
                item.setHidden(needle not in item.text().lower())

    def _game_chosen(self, item, _previous=None) -> None:
        if item is not None:
            self.select(item.data(KEY))

    def _mine_chosen(self, item, _previous=None) -> None:
        if item is not None:
            self.select(item.data(KEY))

    def select(self, key: str) -> None:
        self.key = key
        self._fill_lists()
        self._show()

    def _mine(self):
        if self.studio is None or not self.key:
            return None
        return next((row for row in self.studio.project() if row.key == self.key), None)

    def _show(self) -> None:
        try:
            mine = self._mine()
            game = None
            if mine is None and self.studio is not None and self.key:
                game = next((row for row in self.studio.game() if row.key == self.key), None)
        except CreatorError as exc:
            self.tell(str(exc))
            return
        self.form_host.setVisible(mine is not None)
        self.apply_button.setVisible(mine is not None)
        self.summary.setVisible(game is not None)
        self.look_note.setText("")
        self.game_list.blockSignals(True)
        self.list.blockSignals(True)
        if mine is not None:
            self.title.setText(mine.name)
            self.name.setText(mine.name)
            self.based_on.setText(mine.donor)
            self.behaves.setText(f"behaves like {mine.donor}")
            self.look.blockSignals(True)
            self.look.clear()
            for choice in self.studio.looks(mine.name):
                self.look.addItem(choice.key, choice.sprite)
            if mine.look is None:
                self.look.addItem("the game draws none", None)
            self.look.blockSignals(False)
            self.used.setText("\n".join(f"{title}: {count} placement(s)"
                                        for title, count in mine.used_on) or NOTHING_USES_IT)
            self.look_note.setText("" if mine.look is not None else NO_LOOK_NOTE)
            bounds = self.studio.bounds
            for field, label in FIELDS:
                box = self._inputs[field]
                box.setRange(*bounds[field])
                box.setValue(getattr(mine, field))
            for row in range(self.list.count()):
                if self.list.item(row).data(KEY) == mine.key:
                    self.list.setCurrentRow(row)
        elif game is not None:
            self.title.setText(game.key)
            self.summary.setText(
                f"This is one of the game's own enemy types and cannot be changed.\n"
                f"Hit points {game.hp}, experience {game.experience}, "
                f"strength {game.strength}, endurance {game.endurance}.\n"
                f"The game's maps place it {game.uses} time(s).")
        else:
            self.title.setText("Choose an enemy type.")
            self.summary.clear()
        self.game_list.blockSignals(False)
        self.list.blockSignals(False)

    def apply(self) -> bool:
        mine = self._mine()
        if mine is None:
            return False
        studio, name = self.studio, mine.name

        def action() -> None:
            for field, _label in FIELDS:
                value = self._inputs[field].value()
                if value != getattr(mine, field):
                    studio.set_statistic(name, field, value)
            sprite = self.look.currentData()
            if sprite is not None:
                studio.set_look(name, sprite)

        return self._try(action)

    def _ask_name(self, title: str, text: str) -> str:
        name, accepted = QInputDialog.getText(self, title, text)
        return name.strip() if accepted else ""

    def _ask_donor(self, donors) -> str:
        labels = [donor_label(row) for row in donors]
        choice, accepted = QInputDialog.getItem(
            self, "New enemy", "Copy the statistics and behaviour of:", labels, 0, False)
        return donors[labels.index(choice)].key if accepted and choice in labels else ""

    def new_enemy(self) -> None:
        if self.studio is None:
            return
        try:
            donors = self.studio.donors()
        except CreatorError as exc:
            self.tell(str(exc))
            return
        donor = self.pick_donor(donors)
        if not donor:
            return
        name = self.pick_name("New enemy", "A name for this enemy (small letters, digits, "
                              "- and _):")
        if not name:
            return
        made: list[str] = []
        if self._try(lambda: made.append(self.studio.create(donor, slug(name)))):
            self.select(made[0])

    def duplicate(self) -> None:
        mine = self._mine()
        if mine is None:
            return
        name = self.pick_name("Duplicate enemy", "A name for the copy:")
        made: list[str] = []
        if name and self._try(lambda: made.append(
                self.studio.duplicate(mine.name, slug(name)))):
            self.select(made[0])

    def rename(self) -> None:
        mine = self._mine()
        if mine is None:
            return
        name = self.pick_name("Rename enemy", "The new name:")
        if name and self._try(lambda: self.studio.rename(mine.name, slug(name))):
            self.select(f"enemy:{slug(name)}")

    def delete(self) -> None:
        mine = self._mine()
        if mine is not None and self._try(lambda: self.studio.delete(mine.name)):
            self.key = ""
            self.refresh()

    def undo(self) -> None:
        if self.studio is not None:
            self._try(self.studio.undo)

    def redo(self) -> None:
        if self.studio is not None:
            self._try(self.studio.redo)
