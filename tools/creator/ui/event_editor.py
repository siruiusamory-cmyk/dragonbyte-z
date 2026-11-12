"""The Events tab: build what happens in the game from steps, with no scripting.

The left side lists the events, the middle is one event's trigger and steps, and
the right side holds the step library, the Story view of every flag, and the
trace of what the running game last executed.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..model import events as ev
from ..model.dialogue import DialogueStudio
from ..model.events import ACTIVATIONS, LIBRARY, TRIGGERS, EventStudio
from ..model.project import CreatorError

KEY = Qt.ItemDataRole.UserRole
PIXELS = ("Left", "Top", "Right", "Bottom")
FIELDS = {
    "say": (("Portrait", "portrait", 1), ("Words", "text", 2)),
    "ask": (("Portrait", "portrait", 1), ("Words", "text", 2),
            ("First choice", "line", 3), ("Second choice", "line", 4)),
    "set": (("Flag", "flag", 1),),
    "clear": (("Flag", "flag", 1),),
    "give": (("Item number", "number", 1),),
    "take": (("Item number", "number", 1),),
    "open": tuple((name, "number", at) for at, name in enumerate(PIXELS, 1)),
    "close": tuple((name, "number", at) for at, name in enumerate(PIXELS, 1)),
    "music": (("Music number", "number", 1),),
    "if flag": (("Flag", "flag", 2),),
    "if not_flag": (("Flag", "flag", 2),),
    "if item": (("Item number", "number", 2), ("At least", "number", 3)),
    "if answer": (("Choice", "choice", 2),),
}


class EventEditor(QWidget):
    changed = Signal()
    trace_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.studio: EventStudio | None = None
        self.talks: DialogueStudio | None = None
        self.key = ""
        self.step = 0
        self.output: Path | None = None
        self.messages: list[str] = []
        self.pick_name = self._ask_name
        self._inputs: list = []

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search events...")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Search events")
        self.search.textChanged.connect(lambda _text: self._fill_rows())
        self.show_game = QCheckBox("Show the game's own events (view only)")
        self.show_game.toggled.connect(lambda _on: self._fill_rows())
        self.rows = QListWidget()
        self.rows.setAccessibleName("Events")
        self.rows.currentItemChanged.connect(self._row_chosen)
        left = QWidget()
        column = QVBoxLayout(left)
        for widget in (self.search, self.show_game):
            column.addWidget(widget)
        column.addWidget(self.rows, 1)
        for label, action in (("New event...", self.new_event), ("Duplicate", self.duplicate),
                              ("Rename...", self.rename), ("Put in group...", self.set_group),
                              ("Delete", self.delete)):
            button = QPushButton(label)
            button.clicked.connect(action)
            column.addWidget(button)

        self.title = QLabel("Choose an event.")
        self.title.setWordWrap(True)
        self.trigger = QComboBox()
        self.trigger.setAccessibleName("How the event starts")
        for name, label in TRIGGERS.items():
            self.trigger.addItem(label, name)
        self.map = QComboBox()
        self.map.setAccessibleName("Map the event belongs to")
        self.activation = QComboBox()
        self.activation.setAccessibleName("How the region is set off")
        for name, label in ACTIVATIONS.items():
            self.activation.addItem(label, name)
        self.where = QLabel()
        self.where.setWordWrap(True)
        apply_trigger = QPushButton("Apply")
        apply_trigger.clicked.connect(self.apply_trigger)
        self.trigger.currentIndexChanged.connect(lambda _index: self._trigger_shown())
        start = QHBoxLayout()
        for widget in (QLabel("Starts when"), self.trigger, self.map, self.activation, apply_trigger):
            start.addWidget(widget)
        self.steps = QListWidget()
        self.steps.setAccessibleName("Steps of this event")
        self.steps.currentRowChanged.connect(self._step_chosen)
        step_buttons = QHBoxLayout()
        for label, action in (("Remove step", self.remove_step), ("Move up", lambda: self.move_step(-1)),
                              ("Move down", lambda: self.move_step(1))):
            button = QPushButton(label)
            button.clicked.connect(action)
            step_buttons.addWidget(button)
        self.form_host = QWidget()
        self.form = QFormLayout(self.form_host)
        self.apply_button = QPushButton("Apply step")
        self.apply_button.clicked.connect(self.apply_step)
        self.problem = QLabel()
        self.problem.setWordWrap(True)
        self.problem.setAccessibleName("Problems with this event")
        middle = QWidget()
        centre = QVBoxLayout(middle)
        centre.addWidget(self.title)
        centre.addLayout(start)
        centre.addWidget(self.where)
        centre.addWidget(self.steps, 1)
        centre.addLayout(step_buttons)
        centre.addWidget(self.form_host)
        centre.addWidget(self.apply_button)
        centre.addWidget(self.problem)

        self.library = QListWidget()
        self.library.setAccessibleName("Steps to add")
        for action in LIBRARY:
            item = QListWidgetItem(f"{action.group}: {action.title}"
                                   + ("" if action.proven else "   🔒 not available yet"))
            item.setData(KEY, action.kind)
            item.setToolTip(action.about if action.proven else
                            f"{action.about} This {ev.NOT_PROVEN}.")
            self.library.addItem(item)
        self.about = QLabel()
        self.about.setWordWrap(True)
        self.library.currentItemChanged.connect(
            lambda item, _old: self.about.setText(item.toolTip() if item else ""))
        add = QPushButton("Add after the chosen step")
        add.clicked.connect(lambda: self.add_step(
            self.library.currentItem().data(KEY) if self.library.currentItem() else ""))
        self.library.itemDoubleClicked.connect(lambda item: self.add_step(item.data(KEY)))
        library_page = QWidget()
        page = QVBoxLayout(library_page)
        for widget in (self.library, self.about, add):
            page.addWidget(widget)

        self.story = QListWidget()
        self.story.setAccessibleName("Story flags")
        self.story.setWordWrap(True)
        story_page = QWidget()
        page = QVBoxLayout(story_page)
        page.addWidget(QLabel("Every flag the story remembers, who sets it and who reads it. "
                              "A flag keeps its place in the save file for good."))
        page.addWidget(self.story, 1)
        for label, action in (("New flag...", self.new_flag), ("Rename flag...", self.rename_flag),
                              ("Delete flag", self.delete_flag)):
            button = QPushButton(label)
            button.clicked.connect(action)
            page.addWidget(button)

        self.trace = QListWidget()
        self.trace.setAccessibleName("What the game ran")
        self.trace.setWordWrap(True)
        play = QPushButton("Play with trace")
        play.setToolTip("Start the built game in mGBA and write down each step it runs.")
        play.clicked.connect(self.trace_requested.emit)
        again = QPushButton("Read the trace again")
        again.clicked.connect(self.show_trace)
        trace_page = QWidget()
        page = QVBoxLayout(trace_page)
        page.addWidget(QLabel("The steps the running game really executed, and the flags it "
                              "held, read from the game while it played."))
        page.addWidget(self.trace, 1)
        page.addWidget(play)
        page.addWidget(again)

        self.side = QTabWidget()
        self.side.addTab(library_page, "Add a step")
        self.side.addTab(story_page, "Story")
        self.side.addTab(trace_page, "Trace")

        splitter = QSplitter()
        for widget in (left, middle, self.side):
            splitter.addWidget(widget)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 560, 340])
        outer = QHBoxLayout(self)
        outer.addWidget(splitter)

    def set_project(self, directory: Path, rom_path: Path, output: Path | None = None) -> None:
        self.studio = EventStudio(directory, rom_path)
        self.talks = DialogueStudio(directory, rom_path)
        self.output = output
        self.key = ""
        self.map.clear()
        for identity, title in self.studio.maps():
            self.map.addItem(title, identity)
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
        """Read the events again from the project and redraw everything."""
        if self.studio is None:
            return
        self._fill_rows()
        self._show()
        self._fill_story()

    def _mine(self) -> bool:
        return self.key.startswith("evt-")

    def _fill_rows(self) -> None:
        if self.studio is None:
            return
        try:
            rows = [(row.key, (f"[{row.group}] " if row.group else "") + row.title
                     + f"   ({row.where})" + ("   ⚠" if row.problem else ""))
                    for row in self.studio.rows()]
            if self.show_game.isChecked():
                rows += [(key, "🔒 " + title) for key, title in self.studio.game_events()]
        except CreatorError as exc:
            self.tell(str(exc))
            return
        needle = self.search.text().strip().lower()
        self.rows.blockSignals(True)
        self.rows.clear()
        for key, title in rows:
            if needle in title.lower():
                item = QListWidgetItem(title)
                item.setData(KEY, key)
                self.rows.addItem(item)
                if key == self.key:
                    self.rows.setCurrentItem(item)
        self.rows.blockSignals(False)

    def _row_chosen(self, item, _previous=None) -> None:
        if item is not None:
            self.select(item.data(KEY))

    def select(self, key: str, step: int = 0) -> None:
        self.key, self.step = key, step
        self._fill_rows()
        self._show()

    def _show(self) -> None:
        mine = self._mine()
        rows = []
        try:
            if mine:
                event = self.studio.event(self.key)
                rows = self.studio.steps(self.key)
                self.title.setText(event.name or self.key)
                self.trigger.blockSignals(True)
                self.trigger.setCurrentIndex(max(self.trigger.findData(event.trigger), 0))
                self.trigger.blockSignals(False)
                self.map.setCurrentIndex(max(self.map.findData(event.map), 0))
                self.activation.setCurrentIndex(max(self.activation.findData(event.activation), 0))
                self.where.setText(
                    self.studio.where(self.key, event) + (
                        f"   Region {event.rect[0]}, {event.rect[1]} to {event.rect[2]}, "
                        f"{event.rect[3]}. Draw or move it in Maps, with the Events tool."
                        if event.trigger == ev.REGION and len(event.rect) == 4 else ""))
                problems = [text for key, text in self.studio.problems() if key == self.key]
                if not self.problem.text().startswith("⚠"):
                    self.problem.setText("\n".join("⚠ " + text for text in problems))
            elif self.key:
                self.title.setText("A game event. It can be looked at but is never changed.")
                self.where.setText("")
        except CreatorError:
            self.key, mine = "", False
        self.steps.blockSignals(True)
        self.steps.clear()
        if mine:
            for row in rows:
                self.steps.addItem(f"{row.index + 1:>2}  " + "      " * row.depth + row.text
                                   + ("   ⚠ " + row.problem if row.problem else ""))
        elif self.key:
            for text, known in self.studio.game_steps(self.key):
                self.steps.addItem(("" if known else "🔒 ") + text)
        self.step = min(self.step, max(self.steps.count() - 1, 0))
        self.steps.setCurrentRow(self.step if self.steps.count() else -1)
        self.steps.blockSignals(False)
        for widget in (self.trigger, self.map, self.activation, self.apply_button):
            widget.setEnabled(mine)
        self._trigger_shown()
        self._show_step()

    def _trigger_shown(self) -> None:
        kind = self.trigger.currentData()
        self.map.setVisible(kind != ev.TALK)
        self.activation.setVisible(kind == ev.REGION)

    def _step_chosen(self, row: int) -> None:
        if row >= 0:
            self.step = row
            self._show_step()

    def _current(self) -> tuple | None:
        if not self._mine():
            return None
        steps = self.studio.event(self.key).steps
        return steps[self.step] if 0 <= self.step < len(steps) else None

    def _show_step(self) -> None:
        while self.form.rowCount():
            self.form.removeRow(0)
        self._inputs = []
        step = self._current()
        fields = FIELDS.get(ev.gate(step), ()) if step else ()
        self.apply_button.setVisible(bool(fields))
        for label, kind, at in fields:
            value = step[at] if at < len(step) else ""
            if kind == "text":
                widget = QPlainTextEdit(str(value))
                widget.setMaximumHeight(90)
            elif kind == "line":
                widget = QLineEdit(str(value))
            elif kind == "number":
                widget = QSpinBox()
                widget.setRange(0, 4095)
                widget.setValue(int(value or 0))
            else:
                widget = QComboBox()
                if kind == "portrait":
                    for slot, title in self.talks.portrait_choices():
                        widget.addItem(title, slot)
                elif kind == "choice":
                    widget.addItem("the first choice", 1)
                    widget.addItem("the second choice", 2)
                else:
                    widget.setEditable(True)
                    widget.lineEdit().setPlaceholderText("choose a flag or type a new name")
                    for name in self.studio.flag_names():
                        widget.addItem(name, name)
                index = widget.findData(value)
                if index >= 0 or kind != "flag":
                    widget.setCurrentIndex(max(index, 0))
                else:
                    widget.setEditText(str(value))
            widget.setAccessibleName(label)
            self.form.addRow(label, widget)
            self._inputs.append((kind, at, widget))

    def step_values(self) -> tuple | None:
        """The chosen step with what the form now holds."""
        step = self._current()
        if step is None:
            return None
        values = list(step)
        for kind, at, widget in self._inputs:
            values[at] = (widget.toPlainText() if kind == "text" else widget.text() if kind == "line"
                          else widget.value() if kind == "number"
                          else widget.currentText().strip() if kind == "flag"
                          else widget.currentData())
        return tuple(values)

    def apply_step(self) -> bool:
        step = self.step_values()
        if step is None:
            return False
        studio, key, index = self.studio, self.key, self.step

        def action() -> None:
            for kind, at, _widget in self._inputs:
                if kind == "flag" and step[at] and step[at] not in studio.flag_names():
                    studio.add_flag(step[at])
            studio.set_step(key, index, step)

        return self._try(action)

    def set_step(self, step: tuple) -> bool:
        studio, key, index = self.studio, self.key, self.step
        return self._try(lambda: studio.set_step(key, index, step))

    def add_step(self, kind: str) -> None:
        action = next((item for item in LIBRARY if item.kind == kind), None)
        if action is None or not self._mine():
            self.tell("Choose one of your events and a step to add.")
            return
        if not action.proven:
            self.tell(f"{action.title}: this {ev.NOT_PROVEN}.")
            return
        studio, key = self.studio, self.key
        at = self.step + 1 if self.steps.count() else 0
        made: list[int] = []
        if self._try(lambda: made.append(studio.add_step(key, action.template, at))):
            self.select(key, made[0])

    def remove_step(self) -> None:
        studio, key, index = self.studio, self.key, self.step
        if self._mine():
            self._try(lambda: studio.remove_step(key, index))

    def move_step(self, move: int) -> None:
        studio, key, index = self.studio, self.key, self.step
        made: list[int] = []
        if self._mine() and self._try(lambda: made.append(studio.move_step(key, index, move))):
            self.select(key, made[0])

    def apply_trigger(self) -> None:
        if not self._mine():
            return
        studio, key = self.studio, self.key
        event = studio.event(key)
        trigger, identity = self.trigger.currentData(), self.map.currentData() or ""
        rect = event.rect if len(event.rect) == 4 else (0, 0, 16, 16)
        self._try(lambda: studio.set_trigger(key, trigger, identity, rect,
                                             self.activation.currentData()))

    def _ask_name(self, title: str, text: str) -> str:
        name, accepted = QInputDialog.getText(self, title, text)
        return name.strip() if accepted else ""

    def new_event(self) -> None:
        name = self.pick_name("New event", "A name for this event:")
        if name:
            studio = self.studio
            made: list[str] = []
            if self._try(lambda: made.append(studio.new_event(name))):
                self.select(made[0])

    def duplicate(self) -> None:
        studio, key = self.studio, self.key
        made: list[str] = []
        if self._mine() and self._try(lambda: made.append(studio.duplicate(key))):
            self.select(made[0])

    def rename(self) -> None:
        name = self.pick_name("Rename event", "Your name for this event:") if self._mine() else ""
        if name:
            studio, key = self.studio, self.key
            self._try(lambda: studio.rename(key, name))

    def set_group(self) -> None:
        if self._mine():
            studio, key = self.studio, self.key
            group = self.pick_name("Group", "A group to keep this event in (empty for none):")
            self._try(lambda: studio.set_group(key, group))

    def delete(self) -> None:
        studio, key = self.studio, self.key
        if self._mine() and self._try(lambda: studio.delete(key)):
            self.key = ""
            self.refresh()

    def _fill_story(self) -> None:
        self.story.clear()
        try:
            rows = self.studio.story()
        except CreatorError as exc:
            self.tell(str(exc))
            return
        for row in rows:
            item = QListWidgetItem(
                f"{row.name}\n   set by: {', '.join(row.set_by) or 'nothing'}"
                f"\n   read by: {', '.join(row.read_by) or 'nothing'}"
                + (f"\n   ⚠ {row.note}" if row.note else ""))
            item.setData(KEY, row.name)
            self.story.addItem(item)

    def _flag(self) -> str:
        item = self.story.currentItem()
        if item is None:
            self.tell("Choose a flag in the Story list first.")
        return item.data(KEY) if item else ""

    def new_flag(self) -> None:
        name = self.pick_name("New flag", "A name, such as met_the_guard:")
        if name:
            studio = self.studio
            self._try(lambda: studio.add_flag(name))

    def rename_flag(self) -> None:
        old = self._flag()
        new = self.pick_name("Rename flag", "The new name:") if old else ""
        if new:
            studio = self.studio
            self._try(lambda: studio.rename_flag(old, new))

    def delete_flag(self) -> None:
        name = self._flag()
        if name:
            studio = self.studio
            self._try(lambda: studio.delete_flag(name))

    def show_trace(self) -> None:
        self.trace.clear()
        lines = self.studio.trace(self.output) if self.studio and self.output else []
        self.trace.addItems(lines or ["Nothing yet. Build, press Play with trace, play, then "
                                      "read the trace again."])
        self.side.setCurrentIndex(2)

    def undo(self) -> None:
        if self.studio is not None:
            self._try(self.studio.undo)

    def redo(self) -> None:
        if self.studio is not None:
            self._try(self.studio.redo)
