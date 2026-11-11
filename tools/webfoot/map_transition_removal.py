"""Removing a map's existing transitions. DRAGONBYTE-Z-APP-003.

A map root holds a count at ``+0x40`` and, at ``+0x44``, the address of an array
of 4-byte record pointers. The engine walks exactly ``count`` elements. Removing
a transition is therefore the engine's own data with one pointer left out and the
count lowered: no record is rewritten and no code changes.

The project lists, per map, the canonical array indexes it removes. When the same
build also creates transitions on that map, the creation domain has already
re-emitted the array; the removal then edits that array. Otherwise a shorter
array is placed in owned space and the root is repointed at it.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .allocation import Addressability, AllocationKind, AllocationRequest, allocate
from .binary import GBA_ROM_BASE, FileOffset
from .layout import AnchorId, OwnedRegion, RomRange
from .map_collision import root_address
from .project.atomic import replace_document
from .project.format import ProjectFormatError, dump_toml, load_toml
from .write import ByteChange, GeneratedAllocationProvenance

REMOVALS_FILE = Path("maps") / "transition_removals.toml"
REMOVALS_TABLE = "removed"
DOMAIN = "map_transition_removal"
COUNT_OFFSET = 0x40
ARRAY_OFFSET = 0x44


class TransitionRemovalError(ProjectFormatError):
    """A removal document or request the build must not act on."""


def read_removals(project_dir: str | Path) -> dict[int, tuple[int, ...]]:
    """Each map's removed array indexes, or nothing when the project removes none."""
    path = Path(project_dir) / REMOVALS_FILE
    if not path.exists():
        return {}
    try:
        table = load_toml(path.read_text(encoding="utf-8")).get(REMOVALS_TABLE)
    except (ProjectFormatError, OSError) as exc:
        raise TransitionRemovalError(f"{path}: {exc}") from exc
    if not isinstance(table, dict) or not table:
        raise TransitionRemovalError(f"{path}: [{REMOVALS_TABLE}] must name at least one map")
    removals: dict[int, tuple[int, ...]] = {}
    for key, indexes in table.items():
        if not (key.startswith("map:") and key[4:].isdigit()):
            raise TransitionRemovalError(f"{path}: {key!r} is not a map identity")
        if (not isinstance(indexes, list) or not indexes
                or any(type(index) is not int or index < 0 for index in indexes)):
            raise TransitionRemovalError(f"{path}: {key} must list transition indexes")
        removals[int(key[4:])] = tuple(sorted(set(indexes)))
    return removals


def set_removed(project_dir: str | Path, map_index: int, index: int, removed: bool) -> None:
    """Remove one of a map's existing transitions, or put it back."""
    removals = {key: set(value) for key, value in read_removals(project_dir).items()}
    indexes = removals.setdefault(map_index, set())
    (indexes.add if removed else indexes.discard)(index)
    path = Path(project_dir) / REMOVALS_FILE
    kept = {f"map:{key:04d}": sorted(value) for key, value in sorted(removals.items()) if value}
    if not kept:
        path.unlink(missing_ok=True)
        return
    replace_document(path, dump_toml({REMOVALS_TABLE: kept}))


def apply_removals(image: bytes, profile, removals, changes, reserved=()):
    """Fold the removals into a build's changes.

    ``changes`` is the list the map's other domains have produced so far. Returns
    ``(changes, reserved, generated_allocations)`` with the removals applied.
    """
    changes = list(changes)
    spans: list[RomRange] = []
    generated: list = []
    expansion = profile.generated_expansion
    for map_index, indexes in sorted(removals.items()):
        root = root_address(image, profile, map_index) - GBA_ROM_BASE
        count = int.from_bytes(image[root + COUNT_OFFSET:root + COUNT_OFFSET + 4], "little")
        array = int.from_bytes(image[root + ARRAY_OFFSET:root + ARRAY_OFFSET + 4], "little")
        if any(index >= count for index in indexes):
            raise TransitionRemovalError(
                f"map:{map_index:04d} has {count} transition(s); it cannot remove "
                f"number {max(indexes)}")
        owner = f"{DOMAIN}:map:{map_index:04d}"

        def without(body: bytes) -> bytes:
            return b"".join(body[4 * at:4 * at + 4] for at in range(len(body) // 4)
                            if at not in indexes)

        counted = next((at for at, change in enumerate(changes)
                        if change.offset == root + COUNT_OFFSET), None)
        if counted is not None:
            pointed = next(change for change in changes if change.offset == root + ARRAY_OFFSET)
            placed = int.from_bytes(pointed.new, "little") - GBA_ROM_BASE
            at = next(at for at, change in enumerate(changes) if change.offset == placed)
            body = without(changes[at].new)
            changes[at] = replace(
                changes[at], new=body + changes[at].old[len(body):])
            new_count = int.from_bytes(changes[counted].new, "little") - len(indexes)
            changes[counted] = replace(changes[counted], new=new_count.to_bytes(4, "little"))
            continue

        at = array - GBA_ROM_BASE
        body = without(image[at:at + 4 * count])
        changes.append(ByteChange(
            root + COUNT_OFFSET, image[root + COUNT_OFFSET:root + COUNT_OFFSET + 4],
            (count - len(indexes)).to_bytes(4, "little"), owner,
            f"map:{map_index:04d} root+0x40 transition count {count} -> "
            f"{count - len(indexes)}"))
        if not body:
            continue
        if expansion is None:
            raise TransitionRemovalError(
                "this ROM's profile declares no expansion to hold a shorter transition array")
        allocation = allocate(
            profile,
            [AllocationRequest(
                AnchorId(owner), owner, len(body), 4,
                kind=AllocationKind.TRANSITION_POINTER_ARRAY,
                addressability=Addressability.EXPANDED_ONLY,
                evidence="root+0x44 holds a full GBA address; the creation domain's "
                         "expanded arrays are walked by the retail engine",
            )],
            occupied=tuple(span if isinstance(span, OwnedRegion)
                           else OwnedRegion(span, "build reservation")
                           for span in tuple(reserved) + tuple(spans)),
        )[0]
        destination = allocation.range.start.value
        pointer = FileOffset(destination).to_gba_address(expansion.output_size).raw
        changes.append(ByteChange(
            destination, bytes([expansion.padding_byte]) * len(body), body, owner,
            f"map:{map_index:04d}: its transition pointer array without the removed "
            "transition(s)"))
        changes.append(ByteChange(
            root + ARRAY_OFFSET, image[root + ARRAY_OFFSET:root + ARRAY_OFFSET + 4],
            pointer.to_bytes(4, "little"), owner,
            f"map:{map_index:04d} root+0x44 references the shorter transition array"))
        spans.append(allocation.range)
        generated.append(GeneratedAllocationProvenance(
            domain=DOMAIN, resource=f"map:{map_index:04d}", owner=owner,
            source_range=RomRange(FileOffset(at), 4 * count),
            allocated_range=allocation.range, allocated_rom_address=pointer,
            pointer_offset=root + ARRAY_OFFSET,
            expansion_evidence=allocation.free_region_evidence))
    return changes, tuple(spans), generated
