"""The pause page's seams, its method-table arithmetic and the boundary it keeps.

The seams are signed self-relative words in the pause state's method table; the
dispatcher adds the table base and branches, so the encoder's round trip is the
property that matters. The page also must not touch anything the sprite backport
owns, which is checked against its own source.
"""

import os
from pathlib import Path

import pytest
import yaml

from tools.webfoot import pause_menu as menu
from tools.webfoot.project.patchdoc import decode_relative_thumb

ROOT = Path(__file__).resolve().parents[2]
ROM_SOURCES = Path(__file__).resolve().parents[2] / "tools" / "webfoot" / "patchsource"
DONOR = Path(os.environ.get("PAUSE_MENU_DONOR_ROM", "lg2.gba"))


def declared_sites():
    document = yaml.safe_load(menu.SITES_FILE.read_text(encoding="utf-8"))
    return {row["file_offset"]: row for row in document["patch_sites"]}


@pytest.mark.parametrize("seam", (menu.SEAM_DRAW, menu.SEAM_UPDATE))
def test_both_seams_are_declared_relative_entries_of_the_pause_table(seam):
    site = declared_sites()[seam - menu.GBA_ROM_BASE]
    assert site["kind"] == "relative"
    assert site["base"] == menu.METHOD_TABLE
    assert site["evidence"].strip()


def test_the_encoder_round_trips_through_the_dispatcher_arithmetic():
    for offset in (0x00, 0x08, 0x0C):
        target = menu.NOMINAL_ADDRESS + 0x40 + offset
        stored = menu.relative_entry(target | 1, menu.METHOD_TABLE)
        assert len(stored) == 4
        assert decode_relative_thumb(stored, menu.METHOD_TABLE) == target | 1
        assert stored == (target + 1 - menu.METHOD_TABLE).to_bytes(4, "little", signed=True)


def test_the_fade_guard_chains_the_dialogue_per_frame_entry():
    assert menu.FADE_CHAIN - menu.GBA_ROM_BASE == 0xEF30
    assert menu.FADE_CHAIN - menu.FADE_CHAIN_BASE == 0x08
    source = (ROM_SOURCES / "log1-pause-menu" / "fade_guard.s").read_text(encoding="utf-8")
    assert '.include "generated_fade_target.inc"' in source


def test_the_page_touches_no_object_palette_no_shadow_oam_and_no_oam_append():
    source = (ROM_SOURCES / "log1-pause-menu" / "menu.c").read_text(encoding="utf-8")
    for forbidden, why in (
        ("0x05000200", "the object palette banks the sprite backport allocates"),
        ("0x0202BE24", "the shadow OAM the sprite backport appends to"),
        ("0x0800B01E", "the OAM append the sprite backport replaces"),
    ):
        assert forbidden not in source, f"menu.c names {forbidden}, {why}"


def test_the_donor_extraction_reproduces_the_recorded_digests():
    if not DONOR.is_file():
        pytest.skip(f"the private donor image is not at {DONOR}")
    result = menu.check(DONOR)
    assert result["panel_sha256"] == menu.PANEL_SHA256
    assert result["panel_bytes"] == menu.PANEL_BYTES
    assert result["assets_sha256"] == menu.ASSETS_SHA256
    assert result["first_surface_tile"] == menu.PAGE_TILE + menu.STRIP_CELLS
    labels = dict(result["labels"])
    assert labels["status"] == "Status"
    assert labels["quests"] == "Quests"
    assert labels["name"] == "Goku"
    assert labels["no_quests"] == "No Quests Finished"
    assert labels["level"].startswith("Level")


def test_every_surface_cell_owns_one_tile_and_the_chrome_shares_the_strip():
    upper, lower, first, panel = menu.chrome_maps()
    owned = [tile for grid in (upper, lower) for line in grid for tile in line if tile >= first]
    assert sorted(owned) == list(range(first, panel + menu.PANEL_BYTES // 64))
    assert lower[4][2] == panel
    assert all(menu.PAGE_TILE <= tile < first for line in upper for tile in line
               if tile < first)
