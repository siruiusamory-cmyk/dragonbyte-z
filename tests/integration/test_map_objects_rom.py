"""ROM-gated proof that authored map objects reach the built image and nothing else moves."""

from __future__ import annotations

from dataclasses import replace
import struct

import pytest

from tests.rom_support import canonical_rom_path, mutable_rom_copy
from tools.creator.model import jobs
from tools.creator.model.maps import MapStudio
from tools.creator.model.project import CreatorError, CreatorProject
from tools.webfoot import enemy_types, events, map_objects as mo, story_flags
from tools.webfoot.build import validate_project
from tools.webfoot.profile import RomProfileCatalog

pytestmark = pytest.mark.skipif(
    canonical_rom_path() is None, reason="the canonical Buu's Fury ROM is not present"
)

MAP = 102
KEY = "map:0102"
ENEMY_MAP = 33
ENEMY_KEY = "map:0033"


def _studio(tmp_path):
    rom = mutable_rom_copy(tmp_path)
    project = CreatorProject.create(rom, tmp_path / "Game", "Game")
    return rom, project, MapStudio(project.directory, rom)


def _build(rom, project) -> bytes:
    result = jobs.run_blocking("build", project.directory, rom, project.output)
    assert result["ok"], result
    return project.output.read_bytes()


def _placed_donor(studio) -> int:
    """A donor type row the base game also places, so a sprite can be copied."""
    placed = {mo._u32(studio.image, item.record_offset + mo.TYPE_OFFSET)
              for objects in mo.census(studio.image, studio.profile).values()
              for item in objects if item.family == mo.PLACEMENT}
    return next(row for row in enemy_types.donor_family(studio.profile, studio.image)
                if row in placed)


def _enemy_project(tmp_path, name: str = "ghoul"):
    rom, project, studio = _studio(tmp_path)
    donor = _placed_donor(studio)
    types = enemy_types.claim(enemy_types.Types(), name, donor, studio.profile,
                              studio.image)
    enemy_types.write_types(project.directory, types)
    return rom, project, studio, types


def _added(image: bytes, profile) -> list:
    return [item for item in mo.read_objects(image, profile, ENEMY_MAP)
            if item.family == mo.PLACEMENT and item.record_offset >= 0x00800000]


def _array_address(image: bytes, profile) -> int:
    at = (mo.table_offset(profile, len(image)) + ENEMY_MAP * mo.record_size(profile)
          + mo._field("scripts_pointer_raw"))
    return struct.unpack_from("<I", image, at)[0]


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


def test_enemy_appears_word_encoding(tmp_path):
    rom, project, studio, _types = _enemy_project(tmp_path)
    registry = story_flags.assign(story_flags.read_flags(project.directory), "gate",
                                  studio.profile)
    story_flags.write_flags(project.directory, registry)
    number = registry.names["gate"]
    for name, appears, y in (("always", "always", 152), ("gated", "gate", 168),
                             ("clear", "!gate", 184)):
        mo.place_enemy(project.directory, ENEMY_KEY, name, "enemy:ghoul", 176, y,
                       appears=appears)

    built = _build(rom, project)
    added = _added(built, studio.profile)
    words = {item.y: struct.unpack_from("<I", built, item.record_offset + 0x04)[0]
             for item in added}
    assert words == {152: 0, 168: (1 << 16) | number, 184: (2 << 16) | number}
    assert all(item.family == mo.PLACEMENT and item.record_offset >= 0x00800000
               for item in added)


def test_enemy_project_type_writes_its_claimed_row(tmp_path):
    rom, project, studio, types = _enemy_project(tmp_path)
    entry = types.entries["enemy:ghoul"]
    mo.place_enemy(project.directory, ENEMY_KEY, "ghoul", "enemy:ghoul", 176, 152)
    built = _build(rom, project)
    added = _added(built, studio.profile)
    assert len(added) == 1
    assert struct.unpack_from("<I", built, added[0].record_offset + 0x08)[0] == entry.row
    assert entry.row in enemy_types.spare_rows(studio.profile)


def test_enemy_records_are_above_expansion_base(tmp_path):
    rom, project, studio = _studio(tmp_path)
    mo.place_enemy(project.directory, ENEMY_KEY, "wolf", "enemy:86", 176, 152)
    built = _build(rom, project)
    added = _added(built, studio.profile)
    assert len(added) == 1
    record = added[0].record_offset
    array = _array_address(built, studio.profile)
    row = mo.table_offset(studio.profile, len(built)) + ENEMY_MAP * mo.record_size(
        studio.profile)
    count = built[row + mo._field("trigger_count_raw")]
    assert record >= 0x00800000
    assert mo.GBA_ROM_BASE + record >= 0x08800000
    assert array >= 0x08800000
    slots = struct.unpack_from(f"<{count}I", built, array - mo.GBA_ROM_BASE)
    assert slots[-1] == mo.GBA_ROM_BASE + record


def test_built_object_census_matches_retail(tmp_path):
    _rom, _project, studio = _studio(tmp_path)
    assert mo.builds(0) and mo.builds((1 << 16) | 7) and mo.builds(0x08070000)
    assert not mo.builds(1)
    assert mo.built_objects(studio.image, studio.profile, 134) == 23
    assert mo.built_objects(studio.image, studio.profile, 32) == 0
    assert mo.built_objects(studio.image, studio.profile, 137) == 14
    objects = mo.read_objects(studio.image, studio.profile, 137)
    assert len(objects) == 14
    assert sum(not struct.unpack_from("<I", studio.image,
                                      item.record_offset + mo.CONDITION_OFFSET)[0]
               for item in objects) == 11
    assert len(mo.read_objects(studio.image, studio.profile, 32)) == 51


def test_map_built_object_limit_refused(tmp_path):
    _rom, project, studio, types = _enemy_project(tmp_path)
    mo.place_enemy(project.directory, "map:0134", "ghoul", "enemy:ghoul", 8, 8)
    edits = mo.read_document(project.directory)
    with pytest.raises(mo.MapObjectError,
                       match="would build 24 objects when it loads"):
        mo.materialize_objects(studio.image, studio.profile, edits, {}, types=types)
    with pytest.raises(mo.MapObjectError, match="conservative rule"):
        mo.materialize_objects(studio.image, studio.profile, edits, {}, types=types)
    with pytest.raises(mo.MapObjectError, match="engine itself sets no object count"):
        mo.materialize_objects(studio.image, studio.profile, edits, {}, types=types)


def test_enemy_authoring_leaves_other_maps_unchanged(tmp_path):
    rom, project, studio, _types = _enemy_project(tmp_path)
    mo.place_enemy(project.directory, ENEMY_KEY, "ghoul", "enemy:ghoul", 176, 152)
    built = _build(rom, project)
    image = studio.image
    assert _added(built, studio.profile)
    for index in set(mo.census(image, studio.profile)) - {ENEMY_MAP}:
        assert mo.read_objects(built, studio.profile, index) == mo.read_objects(
            image, studio.profile, index)
    base = mo.read_objects(image, studio.profile, ENEMY_MAP)
    after = mo.read_objects(built, studio.profile, ENEMY_MAP)
    assert after[:len(base)] == base


def test_map_without_enemies_builds_unchanged(tmp_path):
    rom, project, studio, types = _enemy_project(tmp_path)
    built = _build(rom, project)
    image = studio.image
    assert mo.census(built, studio.profile) == mo.census(image, studio.profile)
    start = studio.profile.enemy_stats.address.to_file_offset(len(image))
    row = types.entries["enemy:ghoul"].row
    size = studio.profile.enemy_stats.record_size
    changed = {at for at in range(len(image)) if image[at] != built[at]}
    assert changed and changed <= set(range(start + row * size, start + (row + 1) * size))


def test_enemy_placement_build_deterministic(tmp_path):
    rom, project, studio, _types = _enemy_project(tmp_path)
    mo.place_enemy(project.directory, ENEMY_KEY, "ghoul", "enemy:ghoul", 176, 152)
    first = _build(rom, project)
    second = _build(rom, project)
    assert first == second
    assert _added(first, studio.profile)


def test_enemy_placement_unknown_type_refused(tmp_path):
    _rom, project, studio, types = _enemy_project(tmp_path)
    mo.place_enemy(project.directory, ENEMY_KEY, "ghoul", "enemy:nosuch", 176, 152)
    edits = mo.read_document(project.directory)
    with pytest.raises(mo.MapObjectError, match="which this project holds no enemy type for"):
        mo.materialize_objects(studio.image, studio.profile, edits, {}, types=types)


def test_enemy_placement_unknown_flag_refused(tmp_path):
    _rom, project, studio, types = _enemy_project(tmp_path)
    mo.place_enemy(project.directory, ENEMY_KEY, "ghoul", "enemy:ghoul", 176, 152,
                   appears="nosuchflag")
    edits = mo.read_document(project.directory)
    with pytest.raises(events.EventError, match="not in the story's flags"):
        mo.materialize_objects(studio.image, studio.profile, edits, {}, types=types,
                               condition=events.appearance({}))


def test_enemy_placement_out_of_bounds_refused(tmp_path):
    _rom, project, studio, types = _enemy_project(tmp_path)
    width, height = mo.map_extent(studio.image, studio.profile, ENEMY_MAP)
    mo.place_enemy(project.directory, ENEMY_KEY, "ghoul", "enemy:ghoul", width, 8)
    edits = mo.read_document(project.directory)
    with pytest.raises(mo.MapObjectError, match=f"outside the {width}x{height} extent"):
        mo.materialize_objects(studio.image, studio.profile, edits, {}, types=types)


def test_enemy_placement_deleted_type_refused(tmp_path):
    _rom, project, studio, types = _enemy_project(tmp_path)
    mo.place_enemy(project.directory, ENEMY_KEY, "ghoul", "enemy:ghoul", 176, 152)
    with pytest.raises(enemy_types.EnemyTypeError, match="maps/objects.toml"):
        enemy_types.deleted(project.directory, types, "ghoul")
    enemy_types.write_types(project.directory, enemy_types.Types())
    edits = mo.read_document(project.directory)
    with pytest.raises(mo.MapObjectError, match="which this project holds no enemy type for"):
        mo.materialize_objects(studio.image, studio.profile, edits, {}, types=None)


def test_enemy_placement_sprite_outside_the_donor_pairing_refused(tmp_path):
    _rom, project, studio, types = _enemy_project(tmp_path)
    mo.place_enemy(project.directory, ENEMY_KEY, "ghoul", "enemy:ghoul", 176, 152,
                   sprite=120)
    edits = mo.read_document(project.directory)
    with pytest.raises(mo.MapObjectError, match="the only sprite verified for this enemy"):
        mo.materialize_objects(studio.image, studio.profile, edits, {}, types=types)


def test_enemy_type_pairings_are_the_retail_placements(tmp_path):
    _rom, _project, studio = _studio(tmp_path)
    pairings = mo.enemy_placements(studio.image, studio.profile)

    assert len(pairings) == 125
    assert sum(len(sprites) for sprites in pairings.values()) == 1559
    assert pairings[86] == (209, 211, 209, 215, 213, 209, 213, 211, 215)
    assert mo.verified_sprite(studio.image, studio.profile, 86) == 209
    with pytest.raises(mo.MapObjectError, match="the only sprite verified for this enemy"):
        mo.verified_sprite(studio.image, studio.profile, 86, 211)


def _report(project, rom):
    return validate_project(project.directory, rom, RomProfileCatalog.load("config/roms.yaml"))


def test_validate_refuses_a_map_that_would_build_too_many_objects(tmp_path):
    rom, project, _maps = _studio(tmp_path)
    mo.place_enemy(project.directory, "map:0134", "extra", "enemy:86", 8, 8)

    report = _report(project, rom)

    assert not report.passed
    assert [message for message in report.problems
            if message.startswith("map objects:")
            and "would build 24 objects when it loads" in message
            and "conservative rule" in message]


def test_validate_names_an_enemy_placed_outside_the_map(tmp_path):
    rom, project, studio = _studio(tmp_path)
    width, height = mo.map_extent(studio.image, studio.profile, ENEMY_MAP)
    mo.place_enemy(project.directory, ENEMY_KEY, "extra", "enemy:86", width, 8)

    report = _report(project, rom)

    assert not report.passed
    assert [message for message in report.problems
            if message.startswith("map objects:")
            and f"outside the {width}x{height} extent" in message]
