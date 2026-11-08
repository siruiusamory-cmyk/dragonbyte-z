"""The LOG1 state-9 advance law: assembled bytes, the hook encoding, and exactness.

The retail routine at the clip's advance site reads a tick from the object, derives the
frame as ``tick >> 4``, increments and masks the tick, stores both, and stops the clip at a
capped tick. The law this project wants is ``frame = tick / 7`` clamped to ten, and the
smallest byte change is a four-byte ``BL`` over the increment's mask halfwords, which leaves
``lr`` on the retail frame store. These tests hold the assembled routine's bytes and the
block above; the exactness is asserted over every tick the cap can see.
"""

from __future__ import annotations

import pytest

from tools.webfoot import sprite_limits as sl
from tools.webfoot.project.patchdoc import PatchDocumentError, decode_thumb_bl

LAW_BYTES = bytes.fromhex("013825214143090a0a2900d90a2101300006000e7047c046")
LAW_ADVANCE_SITE = (0x0800 << 16) | 0xC9EC
RETAIL_MASK_BYTES = bytes.fromhex("06000e00")


def law(incremented_tick: int) -> tuple[int, int]:
    """The hook receives the tick after the retail increment at site minus two."""
    tick = incremented_tick - 1
    frame = (tick * 37) >> 8
    if frame > 10:
        frame = 10
    return (tick + 1) & 0xFF, frame


def test_the_assembled_routine_is_the_instructions_the_design_names() -> None:
    assert len(LAW_BYTES) == 24
    halves = [int.from_bytes(LAW_BYTES[index:index + 2], "little") for index in range(0, 24, 2)]
    assert halves.pop(0) == 0x3801
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
    assert halves[10] == 0x46C0
    source = (sl.SOURCE_DIR / "law.s").read_text(encoding="utf-8")
    instructions = [line.split("/*")[0].strip() for line in source.splitlines()]
    instructions = [" ".join(line.split()) for line in instructions
                    if line and not line.startswith(".") and not line.endswith(":")]
    assert instructions == [
        "subs r0, #1", "movs r1, #37", "muls r1, r0, r1", "lsrs r1, r1, #8",
        "cmp r1, #10", "bls .Lsprite_law_keep", "movs r1, #10", "adds r0, #1",
        "lsls r0, r0, #24", "lsrs r0, r0, #24", "bx lr",
    ]


def test_the_law_is_exact_for_every_tick_the_cap_allows() -> None:
    for tick in range(0x50):
        assert law(tick + 1) == (tick + 1, min(tick // 7, 10)), tick
    tick = 0
    frames = []
    while tick < 0x50:
        tick, frame = law(tick + 1)
        frames.append(frame)
    assert len(frames) == 80
    assert [frames.count(frame) for frame in range(11)] == [7] * 10 + [10]


def test_the_hook_encodes_to_the_site_and_decodes_back() -> None:
    target = LAW_ADVANCE_SITE + 0x1000
    encoded = sl.thumb_bl(LAW_ADVANCE_SITE, target)
    assert len(encoded) == 4
    second = int.from_bytes(encoded[2:4], "little")
    assert second & 0xF800 == 0xF800
    first = int.from_bytes(encoded[0:2], "little")
    assert first & 0xF800 == 0xF000
    assert encoded[2] & 0x7 == (target - (LAW_ADVANCE_SITE + 4)) >> 1 & 0x7
    assert LAW_ADVANCE_SITE % 4 == 0
    assert RETAIL_MASK_BYTES == bytes.fromhex("06000e00")
    assert decode_thumb_bl(LAW_ADVANCE_SITE, encoded) == target


def test_the_hook_refuses_the_unreachable_tail_target() -> None:
    target = (0x0800 << 16) | (0x7B << 16) | 0x9C00
    with pytest.raises(PatchDocumentError, match="outside.*Thumb BL range"):
        sl.thumb_bl(LAW_ADVANCE_SITE, target)
