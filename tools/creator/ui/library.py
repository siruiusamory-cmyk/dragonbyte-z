"""The library: browse every map in the game by name and by picture."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QProcess, QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..model import jobs
from ..model.library import map_entries, thumbnail_path

INDEX = Qt.ItemDataRole.UserRole


class LibraryPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._directory: Path | None = None
        self._process: QProcess | None = None
        self._waiting: dict[int, QListWidgetItem] = {}
        self.failed: list[int] = []

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search maps by name or number...")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Search maps")
        self.maps = QListWidget()
        self.maps.setAccessibleName("Maps")
        self.maps.setIconSize(QSize(96, 96))
        self.maps.setUniformItemSizes(True)
        self.status = QLabel()
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(self.search)
        left_layout.addWidget(self.maps, 1)
        left_layout.addWidget(self.status)

        self.title = QLabel("Pick a map to see it.")
        self.picture = QLabel()
        self.picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.picture.setAccessibleName("Map picture")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.picture)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(self.title)
        right_layout.addWidget(scroll, 1)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        QVBoxLayout(self).addWidget(splitter)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._load_pictures)
        self.search.textChanged.connect(self._filter)
        self.maps.currentItemChanged.connect(lambda *_: self._show())

    def set_project(self, directory: Path, rom: Path) -> None:
        self.stop()
        self._directory = Path(directory)
        self.failed = []
        self.maps.clear()
        self._waiting = {}
        for index, label in map_entries(rom):
            item = QListWidgetItem(f"map:{index:04d}   {label}" if label else f"map:{index:04d}")
            item.setData(INDEX, index)
            self.maps.addItem(item)
            self._waiting[index] = item
        self._filter()
        self._load_pictures()
        if not self._waiting:
            return
        job = jobs.write_job("thumbnails", self._directory, rom, self._directory)
        command = jobs.job_command(job)
        process = QProcess(self)
        if jobs.job_directory():
            process.setWorkingDirectory(jobs.job_directory())
        process.finished.connect(lambda code, _status: self._finished(job, code))
        self._process = process
        process.start(command[0], command[1:])
        self._timer.start()
        self._load_pictures()

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

    def _finished(self, job: Path, exit_code: int) -> None:
        self._process = None
        self._timer.stop()
        result = jobs.read_result(job, exit_code)
        self.failed = list(result.get("failed", []))
        self._load_pictures()
        if result.get("error"):
            self.status.setText("⚠ Map pictures stopped early. Reopen the project to continue them.")

    def _load_pictures(self) -> None:
        for index in sorted(self._waiting):
            path = thumbnail_path(self._directory, index)
            if path.is_file():
                self._waiting.pop(index).setIcon(QIcon(str(path)))
        total = self.maps.count()
        if self.working:
            self.status.setText(f"Making map pictures... {total - len(self._waiting)} of {total}")
        elif self._waiting:
            self.status.setText(f"⚠ {len(self._waiting)} of {total} maps have no picture")
        else:
            self.status.setText(f"✔ {total} maps")
        if self.maps.currentItem() is not None and self.picture.pixmap().isNull():
            self._show()

    def _filter(self) -> None:
        needle = self.search.text().casefold()
        for row in range(self.maps.count()):
            item = self.maps.item(row)
            item.setHidden(needle not in item.text().casefold())

    def _show(self) -> None:
        item = self.maps.currentItem()
        if item is None or self._directory is None:
            return
        self.title.setText(item.text())
        picture = QPixmap(str(thumbnail_path(self._directory, item.data(INDEX))))
        self.picture.setPixmap(picture)
        if picture.isNull():
            self.picture.setText("The picture for this map is not ready yet.")
