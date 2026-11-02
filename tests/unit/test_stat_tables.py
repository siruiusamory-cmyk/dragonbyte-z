"""Portable tests for the static stat-table parsers (DATA-001).

These use SYNTHETIC fixtures only, per ``docs/ROM_SAFETY.md``: no ROM bytes are
committed and the suite runs without the proprietary image. The ROM-gated
cross-checks against real data live in `tests/integration/test_stat_tables_rom.py`.
"""

from __future__ import annotations

from dataclasses import replace
from importlib import resources

import pytest

from tools.webfoot.formats import stat_tables as st
from tools.webfoot.profile import RomProfileCatalog


def _enemy_bytes(exp: int, hp: int, type_id: int, level: int,
                 strength: int, power: int, endurance: int) -> bytes:
    """Build one synthetic enemy record in the documented layout."""
    blob = bytearray(st.ENEMY_RECORD_SIZE)
    blob[0:3] = exp.to_bytes(3, "little")
    blob[3] = 0
    blob[4:7] = hp.to_bytes(3, "little")
    blob[7] = 0
    blob[8:10] = type_id.to_bytes(2, "little")
    blob[12] = level
    blob[13] = strength
    blob[14] = power
    blob[15] = endurance
    return bytes(blob)


def _base_bytes(level: int, hp: int, ep: int, strength: int, power: int,
                endurance: int, speed: int, person: int, techs: int) -> bytes:
    blob = bytearray(st.BASE_STAT_RECORD_SIZE)
    blob[0] = level
    blob[1] = 0
    blob[2:4] = hp.to_bytes(2, "little")
    blob[4:6] = ep.to_bytes(2, "little")
    blob[6] = strength
    blob[7] = power
    blob[8] = endurance
    blob[9] = speed
    blob[10] = person
    blob[11] = techs
    return bytes(blob)


def test_enemy_record_round_trips_every_documented_field() -> None:
    data = bytearray(st.ENEMY_TABLE_START + st.ENEMY_RECORD_SIZE)
    data[st.ENEMY_TABLE_START:] = _enemy_bytes(
        exp=225, hp=175, type_id=434, level=60,
        strength=10, power=0, endurance=20,
    )
    rec = st.decode_enemy_record(bytes(data), st.ENEMY_TABLE_START)
    assert rec.exp == 225
    assert rec.hp == 175
    assert rec.type_id == 434
    assert rec.level == 60
    assert rec.strength == 10
    assert rec.power == 0
    assert rec.endurance == 20


def test_enemy_24bit_fields_decode_beyond_16_bits() -> None:
    """Kid Buu's real values exceed 16 bits; the u24 decode must not truncate."""
    data = bytearray(st.ENEMY_TABLE_START + st.ENEMY_RECORD_SIZE)
    data[st.ENEMY_TABLE_START:] = _enemy_bytes(
        exp=96175, hp=125000, type_id=285, level=150,
        strength=66, power=110, endurance=100,
    )
    rec = st.decode_enemy_record(bytes(data), st.ENEMY_TABLE_START)
    assert rec.exp == 96175
    assert rec.hp == 125000


def test_gba_address_is_file_offset_plus_cartridge_base() -> None:
    data = bytearray(st.ENEMY_TABLE_START + st.ENEMY_RECORD_SIZE)
    data[st.ENEMY_TABLE_START:] = _enemy_bytes(1, 1, 1, 1, 1, 1, 1)
    rec = st.decode_enemy_record(bytes(data), st.ENEMY_TABLE_START)
    assert rec.gba_address == rec.offset + 0x08000000


def test_base_stat_record_round_trips_every_documented_field() -> None:
    data = bytearray(st.BASE_STAT_TABLE_START + st.BASE_STAT_RECORD_SIZE)
    data[st.BASE_STAT_TABLE_START:] = _base_bytes(
        level=60, hp=135, ep=90, strength=27, power=27,
        endurance=26, speed=50, person=0x02, techs=4,
    )
    rec = st.decode_base_stat_record(bytes(data), st.BASE_STAT_TABLE_START)
    assert rec.level == 60
    assert rec.hp == 135
    assert rec.ep == 90
    assert rec.strength == 27
    assert rec.power == 27
    assert rec.endurance == 26
    assert rec.speed == 50
    assert rec.person == 0x02
    assert rec.technique_count == 4


def test_structural_check_rejects_nonzero_pad_bytes() -> None:
    """Both pad bytes are what make a record recognisable; either one kills it."""
    good = bytearray(_enemy_bytes(225, 175, 434, 60, 10, 0, 20))
    assert st.looks_like_enemy_record(bytes(good), 0)

    pad_a = bytearray(good)
    pad_a[3] = 1
    assert not st.looks_like_enemy_record(bytes(pad_a), 0)

    pad_b = bytearray(good)
    pad_b[7] = 1
    assert not st.looks_like_enemy_record(bytes(pad_b), 0)


def test_structural_check_rejects_implausible_level() -> None:
    zero = _enemy_bytes(225, 175, 434, 0, 10, 0, 20)
    assert not st.looks_like_enemy_record(zero, 0)
    huge = _enemy_bytes(225, 175, 434, 201, 10, 0, 20)
    assert not st.looks_like_enemy_record(huge, 0)


def test_structural_check_rejects_truncated_input() -> None:
    assert not st.looks_like_enemy_record(b"\x00" * 4, 0)


def test_short_records_raise_rather_than_decode_garbage() -> None:
    with pytest.raises(ValueError):
        st.decode_enemy_record(b"\x00" * 4, 0)
    with pytest.raises(ValueError):
        st.decode_base_stat_record(b"\x00" * 4, 0)


def test_declared_extent_matches_declared_count() -> None:
    """The three published constants must stay mutually consistent."""
    span = st.ENEMY_TABLE_LAST - st.ENEMY_TABLE_START
    assert span % st.ENEMY_RECORD_SIZE == 0
    assert span // st.ENEMY_RECORD_SIZE + 1 == st.ENEMY_RECORD_COUNT


def test_base_stat_names_match_declared_count() -> None:
    assert len(st.BASE_STAT_NAMES) == st.BASE_STAT_RECORD_COUNT


LOG2_RECORD_41 = bytes.fromhex("1400000082000000150000000302038080000000c4f36f08")

LOG2_RECORD_41_OFFSET = 0x006D5A84


def _log2_image(record: bytes, offset: int = LOG2_RECORD_41_OFFSET) -> bytes:
    """Place one LOG2 record in an otherwise empty image at its real offset.

    ``LOG2_RECORD_41`` reproduces the shape O2b measured at index 41 of the
    verified table, including its non-HP words, so a preservation bug cannot
    hide behind a zero-filled fixture: +0x00 is HP-shaped but has no reader,
    +0x08 is unknown, +0x0C..0x0F are packed display bytes, +0x10 is the
    three-valued enum and +0x14 is a descriptor pointer. HP 130 is the value
    the runtime sweep found live on entity 0x0203BC28, which cached this
    record's address.
    """
    data = bytearray(offset + st.LOG2_ENEMY_RECORD_SIZE)
    data[offset : offset + st.LOG2_ENEMY_RECORD_SIZE] = record
    return bytes(data)


def _log2_catalog() -> RomProfileCatalog:
    return RomProfileCatalog.loads(
        resources.files("tools.webfoot.data")
        .joinpath("roms.yaml")
        .read_text(encoding="utf-8"),
        source="packaged tools.webfoot.data/roms.yaml",
    )


def test_log2_record_41_decodes_the_measured_hp() -> None:
    rec = st.decode_log2_enemy_record(
        _log2_image(LOG2_RECORD_41), LOG2_RECORD_41_OFFSET
    )
    assert rec.hp == 130
    assert rec.offset == LOG2_RECORD_41_OFFSET
    assert rec.gba_address == 0x086D5A84


def test_log2_round_trip_is_byte_identical() -> None:
    rec = st.decode_log2_enemy_record(
        _log2_image(LOG2_RECORD_41), LOG2_RECORD_41_OFFSET
    )
    assert st.encode_log2_enemy_record(rec, LOG2_RECORD_41) == LOG2_RECORD_41


def test_log2_hp_edit_preserves_every_other_byte() -> None:
    """Owner decision 2's acceptance test: HP changes, nothing else moves."""
    rec = st.decode_log2_enemy_record(
        _log2_image(LOG2_RECORD_41), LOG2_RECORD_41_OFFSET
    )
    edited = st.encode_log2_enemy_record(replace(rec, hp=999), LOG2_RECORD_41)

    hp = st.LOG2_ENEMY_HP_OFFSET
    assert int.from_bytes(edited[hp : hp + 4], "little") == 999
    assert edited[:hp] == LOG2_RECORD_41[:hp]
    assert edited[hp + 4 :] == LOG2_RECORD_41[hp + 4 :]
    differing = [
        i for i in range(st.LOG2_ENEMY_RECORD_SIZE) if edited[i] != LOG2_RECORD_41[i]
    ]
    assert all(hp <= i < hp + 4 for i in differing)
    assert st.decode_log2_enemy_record(edited, 0).hp == 999


def test_log2_hp_spans_the_full_u32_and_refuses_more() -> None:
    rec = st.decode_log2_enemy_record(
        _log2_image(LOG2_RECORD_41), LOG2_RECORD_41_OFFSET
    )
    for value in (0, 0xFFFFFFFF):
        encoded = st.encode_log2_enemy_record(replace(rec, hp=value), LOG2_RECORD_41)
        assert st.decode_log2_enemy_record(encoded, 0).hp == value
    with pytest.raises(st.StatEncodeError):
        st.encode_log2_enemy_record(replace(rec, hp=0x1_0000_0000), LOG2_RECORD_41)
    with pytest.raises(st.StatEncodeError):
        st.encode_log2_enemy_record(replace(rec, hp=-1), LOG2_RECORD_41)


def test_log2_encode_refuses_a_backing_of_the_wrong_size() -> None:
    rec = st.decode_log2_enemy_record(
        _log2_image(LOG2_RECORD_41), LOG2_RECORD_41_OFFSET
    )
    with pytest.raises(st.StatEncodeError):
        st.encode_log2_enemy_record(rec, LOG2_RECORD_41[:-1])


def test_log2_decode_refuses_a_short_record() -> None:
    with pytest.raises(ValueError):
        st.decode_log2_enemy_record(LOG2_RECORD_41[:-1], 0)


def test_log2_predicate_accepts_a_log2_record_and_rejects_a_buu_one() -> None:
    assert st.looks_like_log2_enemy_record(LOG2_RECORD_41, 0)
    buu = _enemy_bytes(225, 175, 434, 60, 10, 0, 20)
    assert not st.looks_like_log2_enemy_record(buu, 0)


def test_the_buu_predicate_is_no_guard_against_log2_bytes() -> None:
    """Measured: Buu's test ACCEPTS LOG2 records, so it is not the boundary.

    Against the canonical image it accepts 109 of 109 records of the verified
    LOG2 table. A LOG2 record's u32 values at +0x00 and +0x04 are small enough
    to leave +0x03 and +0x07 zero, which satisfies both pad-byte gates by
    accident, and +0x0C lands in 1..200, which satisfies the level gate. It
    reads a 0x1C window over 0x18-stride data and never checks stride.

    This node pins that acceptance rather than asserting a rejection the code
    does not deliver, because the consequence is the safety argument: the
    selector keeps the two codecs apart, and the predicates do not.
    """
    in_table = bytearray(LOG2_RECORD_41 * 2)
    assert st.looks_like_enemy_record(bytes(in_table), 0)

    assert not st.looks_like_enemy_record(LOG2_RECORD_41, 0)


def test_the_selector_never_routes_a_log2_table_to_the_buu_codec() -> None:
    """The selector is the safety boundary, keyed on the declared record size.

    Routing LOG2 bytes through the Buu codec would decode at stride 0x1C with a
    3-byte HP and scatter writes across record boundaries, which is exactly what
    the predicates cannot prevent.
    """
    chosen = st.enemy_codec_for_record_size(st.LOG2_ENEMY_RECORD_SIZE)
    assert chosen is not st.BUUS_ENEMY_CODEC
    assert chosen.decode is st.decode_log2_enemy_record
    assert chosen.encode is st.encode_log2_enemy_record
    assert chosen.looks_like is st.looks_like_log2_enemy_record
    assert chosen.record_size == st.LOG2_ENEMY_RECORD_SIZE

    profile = next(
        item
        for item in _log2_catalog().profiles
        if item.id == "legacy_of_goku_ii_usa_rev0_204142e1"
    )
    from_profile = st.enemy_codec_for_record_size(profile.enemy_stats.record_size)
    assert from_profile is st.LOG2_ENEMY_CODEC


def test_the_predicates_hp_bound_is_declared_and_encode_is_not_bound_by_it() -> None:
    """The observed range guards recognition only; width is the encode bound.

    1..10,200 is what the 109 records measured, not a limit anything in the ROM
    was found to enforce, so an HP above it is unrecognisable as a record while
    still being a legal value to write.
    """
    assert st.LOG2_ENEMY_HP_OBSERVED_RANGE == (1, 10_200)

    rec = st.decode_log2_enemy_record(
        _log2_image(LOG2_RECORD_41), LOG2_RECORD_41_OFFSET
    )
    above = st.encode_log2_enemy_record(replace(rec, hp=10_201), LOG2_RECORD_41)
    assert st.decode_log2_enemy_record(above, 0).hp == 10_201
    assert not st.looks_like_log2_enemy_record(above, 0)

    at_top = st.encode_log2_enemy_record(replace(rec, hp=10_200), LOG2_RECORD_41)
    assert st.looks_like_log2_enemy_record(at_top, 0)


def test_log2_predicate_rejects_each_broken_invariant() -> None:
    hp = st.LOG2_ENEMY_HP_OFFSET

    zero_hp = bytearray(LOG2_RECORD_41)
    zero_hp[hp : hp + 4] = (0).to_bytes(4, "little")
    assert not st.looks_like_log2_enemy_record(bytes(zero_hp), 0)

    bad_enum = bytearray(LOG2_RECORD_41)
    bad_enum[0x10:0x14] = (65).to_bytes(4, "little")
    assert not st.looks_like_log2_enemy_record(bytes(bad_enum), 0)

    bad_pointer = bytearray(LOG2_RECORD_41)
    bad_pointer[0x14:0x18] = (0x030011A0).to_bytes(4, "little")
    assert not st.looks_like_log2_enemy_record(bytes(bad_pointer), 0)

    assert not st.looks_like_log2_enemy_record(b"\x00" * 4, 0)


def test_codec_is_selected_by_declared_record_size() -> None:
    assert (
        st.enemy_codec_for_record_size(st.LOG2_ENEMY_RECORD_SIZE)
        is st.LOG2_ENEMY_CODEC
    )
    assert st.enemy_codec_for_record_size(st.ENEMY_RECORD_SIZE) is st.BUUS_ENEMY_CODEC
    assert st.LOG2_ENEMY_CODEC.decode is st.decode_log2_enemy_record
    assert st.BUUS_ENEMY_CODEC.decode is st.decode_enemy_record


def test_an_unimplemented_record_size_raises_rather_than_falling_back() -> None:
    for size in (0x10, 0x1A, 0x1D, 0x20):
        with pytest.raises(st.UnknownEnemyCodecError):
            st.enemy_codec_for_record_size(size)


def test_selected_codec_decodes_through_its_own_layout() -> None:
    """The selector must route bytes, not merely return a label."""
    log2 = st.enemy_codec_for_record_size(st.LOG2_ENEMY_RECORD_SIZE)
    assert log2.decode(LOG2_RECORD_41, 0).hp == 130

    buu_bytes = _enemy_bytes(225, 175, 434, 60, 10, 0, 20)
    buu = st.enemy_codec_for_record_size(st.ENEMY_RECORD_SIZE)
    assert buu.decode(buu_bytes, 0).hp == 175


def test_log2_profile_declares_the_verified_extent() -> None:
    profile = next(
        item
        for item in _log2_catalog().profiles
        if item.id == "legacy_of_goku_ii_usa_rev0_204142e1"
    )
    table = profile.enemy_stats
    assert table is not None
    assert table.address.raw == 0x086D56AC
    assert table.count == 109
    assert table.record_size == st.LOG2_ENEMY_RECORD_SIZE
    assert table.address.raw + table.total_size == 0x086D60E4
    assert table.evidence and "0x0800E2EA" in table.evidence


def test_the_two_declared_enemy_tables_name_different_codecs() -> None:
    sizes = {
        item.id: item.enemy_stats.record_size
        for item in _log2_catalog().profiles
        if item.enemy_stats is not None
    }
    assert sizes["buus_fury_usa_rev0_01c1707f"] == st.ENEMY_RECORD_SIZE
    assert sizes["legacy_of_goku_ii_usa_rev0_204142e1"] == st.LOG2_ENEMY_RECORD_SIZE
    for size in sizes.values():
        assert st.enemy_codec_for_record_size(size).record_size == size
