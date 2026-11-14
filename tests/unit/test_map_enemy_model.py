"""Enemy placements in the Maps model: add, move, duplicate, remove and Appears.

The game image is needed, so these skip cleanly when the canonical copy is absent,
and they read it read-only through a mutable copy.
"""

from __future__ import annotations

import pytest

from tests.rom_support import canonical_rom_path, mutable_rom_copy
from tools.creator.model.enemies import EnemyStudio
from tools.creator.model.maps import MapStudio
from tools.creator.model.project import CreatorError, CreatorProject
from tools.webfoot import enemy_types
from tools.webfoot import map_objects as mo
from tools.webfoot import story_flags as sf

pytestmark = pytest.mark.skipif(
    canonical_rom_path() is None, reason="the canonical Buu's Fury ROM is not present"
)

DONOR = "enemy:434"
DONOR_ROW = 86
RETAIL_TYPE = f"enemy:{DONOR_ROW}"
MAP = "map:0033"
CROWDED = "map:0134"
RETAIL_ENEMY = "game:1"


@pytest.fixture(scope="module")
def rom(tmp_path_factory):
    return mutable_rom_copy(tmp_path_factory.mktemp("base"))


@pytest.fixture
def maps(rom, tmp_path):
    project = CreatorProject.create(rom, tmp_path / "Game", "Game")
    types = EnemyStudio(project.directory, rom)
    studio = MapStudio(project.directory, rom)
    studio.enemy_types = types
    sf.write_flags(project.directory, sf.assign(sf.Flags(), "met_ghoul", studio.profile))
    sf.write_flags(project.directory, sf.assign(
        sf.read_flags(project.directory), "beat_ghoul", studio.profile))
    return studio, types, project


def _document(maps) -> dict:
    return mo.read_document(maps.directory)


def test_map_enemy_model_add_retail_type(maps):
    studio, _types, project = maps
    key = studio.add_enemy(MAP, RETAIL_TYPE, 176, 152)

    made = _document(studio)[MAP].made[key[5:]]
    assert (made.type, made.x, made.y, made.appears) == (RETAIL_TYPE, 176, 152, "always")
    read = studio.enemy_placements(MAP)
    assert [(item.key, item.name, item.made) for item in read] == [(key, DONOR, True)]
    assert studio.enemy_count(MAP) == 1
    assert studio.built_objects(MAP) == 13
    assert studio.built_object_policy == 23
    assert (project.directory / mo.OBJECTS_FILE).is_file()


def test_map_enemy_model_add_project_type(maps):
    studio, types, _project = maps
    types.create(DONOR, "ghoul")
    key = studio.add_enemy(MAP, "enemy:ghoul", 200, 160)

    assert _document(studio)[MAP].made[key[5:]].type == "enemy:ghoul"
    assert [(item.key, item.name) for item in studio.enemy_placements(MAP)] == [
        (key, "ghoul")]
    assert ("enemy:ghoul", "ghoul") in [
        (choice.key, choice.name) for choice in studio.enemy_choices()]


def test_map_enemy_model_move_duplicate_remove(maps):
    studio, _types, _project = maps
    key = studio.add_enemy(MAP, RETAIL_TYPE, 176, 152)
    studio.move_enemy(MAP, key, 200, 160)
    assert [(item.key, item.x, item.y) for item in studio.enemy_placements(MAP)] == [
        (key, 200, 160)]

    copy = studio.duplicate_enemy(MAP, key, 120, 120)
    assert copy != key
    made = _document(studio)[MAP].made
    assert sorted(made) == sorted([key[5:], copy[5:]])
    assert (made[copy[5:]].x, made[copy[5:]].y) == (120, 120)
    assert made[copy[5:]].type == made[key[5:]].type

    studio.remove_enemy(MAP, key)
    assert [item.key for item in studio.enemy_placements(MAP)] == [copy]
    studio.remove_enemy(MAP, copy)
    assert studio.enemy_placements(MAP) == []
    assert not (studio.directory / mo.OBJECTS_FILE).is_file()


def test_map_enemy_model_retail_placement_read_only(maps):
    studio, _types, _project = maps
    retail = studio.enemy_placements("map:0040")
    assert [(item.key, item.made) for item in retail] == [
        (RETAIL_ENEMY, False), ("game:3", False)]
    assert retail[0].name == DONOR
    before = (studio.directory / mo.OBJECTS_FILE).exists()
    for call in (
            lambda: studio.move_enemy("map:0040", RETAIL_ENEMY, 8, 8),
            lambda: studio.duplicate_enemy("map:0040", RETAIL_ENEMY, 8, 8),
            lambda: studio.remove_enemy("map:0040", RETAIL_ENEMY),
            lambda: studio.set_enemy_appears("map:0040", RETAIL_ENEMY, "met_ghoul")):
        with pytest.raises(CreatorError, match="a retail placement cannot be moved"):
            call()
    assert (studio.directory / mo.OBJECTS_FILE).exists() is before


def test_map_enemy_model_appears_always_set_clear(maps):
    studio, _types, _project = maps
    key = studio.add_enemy(MAP, RETAIL_TYPE, 176, 152)
    studio.set_enemy_appears(MAP, key, "met_ghoul")
    assert studio.enemy_placements(MAP)[0].appears == "met_ghoul"
    studio.set_enemy_appears(MAP, key, "!beat_ghoul")
    assert _document(studio)[MAP].made[key[5:]].appears == "!beat_ghoul"
    studio.set_enemy_appears(MAP, key, "always")
    assert studio.enemy_placements(MAP)[0].appears == "always"


def test_map_enemy_model_flag_chooser_lists_project_flags(maps):
    studio, _types, _project = maps
    assert studio.flag_names() == ["beat_ghoul", "met_ghoul"]


def test_map_enemy_model_over_policy_refused(maps):
    studio, _types, _project = maps
    assert studio.built_objects(CROWDED) == 23
    with pytest.raises(CreatorError, match="would build 24 objects when it loads"):
        studio.add_enemy(CROWDED, RETAIL_TYPE, 8, 8)
    with pytest.raises(CreatorError, match="conservative rule"):
        studio.add_enemy(CROWDED, RETAIL_TYPE, 8, 8)
    assert studio.enemy_placements(CROWDED) == []
    assert studio.built_objects(CROWDED) == 23


def test_map_enemy_model_out_of_bounds_refused(maps):
    studio, _types, _project = maps
    with pytest.raises(CreatorError, match="outside the 994x418 extent this map states"):
        studio.add_enemy(MAP, RETAIL_TYPE, 2000, 100)
    assert studio.enemy_placements(MAP) == []
    key = studio.add_enemy(MAP, RETAIL_TYPE, 176, 152)
    with pytest.raises(CreatorError, match="outside the 994x418 extent this map states"):
        studio.move_enemy(MAP, key, 176, 500)
    assert [(item.x, item.y) for item in studio.enemy_placements(MAP)] == [(176, 152)]


def test_map_enemy_model_never_exposes_a_row_or_address(maps):
    studio, types, _project = maps
    types.create(DONOR, "ghoul")
    key = studio.add_enemy(MAP, "enemy:ghoul", 176, 152)
    entry = enemy_types.read_types(
        studio.directory, studio.profile, studio.image).entries["enemy:ghoul"]
    studio.add_enemy("map:0040", RETAIL_TYPE, 8, 8)
    names = [item.name for item in studio.enemy_placements(MAP)]
    names += [choice.name for choice in studio.enemy_choices()]
    names += studio.flag_names()
    assert [name for name in names if "0x" in name.lower()] == []
    assert f"enemy:{entry.row}" not in names
    assert f"enemy:{entry.donor}" not in names
    assert "ghoul" in names and DONOR in names
    assert key == "made:enemy-1"
    assert studio.enemy_placements(MAP)[0].name == "ghoul"
