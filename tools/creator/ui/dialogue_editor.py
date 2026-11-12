"""The Dialogue tab: reword what the game says and write conversations of your own."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QImage, QKeySequence, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..model import library
from ..model.dialogue import DialogueStudio
from ..model.project import CreatorError

APPLY_DELAY_MS = 800
SCALE = 2
BOX = (160, 64)
LINE_HEIGHT = 14
ORIGIN = (8, 3)
POSITIONS = (("Where the game puts it", ""), ("Top of the screen", "!"),
             ("Middle of the screen", "@"), ("Bottom of the screen", "#"))
KEY = Qt.ItemDataRole.UserRole


class _TextBox(QPlainTextEdit):
    """Hands Undo and Redo to the tab's one history instead of keeping its own."""

    undo_requested = Signal()
    redo_requested = Signal()

    def keyPressEvent(self, event) -> None:
        if event.matches(QKeySequence.StandardKey.Undo):
            self.undo_requested.emit()
        elif event.matches(QKeySequence.StandardKey.Redo):
            self.redo_requested.emit()
        else:
            super().keyPressEvent(event)


class Preview(QWidget):
    """One window of a page, with the game's own letters, wrapping and paging."""

    def __init__(self, editor: "DialogueEditor") -> None:
        super().__init__()
        self.editor = editor
        self.windows: tuple = ()
        self.portrait = 0
        self.index = 0
        self.setAccessibleName("In-game preview")

    def sizeHint(self) -> QSize:
        return QSize((BOX[0] + 72) * SCALE, (BOX[1] + 8) * SCALE)

    minimumSizeHint = sizeHint

    def show_page(self, windows: tuple, portrait: int) -> None:
        self.windows, self.portrait = windows, portrait
        self.index = min(self.index, max(len(windows) - 1, 0))
        self.update()

    def picture(self) -> QImage:
        studio = self.editor.studio
        image = QImage(BOX[0], BOX[1], QImage.Format.Format_RGB32)
        image.fill(QColor(16, 24, 56))
        if studio is None or not self.windows:
            return image
        ink = QColor(255, 255, 255).rgb()
        centred = self.portrait == 0
        for row, line in enumerate(self.windows[self.index]):
            units = [ord(unit) for unit in line]
            drawn, skip = [], False
            for unit in units:
                if skip or unit == 8:
                    skip = unit == 8 and not skip
                    continue
                drawn.append(unit)
            width = sum(studio.advance(unit) for unit in drawn)
            x = max((BOX[0] - width) // 2, 0) if centred else ORIGIN[0]
            y = ORIGIN[1] + row * LINE_HEIGHT
            for unit in drawn:
                glyph = studio.glyph(unit)
                if glyph is not None:
                    for column, bits in enumerate(glyph[1]):
                        for bit in range(16):
                            if bits >> bit & 1 and x + column < BOX[0] and y + bit < BOX[1]:
                                image.setPixel(x + column, y + bit, ink)
                x += studio.advance(unit)
        return image

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.drawImage(0, 0, self.picture().scaled(BOX[0] * SCALE, BOX[1] * SCALE))
        face = self.editor.portrait_picture(self.portrait)
        if face is not None:
            painter.drawPixmap(BOX[0] * SCALE + 8, 0, face.scaled(64 * SCALE, 64 * SCALE))


class DialogueEditor(QWidget):
    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.studio: DialogueStudio | None = None
        self.key = ""
        self.page = 0
        self.messages: list[str] = []
        self.pick_name = self._ask_name
        self._project: Path | None = None
        self._loading = False
        self._faces: dict[int, QPixmap | None] = {}

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search words, speakers and names...")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Search conversations")
        self.search.textChanged.connect(lambda _text: self._fill_rows())
        self.only_mine = QCheckBox("Only mine and ones I changed")
        self.only_mine.toggled.connect(lambda _on: self._fill_rows())
        self.rows = QListWidget()
        self.rows.setAccessibleName("Conversations")
        self.rows.currentItemChanged.connect(self._row_chosen)
        self.count = QLabel()
        left = QWidget()
        column = QVBoxLayout(left)
        column.addWidget(self.search)
        column.addWidget(self.only_mine)
        column.addWidget(self.rows, 1)
        column.addWidget(self.count)
        for label, action in (("New conversation...", self.new_talk),
                              ("Duplicate as my own", self.duplicate),
                              ("Rename...", self.rename), ("Delete", self.delete)):
            button = QPushButton(label)
            button.clicked.connect(action)
            column.addWidget(button)

        self.title = QLabel()
        self.title.setWordWrap(True)
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.page_list = QListWidget()
        self.page_list.setAccessibleName("Pages of this conversation")
        self.page_list.currentRowChanged.connect(self._page_chosen)
        page_buttons = QHBoxLayout()
        self.page_buttons = []
        for label, action in (("Add page", self.add_page), ("Duplicate page", self.duplicate_page),
                              ("Delete page", self.delete_page), ("Move up", lambda: self.move_page(-1)),
                              ("Move down", lambda: self.move_page(1))):
            button = QPushButton(label)
            button.clicked.connect(action)
            page_buttons.addWidget(button)
            self.page_buttons.append(button)
        self.portrait = QComboBox()
        self.portrait.setAccessibleName("Portrait for this page")
        self.portrait.setIconSize(QSize(32, 32))
        self.portrait.activated.connect(self._portrait_chosen)
        self.position = QComboBox()
        self.position.setAccessibleName("Where the box is drawn")
        for label, code in POSITIONS:
            self.position.addItem(label, code)
        self.position.activated.connect(self._position_chosen)
        self.text = _TextBox()
        self.text.setAccessibleName("Words on this page")
        self.text.textChanged.connect(self._typed)
        self.text.undo_requested.connect(self.undo)
        self.text.redo_requested.connect(self.redo)
        self.break_button = QPushButton("Insert new page mark")
        self.break_button.setToolTip("The words after {page} appear after the player presses A.")
        self.break_button.clicked.connect(lambda: self.text.insertPlainText("{page}"))
        self.restore_button = QPushButton("Restore the game's wording")
        self.restore_button.clicked.connect(self.restore)
        self.problem = QLabel()
        self.problem.setWordWrap(True)
        self.users = QLabel()
        self.users.setWordWrap(True)
        face_row = QHBoxLayout()
        face_row.addWidget(QLabel("Portrait"))
        face_row.addWidget(self.portrait, 1)
        face_row.addWidget(QLabel("Box"))
        face_row.addWidget(self.position)
        tools = QHBoxLayout()
        tools.addWidget(self.break_button)
        tools.addWidget(self.restore_button)
        tools.addStretch(1)

        self.rule = QGroupBox("Remembering (flags)")
        rule = QVBoxLayout(self.rule)
        self.sets = QLineEdit()
        self.sets.setPlaceholderText("a name, such as met_the_guard")
        self.sets.setAccessibleName("Flag to remember after this conversation")
        self.when = QLineEdit()
        self.when.setPlaceholderText("a flag name")
        self.when.setAccessibleName("Flag that switches this conversation")
        self.then = QComboBox()
        self.then.setAccessibleName("Conversation to say once the flag is remembered")
        self.resume = QSpinBox()
        self.resume.setAccessibleName("Page to start from the next time")
        self.resume.setMinimum(1)
        for label, widget in (("After this conversation, remember:", self.sets),
                              ("Once this is remembered:", self.when),
                              ("say this conversation instead:", self.then),
                              ("With no flag, start from this page the next time:", self.resume)):
            line = QHBoxLayout()
            line.addWidget(QLabel(label))
            line.addWidget(widget, 1)
            rule.addLayout(line)
        apply_rule = QPushButton("Apply")
        apply_rule.clicked.connect(self.apply_rule)
        rule.addWidget(apply_rule)

        middle = QWidget()
        centre = QVBoxLayout(middle)
        for widget in (self.title, self.note, self.page_list):
            centre.addWidget(widget)
        centre.addLayout(page_buttons)
        centre.addLayout(face_row)
        centre.addWidget(self.text, 1)
        centre.addLayout(tools)
        centre.addWidget(self.problem)
        centre.addWidget(self.users)
        centre.addWidget(self.rule)

        self.preview = Preview(self)
        self.window_label = QLabel()
        earlier, later = QPushButton("◀ Earlier"), QPushButton("After pressing A ▶")
        earlier.clicked.connect(lambda: self._step(-1))
        later.clicked.connect(lambda: self._step(1))
        steps = QHBoxLayout()
        steps.addWidget(earlier)
        steps.addWidget(self.window_label, 1)
        steps.addWidget(later)
        self.notes = QLabel()
        self.notes.setWordWrap(True)
        self.capacity = QLabel()
        self.capacity.setWordWrap(True)
        right = QWidget()
        side = QVBoxLayout(right)
        side.addWidget(QLabel("How the game shows this page"))
        side.addWidget(self.preview)
        side.addLayout(steps)
        side.addWidget(self.notes)
        side.addStretch(1)
        side.addWidget(self.capacity)

        splitter = QSplitter()
        for widget in (left, middle, right):
            splitter.addWidget(widget)
        splitter.setStretchFactor(1, 1)
        outer = QHBoxLayout(self)
        outer.addWidget(splitter)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(APPLY_DELAY_MS)
        self._timer.timeout.connect(self.apply_pending)

    def set_project(self, directory: Path, rom_path: Path) -> None:
        self.studio = DialogueStudio(directory, rom_path)
        self._project = Path(directory)
        self._faces.clear()
        self.key = ""
        self.refresh()

    def portrait_picture(self, slot: int) -> QPixmap | None:
        if slot not in self._faces and self._project is not None:
            path = library.picture_path(self._project, f"portrait:{slot:03d}")
            self._faces[slot] = QPixmap(str(path)) if slot >= 8 and path.is_file() else None
        return self._faces.get(slot)

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

    def refresh(self) -> None:
        """Read the conversations again from the project and redraw everything."""
        if self.studio is None:
            return
        self._timer.stop()
        self._fill_rows()
        self._show()

    def _fill_rows(self) -> None:
        if self.studio is None:
            return
        try:
            rows = self.studio.rows()
        except CreatorError as exc:
            self.tell(str(exc))
            return
        needle = self.search.text().strip().lower()
        self.rows.blockSignals(True)
        self.rows.clear()
        for row in rows:
            if needle and needle not in row.search or (
                    self.only_mine.isChecked() and not (row.mine or row.edited)):
                continue
            mark = "★ " if row.mine else "✎ " if row.edited else ""
            item = QListWidgetItem(mark + row.title)
            item.setData(KEY, row.key)
            self.rows.addItem(item)
            if row.key == self.key:
                self.rows.setCurrentItem(item)
        self.rows.blockSignals(False)
        self.count.setText(f"{self.rows.count()} of {len(rows)} conversations. ★ yours, ✎ reworded")
        if self.rows.currentItem() is None and self.rows.count() and not self.key:
            self.rows.setCurrentRow(0)

    def _row_chosen(self, item, _previous=None) -> None:
        if item is not None and self.apply_pending():
            self.select(item.data(KEY))

    def select(self, key: str, page: int = 0) -> None:
        self.key, self.page = key, page
        self.preview.index = 0
        self._show()

    def _pages(self) -> list:
        try:
            return self.studio.pages(self.key) if self.key else []
        except (CreatorError, KeyError):
            self.key = ""
            return []

    def _show(self) -> None:
        pages = self._pages()
        mine = self.key.startswith("talk-")
        self._loading = True
        self.title.setText(self.studio.name(self.key) if self.key else "Choose a conversation.")
        self.note.setText(self.studio.structure_note(self.key) if self.key else "")
        self.page_list.blockSignals(True)
        self.page_list.clear()
        for page in pages:
            words = page.text.replace("\n", " ")[:48] if page.editable or page.text else "(a game step)"
            who = self.studio.speaker(page.portrait) if page.editable else "Kept as it is"
            self.page_list.addItem(f"{page.index + 1}. {who}: {words}" + ("  ✎" if page.changed and page.line else ""))
        self.page = min(self.page, max(len(pages) - 1, 0))
        self.page_list.setCurrentRow(self.page if pages else -1)
        self.page_list.blockSignals(False)
        page = pages[self.page] if pages else None
        if page is not None and page.editable and page.note:
            self.note.setText((self.note.text() + "\n\n" + page.note).strip())
        self.text.setPlainText(page.text if page else "")
        self.text.setReadOnly(page is None or not page.editable)
        for button in self.page_buttons:
            button.setEnabled(mine)
        self.portrait.setEnabled(mine and page is not None)
        self.position.setEnabled(page is not None and page.editable)
        self.break_button.setEnabled(page is not None and page.editable)
        self.restore_button.setVisible(page is not None and bool(page.line))
        self.restore_button.setEnabled(page is not None and page.changed)
        self.portrait.clear()
        if page is not None:
            choices = self.studio.portrait_choices() if mine else [
                (page.portrait, self.studio.speaker(page.portrait))]
            for slot, label in choices:
                face = self.portrait_picture(slot)
                self.portrait.addItem(QIcon(face) if face is not None else QIcon(), label, slot)
            self.portrait.setCurrentIndex(max(self.portrait.findData(page.portrait), 0))
            self.position.setCurrentIndex(max(self.position.findData(page.text[:1]), 0))
            if not page.editable:
                self.problem.setText(page.note)
            elif not self.problem.text().startswith("⚠"):
                self.problem.setText(page.note)
        self.rule.setVisible(mine)
        if mine:
            sets, when, then, resume = self.studio.rule(self.key)
            self.sets.setText(sets)
            self.when.setText(when)
            self.then.clear()
            self.then.addItem("(nothing)", "")
            for row in self.studio.rows():
                if row.mine and row.key != self.key:
                    self.then.addItem(row.title, row.key)
            self.then.setCurrentIndex(max(self.then.findData(then), 0))
            self.resume.setMaximum(max(len(pages), 1))
            self.resume.setValue(resume + 1)
        if self.key:
            users = self.studio.users(self.key)
            self.users.setText(
                ("Said by: " + "; ".join(users[:5]) + (f" and {len(users) - 5} more." if len(users) > 5 else "."))
                if users else "No character says this yet. Give it to one in Maps, under Characters.")
            if len(users) > 1 and not mine:
                self.users.setText(self.users.text() + " Rewording it changes it for all of them.")
        else:
            self.users.setText("")
        try:
            self.capacity.setText(self.studio.capacity())
        except CreatorError as exc:
            self.capacity.setText(str(exc))
        self._loading = False
        self._preview()

    def _preview(self) -> None:
        pages = self._pages()
        if not pages:
            self.preview.show_page((), 0)
            self.notes.setText("")
            return
        page = pages[self.page]
        text = self.text.toPlainText()
        portrait = self.portrait.currentData() if self.portrait.count() else page.portrait
        shown = self.studio.windows(text, portrait) if (page.editable or page.text) else ()
        self.preview.show_page(shown, portrait)
        self.window_label.setText(
            f"Window {self.preview.index + 1} of {len(shown)}" if shown else "Nothing to show")
        self.notes.setText("\n".join(
            ["The line breaks, the lines in each window and the pages are measured from the game."]
            + self.studio.preview_notes(text, portrait)) if shown else "")

    def _step(self, move: int) -> None:
        self.preview.index = max(0, min(self.preview.index + move, len(self.preview.windows) - 1))
        self._preview()

    def _page_chosen(self, row: int) -> None:
        if row >= 0 and row != self.page and self.apply_pending():
            self.page = row
            self.preview.index = 0
            self._show()

    def _typed(self) -> None:
        if self._loading:
            return
        text = self.text.toPlainText()
        pages = self._pages()
        page = pages[self.page] if pages else None
        if page is not None and page.editable:
            problem = self.studio.problem(text, page.original if page.line else None)
            self.problem.setText("⚠ " + problem if problem else "")
            self._timer.start()
        self._preview()

    def apply_pending(self) -> bool:
        """Write what is typed into the project. False when it cannot be used yet."""
        self._timer.stop()
        pages = self._pages() if self.studio else []
        if not pages or not pages[self.page].editable:
            return True
        text = self.text.toPlainText()
        if text == pages[self.page].text:
            return True
        key, index, studio = self.key, self.page, self.studio
        try:
            studio.set_text(key, index, text)
        except CreatorError as exc:
            self.tell(str(exc))
            return False
        self.problem.setText("")
        self._fill_rows()
        self.changed.emit()
        return True

    def set_text(self, text: str) -> bool:
        self.text.setPlainText(text)
        return self.apply_pending()

    def _portrait_chosen(self, _index: int) -> None:
        key, index, studio, slot = self.key, self.page, self.studio, self.portrait.currentData()
        if self.apply_pending():
            self._try(lambda: studio.set_portrait(key, index, slot))

    def _position_chosen(self, _index: int) -> None:
        text = self.text.toPlainText()
        if text[:1] in ("!", "@", "#"):
            text = text[1:]
        self.set_text(self.position.currentData() + text)
        self._show()

    def restore(self) -> None:
        key, index, studio = self.key, self.page, self.studio
        self._timer.stop()
        self._try(lambda: studio.restore_line(key, index))

    def _ask_name(self, title: str, text: str) -> str:
        name, accepted = QInputDialog.getText(self, title, text)
        return name.strip() if accepted else ""

    def new_talk(self) -> None:
        name = self.pick_name("New conversation", "A name for this conversation:")
        if name and self.apply_pending():
            made: list[str] = []
            studio = self.studio
            if self._try(lambda: made.append(studio.new_talk(name))):
                self.only_mine.setChecked(False)
                self.key = made[0]
                self.refresh()

    def duplicate(self) -> None:
        if not self.key or not self.apply_pending():
            return
        made: list[str] = []
        studio, key = self.studio, self.key
        if self._try(lambda: made.append(studio.duplicate(key))):
            self.key, self.page = made[0], 0
            self.refresh()

    def rename(self) -> None:
        if not self.key.startswith("talk-"):
            self.tell("Only a conversation of your own has a name to change. Duplicate this one first.")
            return
        name = self.pick_name("Rename conversation", "Your name for this conversation:")
        if name:
            studio, key = self.studio, self.key
            self._try(lambda: studio.rename(key, name))

    def delete(self) -> None:
        if not self.key.startswith("talk-"):
            self.tell("A game conversation cannot be deleted. Restore a line to undo its rewording.")
            return
        studio, key = self.studio, self.key
        self._timer.stop()
        if self._try(lambda: studio.delete(key)):
            self.key = ""
            self.refresh()

    def add_page(self) -> None:
        studio, key, index = self.studio, self.key, self.page
        made: list[int] = []
        if self.apply_pending() and self._try(lambda: made.append(studio.add_page(key, index))):
            self.select(key, made[0])

    def duplicate_page(self) -> None:
        studio, key, index = self.studio, self.key, self.page
        if self.apply_pending() and self._try(lambda: studio.duplicate_page(key, index)):
            self.select(key, index + 1)

    def delete_page(self) -> None:
        studio, key, index = self.studio, self.key, self.page
        self._timer.stop()
        self._try(lambda: studio.delete_page(key, index))

    def move_page(self, move: int) -> None:
        studio, key, index = self.studio, self.key, self.page
        if self.apply_pending() and self._try(lambda: studio.move_page(key, index, index + move)):
            self.select(key, index + move)

    def apply_rule(self) -> None:
        studio, key = self.studio, self.key
        sets, when = self.sets.text().strip(), self.when.text().strip()
        then, resume = self.then.currentData() or "", self.resume.value() - 1
        if self.apply_pending():
            self._try(lambda: studio.set_rule(key, sets, when, then, resume))

    def undo(self) -> None:
        self._history(lambda: self.studio.undo())

    def redo(self) -> None:
        self._history(lambda: self.studio.redo())

    def _history(self, move) -> None:
        if self.studio is None:
            return
        self.apply_pending()
        try:
            move()
        except CreatorError as exc:
            self.tell(str(exc))
            return
        self.problem.setText("")
        self.refresh()
        self.changed.emit()
