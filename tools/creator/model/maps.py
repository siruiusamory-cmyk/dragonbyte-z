"""The map editor's model: maps, layers, tiles, collision and doors, with undo.

A retail map is ``map:NNNN``. A map the creator made is ``map-new:<name>``; it is
a private copy of a retail map, and every edit to it lands on that copy.

Each edit is written to the project at once through the SDK's own validated
writers. Undo and redo restore the map documents as they were before or after an
edit, so they step through whole edits and never leave a half-written project.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import os
from pathlib import Path
import re

from tools.dragonbyte.session import Session
from tools.webfoot import map_authoring as new_maps
from tools.webfoot import conversations as cv
from tools.webfoot import map_chunk, map_collision, map_paint, map_resize, map_view
from tools.webfoot import map_objects as mo
from tools.webfoot import map_transition_removal as removal
from tools.webfoot import map_transitions as mt
from tools.webfoot import story_flags as sf
from tools.webfoot.formats import map_collision as grids
from tools.webfoot.formats import map_graphics as mg
from tools.webfoot.formats.map_transitions import TransitionArrival, TransitionRegion

from .enemies import EnemyStudio, PlaceableEnemy
from .project import CreatorError

CHUNK_PIXELS = 256
TILE_PIXELS = 8
TILES_PER_CHUNK = CHUNK_PIXELS // TILE_PIXELS
MAP_FOLDER = "maps"
DATA_FILE = "maps.toml"
NAME_RULE = re.compile(r"[a-z][a-z0-9_-]{0,31}")
WALK = ("down", "up", "left", "right")


@dataclass(frozen=True)
class MapRow:
    key: str
    title: str
    new: bool


@dataclass(frozen=True)
class Layer:
    slot: int
    order: int
    columns: int
    rows: int
    cells: tuple
    choices: tuple
    editable: bool
    picture: bytes
    width: int
    height: int


@dataclass(frozen=True)
class Door:
    key: str
    rect: tuple[int, int, int, int]
    destination: str
    arrival: tuple[int, int]
    created: bool
    removed: bool
    walk: str


@dataclass(frozen=True)
class Character:
    """One thing standing on a map. ``sprite`` is its Library sprite number."""

    key: str
    name: str
    sprite: int
    x: int
    y: int
    kind: str
    made: bool
    removed: bool
    editable: bool
    box: tuple | None
    can_box: bool
    notes: tuple
    says: str = ""
    appears: str = ""


@dataclass(frozen=True)
class CharacterChoice:
    donor_map: int
    donor_slot: int
    sprite: int
    title: str


@dataclass(frozen=True)
class MapEnemy:
    """One enemy standing on a map: the name of its type, where it stands, its rule."""

    key: str
    name: str
    x: int
    y: int
    made: bool
    appears: str
    defeat: str = ""


KINDS = {
    (mo.NPC, True): "character that wanders",
    (mo.NPC, False): "character",
    (mo.PLACEMENT, False): "object",
    (mo.SCENE, False): "story-scene character",
}
VIEW_ONLY = {
    mo.SCENE: (
        "This is a story-scene character. DragonByte Z shows it but cannot move, copy or "
        "remove it yet, because how the game stores it is not established."),
    mo.PLACEMENT: (
        "This is a game object, such as an enemy, an item or a story piece. DragonByte Z "
        "shows it but cannot move, copy or remove it yet: the game brings these in by "
        "its own rules, and a changed one has not been proven in the running game."),
}
LOST = (
    "The character this one was copied from cannot be found, so the game cannot be "
    "built with it. Remove it.")
STORY = (
    "In the base game this character is tied to the story and may not be there when "
    "the map opens. A copy follows the same rule. DragonByte Z cannot change it yet.")
SHARED_BOX = (
    "It has no wander box of its own, so it uses the box of the character it was "
    "copied from. Outside that box it stands still. Draw a wander box to let it walk here.")
ENEMY_PREFIX = "enemy"
GAME_ENEMY = "a game enemy"
LOST_ENEMY = "an enemy type the project no longer holds"


def _friendly(exc: Exception) -> str:
    text = str(exc).strip()
    return text[:1].upper() + text[1:] if text else "That change could not be made."


class MapStudio:
    def __init__(self, project_dir: Path, rom_path: Path) -> None:
        self.directory = Path(project_dir)
        self.image = Path(rom_path).read_bytes()
        session = Session()
        session.open_rom(Path(rom_path))
        self.profile = session.profile
        self._reader = map_view.reader_for(self.image, self.profile)
        self._entries = mg.read_map_entries(self._reader)
        self._labels = map_view.read_map_index(self.image, self.profile)
        self._author = map_chunk.ChunkAuthor(self.image, profile=self.profile)
        self._rendered: dict[int, map_view.MapBrowserResult] = {}
        self._chars: dict[int, bytes] = {}
        self._pictures: dict[tuple, bytes] = {}
        self._undo: list[tuple[dict, dict]] = []
        self._redo: list[tuple[dict, dict]] = []
        self._seen: dict = {}
        self._roots: dict[int, list[int]] = {}
        self._objects: dict[int, tuple] = {}
        self._choices: list | None = None
        self._talks: dict | None = None
        self.enemy_types: EnemyStudio | None = None
        self._type_names: dict[str, str] | None = None
        for index in range(len(self._labels)):
            try:
                root = map_collision.root_address(self.image, self.profile, index)
            except ValueError:
                continue
            self._roots.setdefault(root, []).append(index)

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def _snapshot(self) -> dict[str, bytes]:
        folder = self.directory / MAP_FOLDER
        return {
            path.relative_to(folder).as_posix(): path.read_bytes()
            for path in sorted(folder.rglob("*"))
            if path.is_file() and path.relative_to(folder).as_posix() != DATA_FILE
        }

    def _once(self, name: str, key, make):
        """A read that stays good until the next edit, undo or redo."""
        if (name, key) not in self._seen:
            self._seen[(name, key)] = make()
        return self._seen[(name, key)]

    def _restore(self, snapshot: dict[str, bytes]) -> None:
        self._seen.clear()
        folder = self.directory / MAP_FOLDER
        for name in set(self._snapshot()) - set(snapshot):
            (folder / name).unlink()
        for name, data in snapshot.items():
            path = folder / name
            if not path.is_file() or path.read_bytes() != data:
                path.parent.mkdir(parents=True, exist_ok=True)
                pending = path.with_name(path.name + ".pending")
                pending.write_bytes(data)
                os.replace(pending, path)
        for path in sorted(folder.rglob("*"), reverse=True):
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()

    def _edit(self, action, verbatim: bool = False) -> None:
        before = self._snapshot()
        try:
            action()
        except (ValueError, OSError, KeyError) as exc:
            self._restore(before)
            raise CreatorError(str(exc) if verbatim else _friendly(exc)) from exc
        finally:
            self._seen.clear()
        after = self._snapshot()
        if after != before:
            self._undo.append((before, after))
            self._redo.clear()

    def undo(self) -> None:
        if self._undo:
            step = self._undo.pop()
            self._restore(step[0])
            self._redo.append(step)

    def redo(self) -> None:
        if self._redo:
            step = self._redo.pop()
            self._restore(step[1])
            self._undo.append(step)

    def _authored(self):
        return self._once("authored", "", lambda: new_maps.authored_maps(self.directory))

    def maps(self) -> list[MapRow]:
        rows = [
            MapRow(f"map-new:{item.name}",
                   f"★ {item.name}   (your map, made from {self._title(item.donor)})", True)
            for item in self._authored().ordered()
        ]
        return rows + [
            MapRow(f"map:{entry.index:04d}", self._title(entry.index), False)
            for entry in self._labels
        ]

    def _title(self, index: int) -> str:
        return f"{index:03d}  {self._labels[index].name or 'Unnamed map'}"

    def title(self, key: str) -> str:
        return next((row.title for row in self.maps() if row.key == key), key)

    def _target(self, key: str) -> tuple[Path, int]:
        if key.startswith("map-new:"):
            item = self._authored().maps.get(key[8:])
            if item is None:
                raise CreatorError(f"There is no map called {key[8:]}.")
            return new_maps.content_directory(self.directory, item.name), item.donor
        return self.directory, int(key[4:])

    def _table_index(self, key: str) -> int:
        if not key.startswith("map-new:"):
            return int(key[4:])
        names = [item.name for item in self._authored().ordered()]
        return new_maps.record_count(self.profile) + names.index(key[8:])

    def _key_of(self, table_index: int) -> str:
        rows = new_maps.record_count(self.profile)
        if table_index < rows:
            return f"map:{table_index:04d}"
        ordered = self._authored().ordered()
        position = table_index - rows
        return f"map-new:{ordered[position].name}" if position < len(ordered) else "a map that is gone"

    def create(self, name: str, donor_key: str) -> str:
        name = name.strip().lower()
        if not NAME_RULE.fullmatch(name):
            raise CreatorError(
                "A map name starts with a letter and uses only lowercase letters, "
                "digits, '-' and '_' (up to 32)."
            )
        if donor_key.startswith("map-new:"):
            raise CreatorError("Make a new map from one of the game's own maps.")
        self._edit(lambda: new_maps.create_map(
            self.directory, self.image, self.profile, name, int(donor_key[4:])))
        return f"map-new:{name}"

    def rename(self, key: str, name: str) -> str:
        name = name.strip().lower()
        if not key.startswith("map-new:"):
            raise CreatorError("Only a map you made can be renamed here.")
        if not NAME_RULE.fullmatch(name):
            raise CreatorError(
                "A map name starts with a letter and uses only lowercase letters, "
                "digits, '-' and '_' (up to 32)."
            )
        self._edit(lambda: new_maps.rename_map(
            self.directory, key[8:], name,
            canonical_rows=new_maps.record_count(self.profile)))
        return f"map-new:{name}"

    def _render(self, index: int) -> map_view.MapBrowserResult:
        if index not in self._rendered:
            self._rendered[index] = map_view.render_map(self.image, index, profile=self.profile)
        return self._rendered[index]

    def _char(self, index: int) -> bytes:
        if index not in self._chars:
            block, _stream, _animated = mg.assemble_map_char_block(
                self._reader, self._entries[index].root_address)
            self._chars[index] = block.data
        return self._chars[index]

    def _rgba(self, index: int, pixels: bytes) -> bytes:
        return map_view.to_rgba(pixels, map_view.rgba_table(self._render(index).palette))

    def _painter(self, docs: Path) -> map_paint.MapPainter:
        return map_paint.MapPainter(
            self.image, profile=self.profile, structure=map_resize.read_map_structure(docs))

    def layers(self, key: str) -> list[Layer]:
        """Every layer of the map, drawn back to front, with the creator's edits."""
        return self._once("layers", key, lambda: self._layers(key))

    def _layers(self, key: str) -> list[Layer]:
        docs, index = self._target(key)
        try:
            rendered = self._render(index)
            target = self._painter(docs).target(index)
            layout = map_paint.read_layout_edits(docs).cells()
        except (ValueError, OSError) as exc:
            raise CreatorError(_friendly(exc)) from exc
        editable = {layer.slot: layer for layer in target.editable_layers}
        layers = []
        for drawn in rendered.layers:
            paint = editable.get(drawn.slot)
            if paint is None:
                if drawn.width and drawn.height:
                    layers.append(Layer(drawn.slot, drawn.addend, 0, 0, (), (), False,
                                        self._rgba(index, drawn.pixels), drawn.width, drawn.height))
                continue
            cells = []
            for cell in paint.cells:
                value = layout.get((index, drawn.slot, cell.cell))
                cells.append(value if isinstance(value, str)
                             else paint.pointer(value) if value else cell.pointer)
            layers.append(Layer(
                drawn.slot, drawn.addend, paint.columns, paint.rows, tuple(cells),
                tuple(choice.pointer for choice in paint.vocabulary), True, b"",
                paint.columns * CHUNK_PIXELS, paint.rows * CHUNK_PIXELS))
        return sorted(layers, key=lambda layer: (-layer.order, -layer.slot))

    def _chunk(self, docs: Path, identity: str):
        return map_chunk.read_authored_chunks(docs).chunks[identity]

    def _plane(self, docs: Path, index: int, value) -> tuple[int, ...]:
        if isinstance(value, str):
            return tuple(self._author.resolve(self._chunk(docs, value)).entries)
        return tuple(self._author.plane(self._template(index, value)))

    def _template(self, index: int, address: int) -> map_chunk.ChunkTemplate:
        for slot in range(len(mg.ROOT_LAYER_SLOTS)):
            try:
                choices = self._author.templates(index, slot)
            except ValueError:
                continue
            for choice in choices:
                if choice.address == address:
                    return map_chunk.ChunkTemplate.parse(
                        self._author.template_text(index, slot, choice.ordinal))
        raise CreatorError("This piece of the map cannot be used as the start of a new one.")

    def chunk_picture(self, key: str, value) -> bytes:
        """One 256x256 piece of a layer as RGBA, for a retail or a creator-made chunk."""
        docs, index = self._target(key)
        try:
            if isinstance(value, str):
                plane = self._plane(docs, index, value)
                cache = (index, plane)
                if cache not in self._pictures:
                    drawn = map_view.render_chunk_entries(self._char(index), plane)
                    self._pictures[cache] = self._rgba(index, drawn.pixels)
                return self._pictures[cache]
            cache = (index, value)
            if cache not in self._pictures:
                drawn = map_view.render_chunk_images(
                    self.image, index, [value], profile=self.profile, char_data=self._char(index))[0]
                self._pictures[cache] = self._rgba(index, drawn.pixels)
            return self._pictures[cache]
        except (ValueError, OSError, KeyError) as exc:
            raise CreatorError(_friendly(exc)) from exc

    def _layer(self, key: str, slot: int) -> Layer:
        layer = next((item for item in self.layers(key) if item.slot == slot), None)
        if layer is None or not layer.editable:
            raise CreatorError("This layer cannot be edited.")
        return layer

    def paint(self, key: str, slot: int, cells, value) -> None:
        """Place one chunk in every listed cell of a layer, as one undo step."""
        docs, index = self._target(key)

        def action() -> None:
            if isinstance(value, str):
                map_chunk.set_layout_authored_cells(
                    docs, self.image, {(index, slot, cell): value for cell in cells},
                    profile=self.profile)
                return
            ordinal = self._painter(docs).target(index).layer(slot).ordinal_of(value)
            if ordinal is None:
                raise CreatorError("That piece does not belong to this map.")
            map_paint.set_layout_cells(
                docs, self.profile, self.image,
                {(index, slot, cell): ordinal for cell in cells})

        self._edit(action)

    def resize(self, key: str, slot: int, columns: int, rows: int) -> None:
        docs, index = self._target(key)

        def action() -> None:
            resizer = map_resize.MapResizer(
                self.image, structure=map_resize.read_map_structure(docs), profile=self.profile)
            map_resize.set_layer_resize(
                docs, self.image, resizer.resize(index, slot, columns, rows, 1),
                profile=self.profile)

        self._edit(action)

    def tile_at(self, key: str, slot: int, cell: int, row: int, column: int) -> int:
        docs, index = self._target(key)
        try:
            value = self._layer(key, slot).cells[cell]
            return self._once("plane", (key, value), lambda: self._plane(docs, index, value))[
                row * TILES_PER_CHUNK + column]
        except (ValueError, OSError, KeyError) as exc:
            raise CreatorError(_friendly(exc)) from exc

    def stamp(self, key: str, slot: int, cell: int, tiles: dict) -> None:
        """Set tiles inside one cell's chunk. A retail chunk becomes a new chunk first."""
        docs, index = self._target(key)
        value = self._layer(key, slot).cells[cell]

        def action() -> None:
            if isinstance(value, str):
                chunk = self._chunk(docs, value)
                template = map_chunk.ChunkTemplate.parse(chunk.template)
                edits = {(entry.row, entry.column): entry.entry for entry in chunk.entries}
                name = value.split(":", 1)[1]
            else:
                template = self._template(index, value)
                edits = {}
                taken = set(map_chunk.read_authored_chunks(docs).chunks)
                name = next(
                    candidate for candidate in
                    (f"piece-{slot}-{cell}-{number}" for number in range(1, 10000))
                    if f"chunk:{candidate}" not in taken)
            base = self._author.plane(template)
            edits.update(tiles)
            edits = {place: entry for place, entry in edits.items()
                     if base[place[0] * TILES_PER_CHUNK + place[1]] != entry}
            if not edits:
                if isinstance(value, str):
                    raise CreatorError(
                        "That would make this piece the same as the one it was made from. "
                        "Paint the original piece here instead.")
                return
            chunk = self._author.create(name, template, edits)
            map_chunk.set_authored_chunk(docs, self.image, chunk, profile=self.profile)
            if not isinstance(value, str):
                map_chunk.set_layout_authored_cells(
                    docs, self.image, {(index, slot, cell): chunk.identity}, profile=self.profile)

        self._edit(action)

    def _collision_identity(self, key: str) -> str:
        return key if key.startswith("map-new:") else map_collision.canonical_identity(int(key[4:]))

    def collision(self, key: str) -> bytes:
        """The map's walk grid: the creator's if there is one, else the base game's."""
        _docs, index = self._target(key)
        try:
            authored = map_collision.read_collision(self.directory).get(
                self._collision_identity(key), {})
            return authored.get(grids.WALK) or map_collision.base_grid(
                self.image, self.profile, index, grids.WALK)
        except (ValueError, OSError) as exc:
            raise CreatorError(_friendly(exc)) from exc

    def set_collision(self, key: str, grid: bytes) -> None:
        _docs, index = self._target(key)

        def action() -> None:
            base = map_collision.base_grid(self.image, self.profile, index, grids.WALK)
            keep = key.startswith("map-new:") or bytes(grid) != base
            map_collision.set_grid(
                self.directory, self._collision_identity(key), grids.WALK,
                bytes(grid) if keep else None)

        self._edit(action)

    def collision_note(self, key: str) -> str:
        if key.startswith("map-new:"):
            return ""
        index = int(key[4:])
        others = [other for others in self._roots.values() if index in others
                  for other in others if other != index]
        if not others:
            return ""
        return ("This map shares its walls with " + ", ".join(self._title(other) for other in others)
                + ". Changing them here changes them there too.")

    def _corpus(self):
        return self._once("corpus", "", lambda: mt.read_map_transitions(
            self.image, self.profile,
            authored=new_maps.authored_map_facts(self.image, self.profile, self._authored())))

    def doors(self, key: str) -> list[Door]:
        docs, index = self._target(key)
        try:
            corpus = self._corpus()
            removed = removal.read_removals(docs).get(index, ())
            doors = []
            for entry in corpus.for_map(mt.MapIdentity(index)):
                record = entry.record
                try:
                    arrival = corpus.arrival(entry.identity)
                except ValueError:
                    arrival = None
                destination = corpus.destination(entry.identity)
                doors.append(Door(
                    f"game:{entry.identity.index}",
                    (record.bound_a_raw, record.bound_b_raw, record.bound_c_raw, record.bound_d_raw),
                    self.title(self._key_of(destination.index)) if destination else "an unknown place",
                    (arrival.x, arrival.y) if arrival else (0, 0),
                    False, entry.identity.index in removed,
                    WALK[corpus.gate_direction(entry.identity)]))
            for (source, name), made in sorted(mt.read_transition_creations(docs).edits().items()):
                if source != index:
                    continue
                doors.append(Door(
                    f"made:{name}",
                    (made.region.first[0], made.region.second[0],
                     made.region.first[1], made.region.second[1]),
                    self.title(self._key_of(int(made.destination[4:]))),
                    tuple(made.arrival), True, False, self.door_walk(key)))
            return doors
        except (ValueError, OSError) as exc:
            raise CreatorError(_friendly(exc)) from exc

    def door_walk(self, key: str) -> str:
        """The way the player must be walking for a door made on this map to open.

        A new door takes this from the map's first door in the base game.
        """
        _docs, index = self._target(key)
        entries = self._corpus().for_map(mt.MapIdentity(index))
        return WALK[self._corpus().gate_direction(entries[0].identity)] if entries else ""

    def can_add_door(self, key: str) -> str:
        """Why this map cannot hold a new door, or an empty string."""
        _docs, index = self._target(key)
        if not self._corpus().for_map(mt.MapIdentity(index)):
            return ("This map has no door in the base game to model a new one on, so "
                    "DragonByte Z cannot add one here yet.")
        return ""

    def add_door(self, key: str, rect, destination_key: str, arrival) -> None:
        docs, index = self._target(key)
        problem = self.can_add_door(key)
        if problem:
            raise CreatorError(problem)

        def action() -> None:
            new_maps.sync_contents(self.directory)
            taken = mt.read_transition_creations(docs).names_for_map(index)
            name = next(candidate for candidate in (f"door-{number}" for number in range(1, 10000))
                        if candidate not in taken)
            identity = mt.CreatedTransitionIdentity(mt.MapIdentity(index), name)
            left, top, right, bottom = rect
            mt.set_transition_creations(docs, self.profile, self.image, {
                identity: mt.TransitionCreation(
                    identity, mt.TransitionIdentity(mt.MapIdentity(index), 0),
                    mt.MapIdentity(self._table_index(destination_key)),
                    TransitionRegion((left, right), (top, bottom)),
                    TransitionArrival(int(arrival[0]), int(arrival[1])))})

        self._edit(action)

    def remove_door(self, key: str, door_key: str, removed: bool = True) -> None:
        docs, index = self._target(key)

        def action() -> None:
            kind, name = door_key.split(":", 1)
            if kind == "made":
                mt.remove_transition_creation(
                    docs, mt.CreatedTransitionIdentity(mt.MapIdentity(index), name))
            else:
                removal.set_removed(docs, index, int(name), removed)

        self._edit(action)

    def _base_objects(self, index: int) -> tuple:
        if index not in self._objects:
            self._objects[index] = mo.read_objects(self.image, self.profile, index)
        return self._objects[index]

    def _object_edits(self) -> dict:
        return self._once("objects", "", lambda: mo.read_document(self.directory))

    def _donor(self, made: mo.Made):
        return next((item for item in self._base_objects(made.donor_map)
                     if item.slot == made.donor_slot), None)

    def _says(self, item) -> str:
        """The base-game conversation an NPC record names, as a reference."""
        if item is None or item.family != mo.NPC:
            return ""
        if self._talks is None:
            self._talks = {entry.address: f"event:{event:04d}" for event, entry in
                           cv.read_conversations(self.image, self.profile).items()}
        at = item.record_offset + mo.CONVERSATION_OFFSET
        return self._talks.get(int.from_bytes(self.image[at:at + 4], "little"), "")

    def characters(self, key: str) -> list[Character]:
        """Everything standing on the map, in the game's order, then the creator's own."""
        return self._once("characters", key, lambda: self._characters(key))

    def _characters(self, key: str) -> list[Character]:
        _docs, index = self._target(key)
        try:
            edits = self._object_edits().get(key, mo.MapEdits())
            rows = []
            for item in self._base_objects(index):
                move = edits.moved.get(item.slot)
                rows.append(Character(
                    f"game:{item.slot}", "", item.sprite_id - mo.SPRITE_ID_FLOOR,
                    move.x if move else item.x, move.y if move else item.y,
                    KINDS[(item.family, item.wanders)], False, item.slot in edits.removed,
                    item.family == mo.NPC, item.box, False,
                    (STORY,) if self._conditional(item)
                    else (VIEW_ONLY[item.family],) if item.family in VIEW_ONLY else (),
                    edits.says.get(item.slot) or self._says(item),
                    edits.appears.get(item.slot, "")))
            for name, made in sorted(edits.made.items(), key=lambda pair: mo.made_order(pair[0])):
                if made.type:
                    continue
                donor = self._donor(made)
                if donor is None:
                    rows.append(Character(
                        f"made:{name}", made.name, -1, made.x, made.y, "missing character",
                        True, False, True, None, False, (LOST,)))
                    continue
                sprite = donor.sprite_id if made.sprite_id is None else made.sprite_id
                rows.append(Character(
                    f"made:{name}", made.name, sprite - mo.SPRITE_ID_FLOOR, made.x, made.y,
                    KINDS[(donor.family, donor.wanders)], True, False, True, made.box,
                    donor.wanders,
                    ((SHARED_BOX,) if donor.wanders and made.box is None else ())
                    + ((STORY,) if self._conditional(donor) else ()),
                    made.says or self._says(donor), made.appears))
            return rows
        except (ValueError, OSError) as exc:
            raise CreatorError(_friendly(exc)) from exc

    def character_limits(self, character: Character) -> tuple:
        """What DragonByte Z cannot do with this character yet, said plainly."""
        if not character.editable:
            return ()
        limits = []
        if character.made:
            limits.append(
                "It behaves as the one it was copied from behaves. That cannot be "
                "changed here yet.")
        limits.append("Characters block the player. That cannot be switched off yet.")
        limits.append("The way it faces when the map opens cannot be set yet.")
        return tuple(limits)

    def _conditional(self, item) -> bool:
        """An NPC record whose second word is set was seen not to appear at map load."""
        at = item.record_offset + 4
        return item.family == mo.NPC and any(self.image[at:at + 4])

    def character_choices(self) -> list[CharacterChoice]:
        """One of each different character and object in the base game, to copy from."""
        if self._choices is None:
            seen, self._choices = set(), []
            for index, objects in mo.census(self.image, self.profile).items():
                for item in objects:
                    if item.family != mo.NPC:
                        continue
                    family = next(f for f in mo.FAMILIES.values() if f.name == item.family)
                    record = bytearray(self.image[item.record_offset:item.record_offset + 0x1C])
                    record[family.position_offset:family.position_offset + 4] = bytes(4)
                    if bytes(record) in seen:
                        continue
                    seen.add(bytes(record))
                    self._choices.append(CharacterChoice(
                        index, item.slot, item.sprite_id - mo.SPRITE_ID_FLOOR,
                        f"{KINDS[(item.family, item.wanders)]}, from {self._title(index)}"))
        return self._choices

    def enemy_choices(self) -> list[PlaceableEnemy]:
        """Every enemy type a placement can name: the project's own, then the game's."""
        return [] if self.enemy_types is None else list(self.enemy_types.placeable())

    def _type_name(self, identity: str) -> str:
        if self._type_names is None:
            self._type_names = {item.key: item.name for item in self.enemy_choices()}
        return self._type_names.get(identity, "")

    def enemy_placements(self, key: str) -> list[MapEnemy]:
        """Every enemy on the map, in the game's order, then the creator's own."""
        return self._once("enemies", key, lambda: self._enemy_placements(key))

    def _enemy_placements(self, key: str) -> list[MapEnemy]:
        _docs, index = self._target(key)
        edits = self._object_edits().get(key, mo.MapEdits())
        try:
            rows = []
            for item in self._base_objects(index):
                if item.family != mo.PLACEMENT:
                    continue
                at = item.record_offset + mo.TYPE_OFFSET
                row = int.from_bytes(self.image[at:at + 4], "little")
                rows.append(MapEnemy(f"game:{item.slot}",
                                     self._type_name(f"enemy:{row}") or GAME_ENEMY,
                                     item.x, item.y, False, ""))
            for name, made in sorted(edits.made.items(), key=lambda pair: mo.made_order(pair[0])):
                if made.type:
                    rows.append(MapEnemy(f"made:{name}",
                                         self._type_name(made.type) or LOST_ENEMY,
                                         made.x, made.y, True, made.appears, made.defeat))
            return rows
        except (ValueError, OSError) as exc:
            raise CreatorError(_friendly(exc)) from exc

    def enemy_count(self, key: str) -> int:
        """How many enemies stand on the map, the game's and the creator's."""
        return len(self.enemy_placements(key))

    def built_objects(self, key: str) -> int:
        """How many objects the map builds when it loads, added enemies included."""
        _docs, index = self._target(key)
        try:
            edits = {mo.canonical_identity(index): self._object_edits().get(key, mo.MapEdits())}
            return mo.built_objects(self.image, self.profile, index, edits)
        except (ValueError, OSError) as exc:
            raise CreatorError(_friendly(exc)) from exc

    @property
    def built_object_policy(self) -> int:
        """The most objects a map may build: the largest load the base game itself uses."""
        return mo.BUILT_OBJECT_POLICY

    def flag_names(self) -> list[str]:
        """The story's flags, by the names the project gives them."""
        try:
            return sorted(sf.read_flags(self.directory).names)
        except ValueError as exc:
            raise CreatorError(_friendly(exc)) from exc

    def _check_enemies(self, key: str, index: int) -> None:
        """Refuse the edit the build would refuse; its own reason is passed on."""
        item = mo.read_document(self.directory).get(key, mo.MapEdits())
        types = None if self.enemy_types is None else self.enemy_types.types()
        mo.check_placed_enemies(self.image, self.profile, index, key, item, types,
                                sf.read_flags(self.directory).names)

    @staticmethod
    def _made_name(enemy_key: str) -> str:
        return enemy_key[5:] if enemy_key.startswith("made:") else enemy_key

    def add_enemy(self, key: str, type_key: str, x: int, y: int) -> str:
        """Place an enemy of ``type_key`` on the map and return its key."""
        _docs, index = self._target(key)
        made: list[str] = []

        def action() -> None:
            made.append(mo.place_enemy(self.directory, key, ENEMY_PREFIX, type_key, x, y))
            self._check_enemies(key, index)

        self._edit(action, verbatim=True)
        return f"made:{made[0]}"

    def move_enemy(self, key: str, enemy_key: str, x: int, y: int) -> None:
        """Move an enemy the project added to (x, y)."""
        _docs, index = self._target(key)

        def action() -> None:
            mo.move_enemy(self.directory, key, self._made_name(enemy_key), x, y)
            self._check_enemies(key, index)

        self._edit(action, verbatim=True)

    def duplicate_enemy(self, key: str, enemy_key: str, x: int, y: int) -> str:
        """Copy an enemy the project added, beside itself, and return the copy's key."""
        _docs, index = self._target(key)
        made: list[str] = []

        def action() -> None:
            made.append(mo.duplicate_enemy(
                self.directory, key, self._made_name(enemy_key), ENEMY_PREFIX, x, y))
            self._check_enemies(key, index)

        self._edit(action, verbatim=True)
        return f"made:{made[0]}"

    def remove_enemy(self, key: str, enemy_key: str) -> None:
        """Take an enemy the project added off the map."""
        self._edit(lambda: mo.remove_enemy(
            self.directory, key, self._made_name(enemy_key)), verbatim=True)

    def set_enemy_appears(self, key: str, enemy_key: str, rule: str) -> None:
        """When an added enemy is on the map: always (empty), a flag, or ``!flag``."""
        self._edit(lambda: mo.set_enemy_appears(
            self.directory, key, self._made_name(enemy_key), rule), verbatim=True)

    def set_enemy_defeat_flag(self, key: str, enemy_key: str, flag: str) -> None:
        """The story flag an added enemy sets when it is defeated, or nothing."""
        _docs, index = self._target(key)

        def action() -> None:
            mo.set_enemy_defeat_flag(self.directory, key, self._made_name(enemy_key), flag)
            self._check_enemies(key, index)

        self._edit(action, verbatim=True)

    def _change_objects(self, key: str, change) -> None:
        self._target(key)

        def action() -> None:
            edits = dict(mo.read_document(self.directory))
            item = change(edits.get(key, mo.MapEdits()))
            _docs, index = self._target(key)
            total = len(self._base_objects(index)) - len(item.removed) + len(item.made)
            if total > mo.MAX_OBJECTS:
                raise CreatorError(
                    f"A map can hold {mo.MAX_OBJECTS} characters and objects. This one is full.")
            for place in list(item.moved.values()) + list(item.made.values()):
                mo.mp.encode_position(place.x, place.y)
            edits[key] = item
            mo.write_document(self.directory, edits)

        self._edit(action)

    @staticmethod
    def _shifted(box, dx: int, dy: int):
        if box is None:
            return None
        return (max(box[0] + dx, 0), max(box[1] + dy, 0), max(box[2] + dx, 0), max(box[3] + dy, 0))

    def _put(self, key: str, made: mo.Made) -> str:
        names: list[str] = []

        def change(item: mo.MapEdits) -> mo.MapEdits:
            donor = self._donor(made)
            if donor is None or donor.family != mo.NPC:
                raise CreatorError(VIEW_ONLY[mo.PLACEMENT])
            prefix = "npc" if donor.family == mo.NPC else "object"
            number = max([mo.made_order(name)[1] for name in item.made], default=0) + 1
            names.append(f"{prefix}-{number}")
            return replace(item, made={**item.made, names[0]: made})

        self._change_objects(key, change)
        return f"made:{names[0]}"

    def add_character(self, key: str, donor_map: int, donor_slot: int, x: int, y: int) -> str:
        """Place a copy of one base-game character or object. Returns its key."""
        donor = self._donor(mo.Made(donor_map, donor_slot, x, y))
        box = self._shifted(donor.box, x - donor.x, y - donor.y) if donor else None
        return self._put(key, mo.Made(donor_map, donor_slot, x, y, "", box))

    def duplicate_character(self, key: str, character_key: str, x: int, y: int) -> str:
        _docs, index = self._target(key)
        kind, name = character_key.split(":", 1)
        if kind == "game":
            return self.add_character(key, index, int(name), x, y)
        made = self._object_edits().get(key, mo.MapEdits()).made.get(name)
        if made is None:
            raise CreatorError("That character is gone.")
        return self._put(key, replace(
            made, x=x, y=y, name="", box=self._shifted(made.box, x - made.x, y - made.y)))

    def move_character(self, key: str, character_key: str, x: int, y: int) -> None:
        _docs, index = self._target(key)
        kind, name = character_key.split(":", 1)

        def change(item: mo.MapEdits) -> mo.MapEdits:
            if kind == "made":
                made = item.made[name]
                return replace(item, made={**item.made, name: replace(
                    made, x=x, y=y, box=self._shifted(made.box, x - made.x, y - made.y))})
            base = next(entry for entry in self._base_objects(index) if entry.slot == int(name))
            if base.family != mo.NPC:
                raise CreatorError(VIEW_ONLY[base.family])
            if base.slot in item.removed:
                raise CreatorError("Put this character back before moving it.")
            moved = {slot: move for slot, move in item.moved.items() if slot != base.slot}
            if (x, y) != (base.x, base.y):
                moved[base.slot] = mo.Move(x, y, base.family, base.sprite_id, (base.x, base.y))
            return replace(item, moved=moved)

        self._change_objects(key, change)

    def remove_character(self, key: str, character_key: str, removed: bool = True) -> None:
        """Take a character off the map. A base-game one can be put back."""
        _docs, index = self._target(key)
        kind, name = character_key.split(":", 1)

        def change(item: mo.MapEdits) -> mo.MapEdits:
            if kind == "made":
                return replace(item, made={k: v for k, v in item.made.items() if k != name})
            slot = int(name)
            base = next(entry for entry in self._base_objects(index) if entry.slot == slot)
            if base.family != mo.NPC:
                raise CreatorError(VIEW_ONLY[base.family])
            gone = set(item.removed) - {slot} | ({slot} if removed else set())
            return replace(
                item, removed=tuple(sorted(gone)),
                moved={k: v for k, v in item.moved.items() if k != slot or not removed})

        self._change_objects(key, change)

    def _remake(self, key: str, character_key: str, **fields) -> None:
        kind, name = character_key.split(":", 1)
        if kind != "made":
            raise CreatorError(
                "Only a character you added can be changed this way. Duplicate this one "
                "and change the copy.")
        self._change_objects(key, lambda item: replace(
            item, made={**item.made, name: replace(item.made[name], **fields)}))

    def rename_character(self, key: str, character_key: str, name: str) -> None:
        self._remake(key, character_key, name=" ".join(name.split())[:40])

    def set_box(self, key: str, character_key: str, box) -> None:
        """Where a wandering character you added may walk: left, top, right, bottom."""
        row = next((item for item in self.characters(key) if item.key == character_key), None)
        if row is not None and not row.can_box:
            raise CreatorError(
                "Only a copy of a character that wanders in the base game can have a wander box.")
        self._remake(key, character_key, box=tuple(int(value) for value in box))

    def set_look(self, key: str, character_key: str, sprite: int | None) -> None:
        """Draw a character you added with another Library sprite, or its own again."""
        self._remake(key, character_key,
                     sprite_id=None if sprite is None else sprite + mo.SPRITE_ID_FLOOR)

    def set_says(self, key: str, character_key: str, reference: str) -> None:
        """Give a character a conversation: ``talk-N``, ``event:NNNN``, or its own again."""
        _docs, index = self._target(key)
        kind, name = character_key.split(":", 1)
        if kind == "made":
            self._remake(key, character_key, says=reference)
            return
        base = next(entry for entry in self._base_objects(index) if entry.slot == int(name))
        if base.family != mo.NPC:
            raise CreatorError("Only a character can be given a conversation.")
        own = self._says(base)

        def change(item: mo.MapEdits) -> mo.MapEdits:
            says = {slot: value for slot, value in item.says.items() if slot != base.slot}
            if reference and reference != own:
                says[base.slot] = reference
            return replace(item, says=says)

        self._change_objects(key, change)

    def set_appears(self, key: str, character_key: str, rule: str) -> None:
        """When a character is on the map: always (empty), a flag, or ``!flag``."""
        kind, name = character_key.split(":", 1)
        if kind == "made":
            self._remake(key, character_key, appears=rule)
            return
        slot = int(name)

        def change(item: mo.MapEdits) -> mo.MapEdits:
            appears = {other: value for other, value in item.appears.items() if other != slot}
            if rule:
                appears[slot] = rule
            return replace(item, appears=appears)

        self._change_objects(key, change)

    def reread(self) -> None:
        """Forget what was read, after another tab changed the project."""
        self._seen.clear()
        self._type_names = None

    def arrival_limit(self, key: str) -> tuple[int, int]:
        return self._corpus().destination_bounds(mt.MapIdentity(self._table_index(key)))
