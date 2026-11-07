"""Unit proofs for fixup binding: a declaration names the payload its word lives in.

LOG1-BUU-DIALOGUE-BACKPORT-001. A fixup word is a zeroed slot inside a composed
payload that the allocator fills with an address. Locating it by "the smallest payload
that contains this offset" is a guess, and the real declarations defeat it: lane A's
box words at 0x170/0x174 sit inside both a 376-byte box block and lane B's 464-byte
portrait block. These tests pin the replacement rule - an explicit ``payload`` field -
and every way it fails closed. No image is needed, so the rule is proven in
microseconds and the ROM-gated family only proves placement.
"""

from __future__ import annotations

import pytest

from tools.webfoot.commands.backport import BackportCommandError, _plan_fixups

BLOCKS = {"portrait": bytes(0x1D0), "strips": bytes(0x178)}


def _fixup(**overrides) -> dict:
    entry = {"from": "sites.toml", "symbol": "raster_roshi", "offset": 0x1C4,
             "payload": "portrait", "bytes": 4096}
    entry.update(overrides)
    return entry


def test_two_fixups_at_one_offset_bind_to_the_payload_each_one_names():
    """The 0x170 trap: same offset, two payloads, no geometric tie-break."""
    planned = _plan_fixups(
        [_fixup(symbol="box_raster", offset=0x170, payload="strips", bytes=10240),
         _fixup(symbol="raster_roshi", offset=0x170, payload="portrait")],
        BLOCKS,
    )
    assert [(entry["symbol"], entry["payload"], entry["offset"]) for entry in planned] == [
        ("box_raster", "strips", 0x170),
        ("raster_roshi", "portrait", 0x170),
    ]


def test_a_fixup_that_names_no_payload_is_refused_with_the_field_to_add():
    with pytest.raises(BackportCommandError) as refused:
        _plan_fixups([_fixup(payload=None)], BLOCKS)
    message = str(refused.value)
    assert "sites.toml: fixup 'raster_roshi' at 0x1C4 names no payload" in message
    assert 'payload = "<label>"' in message


def test_a_fixup_naming_a_payload_the_composition_does_not_hold_is_refused():
    with pytest.raises(BackportCommandError, match="names no payload"):
        _plan_fixups([_fixup(payload="bf-box-window")], BLOCKS)


def test_a_word_past_the_end_of_its_named_payload_is_refused():
    with pytest.raises(BackportCommandError, match="holds no 4-byte word"):
        _plan_fixups([_fixup(offset=0x1D0)], BLOCKS)


def test_a_word_that_is_not_reserved_zero_is_refused():
    blocks = {"portrait": bytes(0x1C4) + b"\xaa\xbb\xcc\xdd" + bytes(8)}
    with pytest.raises(BackportCommandError, match="not reserved"):
        _plan_fixups([_fixup()], blocks)


def test_two_fixups_claiming_one_slot_are_refused():
    with pytest.raises(BackportCommandError, match="already fills that word"):
        _plan_fixups([_fixup(), _fixup(symbol="raster_goku")], BLOCKS)
