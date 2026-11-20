"""Make one new character: a Stand pose, and a Walk animation if it walks.

A project can hold one new character. Its pictures are kept as one sheet per
animation under ``sprites/<name>/``, drawn only in colours the game's palette
already has, and the game character whose frames it copies is chosen when the
game is built, from the frame size and the animations the character needs.
A sheet's frames are square, so only square frame sizes are offered.

Each edit is written to the project at once. Undo and redo restore the
character's files as they were before or after an edit.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import os
from pathlib import Path
import re

from tools.dragonbyte.session import Session
from tools.webfoot import map_objects as mo
from tools.webfoot.formats import rgb_png
from tools.webfoot.formats import sprite_graphics as sg
from tools.webfoot.formats.indexed_png import PngError
from tools.webfoot.project.format import ProjectFormatError, load_toml
from tools.webfoot.project.model import (
    SPRITES_FILE,
    AuthoredSprite,
    AuthoredSpriteAnimation,
    AuthoredSprites,
    ProjectError,
    write_authored_sprites,
)
from tools.webfoot.sprite_identity import (
    SPRITE_ID_FLOOR,
    STAND_SLOT,
    WALK_SLOT,
    donor_census,
)

from .library import NAMES, _png, _read, read_names, set_name
from .project import CreatorError

STANDS, WALKS = "Stands", "Walks"
BEHAVIOURS = (STANDS, WALKS)
FACINGS = ("down", "up", "left", "right")
SLOT_TITLES = ("Stand pose", "Walk animation")
SHEETS = ("stand", "walk")
FEWEST_FRAMES = (1, 2)
MOST_FRAMES = 16
KIND = {STANDS: "character", WALKS: "character that wanders"}
HOLE = (255, 0, 255)
LISTED = 6
ONE_ONLY = ("This project already has a new character, {name}. A project can have one "
            "new character. Remove it first to make a different one.")
NEW_COLOURS = ("A new character is drawn in the game's own colours. Change a colour on "
               "one of the game's sprites instead.")
BAD_NAME = "A name starts with a letter and uses letters, digits, spaces, - and _."
NAME_RULE = re.compile(r"[a-z][a-z0-9_-]{0,63}")
DEVICE_NAME = re.compile(r"(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?", re.IGNORECASE)
DEVICE = "{name} is a name Windows keeps for itself. Choose another name."
FOREIGN = ("This project already has a sprite written outside the creator, in "
           "sprites/sprites.toml. The creator leaves it as it is.")
DAMAGED = ("library/names.json is damaged, so this step cannot be undone or redone. "
           "Fix or delete that file, then try again. Nothing was changed.")
NOT_SAVED = "The new character could not be saved: {reason}. Nothing was changed."


@dataclass(frozen=True, slots=True)
class Frame:
    animation: int
    frame: int
    direction: int
    picture: int

    @property
    def label(self) -> str:
        return (f"{SLOT_TITLES[self.animation]}, facing {FACINGS[self.direction]}, "
                f"frame {self.frame + 1}")


@dataclass(frozen=True, slots=True)
class ColourUse:
    index: int
    rgb: tuple[int, int, int]

    @property
    def message(self) -> str:
        return "This is one of the game's own colours. " + NEW_COLOURS


@dataclass(frozen=True, slots=True)
class NewCharacter:
    name: str
    behaviour: str
    width: int
    height: int
    frames: tuple[int, ...]
    sprite: int

    @property
    def size(self) -> str:
        return size_words(self.width, self.height)


def size_words(width: int, height: int) -> str:
    return f"{width} by {height} pixels"


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".pending")
    pending.write_bytes(data)
    os.replace(pending, path)


class CharacterMaker:
    def __init__(self, project_dir: Path, rom_path: Path) -> None:
        self.directory = Path(project_dir)
        self.image = Path(rom_path).read_bytes()
        session = Session()
        session.open_rom(Path(rom_path))
        self.profile = session.profile
        layout = self.profile.actor_sprites
        self.sprite = layout.character_count
        raw = sg.decode_palette(
            self.image, layout.object_palette_address.to_file_offset(len(self.image))).raw
        self._palette = tuple(sg.expand_bgr555(word & 0x7FFF) for word in raw)
        self._index = {}
        for index in range(len(self._palette) - 1, 0, -1):
            self._index[self._palette[index]] = index
        self._census = None
        self._undo: list[tuple[dict, dict]] = []
        self._redo: list[tuple[dict, dict]] = []
        self._stroke = ""
        self._load()

    def _document(self) -> AuthoredSprites:
        path = self.directory / SPRITES_FILE
        if not path.is_file():
            return AuthoredSprites()
        try:
            return AuthoredSprites.from_document(
                load_toml(path.read_text(encoding="utf-8")), path)
        except (OSError, ProjectError, ProjectFormatError) as exc:
            raise CreatorError(f"The new character could not be read: {exc}") from exc

    def _load(self) -> None:
        self.character: NewCharacter | None = None
        self._pictures: dict[tuple[int, int, int], bytes] = {}
        self.unreadable: list[str] = []
        sprites = self._document()
        self.foreign = not sprites.is_empty() and not self._made_here(sprites.only())
        if sprites.is_empty() or self.foreign:
            return
        sprite = sprites.only()
        frames, side = [], 0
        for slot, animation in enumerate(sprite.ordered_animations()):
            side = self._read_sheet(slot, animation)
            frames.append(animation.frames)
        self.character = NewCharacter(
            sprite.name, WALKS if len(frames) > WALK_SLOT else STANDS, side, side,
            tuple(frames), sprite.sprite_id - SPRITE_ID_FLOOR)

    @staticmethod
    def _made_here(sprite) -> bool:
        """Only a sprite shaped as `create` writes it is this creator's character."""
        return (sprite.actor is None and sprite.donor_sprite_id is None
                and not sprite.free_palette_entries)

    def _read_sheet(self, slot: int, animation: AuthoredSpriteAnimation) -> int:
        try:
            rgb, width, side, alpha = rgb_png.decode_truecolour(
                (self.directory / animation.sheet).read_bytes())
        except (OSError, PngError) as exc:
            raise CreatorError(f"The {SLOT_TITLES[slot]} picture could not be read: {exc}") from exc
        for facing in range(len(FACINGS)):
            for frame in range(animation.frames):
                cell = facing * animation.frames + frame
                pixels = bytearray()
                for y in range(side):
                    for x in range(side):
                        at = y * width + cell * side + x
                        colour = tuple(rgb[3 * at:3 * at + 3])
                        if (alpha is not None and alpha[at] == 0) or colour == HOLE:
                            pixels.append(0)
                        elif colour in self._index:
                            pixels.append(self._index[colour])
                        else:
                            pixels.append(0)
                            self.unreadable.append(
                                f"{SLOT_TITLES[slot]} facing {FACINGS[facing]}, frame {frame + 1}")
                self._pictures[(slot, facing, frame)] = bytes(pixels)
        return side

    def census(self):
        if self._census is None:
            self._census = donor_census(self.image, self.profile)
        return self._census

    def sizes(self, behaviour: str) -> list[str]:
        """The frame sizes a character with this behaviour can be made at."""
        walks = behaviour == WALKS
        found = {(donor.envelope.width, donor.envelope.height) for donor in self.census()
                 if (donor.walks or not walks)
                 and donor.envelope.width == donor.envelope.height}
        return [size_words(*size) for size in sorted(found)]

    def frames(self) -> tuple[Frame, ...]:
        if self.character is None:
            return ()
        rows = []
        for slot, count in enumerate(self.character.frames):
            for facing in range(len(FACINGS)):
                for frame in range(count):
                    rows.append(Frame(slot, frame, facing, len(rows)))
        return tuple(rows)

    def _key(self, picture: int) -> tuple[int, int, int]:
        for frame in self.frames():
            if frame.picture == picture:
                return frame.animation, frame.direction, frame.frame
        raise CreatorError(f"There is no picture {picture} in the new character.")

    def picture(self, picture: int) -> tuple[int, int, bytes]:
        character = self._need()
        return character.width, character.height, self._pictures[self._key(picture)]

    def shared_with(self, _picture: int) -> tuple[int, ...]:
        return ()

    def palette(self) -> tuple[tuple[int, int, int], ...]:
        return self._palette

    def colours(self) -> tuple[int, ...]:
        return tuple(sorted(set(self._index.values())))

    def use(self, index: int) -> ColourUse:
        return ColourUse(index, self._palette[index])

    def recolour(self, _index: int, _rgb) -> None:
        raise CreatorError(NEW_COLOURS)

    def problems(self) -> list[str]:
        """What stops the game from being built with this character, in plain words."""
        character = self.character
        if character is None:
            return []
        found = [f"The {where} has a colour the game does not have." for where in
                 dict.fromkeys(self.unreadable)]
        for facing, name in enumerate(FACINGS):
            if not any(any(self._pictures[(STAND_SLOT, facing, frame)])
                       for frame in range(character.frames[STAND_SLOT])):
                found.append(f"The Stand pose facing {name} is empty. Draw it.")
        if character.behaviour == WALKS:
            for facing, name in enumerate(FACINGS):
                drawn = {self._pictures[(WALK_SLOT, facing, frame)]
                         for frame in range(character.frames[WALK_SLOT])}
                drawn.discard(bytes(character.width * character.height))
                if len(drawn) < FEWEST_FRAMES[WALK_SLOT]:
                    found.append(
                        f"The Walk animation facing {name} needs at least two different frames.")
        found.extend(self._placement_problems(character))
        return found

    def _placement_problems(self, character: NewCharacter) -> list[str]:
        try:
            edits = mo.read_document(self.directory)
        except (ValueError, OSError) as exc:
            return [str(exc)]
        found = []
        for key, item in edits.items():
            for made in item.made.values():
                if made.sprite_id != character.sprite + SPRITE_ID_FLOOR:
                    continue
                if self.fits(made.donor_map, made.donor_slot) != character.behaviour:
                    found.append(self._wrong_kind(character, key))
        return found

    def _wrong_kind(self, character: NewCharacter, where: str) -> str:
        return (f"{character.name} {character.behaviour.lower()}, so on {where} it can only "
                f"be a {KIND[character.behaviour]}.")

    def fits(self, donor_map: int | None, donor_slot: int | None) -> str:
        """Which behaviour a copy of this base-game character gives: Stands, Walks or none."""
        if donor_map is None:
            return ""
        item = next((entry for entry in mo.read_objects(self.image, self.profile, donor_map)
                     if entry.slot == donor_slot), None)
        if item is None or item.family != mo.NPC:
            return ""
        return WALKS if item.wanders else STANDS if mo.stands(self.image, item) else ""

    def check_look(self, donor_map: int | None, donor_slot: int | None, where: str) -> None:
        """Refuse drawing a copy of this character with the new one when they do not fit."""
        character = self._need()
        if self.fits(donor_map, donor_slot) != character.behaviour:
            raise CreatorError(self._wrong_kind(character, where))

    def _need(self) -> NewCharacter:
        if self.character is None:
            raise CreatorError("This project has no new character yet.")
        return self.character

    def _name_key(self) -> str:
        return f"sprite:{self.sprite:04d}"

    def _snapshot(self) -> dict[str, bytes]:
        """This character's own files, plus its own entry in the Library names."""
        folder = self.directory / SPRITES_FILE.parent
        found = {path.relative_to(self.directory).as_posix(): path.read_bytes()
                 for path in sorted(folder.rglob("*")) if path.is_file()} if folder.is_dir() else {}
        name = read_names(self.directory).get(self._name_key())
        if name is not None:
            found[NAMES.as_posix()] = name.encode("utf-8")
        return found

    def _restore(self, snapshot: dict[str, bytes], undone: dict[str, bytes]) -> None:
        """Put back this character's files, and its name only when the step changed it."""
        wanted, changed = snapshot.get(NAMES.as_posix()), undone.get(NAMES.as_posix())
        names = self.directory / NAMES
        if wanted != changed and names.exists() and not isinstance(_read(names), dict):
            raise CreatorError(DAMAGED)
        files = {name: data for name, data in snapshot.items() if name != NAMES.as_posix()}
        current = self._snapshot()
        current.pop(NAMES.as_posix(), None)
        for name in set(current) - set(files):
            (self.directory / name).unlink()
        for name, data in files.items():
            path = self.directory / name
            if not path.is_file() or path.read_bytes() != data:
                _write(path, data)
        if wanted != changed:
            set_name(self.directory, self._name_key(), (wanted or b"").decode("utf-8"))
        self._load()

    def _folders(self) -> set[Path]:
        folder = self.directory / SPRITES_FILE.parent
        if not folder.is_dir():
            return set()
        return {folder} | {path for path in folder.rglob("*") if path.is_dir()}

    def _edit(self, action, stroke: str = "") -> None:
        before = self._snapshot()
        folders = self._folders()
        try:
            action()
            self._load()
        except (ValueError, OSError, CreatorError) as exc:
            self._restore(before, self._snapshot())
            for folder in sorted(self._folders() - folders, reverse=True):
                if not any(folder.iterdir()):
                    folder.rmdir()
            if isinstance(exc, OSError):
                raise CreatorError(NOT_SAVED.format(reason=exc.strerror or exc)) from exc
            raise CreatorError(str(exc)) from exc
        after = self._snapshot()
        if after == before:
            return
        if stroke and stroke == self._stroke and self._undo:
            self._undo[-1] = (self._undo[-1][0], after)
        else:
            self._undo.append((before, after))
        self._stroke = stroke
        self._redo.clear()

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def undo(self) -> None:
        if self._undo:
            step = self._undo[-1]
            self._restore(step[0], step[1])
            self._redo.append(self._undo.pop())
            self._stroke = ""

    def redo(self) -> None:
        if self._redo:
            step = self._redo[-1]
            self._restore(step[1], step[0])
            self._undo.append(self._redo.pop())
            self._stroke = ""

    def _sheet(self, name: str, slot: int) -> str:
        return f"{SPRITES_FILE.parent.as_posix()}/{name}/{SHEETS[slot]}.png"

    def _write_sheet(self, character: NewCharacter, slot: int, pictures: dict) -> None:
        frames, side = character.frames[slot], character.height
        width = side * len(FACINGS) * frames
        rgba = bytearray(width * side * 4)
        for facing in range(len(FACINGS)):
            for frame in range(frames):
                pixels = pictures[(slot, facing, frame)]
                cell = facing * frames + frame
                for y in range(side):
                    for x in range(side):
                        index = pixels[y * side + x]
                        if index:
                            at = 4 * (y * width + cell * side + x)
                            rgba[at:at + 4] = bytes(self._palette[index]) + b"\xff"
        _write(self.directory / self._sheet(character.name, slot), _png(width, side, bytes(rgba)))

    def _write_document(self, character: NewCharacter) -> None:
        animations = {
            SHEETS[slot]: AuthoredSpriteAnimation(SHEETS[slot], self._sheet(character.name, slot),
                                                  frames)
            for slot, frames in enumerate(character.frames)}
        write_authored_sprites(self.directory, AuthoredSprites(sprites={character.name: AuthoredSprite(
            name=character.name, sprite_id=character.sprite + SPRITE_ID_FLOOR,
            donor_sprite_id=None, free_palette_entries=(), animations=animations, actor=None)}))

    def create(self, name: str, behaviour: str, size: str) -> NewCharacter:
        """Start a new character with blank pictures."""
        if self.character is not None:
            raise CreatorError(ONE_ONLY.format(name=self.character.name))
        if self.foreign:
            raise CreatorError(FOREIGN)
        if behaviour not in BEHAVIOURS:
            raise CreatorError("A new character either stands or walks.")
        if size not in self.sizes(behaviour):
            raise CreatorError(f"No character in this game is drawn at {size}"
                               + (" with a walk animation." if behaviour == WALKS else "."))
        key = "-".join(name.lower().split())
        if DEVICE_NAME.fullmatch(name.strip()) or DEVICE_NAME.fullmatch(key):
            raise CreatorError(DEVICE.format(name=name.strip()))
        if name != name.rstrip(" .") or NAME_RULE.fullmatch(key) is None:
            raise CreatorError(BAD_NAME)
        width, height = (int(part) for part in size.split()[:3:2])
        frames = FEWEST_FRAMES[:1] if behaviour == STANDS else FEWEST_FRAMES
        character = NewCharacter(key, behaviour, width, height, frames, self.sprite)
        blank = bytes(width * height)
        pictures = {(slot, facing, frame): blank for slot, count in enumerate(frames)
                    for facing in range(len(FACINGS)) for frame in range(count)}

        def action() -> None:
            self._write_document(character)
            for slot in range(len(frames)):
                self._write_sheet(character, slot, pictures)
            set_name(self.directory, f"sprite:{self.sprite:04d}", name)

        self._edit(action)
        return self._need()

    def remove(self) -> None:
        character = self._need()

        def action() -> None:
            write_authored_sprites(self.directory, AuthoredSprites())
            for slot in range(len(character.frames)):
                (self.directory / self._sheet(character.name, slot)).unlink(missing_ok=True)
            if f"sprite:{character.sprite:04d}" in read_names(self.directory):
                set_name(self.directory, f"sprite:{character.sprite:04d}", "")

        self._edit(action)

    def paint(self, picture: int, points, index: int, stroke: str = "") -> None:
        character = self._need()
        key = self._key(picture)
        if type(index) is not int or not 0 <= index < len(self._palette):
            raise CreatorError(f"Colour {index} cannot be drawn.")
        pixels = bytearray(self._pictures[key])
        for x, y in points:
            if not (0 <= x < character.width and 0 <= y < character.height):
                raise CreatorError("That point is outside the picture.")
            pixels[y * character.width + x] = index
        if bytes(pixels) == self._pictures[key]:
            return
        pictures = {**self._pictures, key: bytes(pixels)}
        self._edit(lambda: self._write_sheet(character, key[0], pictures), stroke)

    def _replace(self, character: NewCharacter, slot: int, count: int, pictures: dict) -> None:
        frames = list(character.frames)
        frames[slot] = count
        grown = replace(character, frames=tuple(frames))

        def action() -> None:
            self._write_document(grown)
            self._write_sheet(grown, slot, pictures)

        self._edit(action)

    def _slot(self, slot: int) -> NewCharacter:
        character = self._need()
        if not 0 <= slot < len(character.frames):
            raise CreatorError(f"{character.name} has no {SLOT_TITLES[slot]}.")
        return character

    def set_frames(self, slot: int, count: int) -> None:
        """How many frames each facing of one animation has."""
        character = self._slot(slot)
        if not FEWEST_FRAMES[slot] <= count <= MOST_FRAMES:
            raise CreatorError(f"The {SLOT_TITLES[slot]} has {FEWEST_FRAMES[slot]} to "
                               f"{MOST_FRAMES} frames for each facing.")
        blank = bytes(character.width * character.height)
        pictures = {(slot, facing, frame): self._pictures.get((slot, facing, frame), blank)
                    for facing in range(len(FACINGS)) for frame in range(count)}
        self._replace(character, slot, count, pictures)

    def import_sheet(self, slot: int, path: Path) -> None:
        """Replace one animation's pictures with a sheet: four facings, down, up, left, right.

        Every colour must be one the game already has, exactly. Otherwise nothing
        is changed and the colours that are missing are listed.
        """
        character = self._slot(slot)
        try:
            rgb, width, height, alpha = rgb_png.decode_truecolour(Path(path).read_bytes())
        except OSError as exc:
            raise CreatorError(f"The picture could not be read: {exc.strerror}") from exc
        except PngError as exc:
            raise CreatorError(f"The picture could not be read: {exc}") from exc
        side = character.height
        row = side * len(FACINGS)
        frames = width // row
        if height != side or width % row or not FEWEST_FRAMES[slot] <= frames <= MOST_FRAMES:
            raise CreatorError(
                f"The picture is {width} by {height} pixels. A {SLOT_TITLES[slot]} sheet is "
                f"{side} pixels tall and holds the frames facing down, then up, then left, "
                f"then right, in one row: {row * FEWEST_FRAMES[slot]} pixels wide for "
                f"{FEWEST_FRAMES[slot]} frame(s) each, {row} more for every extra frame, "
                f"up to {MOST_FRAMES}.")
        missing: dict[tuple[int, ...], list[str]] = {}
        pictures = dict(self._pictures)
        for facing in range(len(FACINGS)):
            for frame in range(frames):
                cell = facing * frames + frame
                pixels = bytearray()
                for y in range(side):
                    for x in range(side):
                        at = y * width + cell * side + x
                        colour = tuple(rgb[3 * at:3 * at + 3])
                        if alpha is not None and alpha[at] not in (0, 255):
                            raise CreatorError(
                                f"The {SLOT_TITLES[slot]} facing {FACINGS[facing]}, frame "
                                f"{frame + 1} has a see-through pixel at {x}, {y}. Each pixel "
                                "is either a colour or a hole.")
                        if (alpha is not None and alpha[at] == 0) or colour == HOLE:
                            pixels.append(0)
                        elif colour in self._index:
                            pixels.append(self._index[colour])
                        else:
                            pixels.append(0)
                            place = f"facing {FACINGS[facing]}, frame {frame + 1}"
                            places = missing.setdefault(colour, [])
                            if place not in places:
                                places.append(place)
                pictures[(slot, facing, frame)] = bytes(pixels)
        if missing:
            lines = [f"#{r:02X}{g:02X}{b:02X} ({', '.join(places)})"
                     for (r, g, b), places in list(missing.items())[:LISTED]]
            more = len(missing) - LISTED
            raise CreatorError(
                f"Nothing was imported. The {SLOT_TITLES[slot]} uses colours the game does not "
                "have, and a new character is drawn only in the game's own colours: "
                + "; ".join(lines) + (f"; and {more} more" if more > 0 else "") + ".")
        for facing in range(len(FACINGS)):
            for frame in range(frames, character.frames[slot]):
                pictures.pop((slot, facing, frame), None)
        self._replace(character, slot, frames, pictures)
