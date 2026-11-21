"""A new character built into a private copy of the game, through the creator's own path."""

from __future__ import annotations

from collections import Counter
import hashlib
import struct

import pytest

from tests.rom_support import CANONICAL_ROM_SHA256, canonical_rom_path, mutable_rom_copy
from tools.creator.model import characters as ch
from tools.creator.model import jobs
from tools.creator.model.maps import MapStudio
from tools.creator.model.project import CreatorProject
from tools.postboy.session import Session
from tools.webfoot import map_objects as mo
from tools.webfoot.sprite_identity import (
    STRUCTURE_ANIMATION_TABLE_OFFSET,
    SpriteIdentityError,
    donor_census,
    select_donor,
)

pytestmark = pytest.mark.skipif(
    canonical_rom_path() is None, reason="the canonical Buu's Fury ROM is not present"
)


@pytest.fixture(scope="module")
def rom(tmp_path_factory):
    return mutable_rom_copy(tmp_path_factory.mktemp("rom"))


@pytest.fixture(scope="module")
def census(rom):
    session = Session()
    session.open_rom(rom)
    return donor_census(rom.read_bytes(), session.profile)


def test_the_sdk_finds_126_donors_and_97_that_walk(census):
    """Pins the donor census: 126 admitted, 97 with two distinct walk frames per facing."""
    assert len(census) == 126
    assert Counter(str(d.envelope) for d in census) == {
        "8x8": 5, "16x16": 7, "16x32": 48, "32x16": 2, "32x32": 50, "32x64": 1, "64x64": 13}
    walkers = [d for d in census if d.walks]
    assert len(walkers) == 97
    assert Counter(str(d.envelope) for d in walkers) == {
        "32x32": 34, "32x64": 1, "64x64": 12, "16x32": 45, "16x16": 3, "32x16": 1, "8x8": 1}


def test_a_donor_is_chosen_by_frame_size_and_walk_animation(census):
    assert select_donor(census, (32, 32), walks=True) == 10
    stander = select_donor(census, (32, 64), walks=False)
    assert next(d for d in census if d.sprite_id == stander).envelope.height == 64
    with pytest.raises(SpriteIdentityError, match="no character in this game draws 48x48"):
        select_donor(census, (48, 48), walks=False)


@pytest.mark.timeout(600)
def test_a_project_without_a_new_character_builds_the_game_unchanged(tmp_path, rom):
    """Pins that a project with no new sprite builds byte-identical to the base game."""
    CreatorProject.create(rom, tmp_path / "game", "Game")
    output = tmp_path / "out.gba"
    result = jobs._run({"action": "build", "project": str(tmp_path / "game"), "rom": str(rom),
                        "output": str(output), "result": ""})
    assert result["ok"], result
    assert hashlib.sha256(output.read_bytes()).hexdigest() == CANONICAL_ROM_SHA256


def _paint(maker, slot, facing, frame, index, x0):
    picture = next(f.picture for f in maker.frames()
                   if (f.animation, f.direction, f.frame) == (slot, facing, frame))
    maker.paint(picture, [(x, y) for x in range(x0, x0 + 6) for y in range(6, 28)], index)


@pytest.mark.timeout(1200)
def test_a_walker_placed_on_a_map_is_built_and_reads_back(tmp_path, rom):
    """Pins the whole path: identity 307 with Stand and Walk slots, drawn by a map copy."""
    before = hashlib.sha256(rom.read_bytes()).hexdigest()
    project = tmp_path / "game"
    CreatorProject.create(rom, project, "Game")
    maker = ch.CharacterMaker(project, rom)
    maker.create("Gohan Jr", ch.WALKS, "32 by 32 pixels")
    blocked = jobs._run({"action": "build", "project": str(project), "rom": str(rom),
                         "output": str(tmp_path / "early.gba"), "result": ""})
    assert not blocked["ok"]
    assert any("Stand pose facing left" in p["message"] for p in blocked["problems"])
    for facing in range(4):
        _paint(maker, 0, facing, 0, 5, 10)
        _paint(maker, 1, facing, 0, 5, 4)
        _paint(maker, 1, facing, 1, 5, 20)
    studio = MapStudio(project, rom)
    choice = studio.character_choices()[0]
    placed = studio.add_character("map:0033", choice.donor_map, choice.donor_slot, 40, 184,
                                  choice.sprite)
    studio.set_box("map:0033", placed, (24, 144, 111, 223))
    output = tmp_path / "walker.gba"
    result = jobs._run({"action": "build", "project": str(project), "rom": str(rom),
                        "output": str(output), "result": ""})
    assert result["ok"], result
    image = output.read_bytes()
    session = Session()
    session.open_rom(rom)
    layout = session.profile.actor_sprites
    canonical = rom.read_bytes()
    site = next(o for o in range(0, len(canonical), 4)
                if struct.unpack_from("<I", canonical, o)[0] == layout.character_table_address.raw)
    registry = struct.unpack_from("<I", image, site)[0] - 0x08000000
    structure = struct.unpack_from("<I", image, registry + 4 * layout.character_count)[0] - 0x08000000
    assert image[structure] == 2
    stand, walk = struct.unpack_from("<2I", image, structure + STRUCTURE_ANIMATION_TABLE_OFFSET)
    assert stand and walk and stand != walk
    record = struct.unpack_from("<I", image, walk - 0x08000000)[0]
    assert record == 2
    built = [o for o in mo.read_objects(image, session.profile, 33) if o.sprite_id == 307]
    assert len(built) == 1 and built[0].wanders and built[0].box == (24, 144, 111, 223)
    assert hashlib.sha256(rom.read_bytes()).hexdigest() == before
