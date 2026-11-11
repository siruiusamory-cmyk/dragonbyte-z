"""The text surface: search the records, pick one, edit it, see what is wrong."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..model.project import CreatorError, CreatorProject, TextRecord

APPLY_DELAY_MS = 800


class TextEditor(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project: CreatorProject | None = None
        self._key = ""
        self._loading = False

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search text...")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Search text records")
        self.only_changed = QCheckBox("Only text I changed")
        self.records = QListWidget()
        self.records.setAccessibleName("Text records")
        self.count = QLabel()

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(self.search)
        left_layout.addWidget(self.only_changed)
        left_layout.addWidget(self.records, 1)
        left_layout.addWidget(self.count)

        self.title = QLabel("Select a text record on the left.")
        self.title.setWordWrap(True)
        self.original = QPlainTextEdit()
        self.original.setReadOnly(True)
        self.original.setAccessibleName("Original text")
        self.editor = QPlainTextEdit()
        self.editor.setAccessibleName("Your text")
        self.feedback = QLabel()
        self.feedback.setWordWrap(True)
        self.restore = QPushButton("Restore original text")

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(self.title)
        right_layout.addWidget(QLabel("Original text in the game"))
        right_layout.addWidget(self.original, 1)
        right_layout.addWidget(QLabel("Your text"))
        right_layout.addWidget(self.editor, 2)
        right_layout.addWidget(self.feedback)
        buttons = QHBoxLayout()
        buttons.addWidget(self.restore)
        buttons.addStretch(1)
        right_layout.addLayout(buttons)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(APPLY_DELAY_MS)
        self._timer.timeout.connect(self.apply_pending)
        self.search.textChanged.connect(self._fill)
        self.only_changed.toggled.connect(self._fill)
        self.records.currentItemChanged.connect(self._selected)
        self.editor.textChanged.connect(self._typed)
        self.restore.clicked.connect(self._restore)
        self._show(None)

    def set_project(self, project: CreatorProject | None) -> None:
        self._timer.stop()
        self._project = project
        self._key = ""
        self.refresh()

    def refresh(self) -> None:
        """Reload every record from the model, keeping the selection."""
        self._fill()
        self._show(self._record(self._key))

    def select(self, key: str) -> None:
        self.apply_pending()
        self.search.clear()
        self.only_changed.setChecked(False)
        for row in range(self.records.count()):
            item = self.records.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == key:
                self.records.setCurrentItem(item)
                return

    def apply_pending(self) -> bool:
        """Commit what is typed to the model. False when the model refused it."""
        self._timer.stop()
        record = self._record(self._key)
        if record is None or not record.editable:
            return True
        text = self.editor.toPlainText()
        if text == record.text:
            return True
        try:
            self._project.set_text(self._key, text)
        except CreatorError as exc:
            self._say(str(exc), problem=True)
            return False
        self._say("Change recorded. It is kept safe even before you save.")
        self._mark(self.records.currentItem(), self._record(self._key))
        self.changed.emit()
        return True

    def _record(self, key: str) -> TextRecord | None:
        if self._project is None or not key:
            return None
        try:
            return self._project.record(key)
        except CreatorError:
            return None

    def _fill(self) -> None:
        needle = self.search.text().casefold()
        rows = self._project.records() if self._project else []
        self.records.blockSignals(True)
        self.records.clear()
        for record in rows:
            if self.only_changed.isChecked() and not record.changed:
                continue
            if needle and needle not in f"{record.description}\n{record.text}".casefold():
                continue
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, record.key)
            self._mark(item, record)
            self.records.addItem(item)
            if record.key == self._key:
                self.records.setCurrentItem(item)
        self.records.blockSignals(False)
        self.count.setText(f"{self.records.count()} of {len(rows)} records shown")

    def _mark(self, item: QListWidgetItem | None, record: TextRecord | None) -> None:
        if item is None or record is None:
            return
        prefix = "✎ " if record.changed else ("\U0001f512 " if not record.editable else "")
        item.setText(prefix + record.description)
        item.setToolTip(record.note or record.text)

    def _selected(self, item: QListWidgetItem | None, _previous=None) -> None:
        self.apply_pending()
        self._key = item.data(Qt.ItemDataRole.UserRole) if item else ""
        self._show(self._record(self._key))

    def _show(self, record: TextRecord | None) -> None:
        self._loading = True
        self.editor.setEnabled(record is not None)
        self.restore.setEnabled(bool(record and record.editable and record.changed))
        if record is None:
            self.title.setText("Select a text record on the left.")
            self.original.clear()
            self.editor.clear()
            self._say("")
        else:
            self.title.setText(record.description)
            self.original.setPlainText(record.original)
            if self.editor.toPlainText() != record.text:
                self.editor.setPlainText(record.text)
            self.editor.setReadOnly(not record.editable)
            self._say(record.note)
        self._loading = False

    def _typed(self) -> None:
        if self._loading or self._project is None or not self._key:
            return
        problem = self._project.problem_with(self._key, self.editor.toPlainText())
        self._say(problem, problem=bool(problem))
        self.restore.setEnabled(True)
        self._timer.start()

    def _restore(self) -> None:
        record = self._record(self._key)
        if record is not None:
            self.editor.setPlainText(record.original)
            self.apply_pending()
            self.restore.setEnabled(False)

    def _say(self, message: str, *, problem: bool = False) -> None:
        self.feedback.setText(("⚠ " if problem else "") + message)
        font = self.feedback.font()
        font.setBold(problem)
        self.feedback.setFont(font)
