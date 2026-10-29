"""Headless placement model: capture, preview, place, undo and save one map layer.

DRAGONBYTE-PLACEMENT-001. The authored layout is held in memory on the project
the model opened; a placement changes that value and commits one journal entry,
and only :meth:`PlacementModel.save` writes, through the project's own atomic
document writer. No GUI toolkit is imported, so a test drives the model headless.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping

from tools.webfoot.formats import map_graphics as mg
from tools.webfoot.map_paint import MapPaintError, PaintLayer, PaintTarget
from tools.webfoot.packaged import packaged_profile
from tools.webfoot.profile import RomProfile
from tools.webfoot.project import LayoutEdits, ProjectError, StatProject, read_project

from . import mapedits
from .journal import EditJournal, EditKind, JournalError, project_authority

__all__ = [
    "CapturedBlock",
    "CapturedFeature",
    "Destination",
    "PlacementError",
    "PlacementModel",
    "PlacementPlan",
    "layer_record_sharing",
]


class PlacementError(ValueError):
    """A capture, preview, placement, undo, redo or save was refused; the reason is the message."""


@dataclass(frozen=True, slots=True)
class CapturedBlock:
    """One captured block: the source layer's ordinal and the chunk pointer it names."""

    ordinal: int
    pointer: int


@dataclass(frozen=True, slots=True)
class CapturedFeature:
    """A single block or a row-major rectangle of blocks, captured from one layer."""

    map_index: int
    layer_slot: int
    cell: int
    columns: int
    rows: int
    blocks: tuple[CapturedBlock, ...]

    @property
    def block_count(self) -> int:
        return len(self.blocks)


@dataclass(frozen=True, slots=True)
class Destination:
    """Where a feature's top-left block would land."""

    map_index: int
    layer_slot: int
    cell: int


@dataclass(frozen=True, slots=True)
class PlacementPlan:
    """The cells a placement changes; empty means the placement is a no-op."""

    cells: tuple[int, ...]

    @property
    def count(self) -> int:
        return len(self.cells)


@dataclass(frozen=True, slots=True)
class _Plan:
    layer: PaintLayer
    positions: tuple[int, ...]
    ordinals: tuple[int, ...]
    changed: tuple[int, ...]


class PlacementModel:
    """One opened project and one editable map layer, driven without a window."""

    def __init__(
        self,
        project_dir: str | Path,
        project: StatProject,
        target: PaintTarget,
        layer_slot: int,
        sharing: Mapping[tuple[int, int], tuple[int, ...]],
    ) -> None:
        self._project_dir = Path(project_dir)
        self._project = project
        self._target = target
        self._layer_slot = layer_slot
        self._layer = target.layer(layer_slot)
        self._sharing = sharing
        self._journal = EditJournal()
        self._journal.bind(project_authority(project))
        self._stroke = 0
        self._saved_revisions: set[int] = set()

    @classmethod
    def open(
        cls,
        project_dir: str | Path,
        target: PaintTarget,
        layer_slot: int,
        sharing: Mapping[tuple[int, int], tuple[int, ...]],
        *,
        expected_base_sha256: str | None = None,
    ) -> "PlacementModel":
        """Load the project and open one editable layer of ``target``."""
        try:
            project = read_project(project_dir)
            layer = target.layer(layer_slot)
        except (ProjectError, MapPaintError) as exc:
            raise PlacementError(str(exc)) from exc
        if expected_base_sha256 is not None:
            supplied = expected_base_sha256.lower()
            if supplied != project.meta.base_rom_sha256:
                raise PlacementError(
                    "base image mismatch: this project requires sha256 "
                    f"{project.meta.base_rom_sha256}, the supplied image is {supplied}"
                )
        if not layer.editable:
            raise PlacementError(
                f"BG{layer_slot} of map:{target.map_index:04d} is not editable: "
                f"{layer.read_only_reason}"
            )
        return cls(project_dir, project, target, layer_slot, sharing)

    @property
    def project(self) -> StatProject:
        return self._project

    @property
    def target(self) -> PaintTarget:
        return self._target

    @property
    def layer(self) -> PaintLayer:
        return self._layer

    @property
    def dirty(self) -> bool:
        """Whether the in-memory project differs from the last saved document."""
        return self._journal.is_dirty

    @property
    def history_depth(self) -> int:
        return self._journal.depth

    @property
    def can_undo(self) -> bool:
        return self._journal.can_undo

    @property
    def can_redo(self) -> bool:
        return self._journal.can_redo

    def effective_pointers(self) -> dict[int, int | None]:
        """The chunk pointer each cell of the open layer holds in memory.

        An authored ordinal resolves through the layer's own vocabulary; ``None``
        is an authored value this SDK call cannot resolve to a pointer.
        """
        authored = self._project.layout.cells()
        return {
            cell: self._pointer_of(
                self._layer,
                cell,
                authored.get((self._target.map_index, self._layer_slot, cell)),
            )
            for cell in range(self._layer.cell_count)
        }

    def capture(self, cell: int, columns: int = 1, rows: int = 1) -> CapturedFeature:
        """Capture one block, or a ``columns`` by ``rows`` rectangle, from the open layer."""
        if columns < 1 or rows < 1:
            raise PlacementError("a capture must cover at least one block")
        layer = self._layer
        if not layer.contains(cell):
            raise PlacementError(
                f"chunk cell {cell!r} is outside BG{layer.slot}'s "
                f"{layer.columns}×{layer.rows} grid"
            )
        row0, col0 = divmod(cell, layer.columns)
        if col0 + columns > layer.columns or row0 + rows > layer.rows:
            raise PlacementError(
                f"the capture runs past BG{layer.slot}'s "
                f"{layer.columns}×{layer.rows} grid"
            )
        blocks: list[CapturedBlock] = []
        for row in range(row0, row0 + rows):
            for column in range(col0, col0 + columns):
                index = row * layer.columns + column
                pointer = layer.cells[index].pointer
                ordinal = layer.ordinal_of(pointer)
                if ordinal is None:
                    raise PlacementError(
                        f"chunk cell {index} of BG{layer.slot} holds no chunk this "
                        "map uses, so it cannot be captured"
                    )
                blocks.append(CapturedBlock(ordinal=ordinal, pointer=pointer))
        return CapturedFeature(
            map_index=self._target.map_index,
            layer_slot=layer.slot,
            cell=cell,
            columns=columns,
            rows=rows,
            blocks=tuple(blocks),
        )

    def preview(self, feature: CapturedFeature, destination: Destination) -> PlacementPlan:
        """Validate a placement and report what it would change, without changing anything."""
        return PlacementPlan(cells=self._plan(feature, destination).changed)

    def place(self, feature: CapturedFeature, destination: Destination) -> PlacementPlan:
        """Apply a validated placement to the in-memory project as one history entry."""
        plan = self._plan(feature, destination)
        if not plan.changed:
            return PlacementPlan(cells=())
        document = {
            key: {slot: dict(cells) for slot, cells in layers.items()}
            for key, layers in self._project.layout.maps.items()
        }
        cells = (
            document.setdefault(LayoutEdits.key_for(destination.map_index), {})
            .setdefault(destination.layer_slot, {})
        )
        for cell, ordinal in zip(plan.positions, plan.ordinals):
            if cell in plan.changed:
                cells[cell] = ordinal
        payload = replace(
            mapedits.read(self._project), layout=LayoutEdits(maps=document)
        )
        reason = (
            f"map:{destination.map_index:04d} BG{destination.layer_slot} "
            f"placement of {len(plan.changed)} block(s)"
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
        return PlacementPlan(cells=plan.changed)

    def _plan(self, feature: CapturedFeature, destination: Destination) -> _Plan:
        if len(feature.blocks) != feature.columns * feature.rows:
            raise PlacementError(
                "a captured feature must hold one block per position of its rectangle"
            )
        if destination.map_index != feature.map_index:
            raise PlacementError(
                f"This feature was captured on map {feature.map_index}, so it cannot "
                f"be placed on map {destination.map_index}: a placement stays within "
                "one map"
            )
        try:
            layer = self._target.layer(destination.layer_slot)
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
        if not layer.contains(destination.cell):
            raise PlacementError(
                f"chunk cell {destination.cell!r} is outside BG{layer.slot}'s "
                f"{layer.columns}×{layer.rows} grid"
            )
        row0, col0 = divmod(destination.cell, layer.columns)
        positions: list[tuple[int, int, int]] = []
        missing = 0
        for row in range(feature.rows):
            for column in range(feature.columns):
                if col0 + column >= layer.columns or row0 + row >= layer.rows:
                    missing += 1
                    continue
                positions.append(
                    (row, column, (row0 + row) * layer.columns + col0 + column)
                )
        if missing:
            raise PlacementError(
                f"{missing} of {feature.block_count} blocks do not fit inside "
                f"BG{layer.slot}."
            )
        authored = self._project.layout.cells()
        ordinals: list[int] = []
        changed: list[int] = []
        for block, (_row, _column, index) in zip(feature.blocks, positions):
            ordinal = layer.ordinal_of(block.pointer)
            if ordinal is None:
                raise PlacementError(
                    f"That picture is not one BG{layer.slot} of map "
                    f"{destination.map_index} already uses: chunk "
                    f"{block.pointer:#010x} is not in the map's existing chunks"
                )
            ordinals.append(ordinal)
            current = authored.get(
                (destination.map_index, destination.layer_slot, index)
            )
            if self._pointer_of(layer, index, current) != block.pointer:
                changed.append(index)
        return _Plan(
            layer=layer,
            positions=tuple(position[2] for position in positions),
            ordinals=tuple(ordinals),
            changed=tuple(changed),
        )

    @staticmethod
    def _pointer_of(
        layer: PaintLayer, cell: int, authored: int | str | None
    ) -> int | None:
        if authored is None:
            return layer.cells[cell].pointer
        if isinstance(authored, int):
            return layer.pointer(authored)
        return None

    def begin_stroke(self) -> None:
        """Merge the placements that follow into one history entry."""
        self._stroke += 1

    def end_stroke(self) -> None:
        self._stroke = 0

    def _stroke_key(self) -> str:
        return f"stroke:{self._stroke}" if self._stroke else ""

    def undo(self) -> StatProject:
        try:
            self._project = self._journal.undo(self._project)
        except JournalError as exc:
            raise PlacementError(str(exc)) from exc
        return self._project

    def redo(self) -> StatProject:
        try:
            self._project = self._journal.redo(self._project)
        except JournalError as exc:
            raise PlacementError(str(exc)) from exc
        return self._project

    def save(self) -> int:
        """Write the project document atomically; return the placements that differ from the saved one."""
        self._stroke = 0
        applied = {entry.revision for entry in self._journal.edits()}
        placements = len(applied ^ self._saved_revisions)
        if not self._journal.is_dirty:
            return 0
        try:
            self._journal.save(self._project_dir, self._project)
        except JournalError as exc:
            raise PlacementError(str(exc)) from exc
        self._saved_revisions = applied
        return placements


def layer_record_sharing(
    image: bytes, *, profile: RomProfile | None = None
) -> dict[tuple[int, int], tuple[int, ...]]:
    """Which maps reference each ``(map, layer slot)`` record, measured from one image.

    A cell write happens inside the layer record, so a record another map also
    references would change that map too; this is the census the placement guard
    reads. The measurement is read-only and opens no output.
    """
    resolved = profile if profile is not None else packaged_profile()
    reader = mg.MapGraphicsReader(image, resolved)
    references: dict[int, set[int]] = {}
    maps: list[tuple[int, tuple[mg.LayerRecord, ...]]] = []
    for entry in mg.read_map_entries(reader):
        layers = mg.read_layers(reader, entry.root_address)
        maps.append((entry.index, layers))
        for layer in layers:
            references.setdefault(layer.address, set()).add(entry.index)
    return {
        (index, layer.slot): tuple(sorted(references[layer.address]))
        for index, layers in maps
        for layer in layers
    }
