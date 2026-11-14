"""Project enemy types: one spare type-table row per named type.

The base game names every type row it can build except sixteen, and a project
may put a record of its own on one of those. A type's identity is its name. The
row is assigned once, when the type is claimed, and never derived again, so a
rename cannot move it. The bytes the record was copied from are kept and
compared against the base image, so an image the type was not claimed against is
refused rather than re-seeded with whatever sits on that row now.

A type keeps its donor's behaviour row (+0x08): that field selects the enemy's
behaviour, so a fresh value there would be a different enemy, not the same one.

`STAT_FIELDS` is the record's own byte layout: hp u24 at +0x04, the table's `exp`
u24 at +0x00 which a type document calls `experience`, strength at +0x0D and
endurance at +0x0F. A type's +0x14 word points at its descriptor, and the
descriptor's third word is the callback its defeat runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from types import MappingProxyType

from .data.enemy_families import DONOR_CALLBACK_WORDS, SPARE_ROWS
from .formats import stat_tables as st
from .project.atomic import replace_document
from .project.format import ProjectFormatError, dump_toml, load_toml
from .write import ByteChange

TYPES_FILE = Path("enemies") / "types.toml"
TYPE_KEY = re.compile(r"enemy:[a-z][a-z0-9_-]{0,63}")
TYPE_NAME = re.compile(r"[a-z][a-z0-9_-]{0,63}")
NAME_RULE = (
    "Name the type with small letters, digits, _ and -, starting with a letter."
)

STAT_FIELDS = {
    "hp": (0x04, 3),
    "experience": (0x00, 3),
    "strength": (0x0D, 1),
    "endurance": (0x0F, 1),
}

DESCRIPTOR_FIELD = 0x14
CALLBACK_FIELD = 0x08


class EnemyTypeError(ProjectFormatError):
    """A type document, or a change to one, the project must not act on."""


@dataclass(frozen=True, slots=True)
class EnemyType:
    """One authored type: its row, the retail row it was copied from, its bytes."""

    row: int
    donor: int
    raw: bytes
    edits: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "edits", MappingProxyType(dict(self.edits)))

    def record(self) -> bytes:
        """The bytes this type writes: the claimed record with its edits applied."""
        blob = bytearray(self.raw)
        for name, value in self.edits.items():
            offset, width = STAT_FIELDS[name]
            blob[offset : offset + width] = value.to_bytes(width, "little")
        return bytes(blob)


@dataclass(frozen=True, slots=True)
class Types:
    entries: Mapping[str, EnemyType] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", MappingProxyType(dict(self.entries)))

    def rows(self) -> dict[int, str]:
        """The claimed row of each type, keyed the other way round."""
        return {entry.row: key for key, entry in self.entries.items()}


def spare_rows(profile) -> tuple[int, ...]:
    """The rows this profile leaves unnamed, which a type may claim."""
    rows = SPARE_ROWS.get(profile.id)
    if not rows:
        raise EnemyTypeError(
            f"no spare enemy type rows are declared for profile {profile.id!r}"
        )
    return rows


def _table_offset(profile, image: bytes | bytearray) -> int:
    table = profile.enemy_stats
    if table is None:
        raise EnemyTypeError(
            f"profile {profile.id!r} declares no enemy type table, so it has no "
            "row an enemy type could be written to"
        )
    return table.address.to_file_offset(len(image))


def donor_family(profile, image: bytes | bytearray) -> tuple[int, ...]:
    """The rows a type may be copied from, read out of the image itself.

    A type on another callback has never been run to its defeat, and a record
    with no HP is a donor for nothing, so neither is offered.
    """
    callbacks = DONOR_CALLBACK_WORDS.get(profile.id)
    if not callbacks:
        raise EnemyTypeError(
            f"no donor family is declared for profile {profile.id!r}"
        )
    table = profile.enemy_stats
    if table is None:
        raise EnemyTypeError(f"profile {profile.id!r} declares no enemy type table")
    start = _table_offset(profile, image)
    rows: list[int] = []
    for row in range(table.count):
        offset = start + row * table.record_size
        descriptor = int.from_bytes(
            image[offset + DESCRIPTOR_FIELD : offset + DESCRIPTOR_FIELD + 4], "little"
        )
        if not st.GBA_ROM_BASE <= descriptor < st.GBA_ROM_BASE + len(image):
            continue
        at = descriptor - st.GBA_ROM_BASE + CALLBACK_FIELD
        callback = int.from_bytes(image[at : at + 4], "little")
        if callback in callbacks and st.decode_enemy_record(image, offset).hp:
            rows.append(row)
    return tuple(rows)


def _record_bytes(profile, image: bytes | bytearray, row: int) -> bytes:
    table = profile.enemy_stats
    start = _table_offset(profile, image) + row * table.record_size
    return bytes(image[start : start + table.record_size])


def _require_raw(body: dict, key: str, where: object) -> bytes:
    raw = body.get("raw")
    if not isinstance(raw, str):
        raise EnemyTypeError(
            f"{where}: {key}.raw must be a hexadecimal string carrying the "
            "record's bytes; without it the type cannot be rebuilt"
        )
    try:
        return bytes.fromhex(raw)
    except ValueError as exc:
        raise EnemyTypeError(f"{where}: {key}.raw is not valid hex: {exc}") from exc


def _require_value(field_name: str, value: object, key: str, where: object) -> int:
    width = STAT_FIELDS[field_name][1]
    maximum = (1 << (width * 8)) - 1
    if type(value) is not int or not 0 <= value <= maximum:
        raise EnemyTypeError(
            f"{where}: {key}.{field_name} = {value!r} does not fit the record's "
            f"{width}-byte field (0..{maximum})"
        )
    return value


def type_key(name: str) -> str:
    """The document key of ``name``, refused when it is not a type name."""
    if not isinstance(name, str) or not TYPE_NAME.fullmatch(name):
        raise EnemyTypeError(NAME_RULE)
    return f"enemy:{name}"


def read_types(project_dir: str | Path, profile, image: bytes | bytearray) -> Types:
    """Load and check ``enemies/types.toml`` against the base image.

    Every refusal below is about the image the type was claimed against: the
    row's place in the spare pool, the donor's family and the bytes recorded at
    claim time. A type file does not carry an address, and a build reads its
    row from the profile rather than from the document.
    """
    path = Path(project_dir) / TYPES_FILE
    if not path.is_file():
        return Types()
    try:
        document = load_toml(path.read_text(encoding="utf-8"))
    except (ProjectFormatError, OSError) as exc:
        raise EnemyTypeError(f"{path}: {exc}") from exc
    table = document.get("type")
    if set(document) - {"type"} or not isinstance(table, dict) or not table:
        raise EnemyTypeError(
            f"{path}: holds something that is not a table of enemy types"
        )
    pool = spare_rows(profile)
    size = profile.enemy_stats.record_size
    family = donor_family(profile, image)
    entries: dict[str, EnemyType] = {}
    claimed: dict[int, str] = {}
    for key, body in table.items():
        if not isinstance(key, str) or not TYPE_KEY.fullmatch(key):
            raise EnemyTypeError(f"{path}: {key!r} is not an enemy type name")
        if not isinstance(body, dict):
            raise EnemyTypeError(f"{path}: {key} is not a table")
        row = body.get("row")
        if type(row) is not int or row not in pool:
            raise EnemyTypeError(
                f"{path}: {key}.row = {row!r} is not one of the {len(pool)} rows "
                "the base game never names"
            )
        if row in claimed:
            raise EnemyTypeError(
                f"{path}: {key} and {claimed[row]} both claim row {row}"
            )
        claimed[row] = key
        donor = body.get("donor")
        if type(donor) is not int or donor not in family:
            raise EnemyTypeError(
                f"{path}: {key}.donor = {donor!r} is not one of the "
                f"{len(family)} types whose defeat the base game runs normally"
            )
        raw = _require_raw(body, key, path)
        if len(raw) != size:
            raise EnemyTypeError(
                f"{path}: {key}.raw is {len(raw)} bytes; a type record is {size}"
            )
        base = _record_bytes(profile, image, donor)
        if raw != base:
            differing = ", ".join(
                str(index) for index in range(size) if raw[index] != base[index]
            )
            raise EnemyTypeError(
                f"{path}: {key}.raw does not match this ROM at row {donor} "
                f"(byte(s) {differing}); the type was claimed against another image"
            )
        unknown = set(body) - {"row", "donor", "raw"} - set(STAT_FIELDS)
        if unknown:
            raise EnemyTypeError(
                f"{path}: {key} carries {', '.join(sorted(unknown))}, which a type "
                f"does not name; it holds {', '.join(STAT_FIELDS)}"
            )
        edits = {
            name: _require_value(name, body[name], key, path)
            for name in STAT_FIELDS
            if name in body
        }
        entries[key] = EnemyType(row, donor, raw, edits)
    return Types(entries)


def write_types(project_dir: str | Path, types: Types) -> Path:
    path = Path(project_dir) / TYPES_FILE
    if not types.entries:
        path.unlink(missing_ok=True)
        return path
    body: dict = {}
    for key, entry in sorted(types.entries.items()):
        record = {"row": entry.row, "donor": entry.donor, "raw": entry.raw.hex()}
        record.update({name: entry.edits[name] for name in STAT_FIELDS
                       if name in entry.edits})
        body[key] = record
    return replace_document(path, dump_toml({"type": body}))


def claim(types: Types, name: str, donor: int, profile, image: bytes | bytearray) -> Types:
    """The types with ``name`` claimed from donor row ``donor``, lowest row first."""
    key = type_key(name)
    if key in types.entries:
        return types
    family = donor_family(profile, image)
    if donor not in family:
        raise EnemyTypeError(
            f"row {donor} is not one of the {len(family)} types whose defeat the "
            "base game runs normally, so it is not a donor"
        )
    pool = spare_rows(profile)
    taken = types.rows()
    free = [row for row in pool if row not in taken]
    if not free:
        raise EnemyTypeError(
            f"All {len(pool)} rows the base game never names are taken."
        )
    return Types({**types.entries,
                  key: EnemyType(free[0], donor, _record_bytes(profile, image, donor))})


def duplicated(types: Types, source: str, name: str, profile) -> Types:
    """The types with a copy of ``source`` under ``name``, on a row of its own."""
    key = type_key(name)
    if key in types.entries:
        raise EnemyTypeError(f"An enemy type named {name!r} already exists.")
    entry = types.entries.get(type_key(source))
    if entry is None:
        raise EnemyTypeError(f"There is no enemy type named {source!r}.")
    pool = spare_rows(profile)
    taken = types.rows()
    free = [row for row in pool if row not in taken]
    if not free:
        raise EnemyTypeError(
            f"All {len(pool)} rows the base game never names are taken."
        )
    return Types({**types.entries,
                  key: EnemyType(free[0], entry.donor, entry.raw, entry.edits)})


def renamed(types: Types, old: str, new: str) -> Types:
    """The same type under another name; its row and its bytes do not move."""
    old_key = type_key(old)
    if old_key not in types.entries:
        raise EnemyTypeError(f"There is no enemy type named {old!r}.")
    new_key = type_key(new)
    if new_key == old_key:
        return types
    if new_key in types.entries:
        raise EnemyTypeError(f"An enemy type named {new!r} already exists.")
    return Types({(new_key if key == old_key else key): entry
                  for key, entry in types.entries.items()})


def references(project_dir: str | Path, key: str) -> tuple[str, ...]:
    """Project documents, other than the type file, that name ``key``.

    A name is what every other document stores, so a text search is the whole
    question and no document schema has to be known here.
    """
    root = Path(project_dir)
    own = root / TYPES_FILE
    found: list[str] = []
    for candidate in sorted(root.rglob("*.toml")):
        if candidate == own:
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        if key in text:
            found.append(candidate.relative_to(root).as_posix())
    return tuple(found)


def rename(project_dir: str | Path, types: Types, old: str, new: str) -> Types:
    """Rename a type and every project document that names it, in one edit."""
    old_key = type_key(old)
    renamed_types = renamed(types, old, new)
    if renamed_types is types:
        return types
    new_key = f"enemy:{new}"
    for relative in references(project_dir, old_key):
        path = Path(project_dir) / relative
        text = path.read_text(encoding="utf-8")
        replace_document(
            path, re.sub(re.escape(old_key) + r"(?![a-z0-9_-])", new_key, text)
        )
    return renamed_types


def deleted(project_dir: str | Path, types: Types, name: str) -> Types:
    """The types without ``name``; refused while a project document names it."""
    key = type_key(name)
    if key not in types.entries:
        raise EnemyTypeError(f"There is no enemy type named {name!r}.")
    users = references(project_dir, key)
    if users:
        raise EnemyTypeError(
            f"{key} is named by {', '.join(users)}; remove that reference before "
            "deleting the type"
        )
    return Types({other: entry for other, entry in types.entries.items()
                  if other != key})


def edited(types: Types, name: str, field_name: str, value: int) -> Types:
    """The types with one record field set, or returned to the donor's value."""
    key = type_key(name)
    entry = types.entries.get(key)
    if entry is None:
        raise EnemyTypeError(f"There is no enemy type named {name!r}.")
    if field_name not in STAT_FIELDS:
        raise EnemyTypeError(
            f"{field_name!r} is not an editable enemy type field; editable: "
            f"{', '.join(STAT_FIELDS)}"
        )
    value = _require_value(field_name, value, key, TYPES_FILE.as_posix())
    offset, width = STAT_FIELDS[field_name]
    donor_value = int.from_bytes(entry.raw[offset : offset + width], "little")
    edits = {other: number for other, number in entry.edits.items()}
    if value == donor_value:
        edits.pop(field_name, None)
    else:
        edits[field_name] = value
    return Types({**types.entries, key: EnemyType(entry.row, entry.donor, entry.raw, edits)})


def changes(types: Types, profile, image: bytes | bytearray) -> list[ByteChange]:
    """One attributed change per claimed row, and nothing else in the table."""
    table = profile.enemy_stats
    if not types.entries:
        return []
    if table is None:
        raise EnemyTypeError(f"profile {profile.id!r} declares no enemy type table")
    start = _table_offset(profile, image)
    result: list[ByteChange] = []
    for key, entry in sorted(types.entries.items()):
        offset = start + entry.row * table.record_size
        old = bytes(image[offset : offset + table.record_size])
        new = entry.record()
        if new == old:
            continue
        result.append(
            ByteChange(
                offset=offset,
                old=old,
                new=new,
                owner=key,
                reason=f"enemy type {key} on row {entry.row}",
            )
        )
    return result
