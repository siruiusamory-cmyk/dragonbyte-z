"""The one window: project actions, the text surface, problems, build and play."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..model import jobs
from ..model.project import CreatorError, CreatorProject, RomMissingError
from ..model.settings import AppSettings, launch_emulator
from .dialogue_editor import DialogueEditor
from .library import LibraryPage
from .map_editor import MapEditor
from .new_project import ROM_FILTER, NewProjectDialog
from .text_editor import TextEditor

log = logging.getLogger("dragonbyte-z")
BUILD_STATUS = {
    "current": "✔ Build is up to date",
    "outdated": "⚠ Build is out of date - Build again to play your latest changes",
    "none": "Not built yet",
}


class MainWindow(QMainWindow):
    job_finished = Signal(str, dict)

    def __init__(self, title: str, settings_directory: Path, *, quiet: bool = False) -> None:
        super().__init__()
        self._title = title
        self._settings_directory = Path(settings_directory)
        self.settings = AppSettings.load(self._settings_directory)
        self.project: CreatorProject | None = None
        self.quiet = quiet
        self.messages: list[str] = []
        self._process: QProcess | None = None
        self._job: tuple[str, Path] | None = None
        self._play_after = False
        self.emulator_process = None

        self.editor = TextEditor()
        self.editor.changed.connect(self.refresh_state)
        self.editor.editor.undo_requested.connect(self.undo)
        self.editor.editor.redo_requested.connect(self.redo)
        self.pages = QStackedWidget()
        self.pages.addWidget(self._welcome())
        self.library = LibraryPage()
        self.tabs = QTabWidget()
        self.tabs.addTab(self.editor, "Text")
        self.tabs.addTab(self.library, "Library")
        self.maps = MapEditor()
        self.maps.changed.connect(self.refresh_state)
        self.tabs.addTab(self.maps, "Maps")
        self.dialogue = DialogueEditor()
        self.dialogue.changed.connect(self.refresh_state)
        self.tabs.addTab(self.dialogue, "Dialogue")
        self.tabs.currentChanged.connect(self._tab_changed)
        self.pages.addWidget(self.tabs)
        self.setCentralWidget(self.pages)

        self.problems = QListWidget()
        self.problems.setAccessibleName("Problems")
        self.problems.itemActivated.connect(self._open_problem)
        self.problems.itemClicked.connect(self._open_problem)
        dock = QDockWidget("Problems", self)
        dock.setObjectName("problems")
        dock.setWidget(self.problems)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        self.resizeDocks([dock], [130], Qt.Orientation.Vertical)

        self.actions_by_name: dict[str, QAction] = {}
        bar = QToolBar("Main")
        bar.setObjectName("main")
        bar.setMovable(False)
        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(bar)
        for name, slot, shortcut, tip in (
            ("New Project", self.new_project, QKeySequence.StandardKey.New, "Start a project from your Buu's Fury ROM"),
            ("Open Project", self.open_project, QKeySequence.StandardKey.Open, "Open a project folder"),
            (None, None, None, None),
            ("Save", self.save, QKeySequence.StandardKey.Save, "Save your changes into the project"),
            ("Undo", self.undo, QKeySequence.StandardKey.Undo, "Undo the last change"),
            ("Redo", self.redo, QKeySequence.StandardKey.Redo, "Redo the change you undid"),
            (None, None, None, None),
            ("Validate", self.validate, QKeySequence("F7"), "Check the project for problems"),
            ("Build", self.build, QKeySequence("F6"), "Save, check and build a playable ROM"),
            ("Play", self.play, QKeySequence("F5"), "Play the built ROM in mGBA"),
            (None, None, None, None),
            ("Choose Emulator", self.choose_emulator, None, "Tell DragonByte Z where mGBA is"),
        ):
            if name is None:
                bar.addSeparator()
                continue
            action = QAction(name, self)
            action.setToolTip(tip)
            if shortcut is not None:
                action.setShortcut(shortcut)
            action.triggered.connect(slot)
            bar.addAction(action)
            self.actions_by_name[name] = action

        self.state_label = QLabel()
        self.build_label = QLabel()
        self.statusBar().addWidget(self.state_label, 1)
        self.statusBar().addPermanentWidget(self.build_label)
        self.resize(1180, 760)
        self.refresh_state()

    def _welcome(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading = QLabel("DragonByte Z")
        font = heading.font()
        font.setPointSize(font.pointSize() + 12)
        font.setBold(True)
        heading.setFont(font)
        layout.addWidget(heading, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(
            QLabel("Make your game on the Buu's Fury engine. Start a project or open one."),
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        for text, slot in (("New Project...", self.new_project), ("Open Project...", self.open_project)):
            button = QPushButton(text)
            button.setMinimumSize(260, 44)
            button.clicked.connect(slot)
            layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignCenter)
        self.recent = QListWidget()
        self.recent.setMaximumSize(560, 170)
        self.recent.setAccessibleName("Recent projects")
        self.recent.itemActivated.connect(lambda item: self.open_path(Path(item.text())))
        layout.addWidget(QLabel("Recent projects (double-click to open)"), alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.recent, alignment=Qt.AlignmentFlag.AlignCenter)
        return page

    def _studio_tab(self):
        """The open tab when it keeps its own history on disk, else None."""
        tab = self.tabs.currentWidget()
        return tab if tab in (self.maps, self.dialogue) else None

    def _tab_changed(self, _index: int) -> None:
        self.dialogue.apply_pending()
        if self.project is not None and self.tabs.currentWidget() is self.dialogue:
            self.dialogue.refresh()
        self.refresh_state()

    def tell(self, text: str, *, problem: bool = False) -> None:
        self.messages.append(text)
        log.info("%s", text)
        if self.quiet:
            return
        (QMessageBox.warning if problem else QMessageBox.information)(self, self._title, text)

    def ask(self, text: str, yes: str, no: str = "Cancel") -> bool:
        if self.quiet:
            return True
        box = QMessageBox(QMessageBox.Icon.Question, self._title, text, parent=self)
        accept = box.addButton(yes, QMessageBox.ButtonRole.AcceptRole)
        box.addButton(no, QMessageBox.ButtonRole.RejectRole)
        box.exec()
        return box.clickedButton() is accept

    def refresh_state(self) -> None:
        project = self.project
        busy = self._process is not None
        self.pages.setCurrentIndex(1 if project else 0)
        history = self._studio_tab().studio if self._studio_tab() else project
        enabled = {
            "Save": bool(project and project.dirty),
            "Undo": bool(project and history and history.can_undo),
            "Redo": bool(project and history and history.can_redo),
            "Validate": bool(project) and not busy,
            "Build": bool(project) and not busy,
            "Play": bool(project) and not busy,
        }
        for name, state in enabled.items():
            self.actions_by_name[name].setEnabled(state)
        if project is None:
            self.setWindowTitle(self._title)
            self.state_label.setText("No project open")
            self.build_label.setText("")
            self.recent.clear()
            self.recent.addItems([item for item in self.settings.recent if Path(item).is_dir()])
            return
        mark = "● " if project.dirty else ""
        self.setWindowTitle(f"{mark}{project.name} - {self._title}")
        self.state_label.setText(
            f"{project.name}   |   "
            + ("● Unsaved changes (kept safe for recovery)" if project.dirty else "✔ All changes saved")
            + ("   |   Working..." if busy else "")
        )
        self.build_label.setText(BUILD_STATUS[project.build_status()])

    def new_project(self) -> None:
        if not self._leave_project():
            return
        dialog = NewProjectDialog(self.settings.last_directory, self)
        if dialog.exec():
            self.create_project(dialog.rom_path(), dialog.project_directory(), dialog.project_name())

    def create_project(self, rom: Path, directory: Path, name: str) -> bool:
        try:
            self._adopt(CreatorProject.create(rom, directory, name))
        except CreatorError as exc:
            self.tell(str(exc), problem=True)
            return False
        return True

    def open_project(self) -> None:
        if not self._leave_project():
            return
        chosen = QFileDialog.getExistingDirectory(self, "Open Project Folder", self.settings.last_directory)
        if chosen:
            self.open_path(Path(chosen))

    def open_path(self, directory: Path, rom: Path | None = None) -> bool:
        try:
            project = CreatorProject.open(directory, rom)
        except RomMissingError as exc:
            if self.quiet or rom is not None:
                self.tell(str(exc), problem=True)
                return False
            self.tell(str(exc), problem=True)
            chosen, _ = QFileDialog.getOpenFileName(self, "Locate your Buu's Fury ROM", "", ROM_FILTER)
            return bool(chosen) and self.open_path(directory, Path(chosen))
        except CreatorError as exc:
            self.tell(str(exc), problem=True)
            return False
        self._adopt(project)
        if project.recovered:
            count = len(project.recovered)
            if self.ask(
                f"DragonByte Z closed unexpectedly with {count} unsaved text change(s). Restore them?",
                "Restore my changes",
                "Discard them",
            ):
                project.restore_recovery()
            else:
                project.discard_recovery()
            self.editor.refresh()
            self.refresh_state()
        return True

    def _adopt(self, project: CreatorProject) -> None:
        self.project = project
        self.problems.clear()
        self.settings.remember_project(project.directory)
        self.settings.save(self._settings_directory)
        self.editor.set_project(project)
        self.library.set_project(project.directory, project.rom_path)
        self.maps.set_project(project.directory, project.rom_path)
        self.dialogue.set_project(project.directory, project.rom_path)
        self.refresh_state()

    def _leave_project(self, *, closing: bool = False) -> bool:
        """Settle unsaved changes before the project is replaced or the window closes."""
        if self.project is None:
            return True
        self.editor.apply_pending()
        self.dialogue.apply_pending()
        if not self.project.dirty or self.quiet:
            return True
        box = QMessageBox(QMessageBox.Icon.Question, self._title, "Save your changes first?", parent=self)
        save = box.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton("Discard changes", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is save:
            return self.save()
        if box.clickedButton() is discard:
            if closing:
                self.project.discard_recovery()
                return True
            try:
                self._adopt(self.project.discard_changes())
            except CreatorError as exc:
                self.tell(f"Your changes were not discarded. {exc}", problem=True)
                return False
            return True
        return False

    def closeEvent(self, event) -> None:
        if self._leave_project(closing=True):
            self.library.stop()
            event.accept()
        else:
            event.ignore()

    def save(self) -> bool:
        if self.project is None or not self.editor.apply_pending() or not self.dialogue.apply_pending():
            return False
        try:
            if self.project.dirty:
                self.project.save()
        except CreatorError as exc:
            self.tell(str(exc), problem=True)
            return False
        self.refresh_state()
        return True

    def undo(self) -> None:
        self._history(self._undo_text)

    def redo(self) -> None:
        self._history(self._redo_text)

    def _undo_text(self) -> None:
        if self.project.can_undo:
            self.project.undo()

    def _redo_text(self) -> None:
        if self.project.can_redo:
            self.project.redo()

    def _history(self, move) -> None:
        if self.project is None:
            return
        tab = self._studio_tab()
        if tab is not None:
            (tab.undo if move == self._undo_text else tab.redo)()
            self.refresh_state()
            return
        self.editor.apply_pending()
        try:
            move()
        except CreatorError as exc:
            self.tell(str(exc), problem=True)
        self.editor.refresh()
        self.refresh_state()

    def validate(self) -> None:
        self._start("validate")

    def build(self) -> None:
        self._start("build")

    def _start(self, action: str) -> None:
        if self.project is None or self._process is not None or not self.save():
            return
        project = self.project
        job = jobs.write_job(action, project.directory, project.rom_path, project.output)
        command = jobs.job_command(job)
        process = QProcess(self)
        if jobs.job_directory():
            process.setWorkingDirectory(jobs.job_directory())
        process.finished.connect(lambda code, _status: self._finished(code))
        process.errorOccurred.connect(lambda _error: self._finished(-1))
        self._process, self._job = process, (action, job)
        self.problems.clear()
        self.refresh_state()
        process.start(command[0], command[1:])

    def _finished(self, exit_code: int) -> None:
        if self._process is None or self._job is None:
            return
        action, job = self._job
        self._process.deleteLater()
        self._process, self._job = None, None
        result = jobs.read_result(job, exit_code)
        log.info("%s finished: %s", action, result)
        for problem in result.get("problems", []):
            item = QListWidgetItem("⚠ " + problem["message"])
            item.setData(Qt.ItemDataRole.UserRole, problem.get("record", ""))
            self.problems.addItem(item)
        self.refresh_state()
        play, self._play_after = self._play_after, False
        if result.get("error"):
            self.tell(result["error"], problem=True)
        elif not result.get("ok"):
            self.tell(
                f"{len(result.get('problems', []))} problem(s) found. They are listed in the "
                "Problems panel; click one to go to it. Nothing was built.",
                problem=True,
            )
        elif action == "validate":
            self.tell("No problems found. The project is ready to build.")
        elif play:
            self._launch()
        else:
            self.tell(f"Build succeeded.\n\nYour playable ROM is at:\n{result['output']}")
        self.job_finished.emit(action, result)

    def _open_problem(self, item: QListWidgetItem) -> None:
        key = item.data(Qt.ItemDataRole.UserRole)
        if key:
            self.tabs.setCurrentWidget(self.editor)
            self.editor.select(key)

    def play(self) -> None:
        if self.project is None or self._process is not None:
            return
        self.editor.apply_pending()
        status = self.project.build_status()
        if status == "current":
            self._launch()
            return
        question = (
            "Your project changed since the last build, so the built ROM is out of date. Build it again and play?"
            if status == "outdated"
            else "This project has not been built yet. Build it and play?"
        )
        if self.ask(question, "Build and Play"):
            self._play_after = True
            self.build()

    def _launch(self) -> None:
        emulator = self.settings.emulator_path()
        if emulator is None and not self.quiet:
            self.tell("DragonByte Z needs to know where mGBA is. Choose mGBA.exe once and it is remembered.")
            emulator = self.choose_emulator()
        if emulator is None:
            self.tell("No emulator is set, so the game was not started.", problem=True)
            return
        try:
            self.emulator_process = launch_emulator(emulator, self.project.output)
        except OSError as exc:
            self.tell(f"mGBA could not be started: {exc.strerror}. Choose the emulator again.", problem=True)

    def choose_emulator(self) -> Path | None:
        chosen, _ = QFileDialog.getOpenFileName(self, "Choose mGBA.exe", self.settings.emulator, "Programs (*.exe)")
        if not chosen:
            return None
        self.settings.emulator = chosen
        self.settings.save(self._settings_directory)
        return Path(chosen)
