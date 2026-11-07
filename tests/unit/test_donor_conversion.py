"""Unit proofs for the donor conversion: index-0-only transparency and tiling.

LOG1-BUU-DIALOGUE-BACKPORT-001. The load-bearing rule is that transparency belongs
to the donor INDEX, not to the colour, so an opaque index that happens to paint
BGR555 black must not collapse into slot 0. These run without a ROM; the
equivalence against the real donor payloads is the D report's alpha-verify evidence.
"""

from __future__ import annotations

import struct

import pytest

from tools.webfoot.commands.backport import BackportCommandError, _bank_slot as bank_slot
from tools.webfoot.donor_resources import (
    FONT_BYTES,
    FONT_FILE_OFFSET,
    FONT_SHA256,
    LOW_BANK_ENTRIES,
    DonorResourceError,
    dialogue_font,
    donor_palette,
    low_bank,
    remap_payload,
)


def test_donor_index_one_is_opaque_black_not_transparent() -> None:
    palette = (0x0000, 0x0000) + tuple(0x7FFF for _ in range(254))
    bank = low_bank({"p": bytes([0, 1, 1, 0])}, palette)
    assert bank.transparent and 0 not in bank.opaque
    assert bank.remap[0] == 0
    assert bank.remap[1] > 0
    shared = struct.unpack(f"<{len(bank.palette) // 2}H", bank.palette)
    assert shared[0] == 0x0000 and shared[bank.remap[1]] == 0x0000
    converted = remap_payload(bytes([0, 1, 1, 0]), bank.remap)
    assert all((out == 0) == (donor == 0) for donor, out in zip([0, 1, 1, 0], converted))


def test_opaque_indices_sharing_a_colour_share_one_slot_above_zero() -> None:
    palette = (0x0000, 0x1234, 0x1234) + tuple(0x7FFF for _ in range(253))
    bank = low_bank({"p": bytes([0, 1, 2])}, palette)
    assert bank.remap[1] == bank.remap[2] > 0
    assert bank.collapsed[0x1234] == (1, 2)


def test_overflow_is_refused_not_quantised() -> None:
    palette = tuple(0x1000 + index for index in range(256))
    with pytest.raises(DonorResourceError, match="does not quantise"):
        low_bank({"p": bytes(range(200))}, palette)


def test_an_index_the_bank_never_mapped_is_refused() -> None:
    bank = low_bank({"p": bytes([0, 3])}, (0x0000, 0x1111, 0x2222, 0x3333)
                    + tuple(0x7FFF for _ in range(252)))
    with pytest.raises(DonorResourceError, match="no slot"):
        remap_payload(bytes([7]), bank.remap)


def test_palette_payload_stops_at_the_last_slot_it_uses() -> None:
    """A payload padded to the whole half-bank would let a copy clobber bank 7."""
    bank = low_bank({"p": bytes([0, 5])}, (0x0000, 0, 0, 0, 0, 0x0ABC)
                    + tuple(0x7FFF for _ in range(250)))
    entries = len(bank.palette) // 2
    assert entries == bank.remap[5] + 1 < LOW_BANK_ENTRIES
    shared = struct.unpack(f"<{entries}H", bank.palette)
    assert shared[bank.remap[5]] == 0x0ABC


def test_donor_palette_reads_256_halfwords_from_the_declared_offset() -> None:
    data = bytes(0x5662C)
    data = data[:0x5652C] + struct.pack("<256H", *range(256))
    assert donor_palette(data)[5] == 5


def test_white_lands_on_the_last_bank_slot_and_never_on_donor_index_two() -> None:
    """A donor palette index is not a target slot: the bank sorts and remaps.

    0x7FFF white is the highest BGR555 colour, so it takes the LAST opaque slot. A glyph
    payload that inks the donor's index 2 after this conversion paints whatever colour
    sorted into slot 2 instead - the ink mismatch this test pins shut.
    """
    palette = (0x0000, 0x001F, 0x000B, 0x0010, 0x7FFF) + (0,) * 251
    bank = low_bank({"p": bytes([0, 1, 2, 3, 4])}, palette)
    white = bank_slot(bank.palette, 0x7FFF)
    assert white == 4 and white != 2 and bank.remap[2] == 1
    shared = struct.unpack(f"<{len(bank.palette) // 2}H", bank.palette)
    assert shared[2] == 0x0010 and shared[white] == 0x7FFF


def test_a_colour_must_hold_exactly_one_slot_to_be_inkable() -> None:
    with pytest.raises(BackportCommandError, match="holds 0x1234 in 0 slots"):
        bank_slot(bytes.fromhex("001f7fff"), 0x1234)
    with pytest.raises(BackportCommandError, match="holds 0x7FFF in 2 slots"):
        bank_slot(bytes.fromhex("ff7fff7f"), 0x7FFF)


def test_the_font_span_is_guarded_by_its_own_digest() -> None:
    """The span has no length field, so the digest is the only guard there is."""
    span = bytes(FONT_FILE_OFFSET) + bytes(FONT_BYTES)
    with pytest.raises(DonorResourceError, match="measured against"):
        dialogue_font(span)
    assert FONT_SHA256 == (
        "95e97071f6c0318d9eee0160d63300b6d3fb780c73a4a02c10a0f1cc605fd085")
    with pytest.raises(DonorResourceError, match="ends inside the font span"):
        dialogue_font(span[:-1])
