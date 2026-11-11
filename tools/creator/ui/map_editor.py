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

from ..model import library
from ..model.maps import CHUNK_PIXELS, TILE_PIXELS, TILES_PER_CHUNK, MapStudio
from ..model.project import CreatorError

GRID = 256
TOOLS = (
    ("pieces", "Place pieces", "Click or drag on the map to place the piece chosen on the right."),
    ("tiles", "Draw tiles", "Right-click a tile to pick it up. Left-click or drag to draw it."),
    ("walls", "Walls", "Drag to block or open ground. Hatched ground stops the player."),
    ("doors", "Doors", "Drag a box where the door is. Then choose where it leads."),
    ("characters", "Characters",
     "Click a character to choose it and drag it to move it. Add new ones from the list on the right."),
)
MARKER = 16


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
        self.ghost: tuple[int, int] | None = None
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
        for character in editor.characters:
            chosen = character.key == editor.chosen and editor.tool == "characters"
            x, y = (self.ghost if chosen and self.ghost is not None else (character.x, character.y))
            rect = editor.character_rect(character, x, y)
            picture = editor.sprite_picture(character.sprite)
            painter.setOpacity(0.35 if character.removed else 1.0)
            if picture.isNull():
                painter.setPen(QPen(QColor(255, 255, 255), 1))
                painter.fillRect(rect, QColor(0, 0, 0, 150))
                painter.drawRect(rect)
            else:
                painter.drawPixmap(rect.topLeft(), picture)
            painter.setOpacity(1.0)
            if chosen:
                painter.setPen(QPen(QColor(255, 255, 255), 2))
                painter.drawRect(rect.adjusted(-2, -2, 2, 2))
                painter.drawLine(x - 4, y, x + 4, y)
                painter.drawLine(x, y - 4, x, y + 4)
                if character.box is not None and self.ghost is None:
                    left, top, right, bottom = character.box
                    painter.setPen(QPen(QColor(255, 255, 255), 1, Qt.PenStyle.DashLine))
                    painter.drawRect(left, top, right - left, bottom - top)
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
        self.characters: list = []
        self.chosen = ""
        self.pick_look = self._ask_look
        self._grab: tuple[int, int] | None = None
        self._pictures: dict[int, QPixmap] = {}
        self._labels: dict[str, str] = {}
        self._project: Path | None = None

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
        self.layer_label = QLabel("Layer")
        right_layout.addWidget(self.layer_label)
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
        self.door_label = QLabel("Doors on this map")
        right_layout.addWidget(self.door_label)
        self.door_list = QListWidget()
        self.door_list.setAccessibleName("Doors")
        right_layout.addWidget(self.door_list, 1)
        self.remove_button = QPushButton("Remove / put back door")
        self.remove_button.clicked.connect(self.toggle_door)
        right_layout.addWidget(self.remove_button)
        self.door_widgets = (
            self.layer_label, self.layer_box, self.pieces, self.columns, self.rows,
            self.resize_button, self.show_walls, self.block, self.open, self.wall_note,
            self.door_label, self.door_list, self.remove_button)

        self.character_panel = QWidget()
        panel = QVBoxLayout(self.character_panel)
        panel.setContentsMargins(0, 0, 0, 0)
        panel.addWidget(QLabel("Characters and objects on this map"))
        self.character_list = QListWidget()
        self.character_list.setAccessibleName("Characters on this map")
        self.character_list.currentItemChanged.connect(self._character_chosen)
        panel.addWidget(self.character_list, 2)
        self.character_note = QLabel()
        self.character_note.setWordWrap(True)
        panel.addWidget(self.character_note)
        self.box_button = QPushButton("Draw wander box")
        self.box_button.setCheckable(True)
        for label, action in (
                ("Duplicate", self.duplicate_character),
                ("Remove / put back", self.toggle_character),
                ("Rename...", self.rename_character),
                ("Change look...", self.change_look)):
            button = QPushButton(label)
            button.clicked.connect(action)
            panel.addWidget(button)
        panel.addWidget(self.box_button)
        panel.addWidget(QLabel("Add a copy of one from the game"))
        self.choice_search = QLineEdit()
        self.choice_search.setPlaceholderText("Search characters and objects")
        self.choice_search.setClearButtonEnabled(True)
        self.choice_search.textChanged.connect(self._fill_choices)
        panel.addWidget(self.choice_search)
        self.choice_list = QListWidget()
        self.choice_list.setAccessibleName("Characters to add")
        self.choice_list.setIconSize(QSize(32, 32))
        panel.addWidget(self.choice_list, 2)
        self.add_button = QPushButton("Add to this map")
        self.add_button.clicked.connect(self.add_character)
        panel.addWidget(self.add_button)
        right_layout.addWidget(self.character_panel, 3)

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
        self._project = Path(directory)
        self._pictures.clear()
        self._fill_choices()
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
        try:
            self.characters = self.studio.characters(self.key)
        except CreatorError as exc:
            self.characters = []
            self.tell(str(exc))
        self._fill_characters()
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
        self.canvas.ghost = None
        self.canvas.resize(self.canvas.sizeHint())
        self.canvas.update()

    def _names(self) -> dict[str, str]:
        if not self._labels and self._project is not None:
            self._labels = {asset["key"]: asset["label"]
                            for asset in library.read_index(self._project) or []}
        return {**self._labels, **library.read_names(self._project)} if self._project else {}

    def sprite_picture(self, sprite: int) -> QPixmap:
        """The Library's picture of a sprite, or an empty one before the Library has drawn it."""
        if sprite not in self._pictures or self._pictures[sprite].isNull():
            path = library.picture_path(self._project, f"sprite:{sprite:04d}")
            self._pictures[sprite] = QPixmap(str(path)) if path.is_file() else QPixmap()
        return self._pictures[sprite]

    def character_rect(self, character, x: int, y: int) -> QRect:
        picture = self.sprite_picture(character.sprite)
        width, height = (MARKER, MARKER) if picture.isNull() else (picture.width(), picture.height())
        return QRect(x - width // 2, y - height, width, height)

    def character_title(self, character, names=None) -> str:
        names = self._names() if names is None else names
        key = f"sprite:{character.sprite:04d}"
        return character.name or names.get(key) or key

    def _fill_characters(self) -> None:
        names = self._names()
        self.character_list.blockSignals(True)
        self.character_list.clear()
        for number, character in enumerate(self.characters, 1):
            state = ("✖ removed   " if character.removed else "★ yours   " if character.made
                     else "" if character.editable else "🔒 view only   ")
            item = QListWidgetItem(
                QIcon(self.sprite_picture(character.sprite)),
                f"{number}.  {state}{self.character_title(character, names)}  ({character.kind})"
                f"  at {character.x}, {character.y}")
            item.setData(Qt.ItemDataRole.UserRole, character.key)
            self.character_list.addItem(item)
            if character.key == self.chosen:
                self.character_list.setCurrentItem(item)
        self.character_list.blockSignals(False)
        if self.character_list.currentItem() is None:
            self.chosen = ""
        self._show_character()

    def _fill_choices(self) -> None:
        if self.studio is None:
            return
        names = self._names()
        wanted = self.choice_search.text().strip().lower()
        self.choice_list.clear()
        for choice in self.studio.character_choices():
            key = f"sprite:{choice.sprite:04d}"
            text = f"{names.get(key) or key}  ({choice.title})"
            if wanted in text.lower():
                item = QListWidgetItem(QIcon(self.sprite_picture(choice.sprite)), text)
                item.setData(Qt.ItemDataRole.UserRole, (choice.donor_map, choice.donor_slot))
                self.choice_list.addItem(item)

    def _character(self):
        return next((item for item in self.characters if item.key == self.chosen), None)

    def _character_chosen(self, item, _previous=None) -> None:
        self.chosen = item.data(Qt.ItemDataRole.UserRole) if item is not None else ""
        self._show_character()
        self.canvas.update()

    def _show_character(self) -> None:
        character = self._character()
        self.character_note.setText(
            "\n\n".join(character.notes + self.studio.character_limits(character))
            if character is not None else "")

    def choose_character(self, key: str) -> None:
        self.chosen = key
        self._fill_characters()
        self.canvas.update()

    def _need_character(self):
        character = self._character()
        if character is None:
            self.tell("Choose a character on the map or in the list first.")
        return character

    def add_character(self) -> None:
        item = self.choice_list.currentItem()
        if item is None:
            self.tell("Choose a character to add in the list first.")
            return
        donor_map, donor_slot = item.data(Qt.ItemDataRole.UserRole)
        view = self.scroll.viewport().rect().center() - self.canvas.pos()
        x, y = int(view.x() / self.canvas.zoom), int(view.y() / self.canvas.zoom)
        studio, key = self.studio, self.key
        made: list[str] = []
        if self._try(lambda: made.append(studio.add_character(key, donor_map, donor_slot, x, y))):
            self.choose_character(made[0])
            self.hint.setText("Added. Drag it where it belongs.")

    def duplicate_character(self) -> None:
        character = self._need_character()
        if character is None:
            return
        studio, key = self.studio, self.key
        made: list[str] = []
        if self._try(lambda: made.append(studio.duplicate_character(
                key, character.key, character.x + MARKER, character.y + MARKER))):
            self.choose_character(made[0])

    def toggle_character(self) -> None:
        character = self._need_character()
        if character is not None:
            studio, key = self.studio, self.key
            self._try(lambda: studio.remove_character(key, character.key, not character.removed))

    def rename_character(self) -> None:
        character = self._need_character()
        if character is None:
            return
        name = self.pick_name("Rename character", "Your name for this character:")
        if name:
            studio, key = self.studio, self.key
            self._try(lambda: studio.rename_character(key, character.key, name))

    def change_look(self) -> None:
        character = self._need_character()
        if character is None:
            return
        sprite = self.pick_look()
        if sprite is not None:
            studio, key = self.studio, self.key
            self._try(lambda: studio.set_look(key, character.key, sprite))

    def _ask_look(self) -> int | None:
        names = self._names()
        rows = sorted({choice.sprite for choice in self.studio.character_choices()})
        titles = [f"sprite:{sprite:04d}  {names.get(f'sprite:{sprite:04d}', '')}".strip() for sprite in rows]
        title, accepted = QInputDialog.getItem(
            self, "Change look", "Draw this character with", titles, 0, False)
        return rows[titles.index(title)] if accepted and title in titles else None

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
        for widget in self.door_widgets:
            widget.setVisible(name != "characters")
        self.character_panel.setVisible(name == "characters")
        self.box_button.setChecked(False)
        self.canvas.drag = []
        self.canvas.box = None
        self.canvas.ghost = None
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
        if self.tool == "characters" and not self.box_button.isChecked():
            hit = next((item for item in reversed(self.characters)
                        if self.character_rect(item, item.x, item.y).contains(x, y)), None)
            self._grab = None
            if hit is None:
                self._start = None
                return
            self.choose_character(hit.key)
            if hit.editable and not hit.removed:
                self._grab = (x - hit.x, y - hit.y)
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
        elif self.tool == "doors" or (self.tool == "characters" and self.box_button.isChecked()):
            self.canvas.box = QRect(QPoint(*self._start), QPoint(x, y)).normalized()
        elif self.tool == "characters" and self._grab is not None:
            self.canvas.ghost = (max(x - self._grab[0], 0), max(y - self._grab[1], 0))
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
        elif self.tool == "characters":
            box, ghost, chosen = self.canvas.box, self.canvas.ghost, self.chosen
            self.canvas.box = self.canvas.ghost = self._grab = None
            if self.box_button.isChecked():
                self.box_button.setChecked(False)
                if box is not None and chosen and min(box.width(), box.height()) < TILE_PIXELS:
                    self.tell("Drag a bigger wander box.")
                elif box is not None and chosen:
                    self._try(lambda: studio.set_box(
                        key, chosen, (box.left(), box.top(), box.right() + 1, box.bottom() + 1)))
                else:
                    self.tell("Choose a character first, then drag its wander box.")
            elif ghost is not None and ghost != next(
                    ((item.x, item.y) for item in self.characters if item.key == chosen), ghost):
                self._try(lambda: studio.move_character(key, chosen, *ghost))
            self.canvas.update()
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
