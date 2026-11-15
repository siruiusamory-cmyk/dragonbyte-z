"""Paint a game sprite's pictures and change its colours."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..model.graphics import SpriteEditor
from ..model.project import CreatorError

KEY = Qt.ItemDataRole.UserRole


def picture_image(width: int, height: int, pixels: bytes, palette) -> QImage:
    image = QImage(width, height, QImage.Format.Format_Indexed8)
    image.setColorTable([0] + [QColor(*rgb).rgba() for rgb in palette[1:]])
    for y in range(height):
        for x in range(width):
            image.setPixel(x, y, pixels[y * width + x])
    return image


class PixelCanvas(QWidget):
    painted = Signal(list, bool)

    def __init__(self) -> None:
        super().__init__()
        self.setAccessibleName("Pixel editor")
        self.zoom = 8
        self.image: QImage | None = None

    def show_image(self, image: QImage) -> None:
        self.image = image
        self.setFixedSize(image.size() * self.zoom)
        self.update()

    def set_zoom(self, zoom: int) -> None:
        self.zoom = zoom
        if self.image is not None:
            self.show_image(self.image)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(200, 200, 200))
        if self.image is not None:
            painter.drawImage(self.rect(), self.image)

    def _point(self, position) -> tuple[int, int]:
        return int(position.x()) // self.zoom, int(position.y()) // self.zoom

    def mousePressEvent(self, event) -> None:
        self.painted.emit([self._point(event.position())], True)

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.painted.emit([self._point(event.position())], False)

    def click(self, x: int, y: int, start: bool = True) -> None:
        self.painted.emit([(x, y)], start)


class SpriteEditorPanel(QWidget):
    changed = Signal()
    closed = Signal()

    def __init__(self, editor: SpriteEditor) -> None:
        super().__init__()
        self.editor = editor
        self.colour = editor.colours()[0]
        self._stroke = 0

        self.frames = QListWidget()
        self.frames.setAccessibleName("Frames")
        self.frames.setIconSize(QSize(48, 48))
        for frame in editor.frames():
            item = QListWidgetItem(frame.label)
            item.setData(KEY, frame.picture)
            self.frames.addItem(item)
        self.canvas = PixelCanvas()
        self.zoom = QSpinBox()
        self.zoom.setRange(1, 16)
        self.zoom.setValue(self.canvas.zoom)
        self.zoom.setPrefix("Zoom ")
        self.zoom.setSuffix("x")
        self.shared = QLabel()
        self.shared.setWordWrap(True)
        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        back = QPushButton("Back to the library")
        middle = QVBoxLayout()
        middle.addWidget(back)
        middle.addWidget(self.zoom)
        middle.addWidget(scroll, 1)
        middle.addWidget(self.shared)

        self.colours = QListWidget()
        self.colours.setAccessibleName("Colours")
        self.uses = QLabel()
        self.uses.setWordWrap(True)
        self.uses.setAccessibleName("Who else draws this colour")
        self.red, self.green, self.blue = QSpinBox(), QSpinBox(), QSpinBox()
        rgb = QHBoxLayout()
        for name, box in (("Red", self.red), ("Green", self.green), ("Blue", self.blue)):
            box.setRange(0, 255)
            box.setPrefix(f"{name} ")
            rgb.addWidget(box)
        self.apply_colour = QPushButton("Change colour")
        self.message = QLabel()
        self.message.setWordWrap(True)
        right = QVBoxLayout()
        right.addWidget(QLabel("Colours of this sprite (pick one to paint with)"))
        right.addWidget(self.colours, 1)
        right.addWidget(self.uses)
        right.addLayout(rgb)
        right.addWidget(self.apply_colour)
        right.addWidget(self.message)

        layout = QHBoxLayout(self)
        layout.addWidget(self.frames, 1)
        layout.addLayout(middle, 2)
        layout.addLayout(right, 1)

        back.clicked.connect(self.closed)
        self.zoom.valueChanged.connect(self.canvas.set_zoom)
        self.frames.currentItemChanged.connect(lambda *_: self.refresh())
        self.colours.currentItemChanged.connect(lambda *_: self._pick())
        self.canvas.painted.connect(self.paint)
        self.apply_colour.clicked.connect(self.recolour)
        self.frames.setCurrentRow(0)
        self.refresh()

    @property
    def picture(self) -> int:
        return self.frames.currentItem().data(KEY)

    def refresh(self) -> None:
        palette = self.editor.palette()
        for row in range(self.frames.count()):
            item = self.frames.item(row)
            image = picture_image(*self.editor.picture(item.data(KEY)), palette)
            item.setIcon(QIcon(QPixmap.fromImage(image)))
        if self.frames.currentItem() is None:
            return
        self.canvas.show_image(picture_image(*self.editor.picture(self.picture), palette))
        shared = self.editor.shared_with(self.picture)
        frames = sum(1 for frame in self.editor.frames() if frame.picture == self.picture)
        self.shared.setText(
            f"Picture {self.picture} is drawn by {frames} frame(s) of this sprite"
            + (", and by sprites " + ", ".join(f"{n:04d}" for n in shared) if shared else "")
            + ". Painting it changes all of them.")
        current = self.colour
        self.colours.blockSignals(True)
        self.colours.clear()
        for index in (0,) + self.editor.colours():
            red, green, blue = palette[index]
            text = "Colour 0  transparent" if index == 0 else f"Colour {index}  rgb({red}, {green}, {blue})"
            item = QListWidgetItem(text)
            item.setData(KEY, index)
            swatch = QPixmap(16, 16)
            swatch.fill(QColor(red, green, blue))
            item.setIcon(QIcon(swatch))
            self.colours.addItem(item)
            if index == current:
                self.colours.setCurrentItem(item)
        self.colours.blockSignals(False)
        self._pick()

    def _pick(self) -> None:
        item = self.colours.currentItem()
        if item is None:
            return
        self.colour = item.data(KEY)
        editable = self.colour != 0
        self.apply_colour.setEnabled(editable)
        if not editable:
            self.uses.setText("Colour 0 is transparent.")
            return
        use = self.editor.use(self.colour)
        self.uses.setText(use.message)
        for box, value in zip((self.red, self.green, self.blue), use.rgb):
            box.setValue(value)

    def paint(self, points: list, start: bool) -> None:
        if start:
            self._stroke += 1
        try:
            self.editor.paint(self.picture, points, self.colour, stroke=f"stroke {self._stroke}")
        except CreatorError as exc:
            self.message.setText(f"⚠ {exc}")
            return
        self.message.clear()
        self.refresh()
        self.changed.emit()

    def recolour(self) -> None:
        try:
            self.editor.recolour(self.colour, (self.red.value(), self.green.value(), self.blue.value()))
        except CreatorError as exc:
            self.message.setText(f"⚠ {exc}")
            return
        self.message.setText("Colour changed. " + self.editor.use(self.colour).message)
        self.refresh()
        self.changed.emit()
