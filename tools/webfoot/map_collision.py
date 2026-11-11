"""Authored map collision: the project document and the build domain.

DRAGONBYTE-Z-APP-003. A project states, per map, the whole walkability grid it
wants. The build packs each grid into the engine's own container, places it in
owned space and repoints the one root word that names it. Nothing in the engine
is replaced: the retail loader unpacks the authored container and the retail
test routine reads it.

A canonical map is named ``map:NNNN``. A map the project authored is named
``map-new:<name>``, so adding another map never changes which grid belongs to
which map. An authored map always has a root of its own. Canonical maps can
share one root, so an edit to one is an edit to every map on that root;
``sharers`` reports them and the build refuses two different grids for one root.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
import re
import zlib

from .allocation import Addressability, AllocationKind, AllocationRequest, allocate
from .binary import GBA_ROM_BASE, FileOffset
from .formats import map_collision as fmt
from .layout import AnchorId, OwnedRegion, RomRange
from .map_authoring import read_records, record_count
from .project.atomic import replace_document
from .project.format import ProjectFormatError, dump_toml, load_toml
from .write import ByteChange, GeneratedAllocationProvenance

COLLISION_FILE = Path("maps") / "collision.toml"
COLLISION_TABLE = "collision"
DOMAIN = "map_collision"
_CANONICAL = re.compile(r"map:(\d{4})")
_AUTHORED = re.compile(r"map-new:([a-z][a-z0-9_-]*)")


class MapCollisionEditError(ProjectFormatError):
    """A collision document or edit the build must not act on."""


def canonical_identity(index: int) -> str:
    return f"map:{index:04d}"


def authored_identity(name: str) -> str:
    return f"map-new:{name}"


def _grid_text(grid: bytes) -> str:
    return base64.b64encode(zlib.compress(bytes(grid), 9)).decode("ascii")


def _grid_bytes(text: object, where: str) -> bytes:
    try:
        grid = zlib.decompress(base64.b64decode(text, validate=True))
    except (ValueError, TypeError, zlib.error) as exc:
        raise MapCollisionEditError(f"{where} is not a stored collision grid") from exc
    if len(grid) != fmt.GRID_BYTES:
        raise MapCollisionEditError(f"{where} holds {len(grid)} bytes, not {fmt.GRID_BYTES}")
    return grid


def read_collision(project_dir: str | Path) -> dict[str, dict[str, bytes]]:
    """The project's authored grids, or nothing when it authors none."""
    path = Path(project_dir) / COLLISION_FILE
    if not path.exists():
        return {}
    try:
        document = load_toml(path.read_text(encoding="utf-8"))
    except (ProjectFormatError, OSError) as exc:
        raise MapCollisionEditError(f"{path}: {exc}") from exc
    table = document.get(COLLISION_TABLE)
    if not isinstance(table, dict) or not table:
        raise MapCollisionEditError(f"{path}: [{COLLISION_TABLE}] must name at least one map")
    edits: dict[str, dict[str, bytes]] = {}
    for identity, grids in table.items():
        if not (_CANONICAL.fullmatch(identity) or _AUTHORED.fullmatch(identity)):
            raise MapCollisionEditError(f"{path}: {identity!r} is not a map identity")
        if not isinstance(grids, dict) or not grids or set(grids) - set(fmt.ROOT_OFFSETS):
            raise MapCollisionEditError(
                f"{path}: {identity} must hold a walk grid, a second grid, or both")
        edits[identity] = {which: _grid_bytes(text, f"{path}: {identity}.{which}")
                           for which, text in grids.items()}
    return edits


def write_collision(project_dir: str | Path, edits) -> Path:
    """Persist the collision document, or remove it when no grid is authored."""
    path = Path(project_dir) / COLLISION_FILE
    kept = {identity: grids for identity, grids in edits.items() if grids}
    if not kept:
        path.unlink(missing_ok=True)
        return path
    return replace_document(path, dump_toml({COLLISION_TABLE: {
        identity: {which: _grid_text(grid) for which, grid in sorted(grids.items())}
        for identity, grids in sorted(kept.items())}}))


def set_grid(project_dir: str | Path, identity: str, which: str, grid: bytes | None) -> None:
    """Author one grid of one map, or pass None to return it to the base game's."""
    if not (_CANONICAL.fullmatch(identity) or _AUTHORED.fullmatch(identity)):
        raise MapCollisionEditError(f"{identity!r} is not a map identity")
    if which not in fmt.ROOT_OFFSETS:
        raise MapCollisionEditError(f"there is no collision grid called {which!r}")
    edits = read_collision(project_dir)
    grids = dict(edits.get(identity, {}))
    if grid is None:
        grids.pop(which, None)
    else:
        if len(grid) != fmt.GRID_BYTES:
            raise MapCollisionEditError(f"a collision grid is exactly {fmt.GRID_BYTES} bytes")
        grids[which] = bytes(grid)
    edits[identity] = grids
    write_collision(project_dir, edits)


def rename(project_dir: str | Path, old_name: str, new_name: str) -> None:
    """Carry an authored map's grids to its new name."""
    edits = read_collision(project_dir)
    if authored_identity(old_name) in edits:
        edits[authored_identity(new_name)] = edits.pop(authored_identity(old_name))
        write_collision(project_dir, edits)


def root_address(image: bytes, profile, index: int) -> int:
    """The root record a canonical map loads, read through its table row."""
    records = read_records(image, profile)
    if not 0 <= index < len(records):
        raise MapCollisionEditError(f"map {index} is outside the table's 0..{len(records) - 1}")
    source = records[index].variation_array_pointer_raw - GBA_ROM_BASE
    if not 0 <= source <= len(image) - 4:
        raise MapCollisionEditError(f"map {index} names no root record")
    return int.from_bytes(image[source:source + 4], "little")


def base_grid(image: bytes, profile, index: int, which: str) -> bytes:
    """The grid the base game holds for a canonical map."""
    try:
        return fmt.read_grid(image, root_address(image, profile, index), which).grid
    except fmt.MapCollisionError as exc:
        raise MapCollisionEditError(f"map {index}: {exc}") from exc


def sharers(image: bytes, profile, index: int) -> tuple[int, ...]:
    """The other canonical maps that load the same root, and so the same grids."""
    root = root_address(image, profile, index)
    return tuple(other for other in range(record_count(profile))
                 if other != index and _root_or_none(image, profile, other) == root)


def _root_or_none(image: bytes, profile, index: int) -> int | None:
    try:
        return root_address(image, profile, index)
    except MapCollisionEditError:
        return None


@dataclass(frozen=True, slots=True)
class PendingGrid:
    """A placed grid whose root does not exist until the authored-map domain runs."""

    name: str
    which: str
    allocation: object
    pointer: int
    source_range: RomRange


@dataclass(frozen=True, slots=True)
class CollisionMaterialization:
    changes: tuple[ByteChange, ...]
    reserved: tuple[RomRange, ...]
    generated_allocations: tuple
    authored_root_patches: dict
    pending: tuple[PendingGrid, ...]


def _provenance(resource, owner, allocation, pointer, pointer_offset, source_range):
    return GeneratedAllocationProvenance(
        domain=DOMAIN, resource=resource, owner=owner, source_range=source_range,
        allocated_range=allocation.range, allocated_rom_address=pointer,
        pointer_offset=pointer_offset, expansion_evidence=allocation.free_region_evidence)


def materialize_collision(image: bytes, profile, edits, authored_donors,
                          reserved=()) -> CollisionMaterialization:
    """Pack every authored grid, place it, and repoint the canonical roots.

    ``authored_donors`` maps each authored map name to its donor's canonical
    index. A grid for an authored map is returned as a root word for the
    authored-map domain to write into the root it emits, as a root patch.
    """
    targets = []
    roots: dict[int, str] = {}
    for identity in sorted(edits):
        canonical = _CANONICAL.fullmatch(identity)
        if canonical:
            index = int(canonical.group(1))
            root = root_address(image, profile, index)
            if root in roots:
                raise MapCollisionEditError(
                    f"{identity} and {roots[root]} load the same root record, so they "
                    "cannot hold different collision; author one of them")
            roots[root] = identity
            name = None
        else:
            name = _AUTHORED.fullmatch(identity).group(1)
            if name not in authored_donors:
                raise MapCollisionEditError(
                    f"{identity} has collision but the project authors no map of that name")
            root = root_address(image, profile, authored_donors[name])
        for which in sorted(edits[identity]):
            try:
                stored = fmt.read_grid(image, root, which)
                payload = fmt.encode(edits[identity][which])
            except fmt.MapCollisionError as exc:
                raise MapCollisionEditError(f"{identity}: {exc}") from exc
            targets.append((identity, name, which, stored, payload))
    if not targets:
        return CollisionMaterialization((), (), (), {}, ())

    owners = [f"{DOMAIN}:{identity}:{which}" for identity, _n, which, _s, _p in targets]
    allocations = {item.request.anchor.value: item for item in allocate(
        profile,
        [AllocationRequest(
            AnchorId(owner), owner, len(target[4]), 4,
            kind=AllocationKind.PACKED_STREAM,
            addressability=Addressability.EXPANDED_PERMITTED,
            evidence="a collision container above canonical EOF is unpacked and obeyed "
                     "by the retail loader (DRAGONBYTE-Z-APP-003 runtime trace)",
        ) for owner, target in zip(owners, targets)],
        occupied=tuple(span if isinstance(span, OwnedRegion)
                       else OwnedRegion(span, "build reservation") for span in reserved),
    )}

    expansion = profile.generated_expansion
    changes: list[ByteChange] = []
    generated: list = []
    words: dict[str, dict[int, bytes]] = {}
    pending: list[PendingGrid] = []
    for owner, (identity, name, which, stored, payload) in zip(owners, targets):
        allocation = allocations[owner]
        destination = allocation.range.start.value
        expanded = destination >= profile.size
        old = (bytes([expansion.padding_byte]) * len(payload) if expanded
               else image[destination:destination + len(payload)])
        pointer = FileOffset(destination).to_gba_address(
            expansion.output_size if expanded else profile.size).raw
        changes.append(ByteChange(destination, old, payload, owner,
                                  f"{identity}: the authored {which} collision grid"))
        source_range = RomRange(FileOffset(stored.container_offset),
                                stored.packed_end - stored.container_offset)
        if name is not None:
            words.setdefault(name, {})[fmt.ROOT_OFFSETS[which]] = pointer.to_bytes(4, "little")
            if expanded:
                pending.append(PendingGrid(name, which, allocation, pointer, source_range))
            continue
        at = stored.pointer_offset
        changes.append(ByteChange(at, image[at:at + 4], pointer.to_bytes(4, "little"), owner,
                                  f"{identity}: the root word naming its {which} collision grid"))
        if expanded:
            generated.append(_provenance(f"{identity}:{which}", owner, allocation, pointer,
                                         at, source_range))
    return CollisionMaterialization(
        tuple(changes), tuple(item.range for item in allocations.values()),
        tuple(generated), words, tuple(pending))


def pending_provenance(pending, placements) -> tuple:
    """The provenance of authored maps' grids, once their roots have been placed."""
    roots = {placement.name: placement.root_file_offset for placement in placements}
    return tuple(_provenance(
        f"{authored_identity(item.name)}:{item.which}",
        f"{DOMAIN}:{authored_identity(item.name)}:{item.which}",
        item.allocation, item.pointer,
        roots[item.name] + fmt.ROOT_OFFSETS[item.which], item.source_range)
        for item in pending)
