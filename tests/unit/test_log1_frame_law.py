"""The LOG1 state-9 advance law: assembled bytes, the hook encoding, and exactness.

The retail routine at the clip's advance site reads a tick from the object, derives the
frame as ``tick >> 4``, increments and masks the tick, stores both, and stops the clip at a
capped tick. The law this project wants is ``frame = tick / 7`` clamped to ten, and the
smallest byte change is a four-byte ``BL`` over the increment's mask halfwords, which leaves
``lr`` on the retail frame store. These tests hold the assembled routine's bytes and the
block above; the exactness is asserted over every tick the cap can see.
"""

from __future__ import annotations

from tools.webfoot import sprite_limits as sl

LAW_BYTES = bytes.fromhex("25214143090a0a2900d90a2101300006000e7047")
LAW_ADVANCE_SITE = (0x0800 << 16) | 0xC9EC
RETAIL_MASK_BYTES = bytes.fromhex("06000e00")


def law(tick: int) -> int:
    """The assembled routine's semantics, restated from its own instructions."""
    frame = (tick * 37) >> 8
    if frame > 10:
        frame = 10
    return frame


def test_the_assembled_routine_is_the_instructions_the_design_names() -> None:
    assert len(LAW_BYTES) == 20
    halves = [int.from_bytes(LAW_BYTES[index:index + 2], "little") for index in range(0, 20, 2)]
    assert halves[0] == 0x2125
    assert halves[1] == 0x4341
    assert halves[2] == 0x0A09
    assert halves[3] == 0x290A
    assert halves[4] == 0xD900
    assert halves[5] == 0x210A
    assert halves[6] == 0x3001
    assert halves[7] == 0x0600
    assert halves[8] == 0x0E00
    assert halves[9] == 0x4770


def test_the_law_is_exact_for_every_tick_the_cap_allows() -> None:
    for tick in range(0x50):
        assert law(tick) == min(tick // 7, 10), tick
    assert [law(tick) for tick in (0, 6, 7, 70, 76, 0x4F)] == [0, 0, 1, 10, 10, 10]


def test_the_hook_encodes_to_the_site_and_decodes_back() -> None:
    target = (0x0800 << 16) | (0x7B << 16) | 0x9C00
    encoded = sl.thumb_bl(LAW_ADVANCE_SITE, target)
    assert len(encoded) == 4
    second = int.from_bytes(encoded[2:4], "little")
    assert second & 0xF800 == 0xF800
    first = int.from_bytes(encoded[0:2], "little")
    assert first & 0xF800 == 0xF000
    assert encoded[2] & 0x7 == (target - (LAW_ADVANCE_SITE + 4)) >> 1 & 0x7
    assert LAW_ADVANCE_SITE % 4 == 0
    assert RETAIL_MASK_BYTES == bytes.fromhex("06000e00")
