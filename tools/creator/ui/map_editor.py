"""The Maps tab: make a map from a game map, then place pieces, draw tiles, walls and doors."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..model.maps import CHUNK_PIXELS, TILE_PIXELS, TILES_PER_CHUNK, MapStudio
from ..model.project import CreatorError

GRID = 256
TOOLS = (
    ("pieces", "Place pieces", "Click or drag on the map to place the piece chosen on the right."),
    ("tiles", "Draw tiles", "Right-click a tile to pick it up. Left-click or drag to draw it."),
    ("walls", "Walls", "Drag to block or open ground. Hatched ground stops the player."),
    ("doors", "Doors", "Drag a box where the door is. Then choose where it leads."),
)


def _image(rgba: bytes, width: int, height: int) -> QImage:
    return QImage(rgba, width, height, QImage.Format.Format_RGBA8888).copy()


class MapCanvas(QWidget):
    def __init__(self, editor: "MapEditor") -> None:
        super().__init__()
        self.editor = editor
        self.picture = QImage()
        self.walls = QImage()
        self.zoom = 1.0
        self.drag: list = []
        self.box: QRect | None = None
        self.setMouseTracking(True)

    def sizeHint(self) -> QSize:
        return QSize(int(self.picture.width() * self.zoom), int(self.picture.height() * self.zoom))

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(40, 40, 46))
        painter.scale(self.zoom, self.zoom)
        painter.drawImage(0, 0, self.picture)
        editor = self.editor
        if editor.show_walls.isChecked() or editor.tool == "walls":
            painter.drawImage(QRect(0, 0, GRID * TILE_PIXELS, GRID * TILE_PIXELS), self.walls)
        if editor.tool in ("pieces", "tiles") and editor.layer is not None:
            painter.setPen(QPen(QColor(255, 255, 255, 110), 0, Qt.PenStyle.DotLine))
            for column in range(editor.layer.columns + 1):
                painter.drawLine(column * CHUNK_PIXELS, 0, column * CHUNK_PIXELS, editor.layer.height)
            for row in range(editor.layer.rows + 1):
                painter.drawLine(0, row * CHUNK_PIXELS, editor.layer.width, row * CHUNK_PIXELS)
        for number, door in enumerate(editor.doors, 1):
            left, top, right, bottom = door.rect
            pen = QPen(QColor(255, 255, 255), 2, Qt.PenStyle.DashLine if door.removed else Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.setBrush(QBrush(QColor(0, 0, 0, 60 if door.removed else 130)))
            painter.drawRect(left, top, max(right - left, 4), max(bottom - top, 4))
            painter.drawText(left + 3, top + 12, f"{number}")
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if self.box is not None:
            painter.setPen(QPen(QColor(255, 255, 255), 2, Qt.PenStyle.DashLine))
            painter.drawRect(self.box)
        if editor.tool == "tiles":
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            for cell, row, column in self.drag:
                origin = editor.cell_origin(cell)
                painter.drawRect(origin[0] + column * TILE_PIXELS, origin[1] + row * TILE_PIXELS,
                                 TILE_PIXELS, TILE_PIXELS)
        if editor.tool == "pieces":
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            for cell in self.drag:
                origin = editor.cell_origin(cell)
                painter.drawRect(origin[0], origin[1], CHUNK_PIXELS, CHUNK_PIXELS)

    def _place(self, event) -> tuple[int, int]:
        point = event.position()
        return int(point.x() / self.zoom), int(point.y() / self.zoom)

    def mousePressEvent(self, event) -> None:
        self.editor.down(*self._place(event), event.button() == Qt.MouseButton.RightButton)

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.editor.move(*self._place(event))

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.editor.up(*self._place(event))


class MapEditor(QWidget):
    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.studio: MapStudio | None = None
        self.key = ""
        self.tool = "pieces"
        self.layers: list = []
        self.layer = None
        self.doors: list = []
        self.grid = bytearray()
        self.tile: int | None = None
        self.pending_door: tuple | None = None
        self.messages: list[str] = []
        self.pick_destination = self._ask_destination
        self.pick_name = self._ask_name
        self._start: tuple[int, int] | None = None
        self._wall_dirty = False

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search maps")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._fill_maps)
        self.map_list = QListWidget()
        self.map_list.setAccessibleName("Maps")
        self.map_list.currentItemChanged.connect(self._map_chosen)
        self.new_button = QPushButton("New Map From This Map...")
        self.new_button.clicked.connect(self.new_map)
        self.rename_button = QPushButton("Rename My Map...")
        self.rename_button.clicked.connect(self.rename_map)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        for widget in (self.search, self.map_list, self.new_button, self.rename_button):
            left_layout.addWidget(widget)

        self.canvas = MapCanvas(self)
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.canvas)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.cancel = QPushButton("Cancel the new door")
        self.cancel.clicked.connect(self.cancel_door)
        self.cancel.hide()
        middle = QWidget()
        middle_layout = QVBoxLayout(middle)
        top = QHBoxLayout()
        top.addWidget(self.hint, 1)
        top.addWidget(self.cancel)
        self.zoom = QComboBox()
        self.zoom.addItems(["50%", "100%", "200%", "400%"])
        self.zoom.setCurrentIndex(1)
        self.zoom.setAccessibleName("Zoom")
        self.zoom.currentTextChanged.connect(self._zoomed)
        top.addWidget(self.zoom)
        middle_layout.addLayout(top)
        middle_layout.addWidget(self.scroll, 1)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.tools = QButtonGroup(self)
        for name, label, _hint in TOOLS:
            button = QRadioButton(label)
            button.setChecked(name == self.tool)
            button.toggled.connect(lambda on, name=name: on and self.set_tool(name))
            self.tools.addButton(button)
            right_layout.addWidget(button)
        right_layout.addWidget(QLabel("Layer"))
        self.layer_box = QComboBox()
        self.layer_box.setAccessibleName("Layer")
        self.layer_box.currentIndexChanged.connect(self._layer_chosen)
        right_layout.addWidget(self.layer_box)
        self.pieces = QListWidget()
        self.pieces.setAccessibleName("Pieces")
        self.pieces.setViewMode(QListWidget.ViewMode.IconMode)
        self.pieces.setIconSize(QSize(72, 72))
        self.pieces.setResizeMode(QListWidget.ResizeMode.Adjust)
        right_layout.addWidget(self.pieces, 2)
        size = QHBoxLayout()
        self.columns = QSpinBox()
        self.rows = QSpinBox()
        for box, name in ((self.columns, "Layer width in pieces"), (self.rows, "Layer height in pieces")):
            box.setRange(1, 8)
            box.setAccessibleName(name)
            size.addWidget(box)
        self.resize_button = QPushButton("Resize layer")
        self.resize_button.clicked.connect(lambda: self.resize_layer(self.columns.value(), self.rows.value()))
        size.addWidget(self.resize_button)
        right_layout.addLayout(size)
        self.show_walls = QCheckBox("Show walls")
        self.show_walls.toggled.connect(lambda _on: self.canvas.update())
        right_layout.addWidget(self.show_walls)
        self.block = QRadioButton("Block ground")
        self.open = QRadioButton("Open ground")
        self.block.setChecked(True)
        walls = QButtonGroup(self)
        for button in (self.block, self.open):
            walls.addButton(button)
            right_layout.addWidget(button)
        self.wall_note = QLabel()
        self.wall_note.setWordWrap(True)
        right_layout.addWidget(self.wall_note)
        right_layout.addWidget(QLabel("Doors on this map"))
        self.door_list = QListWidget()
        self.door_list.setAccessibleName("Doors")
        right_layout.addWidget(self.door_list, 1)
        self.remove_button = QPushButton("Remove / put back door")
        self.remove_button.clicked.connect(self.toggle_door)
        right_layout.addWidget(self.remove_button)

        splitter = QSplitter()
        for widget in (left, middle, right):
            splitter.addWidget(widget)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 640, 280])
        layout = QVBoxLayout(self)
        layout.addWidget(splitter)
        self.set_tool(self.tool)

    def set_project(self, directory: Path, rom_path: Path) -> None:
        self.studio = MapStudio(directory, rom_path)
        self.key = ""
        self.pending_door = None
        self.cancel.hide()
        self._fill_maps()
        if self.map_list.count():
            self.map_list.setCurrentRow(0)

    def tell(self, text: str) -> None:
        self.messages.append(text)
        self.hint.setText("⚠ " + text)

    def _try(self, action) -> bool:
        try:
            action()
        except CreatorError as exc:
            self.tell(str(exc))
            self.refresh()
            return False
        self.refresh()
        self.changed.emit()
        return True

    def _fill_maps(self) -> None:
        if self.studio is None:
            return
        wanted = self.search.text().strip().lower()
        self.map_list.blockSignals(True)
        self.map_list.clear()
        for row in self.studio.maps():
            if wanted in row.title.lower():
                item = QListWidgetItem(row.title)
                item.setData(Qt.ItemDataRole.UserRole, row.key)
                self.map_list.addItem(item)
                if row.key == self.key:
                    self.map_list.setCurrentItem(item)
        self.map_list.blockSignals(False)

    def _map_chosen(self, item, _previous=None) -> None:
        if item is not None:
            self.select_map(item.data(Qt.ItemDataRole.UserRole))

    def select_map(self, key: str) -> None:
        self.key = key
        self.layer = None
        self.refresh()
        for row in range(self.map_list.count()):
            if self.map_list.item(row).data(Qt.ItemDataRole.UserRole) == key:
                self.map_list.blockSignals(True)
                self.map_list.setCurrentRow(row)
                self.map_list.blockSignals(False)

    def refresh(self) -> None:
        """Read the map again from the project and redraw everything."""
        if self.studio is None or not self.key:
            return
        if self.key not in [row.key for row in self.studio.maps()]:
            self.key = self.studio.maps()[0].key
            self._fill_maps()
        try:
            self.layers = self.studio.layers(self.key)
            self.doors = self.studio.doors(self.key)
            self.grid = bytearray(self.studio.collision(self.key))
            note = self.studio.collision_note(self.key)
        except CreatorError as exc:
            self.layers, self.doors, self.grid, note = [], [], bytearray(GRID * GRID // 8), ""
            self.tell(str(exc))
        editable = [layer for layer in self.layers if layer.editable]
        slot = self.layer.slot if self.layer is not None else None
        self.layer = next((layer for layer in editable if layer.slot == slot), editable[0] if editable else None)
        self.layer_box.blockSignals(True)
        self.layer_box.clear()
        for layer in sorted(editable, key=lambda layer: layer.slot):
            self.layer_box.addItem(f"Layer {layer.slot + 1}  ({layer.columns} x {layer.rows} pieces)", layer.slot)
            if layer is self.layer:
                self.layer_box.setCurrentIndex(self.layer_box.count() - 1)
        self.layer_box.blockSignals(False)
        self.wall_note.setText(note)
        self.rename_button.setEnabled(self.key.startswith("map-new:"))
        self.new_button.setEnabled(not self.key.startswith("map-new:"))
        self._fill_pieces()
        self._fill_doors()
        self._compose()
        self._draw_walls()
        self.canvas.drag = []
        self.canvas.box = None
        self.canvas.resize(self.canvas.sizeHint())
        self.canvas.update()

    def _layer_chosen(self, _index: int) -> None:
        slot = self.layer_box.currentData()
        self.layer = next((layer for layer in self.layers if layer.slot == slot), self.layer)
        self._fill_pieces()
        self.canvas.update()

    def _fill_pieces(self) -> None:
        chosen = self.pieces.currentItem().data(Qt.ItemDataRole.UserRole) if self.pieces.currentItem() else None
        self.pieces.clear()
        if self.layer is None:
            return
        self.columns.setValue(self.layer.columns)
        self.rows.setValue(self.layer.rows)
        values = list(self.layer.choices) + sorted(
            {cell for cell in self.layer.cells if isinstance(cell, str)})
        for value in values:
            try:
                picture = _image(self.studio.chunk_picture(self.key, value), CHUNK_PIXELS, CHUNK_PIXELS)
            except CreatorError:
                continue
            item = QListWidgetItem(QIcon(QPixmap.fromImage(picture)), "yours" if isinstance(value, str) else "")
            item.setData(Qt.ItemDataRole.UserRole, value)
            self.pieces.addItem(item)
            if value == chosen:
                self.pieces.setCurrentItem(item)
        if self.pieces.currentItem() is None and self.pieces.count():
            self.pieces.setCurrentRow(0)

    def _fill_doors(self) -> None:
        self.door_list.clear()
        for number, door in enumerate(self.doors, 1):
            state = "✖ removed   " if door.removed else ("★ yours   " if door.created else "")
            item = QListWidgetItem(
                f"{number}.  {state}to {door.destination}, arriving at {door.arrival[0]}, {door.arrival[1]}"
                f"   (opens walking {door.walk})")
            item.setData(Qt.ItemDataRole.UserRole, door.key)
            self.door_list.addItem(item)

    def _compose(self) -> None:
        width = max((layer.width for layer in self.layers), default=CHUNK_PIXELS)
        height = max((layer.height for layer in self.layers), default=CHUNK_PIXELS)
        picture = QImage(width, height, QImage.Format.Format_RGBA8888)
        picture.fill(QColor(0, 0, 0))
        painter = QPainter(picture)
        for layer in self.layers:
            if not layer.editable:
                painter.drawImage(0, 0, _image(layer.picture, layer.width, layer.height))
                continue
            for cell, value in enumerate(layer.cells):
                try:
                    rgba = self.studio.chunk_picture(self.key, value)
                except CreatorError:
                    continue
                painter.drawImage((cell % layer.columns) * CHUNK_PIXELS, (cell // layer.columns) * CHUNK_PIXELS,
                                  _image(rgba, CHUNK_PIXELS, CHUNK_PIXELS))
        painter.end()
        self.canvas.picture = picture

    def _draw_walls(self) -> None:
        walls = QImage(GRID, GRID, QImage.Format.Format_ARGB32)
        walls.fill(0)
        for y in range(GRID):
            for x in range(GRID):
                if not self.grid[y * 32 + (x >> 3)] >> (x & 7) & 1:
                    walls.setPixel(x, y, (0xB0 if (x + y) % 2 else 0x58) << 24)
        self.canvas.walls = walls

    def _zoomed(self, text: str) -> None:
        self.canvas.zoom = int(text.rstrip("%")) / 100
        self.canvas.resize(self.canvas.sizeHint())
        self.canvas.update()

    def set_tool(self, name: str) -> None:
        self.tool = name
        self.hint.setText(next(hint for tool, _label, hint in TOOLS if tool == name))
        for button, (tool, _label, _hint) in zip(self.tools.buttons(), TOOLS):
            if tool == name and not button.isChecked():
                button.setChecked(True)
        self.canvas.drag = []
        self.canvas.box = None
        self.canvas.update()

    def cell_origin(self, cell: int) -> tuple[int, int]:
        return (cell % self.layer.columns) * CHUNK_PIXELS, (cell // self.layer.columns) * CHUNK_PIXELS

    def _cell(self, x: int, y: int) -> int | None:
        layer = self.layer
        if layer is None or not (0 <= x < layer.width and 0 <= y < layer.height):
            return None
        return (y // CHUNK_PIXELS) * layer.columns + x // CHUNK_PIXELS

    def _tile(self, x: int, y: int) -> tuple[int, int, int] | None:
        cell = self._cell(x, y)
        if cell is None:
            return None
        return cell, (y % CHUNK_PIXELS) // TILE_PIXELS, (x % CHUNK_PIXELS) // TILE_PIXELS

    def down(self, x: int, y: int, right: bool = False) -> None:
        if self.studio is None or not self.key:
            return
        if self.pending_door is not None:
            self._finish_door(x, y)
            return
        self._start = (x, y)
        if self.tool == "tiles" and right:
            place = self._tile(x, y)
            if place is not None:
                try:
                    self.tile = self.studio.tile_at(self.key, self.layer.slot, *place)
                    self.hint.setText("Tile picked up. Left-click or drag to draw it.")
                except CreatorError as exc:
                    self.tell(str(exc))
            self._start = None
            return
        if right:
            self._start = None
            return
        self.move(x, y)

    def move(self, x: int, y: int) -> None:
        if self._start is None:
            return
        if self.tool == "pieces":
            cell = self._cell(x, y)
            if cell is not None and cell not in self.canvas.drag:
                self.canvas.drag.append(cell)
        elif self.tool == "tiles":
            place = self._tile(x, y)
            if place is not None and place not in self.canvas.drag:
                self.canvas.drag.append(place)
        elif self.tool == "walls":
            tx, ty = x // TILE_PIXELS, y // TILE_PIXELS
            if 0 <= tx < GRID and 0 <= ty < GRID:
                index, bit = ty * 32 + (tx >> 3), 1 << (tx & 7)
                self.grid[index] = self.grid[index] | bit if self.open.isChecked() else self.grid[index] & ~bit
                self.canvas.walls.setPixel(
                    tx, ty, 0 if self.open.isChecked() else (0xB0 if (tx + ty) % 2 else 0x58) << 24)
                self._wall_dirty = True
        elif self.tool == "doors":
            self.canvas.box = QRect(QPoint(*self._start), QPoint(x, y)).normalized()
        self.canvas.update()

    def up(self, x: int, y: int) -> None:
        if self._start is None:
            return
        self.move(x, y)
        self._start = None
        studio, key = self.studio, self.key
        if self.tool == "pieces" and self.canvas.drag and self.pieces.currentItem() is not None:
            value = self.pieces.currentItem().data(Qt.ItemDataRole.UserRole)
            cells = list(self.canvas.drag)
            self._try(lambda: studio.paint(key, self.layer.slot, cells, value))
        elif self.tool == "tiles" and self.canvas.drag:
            if self.tile is None:
                self.tell("Right-click a tile first to pick it up.")
                self.refresh()
                return
            by_cell: dict[int, dict] = {}
            for cell, row, column in self.canvas.drag:
                by_cell.setdefault(cell, {})[(row, column)] = self.tile
            slot = self.layer.slot
            for cell, tiles in by_cell.items():
                if not self._try(lambda: studio.stamp(key, slot, cell, tiles)):
                    break
        elif self.tool == "walls" and self._wall_dirty:
            self._wall_dirty = False
            grid = bytes(self.grid)
            self._try(lambda: studio.set_collision(key, grid))
        elif self.tool == "doors" and self.canvas.box is not None:
            box = self.canvas.box
            self.canvas.box = None
            if box.width() < 4 or box.height() < 4:
                self.tell("Drag a bigger box for the door.")
                self.canvas.update()
                return
            self.start_door((box.left(), box.top(), box.right() + 1, box.bottom() + 1))
        else:
            self.canvas.drag = []
            self.canvas.update()

    def start_door(self, rect: tuple[int, int, int, int]) -> None:
        problem = self.studio.can_add_door(self.key)
        if problem:
            self.tell(problem)
            return
        destination = self.pick_destination()
        if not destination:
            self.canvas.update()
            return
        self.pending_door = (self.key, rect, destination)
        self.cancel.show()
        self.select_map(destination)
        self.hint.setText(f"Click where the player arrives in {self.studio.title(destination)}.")

    def _finish_door(self, x: int, y: int) -> None:
        source, rect, destination = self.pending_door
        if self.key != destination:
            self.select_map(destination)
            self.tell(f"Click where the player arrives in {self.studio.title(destination)}, or cancel the door.")
            return
        self.pending_door = None
        self.cancel.hide()
        studio = self.studio
        self.select_map(source)
        if self._try(lambda: studio.add_door(source, rect, destination, (x, y))):
            self.set_tool("doors")
            self.hint.setText(
                f"Door added. It opens when the player walks {studio.door_walk(source)} into it. "
                "Build and play to walk through it.")

    def cancel_door(self) -> None:
        if self.pending_door is not None:
            source = self.pending_door[0]
            self.pending_door = None
            self.cancel.hide()
            self.select_map(source)
            self.set_tool("doors")

    def toggle_door(self) -> None:
        item = self.door_list.currentItem()
        if item is None:
            self.tell("Choose a door in the list first.")
            return
        door = next(door for door in self.doors if door.key == item.data(Qt.ItemDataRole.UserRole))
        studio, key = self.studio, self.key
        self._try(lambda: studio.remove_door(key, door.key, not door.removed))

    def resize_layer(self, columns: int, rows: int) -> None:
        if self.layer is None:
            return
        studio, key, slot = self.studio, self.key, self.layer.slot
        self._try(lambda: studio.resize(key, slot, columns, rows))

    def _ask_name(self, title: str, text: str) -> str:
        name, accepted = QInputDialog.getText(self, title, text)
        return name if accepted else ""

    def _ask_destination(self) -> str:
        rows = self.studio.maps()
        title, accepted = QInputDialog.getItem(
            self, "Where does this door lead?", "Destination map", [row.title for row in rows], 0, False)
        return next((row.key for row in rows if row.title == title), "") if accepted else ""

    def new_map(self) -> None:
        name = self.pick_name("New map", "Name for your new map (lowercase letters, digits, - and _):")
        if not name:
            return
        studio, donor = self.studio, self.key
        made: list[str] = []
        if self._try(lambda: made.append(studio.create(name, donor))):
            self._fill_maps()
            self.select_map(made[0])

    def rename_map(self) -> None:
        name = self.pick_name("Rename map", "New name:")
        if not name:
            return
        studio, key = self.studio, self.key
        made: list[str] = []
        if self._try(lambda: made.append(studio.rename(key, name))):
            self.key = made[0]
            self._fill_maps()
            self.refresh()

    def undo(self) -> None:
        if self.studio is not None and self.studio.can_undo:
            self.studio.undo()
            self._fill_maps()
            self.refresh()

    def redo(self) -> None:
        if self.studio is not None and self.studio.can_redo:
            self.studio.redo()
            self._fill_maps()
            self.refresh()
