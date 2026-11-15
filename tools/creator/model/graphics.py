"""Paint and recolour the game's own sprites.

A sprite's pictures are extracted into the project the first time it is opened.
Every paint stroke and recolour is one edit in the project's history; Save writes
the pictures and the colour changes. Who else draws a colour is stated for the
game's sprites and portraits only. Other uses are not known, and the page says so.
"""

from __future__ import annotations

from dataclasses import dataclass

from tools.dragonbyte import graphicsedits
from tools.dragonbyte.journal import EditKind
from tools.webfoot.build import extract_character_graphics
from tools.webfoot.donor_resources import portrait_palette_users
from tools.webfoot.graphics import CharacterIdentity, GraphicsError, load_actor_sprites
from tools.webfoot.graphics_authoring import read_asset_pixels, read_graphics_manifest
from tools.webfoot.project.model import PixelOverride

from .project import CreatorError, CreatorProject

OTHER_USES = (
    "Other uses not known: menus, the HUD and effects may also draw this colour, "
    "and they change too."
)
NEW_COLOURS = (
    "Only colours this sprite already draws in the game can be changed. "
    "New colours are not offered yet."
)


@dataclass(frozen=True, slots=True)
class Frame:
    animation: int
    frame: int
    direction: int
    picture: int

    @property
    def label(self) -> str:
        return (f"Animation {self.animation + 1}, frame {self.frame + 1}, "
                f"direction {self.direction + 1} - picture {self.picture}")


@dataclass(frozen=True, slots=True)
class ColourUse:
    index: int
    rgb: tuple[int, int, int]
    sprites: tuple[int, ...]
    portraits: tuple[int, ...]

    @property
    def message(self) -> str:
        lines = []
        if self.sprites:
            lines.append(f"Colour {self.index} is also drawn by sprites "
                         + ", ".join(f"{number:04d}" for number in self.sprites) + ".")
        if self.portraits:
            lines.append(f"Colour {self.index} is drawn by portraits "
                         + ", ".join(f"{number:03d}" for number in self.portraits) + ".")
        if not lines:
            lines.append(f"No other game sprite and no portrait draws colour {self.index}.")
        return "\n".join(lines + [OTHER_USES])


class SpriteEditor:
    def __init__(self, project: CreatorProject, sprite: int) -> None:
        session = project._session
        self._project = project
        self.sprite = sprite
        self._sprites = load_actor_sprites(session.base_image, session.identification)
        try:
            character = self._sprites.character(
                CharacterIdentity(self._sprites.profile.id, sprite))
        except GraphicsError as exc:
            raise CreatorError(f"There is no sprite {sprite}.") from exc
        try:
            extract_character_graphics(session.rom_path, project.directory, session.catalog,
                                       sprite, self._sprites)
        except OSError as exc:
            raise CreatorError(f"The sprite's pictures could not be written: {exc}") from exc
        manifest = read_graphics_manifest(project.directory)
        self._graphics = {graphic.index: self._sprites.graphic(graphic)
                          for graphic in character.graphics}
        held = session.project.graphics_overrides.pixels
        fresh = {}
        for graphic in self._graphics.values():
            key = str(graphic.identity)
            if key not in held:
                fresh[key] = PixelOverride(
                    identity=key,
                    file=manifest.assets[key].file,
                    pixels=read_asset_pixels(project.directory, manifest, key),
                    width=graphic.width,
                    height=graphic.height,
                    colour_256=graphic.colour_256,
                )
        session.project = graphicsedits.install_pixels(
            session.project, graphicsedits.AuthoredPixels(session.project.meta, fresh))
        self._frames = tuple(
            Frame(animation.index, frame.frame_index, direction, graphic.index)
            for animation in self._sprites.get_actor_animations(character.identity)
            for frame in animation.frames
            for direction, graphic in enumerate(frame.graphics)
            if graphic is not None
        )
        self._portraits: dict | None = None

    def frames(self) -> tuple[Frame, ...]:
        return self._frames

    def _override(self, picture: int) -> PixelOverride:
        graphic = self._graphics.get(picture)
        if graphic is None:
            raise CreatorError(f"Picture {picture} is not part of sprite {self.sprite}.")
        return self._project._session.project.graphics_overrides.pixels[str(graphic.identity)]

    def picture(self, picture: int) -> tuple[int, int, bytes]:
        override = self._override(picture)
        return override.width, override.height, override.pixels

    def shared_with(self, picture: int) -> tuple[int, ...]:
        return tuple(character.index for character in self._graphics[picture].characters
                     if character.index != self.sprite)

    def palette(self) -> tuple[tuple[int, int, int], ...]:
        overrides = self._project._session.project.graphics_overrides.palette
        return tuple(overrides.get(index, rgb)
                     for index, rgb in enumerate(self._sprites.palette.rgb))

    def colours(self) -> tuple[int, ...]:
        used = set()
        for graphic in self._graphics.values():
            used.update(graphic.pixels)
        used.discard(0)
        return tuple(sorted(used))

    def paint(self, picture: int, points, index: int, stroke: str = "") -> None:
        override = self._override(picture)
        limit = 255 if override.colour_256 else 15
        if type(index) is not int or not 0 <= index <= limit:
            raise CreatorError(f"Colour {index} cannot be drawn in this picture.")
        pixels = bytearray(override.pixels)
        for x, y in points:
            if not (0 <= x < override.width and 0 <= y < override.height):
                raise CreatorError("That point is outside the picture.")
            pixels[y * override.width + x] = index
        if bytes(pixels) == override.pixels:
            return
        edited = PixelOverride(identity=override.identity, file=override.file,
                               pixels=bytes(pixels), width=override.width,
                               height=override.height, colour_256=override.colour_256)
        meta = self._project._session.project.meta
        self._project._apply(
            EditKind.ASSET, graphicsedits.PIXELS_TARGET,
            graphicsedits.AuthoredPixels(meta, {override.identity: edited}),
            f"paint picture {picture}", coalesce_key=stroke)

    def recolour(self, index: int, rgb: tuple[int, int, int]) -> None:
        if index not in self.colours():
            raise CreatorError(NEW_COLOURS)
        rgb = tuple(rgb)
        if len(rgb) != 3 or any(type(c) is not int or not 0 <= c <= 255 for c in rgb):
            raise CreatorError("Red, green and blue are each 0 to 255.")
        project = self._project._session.project
        palette = dict(project.graphics_overrides.palette)
        if rgb == self._sprites.palette.rgb[index]:
            palette.pop(index, None)
        else:
            palette[index] = rgb
        if palette == project.graphics_overrides.palette:
            return
        self._project._apply(
            EditKind.SEMANTIC, graphicsedits.GRAPHICS_TARGET,
            graphicsedits.AuthoredPalette(project.meta, palette), f"recolour {index}")

    def use(self, index: int) -> ColourUse:
        if self._portraits is None:
            self._portraits = portrait_palette_users(self._sprites.base_bytes)
        sprites = sorted({character.index
                          for graphic in self._sprites.palette_users(index)
                          for character in self._sprites.graphic(graphic).characters}
                         - {self.sprite})
        return ColourUse(index, self.palette()[index], tuple(sprites),
                         self._portraits.get(index, ()))
