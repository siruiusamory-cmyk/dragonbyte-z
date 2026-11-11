"""The library: browse the game's maps, character sprites and portraits."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QProcess, QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSplitter,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from ..model import jobs
from ..model.library import KINDS, picture_path, read_index, read_names, set_name

KEY = Qt.ItemDataRole.UserRole
TITLES = {"map": "Maps", "sprite": "Sprites", "portrait": "Portraits"}
PREVIEW = 384


class LibraryPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._directory: Path | None = None
        self._process: QProcess | None = None
        self._assets: dict[str, dict] = {}
        self._names: dict[str, str] = {}
        self._waiting: dict[str, QListWidgetItem] = {}
        self._stopped_early = False
        self.failed: list[str] = []

        self.kinds = QTabBar()
        self.kinds.setAccessibleName("Kind of asset")
        for kind in KINDS:
            self.kinds.addTab(TITLES[kind])
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by name or number...")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Search the library")
        self.items = QListWidget()
        self.items.setAccessibleName("Library items")
        self.items.setIconSize(QSize(96, 96))
        self.items.setUniformItemSizes(True)
        self.status = QLabel()
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(self.kinds)
        left_layout.addWidget(self.search)
        left_layout.addWidget(self.items, 1)
        left_layout.addWidget(self.status)

        self.title = QLabel("Pick something to see it.")
        self.name = QLineEdit()
        self.name.setPlaceholderText("Give it your own name (optional)")
        self.name.setAccessibleName("Your name for this")
        self.name.setEnabled(False)
        name_row = QHBoxLayout()
        name_label = QLabel("Your &name:")
        name_label.setBuddy(self.name)
        name_row.addWidget(name_label)
        name_row.addWidget(self.name, 1)
        self.picture = QLabel()
        self.picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.picture.setAccessibleName("Picture")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.picture)
        self.uses = QLabel()
        self.uses.setWordWrap(True)
        self.uses.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.uses.setAccessibleName("Where it is used")
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(self.title)
        right_layout.addLayout(name_row)
        right_layout.addWidget(scroll, 1)
        right_layout.addWidget(QLabel("Where it is used"))
        right_layout.addWidget(self.uses)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([440, 740])
        QVBoxLayout(self).addWidget(splitter)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._poll)
        self.kinds.currentChanged.connect(lambda _index: self._fill())
        self.search.textChanged.connect(self._filter)
        self.items.currentItemChanged.connect(lambda *_: self._show())
        self.name.editingFinished.connect(self.apply_name)

    def set_project(self, directory: Path, rom: Path) -> None:
        self.stop()
        self._directory = Path(directory)
        self._names = read_names(self._directory)
        self._assets = {}
        self._stopped_early = False
        self.failed = []
        self._adopt_index()
        if self._assets and all(picture_path(self._directory, key).is_file() for key in self._assets):
            return
        job = jobs.write_job("library", self._directory, rom, self._directory)
        command = jobs.job_command(job)
        process = QProcess(self)
        if jobs.job_directory():
            process.setWorkingDirectory(jobs.job_directory())
        process.finished.connect(lambda code, _status: self._finished(job, code))
        self._process = process
        process.start(command[0], command[1:])
        self._timer.start()
        self._poll()

    def stop(self) -> None:
        self._timer.stop()
        if self._process is not None:
            process, self._process = self._process, None
            process.finished.disconnect()
            process.kill()
            process.waitForFinished(3000)

    @property
    def working(self) -> bool:
        return self._process is not None

    @property
    def kind(self) -> str:
        return KINDS[self.kinds.currentIndex()]

    def _finished(self, job: Path, exit_code: int) -> None:
        self._process = None
        self._timer.stop()
        result = jobs.read_result(job, exit_code)
        self.failed = list(result.get("failed", []))
        self._stopped_early = not result.get("ok")
        self._poll()

    def _adopt_index(self) -> None:
        assets = read_index(self._directory)
        if assets is None:
            self._fill()
            return
        self._assets = {asset["key"]: asset for asset in assets}
        self._fill()

    def _poll(self) -> None:
        if not self._assets:
            self._adopt_index()
        self._load_pictures()

    def _text(self, asset: dict) -> str:
        own = self._names.get(asset["key"], "")
        parts = [own, asset["key"], asset["label"]] if own else [asset["key"], asset["label"]]
        return "   ".join(part for part in parts if part)

    def _fill(self) -> None:
        self.items.clear()
        self._waiting = {}
        for asset in self._assets.values():
            if asset["kind"] != self.kind:
                continue
            item = QListWidgetItem(self._text(asset))
            item.setData(KEY, asset["key"])
            self.items.addItem(item)
            self._waiting[asset["key"]] = item
        self._filter()
        self._load_pictures()
        self._show()

    def _load_pictures(self) -> None:
        for key in list(self._waiting):
            path = picture_path(self._directory, key)
            if path.is_file():
                picture = QPixmap(str(path))
                if picture.width() < 96:
                    picture = picture.scaledToWidth(96, Qt.TransformationMode.FastTransformation)
                self._waiting.pop(key).setIcon(QIcon(picture))
        total = self.items.count()
        title = TITLES[self.kind].lower()
        if not self._assets:
            self.status.setText(
                "⚠ The library could not be read. Reopen the project to try again."
                if self._stopped_early
                else "Reading the game..."
            )
        elif self.working:
            self.status.setText(f"Making pictures... {total - len(self._waiting)} of {total} {title}")
        elif self._waiting:
            self.status.setText(f"⚠ {len(self._waiting)} of {total} {title} have no picture")
        else:
            self.status.setText(f"✔ {total} {title}")
        if self.items.currentItem() is not None and self.picture.pixmap().isNull():
            self._show()

    def _filter(self) -> None:
        needle = self.search.text().casefold()
        for row in range(self.items.count()):
            item = self.items.item(row)
            item.setHidden(needle not in item.text().casefold())

    def select(self, key: str) -> bool:
        asset = self._assets.get(key)
        if asset is None:
            return False
        self.kinds.setCurrentIndex(KINDS.index(asset["kind"]))
        self.search.clear()
        for row in range(self.items.count()):
            if self.items.item(row).data(KEY) == key:
                self.items.setCurrentRow(row)
                return True
        return False

    def _show(self) -> None:
        item = self.items.currentItem()
        self.name.setEnabled(item is not None)
        if item is None or self._directory is None:
            self.title.setText("Pick something to see it.")
            self.name.clear()
            self.picture.clear()
            self.uses.clear()
            return
        key = item.data(KEY)
        asset = self._assets[key]
        self.title.setText("   ".join(part for part in (key, asset["label"]) if part))
        self.name.setText(self._names.get(key, ""))
        self.uses.setText("\n".join(asset["uses"]))
        picture = QPixmap(str(picture_path(self._directory, key)))
        if picture.isNull():
            self.picture.setText("The picture is not ready yet.")
            return
        scale = PREVIEW // max(picture.width(), picture.height())
        if scale > 1:
            picture = picture.scaled(picture.size() * scale, Qt.AspectRatioMode.KeepAspectRatio)
        self.picture.setPixmap(picture)

    def apply_name(self) -> None:
        item = self.items.currentItem()
        if item is None or self._directory is None:
            return
        key = item.data(KEY)
        if " ".join(self.name.text().split()) == self._names.get(key, ""):
            return
        try:
            self._names = set_name(self._directory, key, self.name.text())
        except OSError as exc:
            self.status.setText(f"⚠ The name could not be saved: {exc.strerror}")
            return
        item.setText(self._text(self._assets[key]))
