"""ROM-gated proof that authored map objects reach the built image and nothing else moves."""

from __future__ import annotations

from dataclasses import replace
import struct

import pytest

from tests.rom_support import canonical_rom_path, mutable_rom_copy
from tools.creator.model import jobs
from tools.creator.model.maps import MapStudio
from tools.creator.model.project import CreatorError, CreatorProject
from tools.webfoot import map_objects as mo

pytestmark = pytest.mark.skipif(
    canonical_rom_path() is None, reason="the canonical Buu's Fury ROM is not present"
)

MAP = 102
KEY = "map:0102"


def _studio(tmp_path):
    rom = mutable_rom_copy(tmp_path)
    project = CreatorProject.create(rom, tmp_path / "Game", "Game")
    return rom, project, MapStudio(project.directory, rom)


def _build(rom, project) -> bytes:
    result = jobs.run_blocking("build", project.directory, rom, project.output)
    assert result["ok"], result
    return project.output.read_bytes()


def test_the_census_reads_every_slot_of_every_family(tmp_path):
    rom, _project, studio = _studio(tmp_path)
    found = mo.census(studio.image, studio.profile)
    slots = [item for objects in found.values() for item in objects]
    families = {name: sum(item.family == name for item in slots)
                for name in (mo.PLACEMENT, mo.NPC, mo.SCENE)}
    assert (len(found), len(slots)) == (316, 1898)
    assert families == {mo.PLACEMENT: 1559, mo.NPC: 191, mo.SCENE: 148}
    assert sum(len({item.family for item in objects}) > 1 for objects in found.values()) == 43
    assert max(len(objects) for objects in found.values()) == 51
    assert not any(item.writable for item in slots if item.family == mo.SCENE)


def test_a_move_writes_four_bytes_and_additions_keep_the_games_order(tmp_path):
    rom, project, studio = _studio(tmp_path)
    image = studio.image
    base = mo.read_objects(image, studio.profile, MAP)
    wanderer = next(item for item in base if item.wanders)
    stander = next(item for item in base if item.family == mo.NPC and not item.wanders)

    studio.move_character(KEY, f"game:{stander.slot}", stander.x + 8, stander.y)
    built = _build(rom, project)
    changed = [at for at in range(len(image)) if image[at] != built[at]]
    at = stander.record_offset + 8
    assert changed and set(changed) <= set(range(at, at + 4))
    assert rom.read_bytes() == image

    copy = studio.duplicate_character(KEY, f"game:{wanderer.slot}", 200, 400)
    studio.rename_character(KEY, copy, "Twin")
    studio.remove_character(KEY, f"game:{base[-1].slot}")
    built = _build(rom, project)
    after = mo.read_objects(built, studio.profile, MAP)
    assert len(after) == len(base)
    kept = after[:len(base) - 1]
    assert [item.pointer_raw for item in kept] == [item.pointer_raw for item in base[:-1]]
    assert (kept[stander.slot].x, kept[stander.slot].y) == (stander.x + 8, stander.y)
    added = after[-1]
    assert (added.family, added.sprite_id, added.x, added.y) == (mo.NPC, wanderer.sprite_id, 200, 400)
    assert added.wanders and added.box != wanderer.box
    assert added.record_offset >= len(image)
    for other in set(mo.census(image, studio.profile)) - {MAP}:
        assert mo.read_objects(built, studio.profile, other) == mo.read_objects(
            image, studio.profile, other)

    while studio.can_undo:
        studio.undo()
    assert not (project.directory / mo.OBJECTS_FILE).exists()
    assert [item.key for item in studio.characters(KEY)] == [f"game:{item.slot}" for item in base]


def test_a_made_map_carries_its_own_objects_and_leaves_its_donor_alone(tmp_path):
    rom, project, studio = _studio(tmp_path)
    image = studio.image
    base = mo.read_objects(image, studio.profile, MAP)
    key = studio.create("plaza", KEY)
    mover = next(item for item in base if item.writable)
    studio.move_character(key, f"game:{mover.slot}", mover.x + 16, mover.y + 16)
    studio.add_character(key, MAP, mover.slot, 300, 300)
    key = studio.rename(key, "square")
    assert set(mo.read_document(project.directory)) == {"map-new:square"}
    built = _build(rom, project)
    assert mo.read_objects(built, studio.profile, MAP) == base

    last = base[-1]
    studio.move_character(KEY, f"game:{last.slot}", last.x + 8, last.y + 8)
    built = _build(rom, project)
    donor = mo.read_objects(built, studio.profile, MAP)
    assert (donor[-1].x, donor[-1].y) == (last.x + 8, last.y + 8)
    assert donor[-1].record_offset >= len(image)
    assert all(
        built[item.record_offset:item.record_offset + 0x1C]
        == image[item.record_offset:item.record_offset + 0x1C] for item in base)

    family = next(item for item in mo.FAMILIES.values() if item.name == mover.family)
    place = family.position_offset

    def word(offset: int) -> bytes:
        return (mo.GBA_ROM_BASE + offset).to_bytes(4, "little")

    added = built.index(struct.pack("<2H", 300, 300), len(image)) - place
    array = built.index(word(added), len(image)) - 4 * len(base)
    slots = struct.unpack_from(f"<{len(base) + 1}I", built, array)
    kept = [item.pointer_raw for item in base]
    assert [raw for slot, raw in enumerate(slots[:-1]) if slot != mover.slot] == [
        raw for slot, raw in enumerate(kept) if slot != mover.slot]
    moved = slots[mover.slot] - mo.GBA_ROM_BASE
    assert moved >= len(image)
    assert struct.unpack_from("<2H", built, moved + place) == (mover.x + 16, mover.y + 16)
    shift = mo._field("trigger_count_raw") - mo._field("scripts_pointer_raw")
    named = [at for at in range(len(image), len(built) - 4, 4) if built[at:at + 4] == word(array)]
    assert [at for at in named if built[at + shift] == len(base) + 1]


def test_edits_that_cannot_be_trusted_are_refused(tmp_path):
    rom, project, studio = _studio(tmp_path)
    found = mo.census(studio.image, studio.profile)
    scene_map, scene = next((index, item) for index, objects in found.items()
                            for item in objects if item.family == mo.SCENE)
    with pytest.raises(CreatorError, match="story-scene"):
        studio.move_character(f"map:{scene_map:04d}", f"game:{scene.slot}", 8, 8)
    with pytest.raises(CreatorError, match="you added"):
        studio.set_look(KEY, "game:0", 5)

    base = mo.read_objects(studio.image, studio.profile, MAP)
    studio.move_character(KEY, "game:0", base[0].x + 8, base[0].y)
    edits = mo.read_document(project.directory)
    stale = replace(edits[KEY].moved[0], was=(1, 1))
    mo.write_document(project.directory, {KEY: mo.MapEdits({0: stale})})
    result = jobs.run_blocking("validate", project.directory, rom, project.output)
    assert not result["ok"] and "not the one this edit was made for" in str(result)

    placed_map, placed = next((index, item) for index, objects in found.items()
                              for item in objects if item.family == mo.PLACEMENT)
    for unproven in (mo.MapEdits(made={"npc-1": mo.Made(placed_map, placed.slot, 8, 8)}),
                     mo.MapEdits(removed=(placed.slot,))):
        with pytest.raises(mo.MapObjectError, match="not established"):
            mo.materialize_objects(
                studio.image, studio.profile, {f"map:{placed_map:04d}": unproven}, {})
    (project.directory / mo.OBJECTS_FILE).write_text(
        '[objects."map:0102"]\nremoved = 3\n', encoding="utf-8")
    with pytest.raises(mo.MapObjectError):
        mo.read_document(project.directory)

    full = {f"npc-{number}": mo.Made(MAP, 0, 8, 8) for number in range(1, mo.MAX_OBJECTS + 1)}
    with pytest.raises(mo.MapObjectError, match="255"):
        mo.materialize_objects(studio.image, studio.profile, {KEY: mo.MapEdits(made=full)}, {})
