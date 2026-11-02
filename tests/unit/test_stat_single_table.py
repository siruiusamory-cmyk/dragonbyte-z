"""The semantic stat layer against a profile that declares one stat table.

A profile may declare an enemy stat table and no character base-stat table. This
module loads such a profile through the public entry point and pins what the
layer then does: the enemy table is served, the character side is absent rather
than invented, an enemy record is named by its own format's key, and an HP edit
reaches the four bytes at `+0x04` and nothing else.

Synthetic images throughout, per ``docs/ROM_SAFETY.md``: no ROM bytes are
committed, and the profile whose shape is being loaded is the packaged one, read
from the package rather than restated here. The ROM-gated proof that the real
canonical image loads lives in
``tests/integration/test_stat_write_rom.py``.
"""

from __future__ import annotations

from dataclasses import replace
from importlib import resources
from pathlib import Path

import pytest

from tools.webfoot.formats import stat_tables as st
from tools.webfoot.gba_header import GbaHeader
from tools.webfoot.hashing import RomHashes
from tools.webfoot.profile import (
    ProfileMatch,
    RomProfile,
    RomProfileCatalog,
    VerificationStatus,
)
from tools.webfoot.rom import RomIdentification
from tools.webfoot.stats import (
    StatProfileError,
    UnknownFieldError,
    UnknownRecordError,
    stat_tables_from_image,
)


def _catalog() -> RomProfileCatalog:
    return RomProfileCatalog.loads(
        resources.files("tools.webfoot.data")
        .joinpath("roms.yaml")
        .read_text(encoding="utf-8"),
        source="packaged tools.webfoot.data/roms.yaml",
    )


def _single_table_profile() -> RomProfile:
    """The packaged profile that declares an enemy table and no character one.

    Selected by declared shape, not by name: which profiles exist is catalogue
    data, and a layer that has to be told which game it is looking at has
    reintroduced the coupling TOOLKIT-005 removed.
    """
    return next(
        item
        for item in _catalog().profiles
        if item.enemy_stats is not None and item.character_base_stats is None
    )


def _two_table_profile() -> RomProfile:
    return next(
        item
        for item in _catalog().profiles
        if item.enemy_stats is not None and item.character_base_stats is not None
    )


def _identification(profile: RomProfile) -> RomIdentification:
    """A stand-in identity for `profile`: this module exercises decode, not identify."""
    return RomIdentification(
        path=Path("stand-in.gba"),
        size=profile.size,
        hashes=RomHashes(crc32="", md5="", sha1="", sha256=profile.sha256),
        header=GbaHeader.from_bytes(bytes(0xC0)),
        profile_match=ProfileMatch(
            status=VerificationStatus.VERIFIED,
            profile=profile,
            reason="stand-in identity: the image is synthetic and unhashed",
        ),
    )


def _single_table_records(count: int) -> list[bytes]:
    """Records whose non-HP words are identical across the table.

    That is the measured shape of this format and the reason its identity cannot
    be a record field: every record here carries the same word at `+0x08`, so a
    scheme keyed on record content would collapse the table into one entry.
    """
    records = []
    for index in range(count):
        record = bytearray(b"\x5a" * st.LOG2_ENEMY_RECORD_SIZE)
        hp = 130 if index == 41 else 100 + index
        record[4:8] = hp.to_bytes(4, "little")
        records.append(bytes(record))
    return records


def _two_table_enemy_records(count: int) -> list[bytes]:
    """Buu-shaped enemy records, each with its own type id so identity holds."""
    records = []
    for index in range(count):
        record = bytearray(st.ENEMY_RECORD_SIZE)
        record[4:7] = (100 + index).to_bytes(3, "little")
        record[8:10] = index.to_bytes(2, "little")
        record[12] = 60
        records.append(bytes(record))
    return records


def _image_with(profile: RomProfile, records: list[bytes]) -> bytes:
    table = profile.enemy_stats
    data = bytearray(profile.size)
    base = table.address.to_file_offset(profile.size)
    for index, record in enumerate(records):
        start = base + index * table.record_size
        data[start : start + table.record_size] = record
    return bytes(data)


@pytest.fixture(scope="module")
def single_table():
    profile = _single_table_profile()
    data = _image_with(profile, _single_table_records(profile.enemy_stats.count))
    return profile, data, stat_tables_from_image(_identification(profile), profile, data)


def test_a_profile_declaring_only_an_enemy_table_loads(single_table) -> None:
    profile, _, tables = single_table
    assert tables.profile.id == profile.id
    assert len(list(tables.enemies())) == profile.enemy_stats.count
    assert list(tables.characters()) == []


def test_a_profile_declaring_no_stat_table_is_refused_by_name() -> None:
    """The refusal survives: an undeclared profile is refused, not served empty."""
    profile = replace(_single_table_profile(), enemy_stats=None)
    with pytest.raises(StatProfileError, match="does not declare enemy_stats"):
        stat_tables_from_image(_identification(profile), profile, bytes(profile.size))


def test_a_supplied_profile_cannot_drop_a_table_the_contract_declares() -> None:
    """The packaged contract decides which tables a profile has."""
    profile = _two_table_profile()
    supplied = replace(profile, character_base_stats=None)
    data = _image_with(profile, _two_table_enemy_records(profile.enemy_stats.count))
    with pytest.raises(StatProfileError, match="conflicts with the packaged contract"):
        stat_tables_from_image(_identification(profile), supplied, data)


def test_a_supplied_profile_cannot_add_a_table_the_contract_lacks() -> None:
    """The comparison is symmetric: an invented table is refused, not decoded."""
    profile = _single_table_profile()
    supplied = replace(
        profile, character_base_stats=_two_table_profile().character_base_stats
    )
    data = _image_with(profile, _single_table_records(profile.enemy_stats.count))
    with pytest.raises(StatProfileError, match="conflicts with the packaged contract"):
        stat_tables_from_image(_identification(profile), supplied, data)


def test_the_character_side_is_absent_rather_than_invented(single_table) -> None:
    _, _, tables = single_table
    character = st.StatIdentity(kind="character", key=0)
    assert list(tables.characters()) == []
    with pytest.raises(UnknownRecordError, match="no character record"):
        tables.character(character)
    with pytest.raises(UnknownRecordError, match="no character record"):
        tables.set_character_field(character, "hp", 1)
    assert {change.owner.split(":")[0] for change in tables.changes()} == {"enemy"}


def test_enemy_identity_is_the_table_index_and_survives_a_reload(single_table) -> None:
    """No record field is unique here, so the index is the only stable handle."""
    profile, data, tables = single_table
    identities = [entry.identity for entry in tables.enemies()]
    assert identities == [
        st.StatIdentity(kind="enemy", key=index)
        for index in range(profile.enemy_stats.count)
    ]
    assert len({entry.original_bytes[0x08:0x0C] for entry in tables.enemies()}) == 1

    reloaded = stat_tables_from_image(
        _identification(profile), profile, data
    )
    assert [entry.identity for entry in reloaded.enemies()] == identities

    target = identities[41]
    assert tables.enemy(target).record.hp == 130
    tables.set_enemy_field(target, "hp", 999)
    assert tables.enemy(target).identity == target
    assert tables.enemy(target).record.hp == 999


def test_an_enemy_hp_edit_rewrites_only_that_record_hp_span(single_table) -> None:
    profile, _, tables = single_table
    identity = st.StatIdentity(kind="enemy", key=41)
    tables.set_enemy_field(identity, "hp", 999)

    changes = tables.plan().effective_changes
    assert len(changes) == 1
    change = changes[0]
    assert change.owner == "enemy:41"
    assert change.offset == (
        profile.enemy_stats.address.to_file_offset(profile.size) + 41 * 0x18
    )
    differing = [
        index for index in range(len(change.old)) if change.old[index] != change.new[index]
    ]
    assert differing, "the edit changed no byte, so the fixture proves nothing"
    assert all(st.LOG2_ENEMY_HP_OFFSET <= index < st.LOG2_ENEMY_HP_OFFSET + 4
               for index in differing)
    assert int.from_bytes(change.new[4:8], "little") == 999
    assert change.new[:4] == change.old[:4]
    assert change.new[8:] == change.old[8:]


def test_a_field_this_record_does_not_decode_is_refused_by_name(single_table) -> None:
    _, _, tables = single_table
    identity = st.StatIdentity(kind="enemy", key=41)
    with pytest.raises(UnknownFieldError, match="editable: hp"):
        tables.set_enemy_field(identity, "exp", 5)


def test_a_profile_declaring_both_tables_still_serves_its_characters() -> None:
    """The two-table path is unchanged: nine characters, named from the roster."""
    profile = _two_table_profile()
    data = bytearray(
        _image_with(profile, _two_table_enemy_records(profile.enemy_stats.count))
    )
    character_base = profile.character_base_stats.address.to_file_offset(profile.size)
    for index in range(profile.character_base_stats.count):
        start = character_base + index * profile.character_base_stats.record_size
        data[start] = 60
    tables = stat_tables_from_image(
        _identification(profile), profile, bytes(data)
    )
    characters = list(tables.characters())
    assert len(characters) == len(st.BASE_STAT_NAMES)
    assert characters[0].alias == st.BASE_STAT_NAMES[0]
    assert len(list(tables.enemies())) == profile.enemy_stats.count
