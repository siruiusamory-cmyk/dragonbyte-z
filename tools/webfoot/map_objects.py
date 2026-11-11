"""Map objects: what stands on a map, the project document, and the build domain.

DRAGONBYTE-Z-APP-004. A map names its objects through one engine-counted pointer
array (``MapEntry+0x04`` slots at ``MapEntry+0x14``). Three record families share
that array, and each record carries the sprite id the engine draws it with. This
module reads all three through one query, holds a project's edits in one document
and compiles them with one writer. Only the NPC family is written; the other two
are read and carried through unchanged, so a map that mixes families stays whole.

A base-game object is named by its slot in the engine's array. An object the
project adds is named by an id the application assigns once; its display name is
separate, so renaming or reordering never changes what a reference means. Every
edit to a base-game object records what that object was, and the build refuses an
edit whose record no longer matches instead of applying it to something else.

Nothing in the engine is replaced. An added object is a copy of a base-game
record with its position changed, reached through a longer copy of the map's own
array; base-game slots keep their order and their records are not rewritten,
except for the position word of one that the project moved on a base-game map no
authored map was made from. Where an authored map shares the record, the move is
a copy, so the authored map keeps what it had.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import struct
from types import MappingProxyType

from .allocation import Addressability, AllocationKind, AllocationRequest, allocate
from .binary import GBA_ROM_BASE, FileOffset
from .formats import map_entry as me
from .formats import map_placements as mp
from .layout import AnchorId, OwnedRegion, RomRange
from .map_authoring import read_records, record_size, table_offset
from .project.atomic import replace_document
from .project.format import ProjectFormatError, dump_toml, load_toml
from .sprite_attachment import ENTRY_CLASS_RAW, SUPPORTED_FAMILIES, FAMILY_MAP_SIBLING
from .write import ByteChange

OBJECTS_FILE = Path("maps") / "objects.toml"
OBJECTS_TABLE = "objects"
DOMAIN = "map_objects"
MAX_OBJECTS = 0xFF
ALIGNMENT = 4
SPRITE_ID_FLOOR = 10
ID_RULE = re.compile(r"[a-z][a-z0-9]*-[0-9]{1,6}")
_CANONICAL = re.compile(r"map:(\d{4})")
_AUTHORED = re.compile(r"map-new:([a-z][a-z0-9_-]*)")

PLACEMENT = "placement"
NPC = "npc"
SCENE = "scene"


class MapObjectError(ProjectFormatError):
    """An object document or edit the build must not act on."""


@dataclass(frozen=True, slots=True)
class Family:
    """One record family: where its position and sprite id sit, and what is proven.

    ``writable`` is false for a family whose record layout is only inferred, or
    whose edits have not been proven in the running game; such objects are shown
    and never written.
    """

    name: str
    factory_raw: int
    position_offset: int
    sprite_offset: int
    writable: bool


_NPC_LAYOUT = SUPPORTED_FAMILIES[FAMILY_MAP_SIBLING]
FAMILIES = {
    family.factory_raw: family for family in (
        Family(PLACEMENT, mp.FACTORY_RAW, 0x0C, 0x10, False),
        Family(NPC, _NPC_LAYOUT.factory_raw, _NPC_LAYOUT.position_offset,
               _NPC_LAYOUT.sprite_id_offset, True),
        Family(SCENE, next(raw for raw in mp.SIBLING_FACTORIES
                           if raw != _NPC_LAYOUT.factory_raw), 0x08, 0x0C, False),
    )
}


@dataclass(frozen=True, slots=True)
class MapObject:
    """One slot of a map's object array, as far as its record is understood."""

    slot: int
    family: str
    sprite_id: int
    x: int
    y: int
    record_offset: int
    pointer_raw: int
    writable: bool
    wanders: bool
    box: tuple[int, int, int, int] | None


@dataclass(frozen=True, slots=True)
class Move:
    x: int
    y: int
    family: str
    sprite_id: int
    was: tuple[int, int]


@dataclass(frozen=True, slots=True)
class Made:
    donor_map: int
    donor_slot: int
    x: int
    y: int
    name: str = ""
    box: tuple[int, int, int, int] | None = None
    sprite_id: int | None = None


@dataclass(frozen=True, slots=True)
class MapEdits:
    moved: dict = field(default_factory=dict)
    made: dict = field(default_factory=dict)
    removed: tuple = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "moved", MappingProxyType(dict(self.moved)))
        object.__setattr__(self, "made", MappingProxyType(dict(self.made)))

    def is_empty(self) -> bool:
        return not (self.moved or self.made or self.removed)


def canonical_identity(index: int) -> str:
    return f"map:{index:04d}"


def authored_identity(name: str) -> str:
    return f"map-new:{name}"


def _field(name: str) -> int:
    return next(item.offset for item in me.MAP_ENTRY_LAYOUT if item.name == name)


def _u32(image: bytes, offset: int) -> int:
    return struct.unpack_from("<I", image, offset)[0]


def _position(image: bytes, offset: int) -> tuple[int, int]:
    low, high = struct.unpack_from("<2H", image, offset)
    return mp.decode_position(low, high)


def _entry_target(image: bytes, record_offset: int) -> int | None:
    """The file offset of the behaviour entry an NPC record dispatches, if in the image."""
    target = _u32(image, record_offset + _NPC_LAYOUT.table_entry_offset) - GBA_ROM_BASE
    return target if 0 <= target <= len(image) - _NPC_LAYOUT.entry_size else None


def _box(image: bytes, record_offset: int) -> tuple[int, int, int, int] | None:
    """The wander box of an NPC whose dispatched entry is the decoded wander class."""
    target = _entry_target(image, record_offset)
    if target is None or _u32(image, target) != ENTRY_CLASS_RAW:
        return None
    return struct.unpack_from("<4H", image, target + _NPC_LAYOUT.box_offset)


def read_objects(image: bytes, profile, index: int) -> tuple[MapObject, ...]:
    """Every object on one base-game map, in the engine's own array order."""
    records = read_records(image, profile)
    if not 0 <= index < len(records):
        raise MapObjectError(f"map {index} is outside the table's 0..{len(records) - 1}")
    entry = records[index]
    count, word = entry.trigger_count_raw, entry.scripts_pointer_raw
    if not count or not word:
        return ()
    try:
        slots = mp.iter_object_slots(image, word - GBA_ROM_BASE, count)
    except mp.MapPlacementError as exc:
        raise MapObjectError(f"map {index}: {exc}") from exc
    objects = []
    for slot in slots:
        family = FAMILIES.get(slot.family_raw)
        if family is None or slot.target_offset is None:
            raise MapObjectError(
                f"map {index} slot {slot.index} holds a record of no known family")
        at = slot.target_offset
        x, y = _position(image, at + family.position_offset)
        box = _box(image, at) if family.name == NPC else None
        objects.append(MapObject(
            slot.index, family.name, _u32(image, at + family.sprite_offset), x, y, at,
            slot.pointer_raw, family.writable, box is not None, box))
    return tuple(objects)


def census(image: bytes, profile) -> dict[int, tuple[MapObject, ...]]:
    """The objects of every base-game map that has any."""
    found = {}
    for index in range(len(read_records(image, profile))):
        objects = read_objects(image, profile, index)
        if objects:
            found[index] = objects
    return found


def _whole(value, where: str) -> int:
    if type(value) is not int:
        raise MapObjectError(f"{where} must be a whole number")
    return value


def _pair(value, where: str, size: int = 2) -> tuple:
    if not isinstance(value, list) or len(value) != size:
        raise MapObjectError(f"{where} must hold {size} whole numbers")
    return tuple(_whole(item, where) for item in value)


def read_document(project_dir: str | Path) -> dict[str, MapEdits]:
    """The project's object edits by map, or nothing when it has none."""
    path = Path(project_dir) / OBJECTS_FILE
    if not path.exists():
        return {}
    try:
        document = load_toml(path.read_text(encoding="utf-8"))
    except (ProjectFormatError, OSError) as exc:
        raise MapObjectError(f"{path}: {exc}") from exc
    table = document.get(OBJECTS_TABLE)
    if not isinstance(table, dict) or not table:
        raise MapObjectError(f"{path}: [{OBJECTS_TABLE}] must name at least one map")
    edits = {}
    for identity, body in table.items():
        if not (_CANONICAL.fullmatch(identity) or _AUTHORED.fullmatch(identity)):
            raise MapObjectError(f"{path}: {identity!r} is not a map identity")
        if not isinstance(body, dict) or set(body) - {"moved", "made", "removed"} or not (
                isinstance(body.get("moved", {}), dict) and isinstance(body.get("made", {}), dict)
                and isinstance(body.get("removed", []), list)):
            raise MapObjectError(f"{path}: {identity} holds something that is not an object edit")
        moved, made = {}, {}
        for key, row in body.get("moved", {}).items():
            where = f"{path}: {identity} moved {key}"
            if not key.isdecimal() or not isinstance(row, dict):
                raise MapObjectError(f"{where} is not a base-game object")
            moved[int(key)] = Move(
                _whole(row.get("x"), where), _whole(row.get("y"), where),
                str(row.get("family", "")), _whole(row.get("sprite"), where),
                _pair(row.get("was"), where))
        for key, row in body.get("made", {}).items():
            where = f"{path}: {identity} made {key}"
            if not ID_RULE.fullmatch(key) or not isinstance(row, dict):
                raise MapObjectError(f"{where} is not an added object")
            donor = _CANONICAL.fullmatch(str(row.get("donor_map", "")))
            if not donor:
                raise MapObjectError(f"{where} names no base-game map to copy from")
            made[key] = Made(
                int(donor.group(1)), _whole(row.get("donor_slot"), where),
                _whole(row.get("x"), where), _whole(row.get("y"), where),
                str(row.get("name", "")),
                _pair(row["box"], where, 4) if "box" in row else None,
                _whole(row["sprite"], where) if "sprite" in row else None)
        removed = tuple(sorted({_whole(item, f"{path}: {identity} removed")
                                for item in body.get("removed", [])}))
        edits[identity] = MapEdits(moved, made, removed)
    return edits


def write_document(project_dir: str | Path, edits) -> Path:
    """Persist the object document, or remove it when no edit remains."""
    path = Path(project_dir) / OBJECTS_FILE
    table = {}
    for identity, item in sorted(edits.items()):
        if item.is_empty():
            continue
        body = {}
        if item.moved:
            body["moved"] = {
                str(slot): {"x": move.x, "y": move.y, "family": move.family,
                            "sprite": move.sprite_id, "was": list(move.was)}
                for slot, move in sorted(item.moved.items())}
        if item.made:
            body["made"] = {}
            for key, made in sorted(item.made.items(), key=lambda pair: made_order(pair[0])):
                row = {"donor_map": canonical_identity(made.donor_map),
                       "donor_slot": made.donor_slot, "x": made.x, "y": made.y,
                       "name": made.name}
                if made.box is not None:
                    row["box"] = list(made.box)
                if made.sprite_id is not None:
                    row["sprite"] = made.sprite_id
                body["made"][key] = row
        if item.removed:
            body["removed"] = list(item.removed)
        table[identity] = body
    if not table:
        path.unlink(missing_ok=True)
        return path
    return replace_document(path, dump_toml({OBJECTS_TABLE: table}))


def made_order(key: str) -> tuple[str, int]:
    """Added objects build in the order they were made, whatever they are called."""
    prefix, number = key.rsplit("-", 1)
    return prefix, int(number)


def rename(project_dir: str | Path, old_name: str, new_name: str) -> None:
    """Carry an authored map's objects to its new name."""
    edits = read_document(project_dir)
    if authored_identity(old_name) in edits:
        edits[authored_identity(new_name)] = edits.pop(authored_identity(old_name))
        write_document(project_dir, edits)


@dataclass(frozen=True, slots=True)
class ObjectMaterialization:
    changes: tuple[ByteChange, ...]
    reserved: tuple
    generated_allocations: tuple
    authored_entry_patches: dict
    pending: tuple = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "authored_entry_patches",
                           MappingProxyType(dict(self.authored_entry_patches)))


def pending_provenance(pending, placements) -> tuple:
    """The provenance of authored maps' arrays, once their table rows are placed."""
    rows = {placement.name: placement.record_file_offset for placement in placements}
    return tuple(allocation.generated_allocation_provenance(
        domain=DOMAIN, resource=owner, pointer_offset=rows[name] + offset,
        source_range=source_range)
        for name, owner, allocation, offset, source_range in pending)


def _record_bytes(image: bytes, source: MapObject, x: int, y: int, where: str) -> bytes:
    """A copy of one base-game record standing somewhere else, otherwise verbatim."""
    if not source.writable:
        raise MapObjectError(
            f"{where}: editing a {source.family} record is not established, so it "
            "cannot be copied or moved")
    try:
        low, high = mp.encode_position(x, y)
    except mp.MapPlacementError as exc:
        raise MapObjectError(f"{where}: {exc}") from exc
    record = bytearray(image[source.record_offset:source.record_offset + _NPC_LAYOUT.header_size])
    struct.pack_into("<2H", record, _NPC_LAYOUT.position_offset, low, high)
    return bytes(record)


def _with_sprite(record: bytes, source: MapObject, sprite_id: int | None) -> bytes:
    if sprite_id is None:
        return record
    family = next(item for item in FAMILIES.values() if item.name == source.family)
    patched = bytearray(record)
    struct.pack_into("<I", patched, family.sprite_offset, sprite_id)
    return bytes(patched)


def _own_box(image: bytes, record: bytes, source: MapObject, box, address: int,
             where: str) -> bytes:
    """Give a copied wanderer an entry of its own that carries the authored box.

    Only the decoded wander class has a known entry size and box position. A copy
    without a box keeps dispatching the entry its donor dispatches.
    """
    if box is None:
        return record
    target = _entry_target(image, source.record_offset)
    if source.family != NPC or not source.wanders or target is None:
        raise MapObjectError(
            f"{where}: only a character that wanders in the base game has a box to set")
    x1, y1, x2, y2 = box
    if not (0 <= x1 <= x2 <= 0xFFFF and 0 <= y1 <= y2 <= 0xFFFF):
        raise MapObjectError(f"{where}: the wander box is not left-to-right, top-to-bottom")
    entry = bytearray(image[target:target + _NPC_LAYOUT.entry_size])
    struct.pack_into("<4H", entry, _NPC_LAYOUT.box_offset, x1, y1, x2, y2)
    header = bytearray(record)
    struct.pack_into("<I", header, _NPC_LAYOUT.table_count_offset, 1)
    struct.pack_into("<I", header, _NPC_LAYOUT.table_entry_offset,
                     address + _NPC_LAYOUT.header_size)
    return bytes(header) + bytes(entry)


def _record_size(source: MapObject, image: bytes, box) -> int:
    return _NPC_LAYOUT.header_size + (_NPC_LAYOUT.entry_size if box is not None else 0)


def _only_named_by(image: bytes, array_word: int, field_offset: int, where: str) -> None:
    needle = array_word.to_bytes(4, "little")
    at = image.find(needle)
    while at != -1:
        if at % ALIGNMENT == 0 and at != field_offset:
            raise MapObjectError(
                f"{where}: its object array is also named at file 0x{at:06X}, and a "
                "longer copy of the array would leave that reference behind")
        at = image.find(needle, at + 1)


def materialize_objects(image: bytes, profile, edits, authored_donors,
                        reserved=()) -> ObjectMaterialization:
    """Compile every object edit into attributed changes.

    ``authored_donors`` maps each authored map name to its donor's base-game
    index. An authored map starts with its donor's objects; its array fields are
    returned as a patch to the row the authored-map domain emits, and a moved
    object on it is a copy, so the donor map is never changed through it.
    """
    cache: dict[int, tuple[MapObject, ...]] = {}

    def objects_of(index: int) -> tuple[MapObject, ...]:
        if index not in cache:
            cache[index] = read_objects(image, profile, index)
        return cache[index]

    stride = record_size(profile)
    table_at = table_offset(profile, len(image))
    count_field, array_field = _field("trigger_count_raw"), _field("scripts_pointer_raw")
    plans = []
    requests = []
    for identity in sorted(edits):
        item = edits[identity]
        if item.is_empty():
            continue
        canonical = _CANONICAL.fullmatch(identity)
        if canonical:
            base_index, name = int(canonical.group(1)), None
        else:
            name = _AUTHORED.fullmatch(identity).group(1)
            if name not in authored_donors:
                raise MapObjectError(
                    f"{identity} has objects but the project authors no map of that name")
            base_index = authored_donors[name]
        base = objects_of(base_index)
        by_slot = {entry.slot: entry for entry in base}
        for slot, move in item.moved.items():
            where = f"{identity}: moved object {slot}"
            current = by_slot.get(slot)
            if current is None:
                raise MapObjectError(f"{where}: the base game has no such object on this map")
            if (current.family, current.sprite_id, (current.x, current.y)) != (
                    move.family, move.sprite_id, move.was):
                raise MapObjectError(
                    f"{where}: the object in that slot is not the one this edit was "
                    "made for, so it is not applied")
            if slot in item.removed:
                raise MapObjectError(f"{where}: it is both moved and removed")
        for slot in item.removed:
            if slot not in by_slot:
                raise MapObjectError(
                    f"{identity}: removed object {slot}: the base game has no such object")
            if not by_slot[slot].writable:
                raise MapObjectError(
                    f"{identity}: removed object {slot}: removing a {by_slot[slot].family} "
                    "record is not established")
        kept = [entry for entry in base if entry.slot not in item.removed]
        total = len(kept) + len(item.made)
        if total > MAX_OBJECTS:
            raise MapObjectError(
                f"{identity} would hold {total} objects; the game counts a map's objects "
                f"in one byte, so {MAX_OBJECTS} is the most a map can have")
        copies = []
        in_place = []
        for slot, move in sorted(item.moved.items()):
            where = f"{identity}: moved object {slot}"
            if name is None and base_index not in authored_donors.values():
                _record_bytes(image, by_slot[slot], move.x, move.y, where)
                in_place.append((by_slot[slot], move))
            else:
                copies.append((f"slot-{slot}", by_slot[slot], move.x, move.y, None, None, where))
        for key, made in sorted(item.made.items(), key=lambda pair: made_order(pair[0])):
            where = f"{identity}: added object {key}"
            donors = {entry.slot: entry for entry in objects_of(made.donor_map)} \
                if 0 <= made.donor_map < len(read_records(image, profile)) else {}
            donor = donors.get(made.donor_slot)
            if donor is None:
                raise MapObjectError(f"{where}: the object it copies does not exist")
            if made.sprite_id is not None and made.sprite_id < SPRITE_ID_FLOOR:
                raise MapObjectError(f"{where}: {made.sprite_id} is not a character sprite")
            copies.append((key, donor, made.x, made.y, made.box, made.sprite_id, where))
        rebuild = bool(item.made or item.removed or copies)
        if rebuild and name is None and base:
            _only_named_by(image, read_records(image, profile)[base_index].scripts_pointer_raw,
                           table_at + base_index * stride + array_field, identity)
        for key, source, _x, _y, box, _sprite, where in copies:
            _record_bytes(image, source, _x, _y, where)
            owner = f"{DOMAIN}:{identity}:{key}"
            requests.append(AllocationRequest(
                AnchorId(owner), owner, _record_size(source, image, box), ALIGNMENT,
                kind=AllocationKind.MAP_OBJECT_RECORD,
                addressability=Addressability.EXPANDED_ONLY,
                evidence="a copy of one base-game object record with its own position, "
                         "reached only through this map's re-emitted object array"))
        if rebuild and total:
            owner = f"{DOMAIN}:{identity}:array"
            requests.append(AllocationRequest(
                AnchorId(owner), owner, 4 * total, ALIGNMENT,
                kind=AllocationKind.PLACEMENT_REFERENCE_ARRAY,
                addressability=Addressability.EXPANDED_ONLY,
                evidence="the map's object array re-emitted: every kept base-game slot "
                         "in its original order, then the project's added objects"))
        plans.append((identity, name, base_index, base, kept, copies, in_place, rebuild, total))
    if not plans:
        return ObjectMaterialization((), (), (), {})

    allocations = {allocation.request.anchor.value: allocation for allocation in allocate(
        profile, tuple(requests),
        occupied=tuple(span if isinstance(span, OwnedRegion)
                       else OwnedRegion(span, "build reservation") for span in reserved))
    } if requests else {}
    padding = profile.generated_expansion.padding_byte
    changes: list[ByteChange] = []
    generated: list = []
    patches: dict[str, dict[int, bytes]] = {}
    pending: list = []
    for identity, name, base_index, base, kept, copies, in_place, rebuild, total in plans:
        for current, move in in_place:
            family = next(item for item in FAMILIES.values() if item.name == current.family)
            at = current.record_offset + family.position_offset
            low, high = mp.encode_position(move.x, move.y)
            changes.append(ByteChange(
                at, image[at:at + 4], struct.pack("<2H", low, high),
                f"{DOMAIN}:{identity}:slot-{current.slot}",
                f"{identity}: base-game object {current.slot} moved to ({move.x}, {move.y})"))
        if not rebuild:
            continue
        pointers = {entry.slot: entry.pointer_raw for entry in kept}
        added = []
        array_owner = f"{DOMAIN}:{identity}:array"
        array = allocations.get(array_owner)
        ordered = [entry.slot for entry in kept]
        tail_at = len(ordered)
        for key, source, x, y, box, sprite_id, where in copies:
            owner = f"{DOMAIN}:{identity}:{key}"
            allocation = allocations[owner]
            payload = _own_box(
                image, _with_sprite(_record_bytes(image, source, x, y, where), source, sprite_id),
                source, box, allocation.rom_address, where)
            at = allocation.range.start.value
            changes.append(ByteChange(
                at, bytes([padding]) * len(payload), payload, owner,
                f"{identity}: object {key}, a copy of a base-game {source.family} record "
                f"at ({x}, {y})"))
            if key.startswith("slot-") and int(key[5:]) in pointers:
                pointers[int(key[5:])] = allocation.rom_address
                position = ordered.index(int(key[5:]))
            else:
                added.append(allocation.rom_address)
                position = tail_at + len(added) - 1
            generated.append(allocation.generated_allocation_provenance(
                domain=DOMAIN, resource=owner,
                pointer_offset=array.range.start.value + 4 * position,
                source_range=RomRange(FileOffset(source.record_offset), len(payload))))
        words = [pointers[slot] for slot in ordered] + added
        row_at = table_at + base_index * stride
        old_word = image[row_at + array_field:row_at + array_field + 4]
        if array is None:
            new_word = old_word
        else:
            payload = struct.pack(f"<{len(words)}I", *words)
            at = array.range.start.value
            changes.append(ByteChange(
                at, bytes([padding]) * len(payload), payload, array_owner,
                f"{identity}: its object array with {len(words)} slots"))
            new_word = array.rom_address.to_bytes(4, "little")
        if name is not None:
            patches[name] = {count_field: bytes([total]), array_field: new_word}
            if array is not None:
                pending.append((name, array_owner, array, array_field, RomRange(
                    FileOffset(row_at + array_field), 4)))
            continue
        changes.append(ByteChange(
            row_at + count_field, image[row_at + count_field:row_at + count_field + 1],
            bytes([total]), array_owner,
            f"{identity}: the object count the engine's loop reads, {len(base)} -> {total}"))
        if array is not None:
            changes.append(ByteChange(
                row_at + array_field, old_word, new_word, array_owner,
                f"{identity}: the field that names its object array"))
            generated.append(array.generated_allocation_provenance(
                domain=DOMAIN, resource=array_owner, pointer_offset=row_at + array_field,
                source_range=RomRange(
                    FileOffset(int.from_bytes(old_word, "little") - GBA_ROM_BASE)
                    if base else FileOffset(row_at + array_field), 4 * max(len(base), 1))))
    return ObjectMaterialization(
        tuple(changes),
        tuple(OwnedRegion(allocation.range, owner) for owner, allocation in allocations.items()),
        tuple(generated), patches, tuple(pending))
