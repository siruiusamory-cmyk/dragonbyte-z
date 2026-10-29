"""Headless 8x8 screen-entry editing over one editable map layer.

DRAGONBYTE-FINE-001. A selection is a rectangle of the layer's stitched entry
plane held with its map and layer identity. A placement composes one authored
chunk body per destination chunk cell from that cell's current effective body,
carries every other entry of the body verbatim, and commits the authored layout
and chunk documents as ONE journal entry, so one gesture is one undo and Save is
the project's own atomic per-document writer. No GUI toolkit is imported.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
from typing import Mapping

from tools.webfoot import map_chunk
from tools.webfoot.formats import map_graphics as mg
from tools.webfoot.map_paint import MapPaintError, PaintLayer, PaintTarget
from tools.webfoot.packaged import packaged_profile
from tools.webfoot.profile import RomProfile
from tools.webfoot.project import (
    AuthoredChunk,
    AuthoredChunkEntry,
    AuthoredChunks,
    LayoutEdits,
    StatProject,
)

from . import mapedits
from .journal import EditKind, JournalError
from .placement import PlacementError, PlacementModel

__all__ = [
    "EntryDestination",
    "EntryModel",
    "EntryPlan",
    "EntrySelection",
    "EntrySources",
    "EntryTemplate",
    "entry_sources",
]

_SIDE = mg.CHUNK_SIDE_TILES
_ENTRY_COUNT = mg.CHUNK_ENTRY_COUNT


@dataclass(frozen=True, slots=True)
class EntryTemplate:
    """One canonical chunk body and the stored template identity that names it."""

    template: str
    body: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class EntrySources:
    """What an entry model reads from the immutable image.

    ``bodies`` is keyed by ``(map index, layer slot, chunk cell)`` and
    ``assembled`` and ``missing`` are the map's own character-block counts, so a
    test can build the value without an image.
    """

    bodies: Mapping[tuple[int, int, int], EntryTemplate]
    assembled: Mapping[int, int]
    missing: Mapping[int, frozenset[int]]


@dataclass(frozen=True, slots=True)
class EntrySelection:
    """A row-major rectangle of 8x8 screen entries captured from one layer."""

    map_index: int
    layer_slot: int
    x: int
    y: int
    columns: int
    rows: int
    entries: tuple[int, ...]

    @property
    def count(self) -> int:
        return len(self.entries)


@dataclass(frozen=True, slots=True)
class EntryDestination:
    """Where a selection's top-left entry would land, in the layer's own plane."""

    map_index: int
    layer_slot: int
    x: int
    y: int


@dataclass(frozen=True, slots=True)
class EntryPlan:
    """The chunk cells, authored chunks and entry changes a placement would make."""

    cells: tuple[int, ...]
    chunks: tuple[str, ...]
    entries_changed: int


@dataclass(frozen=True, slots=True)
class _Plan:
    layout: tuple[tuple[int, str | None], ...]
    chunks: tuple[AuthoredChunk, ...]
    cells: tuple[int, ...]
    changed: int


def entry_sources(
    image: bytes, map_index: int, *, profile: RomProfile | None = None
) -> EntrySources:
    """Read one map's canonical chunk bodies and its assembled ordinal bounds."""
    resolved = profile if profile is not None else packaged_profile()
    try:
        reader = mg.MapGraphicsReader(image, resolved)
        author = map_chunk.ChunkAuthor(image, profile=resolved)
        entry = mg.read_map_entries(reader)[map_index]
        assembled = map_chunk.assembled_entries(
            reader, map_index, entry.root_address
        )
        bodies: dict[tuple[int, int, int], EntryTemplate] = {}
        cache: dict[int, tuple[int, ...]] = {}
        for layer in mg.read_layers(reader, entry.root_address):
            if layer.handler != mg.DOMINANT_LAYER_HANDLER:
                continue
            ordinals = {
                choice.address: choice.ordinal
                for choice in author.templates(map_index, layer.slot)
            }
            for cell, pointer in enumerate(layer.chunk_addresses):
                if not pointer:
                    continue
                body = cache.get(pointer)
                if body is None:
                    body = mg.dominant_chunk_words(reader, pointer)
                    cache[pointer] = body
                bodies[(map_index, layer.slot, cell)] = EntryTemplate(
                    template=map_chunk.ChunkTemplate(
                        map_index, layer.slot, ordinals[pointer]
                    ).text,
                    body=body,
                )
    except mg.MapGraphicsError as exc:
        raise PlacementError(str(exc)) from exc
    return EntrySources(
        bodies=bodies,
        assembled={map_index: assembled.tile_count},
        missing={map_index: assembled.missing},
    )


class EntryModel(PlacementModel):
    """One opened project, one editable layer, and that map's entry sources."""

    def __init__(
        self,
        project_dir: str | Path,
        project: StatProject,
        target: PaintTarget,
        layer_slot: int,
        sharing: Mapping[tuple[int, int], tuple[int, ...]],
        sources: EntrySources,
    ) -> None:
        super().__init__(project_dir, project, target, layer_slot, sharing)
        self._sources = sources
        self._template_bodies = {
            source.template: source.body for source in sources.bodies.values()
        }

    @classmethod
    def open(
        cls,
        project_dir: str | Path,
        target: PaintTarget,
        layer_slot: int,
        sharing: Mapping[tuple[int, int], tuple[int, ...]],
        sources: EntrySources,
        *,
        expected_base_sha256: str | None = None,
    ) -> "EntryModel":
        model = PlacementModel.open(
            project_dir,
            target,
            layer_slot,
            sharing,
            expected_base_sha256=expected_base_sha256,
        )
        return cls(
            model._project_dir,
            model.project,
            model.target,
            layer_slot,
            sharing,
            sources,
        )

    def entry_vocabulary(self) -> frozenset[int]:
        """Every ordinal this map's assembled character block can draw a tile with."""
        map_index = self.target.map_index
        assembled = self._sources.assembled.get(map_index)
        if assembled is None:
            raise PlacementError(
                f"map:{map_index:04d}'s assembled character block was not measured, "
                "so no entry vocabulary is known for it"
            )
        missing = self._sources.missing.get(map_index, frozenset())
        return frozenset(value for value in range(assembled) if value not in missing)

    def capture_entries(
        self, x: int, y: int, columns: int, rows: int
    ) -> EntrySelection:
        """Capture a rectangle of the open layer's effective 8x8 entry plane."""
        if type(columns) is not int or type(rows) is not int or columns < 1 or rows < 1:
            raise PlacementError("a capture must cover at least one 8x8 entry")
        layer = self.layer
        width = layer.columns * _SIDE
        height = layer.rows * _SIDE
        if (
            type(x) is not int
            or type(y) is not int
            or x < 0
            or y < 0
            or x + columns > width
            or y + rows > height
        ):
            raise PlacementError(
                f"a capture at ({x}, {y}) covering {columns}×{rows} entries is "
                f"outside BG{layer.slot}'s {width}×{height} entry plane"
            )
        plane = self._plane(layer, self.project.layout.cells())
        entries = tuple(
            plane[(y + row) * width + x + column]
            for row in range(rows)
            for column in range(columns)
        )
        self._check_entries(entries, self.target.map_index, "the capture")
        return EntrySelection(
            map_index=self.target.map_index,
            layer_slot=layer.slot,
            x=x,
            y=y,
            columns=columns,
            rows=rows,
            entries=entries,
        )

    def preview_entries(
        self, selection: EntrySelection, destination: EntryDestination
    ) -> EntryPlan:
        """Validate a placement and report what it would change, changing nothing."""
        plan = self._entry_plan(selection, destination)
        return EntryPlan(
            cells=plan.cells,
            chunks=tuple(chunk.identity for chunk in plan.chunks),
            entries_changed=plan.changed,
        )

    def place_entries(
        self, selection: EntrySelection, destination: EntryDestination
    ) -> EntryPlan:
        """Apply a validated placement to the in-memory project as one history entry."""
        plan = self._entry_plan(selection, destination)
        if not plan.changed:
            return EntryPlan(cells=(), chunks=(), entries_changed=0)
        document = {
            key: {slot: dict(cells) for slot, cells in layers.items()}
            for key, layers in self.project.layout.maps.items()
        }
        cells = (
            document.setdefault(LayoutEdits.key_for(destination.map_index), {})
            .setdefault(destination.layer_slot, {})
        )
        replaced: set[str] = set()
        for cell, identity in plan.layout:
            previous = cells.get(cell)
            if isinstance(previous, str):
                replaced.add(previous)
            if identity is None:
                cells.pop(cell, None)
            else:
                cells[cell] = identity
        chunks = dict(self.project.chunks.chunks)
        for chunk in plan.chunks:
            chunks[chunk.identity] = chunk
        referenced = {
            value
            for layers in document.values()
            for layer_cells in layers.values()
            for value in layer_cells.values()
            if isinstance(value, str)
        }
        for identity in sorted(replaced - referenced):
            chunks.pop(identity, None)
        payload = replace(
            mapedits.read(self.project),
            layout=LayoutEdits(maps=document),
            chunks=AuthoredChunks(chunks=dict(sorted(chunks.items()))),
        )
        reason = (
            f"map:{destination.map_index:04d} BG{destination.layer_slot} entry "
            f"placement of {plan.changed} 8x8 tile(s)"
        )
        try:
            self._project = self._journal.apply(
                self._project,
                kind=EditKind.SEMANTIC,
                target=mapedits.MAPS_TARGET,
                after=payload,
                reason=reason,
                coalesce_key=self._stroke_key(),
            )
        except JournalError as exc:
            raise PlacementError(str(exc)) from exc
        return EntryPlan(
            cells=plan.cells,
            chunks=tuple(chunk.identity for chunk in plan.chunks),
            entries_changed=plan.changed,
        )

    def _entry_plan(
        self, selection: EntrySelection, destination: EntryDestination
    ) -> _Plan:
        if not isinstance(selection, EntrySelection):
            raise PlacementError("a placement carries an EntrySelection")
        if not isinstance(destination, EntryDestination):
            raise PlacementError("a placement names an EntryDestination")
        entries = self._check_entries(
            selection.entries, selection.map_index, "this selection"
        )
        if (
            type(selection.columns) is not int
            or type(selection.rows) is not int
            or selection.columns < 1
            or selection.rows < 1
            or len(entries) != selection.columns * selection.rows
        ):
            raise PlacementError(
                "a selection holds one entry per position of its rectangle"
            )
        if destination.map_index != selection.map_index:
            raise PlacementError(
                f"This selection was captured on map {selection.map_index}, so it "
                f"cannot be placed on map {destination.map_index}: a placement stays "
                "within one map"
            )
        if destination.map_index != self.target.map_index:
            raise PlacementError(
                f"this model edits map {self.target.map_index}, so a destination on "
                f"map {destination.map_index} is refused"
            )
        if destination.layer_slot != selection.layer_slot:
            raise PlacementError(
                f"this selection was captured on BG{selection.layer_slot} of map "
                f"{selection.map_index}, so it cannot be placed on "
                f"BG{destination.layer_slot}: a capture stays on the layer it came from"
            )
        layer = self._destination_layer(destination)
        width = layer.columns * _SIDE
        height = layer.rows * _SIDE
        if (
            type(destination.x) is not int
            or type(destination.y) is not int
            or destination.x < 0
            or destination.y < 0
            or destination.x + selection.columns > width
            or destination.y + selection.rows > height
        ):
            raise PlacementError(
                f"the destination at ({destination.x}, {destination.y}) covering "
                f"{selection.columns}×{selection.rows} entries runs past "
                f"BG{layer.slot}'s {width}×{height} entry plane"
            )
        authored = self.project.layout.cells()
        plane = self._plane(layer, authored)
        updates: dict[int, list[tuple[int, int]]] = {}
        changed = 0
        for row in range(selection.rows):
            for column in range(selection.columns):
                value = entries[row * selection.columns + column]
                x = destination.x + column
                y = destination.y + row
                cell = (y // _SIDE) * layer.columns + x // _SIDE
                local = (y % _SIDE) * _SIDE + x % _SIDE
                updates.setdefault(cell, []).append((local, value))
                if plane[y * width + x] != value:
                    changed += 1
        if not changed:
            return _Plan(layout=(), chunks=(), cells=(), changed=0)
        layout: list[tuple[int, str | None]] = []
        chunks: list[AuthoredChunk] = []
        cells: list[int] = []
        for cell in sorted(updates):
            canonical = self._canonical(layer.slot, cell)
            body = list(self._body(layer.slot, cell, authored))
            for local, value in updates[cell]:
                body[local] = value
            composed = tuple(body)
            if composed == canonical.body:
                layout.append((cell, None))
                continue
            chunk = self._compose(layer.slot, cell, canonical, composed)
            chunks.append(chunk)
            layout.append((cell, chunk.identity))
            cells.append(cell)
        return _Plan(
            layout=tuple(layout),
            chunks=tuple(sorted(chunks, key=lambda chunk: chunk.identity)),
            cells=tuple(cells),
            changed=changed,
        )

    def _destination_layer(self, destination: EntryDestination) -> PaintLayer:
        try:
            layer = self.target.layer(destination.layer_slot)
        except MapPaintError as exc:
            raise PlacementError(str(exc)) from exc
        if not layer.editable:
            raise PlacementError(
                f"BG{destination.layer_slot} of map:{destination.map_index:04d} is "
                f"not editable: {layer.read_only_reason}"
            )
        shared = self._sharing.get((destination.map_index, destination.layer_slot))
        if shared is None:
            raise PlacementError(
                f"the layer record behind map {destination.map_index} "
                f"BG{destination.layer_slot} was not measured for sharing, so a "
                "placement there is refused"
            )
        others = tuple(index for index in shared if index != destination.map_index)
        if others:
            names = ", ".join(str(index) for index in others)
            raise PlacementError(
                f"BG{destination.layer_slot} of map {destination.map_index} is a "
                f"layer record shared with map {names}, so a change here would "
                "change all of them"
            )
        return layer

    def _compose(
        self,
        layer_slot: int,
        cell: int,
        canonical: EntryTemplate,
        body: tuple[int, ...],
    ) -> AuthoredChunk:
        edits = tuple(
            AuthoredChunkEntry(
                row=index // _SIDE,
                column=index % _SIDE,
                prior=canonical.body[index],
                entry=body[index],
            )
            for index in range(_ENTRY_COUNT)
            if body[index] != canonical.body[index]
        )
        return AuthoredChunk(
            identity=self._identity(layer_slot, cell, canonical.template, edits),
            template=canonical.template,
            entries=edits,
        )

    def _identity(
        self,
        layer_slot: int,
        cell: int,
        template: str,
        edits: tuple[AuthoredChunkEntry, ...],
    ) -> str:
        map_index = self.target.map_index
        material = "|".join(
            [f"{map_index:04d}", str(layer_slot), str(cell), template]
            + [f"{edit.cell}:{edit.prior:04x}:{edit.entry:04x}" for edit in edits]
        )
        digest = sha256(material.encode("ascii")).hexdigest()[:12]
        return f"chunk:e{map_index:04d}-{layer_slot}-{cell}-{digest}"

    def _check_entries(
        self, entries: tuple[int, ...], map_index: int, what: str
    ) -> tuple[int, ...]:
        assembled = self._sources.assembled.get(map_index)
        if assembled is None:
            raise PlacementError(
                f"map:{map_index:04d}'s assembled character block was not measured, "
                f"so {what} cannot be judged"
            )
        rule = map_chunk.AssembledEntries(
            map_index=map_index,
            tile_count=assembled,
            missing=self._sources.missing.get(map_index, frozenset()),
        )
        for entry in entries:
            if type(entry) is not int or not 0 <= entry <= 0xFFFF:
                raise PlacementError(
                    f"{what} holds {entry!r}, which is not a 16-bit screen entry"
                )
            problem = rule.refusal(entry)
            if problem is not None:
                raise PlacementError(f"{what} holds {problem}")
        return entries

    def _plane(self, layer: PaintLayer, authored: Mapping) -> tuple[int, ...]:
        bodies = [self._body(layer.slot, cell, authored) for cell in range(layer.cell_count)]
        out: list[int] = []
        for block_y in range(layer.rows):
            for local_y in range(_SIDE):
                for block_x in range(layer.columns):
                    body = bodies[block_y * layer.columns + block_x]
                    start = local_y * _SIDE
                    out.extend(body[start : start + _SIDE])
        return tuple(out)

    def _body(
        self, layer_slot: int, cell: int, authored: Mapping
    ) -> tuple[int, ...]:
        value = authored.get((self.target.map_index, layer_slot, cell))
        if isinstance(value, str):
            chunk = self.project.chunks.get(value)
            if chunk is None:
                raise PlacementError(
                    f"chunk cell {cell} of BG{layer_slot} names authored chunk "
                    f"{value!r}, which this project does not declare"
                )
            template = self._template_bodies.get(chunk.template)
            if template is None:
                raise PlacementError(
                    f"authored chunk {value!r} names template {chunk.template}, which "
                    f"is not a canonical chunk of map:{self.target.map_index:04d}"
                )
            body = list(template)
            for edit in chunk.entries:
                if body[edit.cell] != edit.prior:
                    raise PlacementError(
                        f"authored chunk {value!r} stores prior {edit.prior:#06x} at "
                        f"cell {edit.key}, but its template holds "
                        f"{body[edit.cell]:#06x}"
                    )
                body[edit.cell] = edit.entry
            return tuple(body)
        return self._canonical(layer_slot, cell).body

    def _canonical(self, layer_slot: int, cell: int) -> EntryTemplate:
        source = self._sources.bodies.get(
            (self.target.map_index, layer_slot, cell)
        )
        if source is None:
            raise PlacementError(
                f"chunk cell {cell} of BG{layer_slot} of map:"
                f"{self.target.map_index:04d} holds no canonical chunk, so an "
                "authored body cannot be composed against it"
            )
        return source
