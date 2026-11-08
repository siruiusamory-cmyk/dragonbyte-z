"""ROM-gated proof of the phase 3 actor draw payload: budget and per-piece bank.

LOG1-BUU-SPRITE-BACKPORT-001 phase 3 (DBZ-033). The payload replaces the retail
draw method 0x0800B01E at all 77 words that dispatch to it, and it is the retail
body except the two instructions its bank selector displaces and the final
`bx lr`, which the guard's saved `lr` turns into `pop {pc}`. This test reads the
canonical image, builds the payload, places it through the same allocator and
patch document the build uses, and asserts every number the module documents -
including that nothing outside the declared sites and the payload's own
placement changes.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from tools.webfoot import sprite_limits as sl
from tools.webfoot.catalog import load_catalog
from tools.webfoot.project.patchdoc import materialize_patch, read_patch_document


def _image() -> bytes:
    path = os.environ.get("WEBFOOT_LOG1_ROM")
    if not path:
        pytest.skip("WEBFOOT_LOG1_ROM is not set")
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != sl.LOG1_SHA256:
        pytest.skip(f"{path} is not the canonical Legacy of Goku image")
    return data


def test_frame_law_hook_follows_the_retail_tick_increment() -> None:
    image = _image()
    site = 0xC9EC
    assert image[site - 6:site + 12] == bytes.fromhex(
        "007c010901300006000ea174207450280dd3")


def test_the_payload_is_the_retail_body_and_only_two_sites_move() -> None:
    image = _image()
    body, pool = sl.canonical_bytes(image)
    payload = sl.compose_payload(image)
    prologue = sl.PROLOGUE.read_bytes()
    pad = (2 - len(prologue)) % 4
    body_offset = len(prologue) + pad
    copied = payload[body_offset:body_offset + len(body)]
    changed = [i for i in range(len(body)) if copied[i] != body[i]]
    expected = list(range(sl.BODY_BANK_OFFSET, sl.BODY_BANK_OFFSET + 4)) + list(
        range(sl.BODY_BX_LR, sl.BODY_BX_LR + 2))
    assert changed == expected, changed
    assert payload[body_offset + len(body):body_offset + len(body) + 12] == pool
    assert payload[len(prologue) - 2:len(prologue)] == sl.thumb_branch(
        len(prologue) - 2, body_offset)
    assert len(payload) == body_offset + len(body) + len(pool) + len(
        sl.BANK_HELPER.read_bytes())


def test_every_draw_method_word_is_one_of_the_seventy_seven() -> None:
    image = _image()
    sites = sl.pointer_sites(image)
    assert len(sites) == 77
    method = sl.APPEND_ENTRY | 1
    for site in sites:
        assert image[site:site + 4] == method.to_bytes(4, "little")


def test_the_materialised_patch_touches_only_its_own_sites(tmp_path: Path) -> None:
    image = _image()
    sl.write_project_patch(tmp_path, image)
    document = read_patch_document(tmp_path)
    profile = next(p for p in load_catalog(None).profiles if p.game == "legacy_of_goku")
    materialization = materialize_patch(document, profile, image)
    assert len(materialization.changes) == 78
    assert len(materialization.allocations) == 1
    placed = materialization.allocations[0].range.start.value
    size = len(sl.compose_payload(image))
    allowed = set(sl.pointer_sites(image)) | set(range(placed, placed + size))
    for change in materialization.changes:
        assert change.offset in allowed, hex(change.offset)
        assert image[change.offset:change.offset + len(change.old)] == change.old


def test_the_retail_cells_leave_the_bank_bits_zero() -> None:
    image = _image()

    def u32(address: int) -> int:
        offset = address - sl.GBA_ROM_BASE
        return int.from_bytes(image[offset:offset + 4], "little")

    checked = 0
    for art in range(sl.ART_COUNT):
        definition = u32(sl.ART_TABLE + art * 4)
        if definition == 0:
            continue
        animation_table = u32(definition + 0x28)
        if animation_table == 0:
            continue
        for state in range(sl.STATE_LIMIT):
            for facing in range(4):
                cell = u32(animation_table + state * 16 + facing * 4)
                if cell == 0:
                    continue
                checked += 1
                attribute_a = image[cell - sl.GBA_ROM_BASE + 0x0A]
                assert sl.cell_bank(attribute_a) is None, (art, state, facing, attribute_a)
    assert checked > 1000, checked


def test_the_budget_predicate_refuses_at_the_ceiling() -> None:
    assert sl.budgets_hold(127, 1008, 16, 0, 0)
    assert not sl.budgets_hold(128, 0, 1, 0, 0)
    assert not sl.budgets_hold(0, 1009, 16, 0, 0)
    assert not sl.budgets_hold(0, 0, 16, sl.OBJ_WINDOW_BYTES - 16 * 32 + 1, 0)
    assert sl.cell_bank(0x00) is None
    assert sl.cell_bank(0x40) == 0
    assert sl.cell_bank(0x7C) == 15


def test_the_refusal_returns_to_the_caller_and_moves_no_cursor() -> None:
    prologue = sl.PROLOGUE.read_bytes()
    push, pops = sl.stack_frame(prologue)
    refusal = [half for _, half in pops if half >> 8 == 0xBD]
    accept = [half for _, half in pops if half >> 8 == 0xBC]
    assert len(refusal) == 1 and len(accept) == 1, pops
    assert push & 0x1FF == refusal[0] & 0x1FF, (push, refusal[0])
    exits = {offset for offset, _ in pops}
    assert {target for _, target in sl.branch_targets(prologue[:-2])} <= exits
    assert not [site for site in sl.store_sites(prologue) if site[0] == 1]


def test_the_lr_round_trip() -> None:
    image = _image()
    body, pool = sl.canonical_bytes(image)
    payload = sl.compose_payload(image)
    prologue = sl.PROLOGUE.read_bytes()
    body_offset = len(prologue) + (2 - len(prologue)) % 4
    copied = payload[body_offset:body_offset + len(body)]
    push, _pops = sl.stack_frame(prologue)
    assert push & 0x100, push
    assert body[sl.BODY_BX_LR:sl.BODY_BX_LR + 2] == bytes.fromhex("7047")
    assert copied[sl.BODY_BX_LR:sl.BODY_BX_LR + 2] == bytes.fromhex("00bd")
    assert copied[sl.BODY_BX_LR - 2:sl.BODY_BX_LR] == body[sl.BODY_BX_LR - 2:sl.BODY_BX_LR]
    assert payload[body_offset + len(body):body_offset + len(body) + 12] == pool


def test_the_ceiling_stress_leaves_the_neighbouring_tiles_untouched() -> None:
    _image()
    prologue = sl.PROLOGUE.read_bytes()
    assert not [site for site in sl.store_sites(prologue) if site[0] == 1]
    ceiling = sl.TILE_FIELD_LIMIT
    assert sl.budgets_hold(0, ceiling - 16, 16, 0, 0)
    assert not sl.budgets_hold(0, ceiling - 15, 16, 0, 0)
    assert not sl.budgets_hold(0, ceiling, 1, 0, 0)
    assert not sl.budgets_hold(0, ceiling + 640, 1, 0, 0)
