"""The map editor's model: maps, layers, tiles, collision and doors, with undo.

A retail map is ``map:NNNN``. A map the creator made is ``map-new:<name>``; it is
a private copy of a retail map, and every edit to it lands on that copy.

Each edit is written to the project at once through the SDK's own validated
writers. Undo and redo restore the map documents as they were before or after an
edit, so they step through whole edits and never leave a half-written project.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re

from tools.dragonbyte.session import Session
from tools.webfoot import map_authoring as new_maps
from tools.webfoot import map_chunk, map_collision, map_paint, map_resize, map_view
from tools.webfoot import map_transition_removal as removal
from tools.webfoot import map_transitions as mt
from tools.webfoot.formats import map_collision as grids
from tools.webfoot.formats import map_graphics as mg
from tools.webfoot.formats.map_transitions import TransitionArrival, TransitionRegion

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

    def _edit(self, action) -> None:
        before = self._snapshot()
        try:
            action()
        except (ValueError, OSError, KeyError) as exc:
            self._restore(before)
            raise CreatorError(_friendly(exc)) from exc
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
                arrival = corpus.arrival(entry.identity)
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

    def arrival_limit(self, key: str) -> tuple[int, int]:
        return self._corpus().destination_bounds(mt.MapIdentity(self._table_index(key)))
