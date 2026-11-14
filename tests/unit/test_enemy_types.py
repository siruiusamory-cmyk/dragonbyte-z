"""Project enemy types: claim, rename, duplicate, delete, statistics, refusals."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.webfoot import enemy_types
from tools.webfoot.formats import stat_tables as st
from tools.webfoot.project.atomic import replace_document
from tools.webfoot.project.format import dump_toml

PROFILE = "buus_fury_usa_rev0_01c1707f"
TABLE_OFFSET = 0x4000
DESCRIPTOR_OFFSET = 0x8000
DESCRIPTOR_STRIDE = 16
IMAGE_SIZE = 0x9000
FAMILY = 0x08018951
OTHER_CALLBACKS = (0x08018937, 0x080333C5, 0x08032D45)


class _Address:
    def to_file_offset(self, size: int) -> int:
        return TABLE_OFFSET


class _Table:
    address = _Address()
    count = 150
    record_size = st.ENEMY_RECORD_SIZE


class _Profile:
    id = PROFILE
    enemy_stats = _Table()


def _image(callbacks=None, hp=None) -> bytes:
    """A synthetic type table: one row per record, a descriptor each."""
    data = bytearray(st.GBA_ROM_BASE + IMAGE_SIZE)
    callbacks = callbacks or {}
    hp = hp or {}
    for row in range(_Table.count):
        offset = TABLE_OFFSET + row * _Table.record_size
        blob = bytearray(_Table.record_size)
        blob[0x00:0x03] = (row * 7).to_bytes(3, "little")
        blob[0x04:0x07] = hp.get(row, 100).to_bytes(3, "little")
        blob[0x08:0x0A] = (900 + row).to_bytes(2, "little")
        blob[0x0C] = 10
        blob[0x0D] = 11
        blob[0x0E] = 12
        blob[0x0F] = 13
        descriptor = DESCRIPTOR_OFFSET + row * DESCRIPTOR_STRIDE
        blob[0x14:0x18] = (st.GBA_ROM_BASE + descriptor).to_bytes(4, "little")
        data[offset:offset + _Table.record_size] = blob
        word = st.GBA_ROM_BASE + descriptor
        data[descriptor:descriptor + 4] = (0).to_bytes(4, "little")
        data[descriptor + 4:descriptor + 8] = (0).to_bytes(4, "little")
        data[descriptor + 8:descriptor + 12] = callbacks.get(
            row, FAMILY).to_bytes(4, "little")
    return bytes(data)


@pytest.fixture
def image() -> bytes:
    return _image()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return tmp_path


def _claim(project: Path, image: bytes, name: str, donor: int, **kwargs):
    types = kwargs.get("types") or enemy_types.Types()
    types = enemy_types.claim(types, name, donor, _Profile(), image)
    enemy_types.write_types(project, types)
    return enemy_types.read_types(project, _Profile(), image)


def test_enemy_claim_takes_lowest_free_row(project: Path, image: bytes) -> None:
    types = _claim(project, image, "wolf", 1)
    assert types.entries["enemy:wolf"].row == 30
    types = _claim(project, image, "ape", 2, types=types)
    assert types.entries["enemy:ape"].row == 31

    claimed = {entry.row for entry in types.entries.values()}
    pool = set(enemy_types.spare_rows(_Profile()))
    assert claimed == {30, 31} and claimed <= pool


def test_enemy_rename_keeps_row_and_bytes(project: Path, image: bytes) -> None:
    types = _claim(project, image, "wolf", 1)
    before = types.entries["enemy:wolf"]
    types = enemy_types.rename(project, types, "wolf", "cave-wolf")
    enemy_types.write_types(project, types)
    after = enemy_types.read_types(project, _Profile(), image).entries

    assert set(after) == {"enemy:cave-wolf"}
    assert after["enemy:cave-wolf"].row == before.row
    assert after["enemy:cave-wolf"].raw == before.raw
    assert after["enemy:cave-wolf"].donor == before.donor


def test_enemy_rename_rewrites_references(project: Path, image: bytes) -> None:
    types = _claim(project, image, "wolf", 1)
    other = project / "maps" / "placements.toml"
    other.parent.mkdir(parents=True)
    other.write_text(
        dump_toml({"placement": {"map:0001/placement:0000": {
            "type": "enemy:wolf", "sibling": "enemy:wolf-king"}}}),
        encoding="utf-8")

    types = enemy_types.rename(project, types, "wolf", "cave-wolf")
    text = other.read_text(encoding="utf-8")
    assert "enemy:cave-wolf" in text
    assert "enemy:wolf\"" not in text
    assert "enemy:wolf-king" in text
    assert types.entries["enemy:cave-wolf"].row == 30


def test_enemy_reorder_changes_nothing(project: Path, image: bytes) -> None:
    types = _claim(project, image, "wolf", 1)
    types = _claim(project, image, "ape", 2, types=types)
    path = project / enemy_types.TYPES_FILE
    canonical = path.read_text(encoding="utf-8")
    replace_document(path, "\n\n".join(reversed(canonical.split("\n\n"))))

    assert enemy_types.read_types(project, _Profile(), image) == types
    enemy_types.write_types(project, types)
    assert path.read_text(encoding="utf-8") == canonical


def test_enemy_duplicate_takes_new_row(project: Path, image: bytes) -> None:
    types = _claim(project, image, "wolf", 1)
    source = types.entries["enemy:wolf"]
    types = enemy_types.duplicated(types, "wolf", "wolf-copy", _Profile())
    copy_entry = types.entries["enemy:wolf-copy"]

    assert types.entries["enemy:wolf"].row == source.row
    assert copy_entry.row == 31
    assert copy_entry.raw == source.raw
    assert copy_entry.donor == source.donor
    assert copy_entry.row != source.row


def test_enemy_delete_refused_while_referenced(project: Path, image: bytes) -> None:
    types = _claim(project, image, "wolf", 1)
    other = project / "maps" / "placements.toml"
    other.parent.mkdir(parents=True)
    other.write_text(dump_toml({"placement": {"map:0001/placement:0000": {
        "type": "enemy:wolf"}}}), encoding="utf-8")

    with pytest.raises(enemy_types.EnemyTypeError) as refused:
        enemy_types.deleted(project, types, "wolf")
    assert "maps/placements.toml" in str(refused.value)

    other.unlink()
    types = enemy_types.deleted(project, types, "wolf")
    assert types.entries == {}
    types = _claim(project, image, "ape", 2, types=types)
    assert types.entries["enemy:ape"].row == 30


def test_enemy_two_types_one_row_refused(project: Path, image: bytes) -> None:
    path = project / enemy_types.TYPES_FILE
    raw = enemy_types._record_bytes(_Profile(), image, 1).hex()
    path.parent.mkdir(parents=True)
    path.write_text(dump_toml({"type": {
        "enemy:wolf": {"row": 30, "donor": 1, "raw": raw},
        "enemy:ape": {"row": 30, "donor": 1, "raw": raw},
    }}), encoding="utf-8")

    with pytest.raises(enemy_types.EnemyTypeError) as refused:
        enemy_types.read_types(project, _Profile(), image)
    message = str(refused.value)
    assert "enemy:wolf" in message and "enemy:ape" in message and "30" in message


def test_enemy_claimed_bytes_pinned_to_base(project: Path, image: bytes) -> None:
    types = _claim(project, image, "wolf", 1)
    path = project / enemy_types.TYPES_FILE
    raw = bytearray(types.entries["enemy:wolf"].raw)
    raw[5] ^= 0xFF
    path.write_text(dump_toml({"type": {"enemy:wolf": {
        "row": 30, "donor": 1, "raw": bytes(raw).hex(),
    }}}), encoding="utf-8")

    with pytest.raises(enemy_types.EnemyTypeError) as refused:
        enemy_types.read_types(project, _Profile(), image)
    message = str(refused.value)
    assert "does not match this ROM" in message
    assert "row 1" in message and "byte(s) 5" in message


def test_enemy_pool_exhausted_refused(project: Path, image: bytes) -> None:
    types = enemy_types.Types()
    for index, donor in enumerate(range(1, 17)):
        types = enemy_types.claim(types, f"type-{index}", donor, _Profile(), image)
    with pytest.raises(enemy_types.EnemyTypeError) as refused:
        enemy_types.claim(types, "type-17", 1, _Profile(), image)
    assert "All 16 rows the base game never names are taken." == str(refused.value)


def test_enemy_types_toml_has_no_address(project: Path, image: bytes) -> None:
    types = _claim(project, image, "wolf", 1)
    enemy_types.edited(types, "wolf", "hp", 999)
    enemy_types.write_types(project, types)
    text = (project / enemy_types.TYPES_FILE).read_text(encoding="utf-8")

    assert "row = 30" in text
    assert "0x" not in text
    assert "711274" not in text.lower()
    assert "offset" not in text


def test_enemy_donor_family_only(project: Path, image: bytes) -> None:
    others = {24: OTHER_CALLBACKS[0], 58: OTHER_CALLBACKS[1],
              60: OTHER_CALLBACKS[2], 61: OTHER_CALLBACKS[2],
              127: OTHER_CALLBACKS[1], 140: OTHER_CALLBACKS[1]}
    image = _image(callbacks=others, hp={3: 0})

    for donor in others:
        with pytest.raises(enemy_types.EnemyTypeError) as refused:
            enemy_types.claim(enemy_types.Types(), "wolf", donor, _Profile(), image)
        assert "is not one of the" in str(refused.value)

    with pytest.raises(enemy_types.EnemyTypeError) as refused:
        enemy_types.claim(enemy_types.Types(), "wolf", 3, _Profile(), image)
    assert "is not one of the" in str(refused.value)
    types = enemy_types.claim(enemy_types.Types(), "wolf", 1, _Profile(), image)
    assert types.entries["enemy:wolf"].row == 30


def test_enemy_claim_unknown_donor_refused(project: Path, image: bytes) -> None:
    with pytest.raises(enemy_types.EnemyTypeError) as refused:
        enemy_types.claim(enemy_types.Types(), "wolf", 900, _Profile(), image)
    assert "is not one of the" in str(refused.value)


def test_enemy_statistics_range_refused(project: Path, image: bytes) -> None:
    types = _claim(project, image, "wolf", 1)

    with pytest.raises(enemy_types.EnemyTypeError) as refused:
        enemy_types.edited(types, "wolf", "hp", 1 << 24)
    assert "does not fit the record's 3-byte field (0..16777215)" in str(refused.value)

    with pytest.raises(enemy_types.EnemyTypeError) as refused:
        enemy_types.edited(types, "wolf", "strength", 256)
    assert "0..255" in str(refused.value)

    with pytest.raises(enemy_types.EnemyTypeError) as refused:
        enemy_types.edited(types, "wolf", "level", 2)
    assert "not an editable enemy type field" in str(refused.value)

    edited = enemy_types.edited(types, "wolf", "hp", 500)
    assert edited.entries["enemy:wolf"].edits == {"hp": 500}
    assert edited.entries["enemy:wolf"].record()[0x04:0x07] == (500).to_bytes(3, "little")

    donor_value = int.from_bytes(types.entries["enemy:wolf"].raw[4:7], "little")
    cleared = enemy_types.edited(edited, "wolf", "hp", donor_value)
    assert cleared.entries["enemy:wolf"].edits == {}


def test_enemy_retail_row_not_writable(project: Path, image: bytes) -> None:
    path = project / enemy_types.TYPES_FILE
    raw = enemy_types._record_bytes(_Profile(), image, 1).hex()
    path.parent.mkdir(parents=True)
    path.write_text(dump_toml({"type": {"enemy:wolf": {
        "row": 1, "donor": 1, "raw": raw}}}), encoding="utf-8")

    with pytest.raises(enemy_types.EnemyTypeError) as refused:
        enemy_types.read_types(project, _Profile(), image)
    assert "is not one of the 16 rows the base game never names" in str(refused.value)

    types = _claim(project, image, "ape", 2)
    written = {change.offset for change in
               enemy_types.changes(types, _Profile(), image)}
    assert written == {TABLE_OFFSET + 30 * _Table.record_size}


def test_enemy_type_table_extent_is_the_profiles(project: Path, image: bytes) -> None:
    assert _Profile().enemy_stats.count == 150
    assert len(enemy_types.donor_family(_Profile(), image)) == 150
