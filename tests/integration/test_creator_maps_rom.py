"""ROM-gated proof of the map editor's model: every edit, undo, redo and a build."""

from __future__ import annotations

import pytest

from tests.rom_support import canonical_rom_path, mutable_rom_copy
from tools.creator.model import jobs
from tools.creator.model.maps import MapStudio
from tools.creator.model.project import CreatorError, CreatorProject, source_digest
from tools.webfoot.formats import map_collision as grids

pytestmark = pytest.mark.skipif(
    canonical_rom_path() is None, reason="the canonical Buu's Fury ROM is not present"
)

RETAIL = "map:0033"


@pytest.fixture
def studio(tmp_path):
    rom = mutable_rom_copy(tmp_path)
    project = CreatorProject.create(rom, tmp_path / "Game", "Game")
    return MapStudio(project.directory, rom), project, rom


def test_a_map_is_made_painted_tiled_resized_walled_and_joined_then_built(studio):
    maps, project, rom = studio
    source = rom.read_bytes()
    arena = maps.create("arena", RETAIL)
    assert maps.maps()[0].key == arena and maps.maps()[0].new

    layer = next(item for item in maps.layers(arena) if item.editable and item.slot == 0)
    other = next(choice for choice in layer.choices if choice != layer.cells[0])
    maps.paint(arena, 0, [0], other)
    assert maps.layers(arena)[[item.slot for item in maps.layers(arena)].index(0)].cells[0] == other
    assert len(maps.chunk_picture(arena, other)) == 256 * 256 * 4

    tile = maps.tile_at(arena, 0, 1, 20, 20)
    different = next(maps.tile_at(arena, 0, 1, row, 3) for row in range(32)
                     if maps.tile_at(arena, 0, 1, row, 3) != tile)
    maps.stamp(arena, 0, 1, {(20, 20): different})
    made = next(item for item in maps.layers(arena) if item.slot == 0).cells[1]
    assert isinstance(made, str) and maps.tile_at(arena, 0, 1, 20, 20) == different
    assert len(maps.chunk_picture(arena, made)) == 256 * 256 * 4

    maps.resize(arena, 2, 5, 2)
    assert next(item for item in maps.layers(arena) if item.slot == 2).columns == 5

    grid = grids.with_cells(maps.collision(arena), [(31, y) for y in range(256)], False)
    maps.set_collision(arena, grid)
    assert maps.collision(arena) == grid and maps.collision(RETAIL) != grid

    assert not maps.can_add_door(RETAIL)
    maps.add_door(RETAIL, (296, 152, 312, 216), arena, (144, 160))
    maps.add_door(arena, (112, 152, 120, 216), RETAIL, (200, 160))
    maps.remove_door(arena, "game:0")
    inside = maps.doors(arena)
    assert [door.removed for door in inside if not door.created] == [True]
    assert [door.destination for door in inside if door.created] == [maps.title(RETAIL)]
    assert [door.destination for door in maps.doors(RETAIL) if door.created] == [maps.title(arena)]

    ring = maps.rename(arena, "ring")
    assert [door.destination for door in maps.doors(RETAIL) if door.created] == [maps.title(ring)]
    assert maps.collision(ring) == grid

    result = jobs.run_blocking("build", project.directory, rom, project.output)
    assert result["ok"], result
    reopened = MapStudio(project.directory, rom)
    assert reopened.collision(ring) == grid
    assert [door.destination for door in reopened.doors(RETAIL) if door.created] == [maps.title(ring)]
    again = jobs.run_blocking("build", project.directory, rom, project.output)
    assert again["ok"] and again["sha256"] == result["sha256"]
    assert rom.read_bytes() == source


def test_undo_and_redo_step_through_whole_map_edits(studio):
    maps, project, _rom = studio
    empty = source_digest(project.directory)
    arena = maps.create("arena", RETAIL)
    made = source_digest(project.directory)
    base = maps.collision(arena)
    maps.set_collision(arena, grids.with_cells(base, [(5, 5)], not grids.walkable(base, 5, 5)))
    walled = source_digest(project.directory)

    maps.undo()
    assert source_digest(project.directory) == made and maps.collision(arena) == base
    maps.undo()
    assert source_digest(project.directory) == empty and not maps.can_undo
    assert [row for row in maps.maps() if row.new] == []
    maps.redo()
    maps.redo()
    assert source_digest(project.directory) == walled and not maps.can_redo


def test_a_refused_edit_changes_nothing_and_says_why(studio):
    maps, project, _rom = studio
    before = source_digest(project.directory)
    with pytest.raises(CreatorError, match="starts with a letter"):
        maps.create("9 Bad Name", RETAIL)
    with pytest.raises(CreatorError):
        maps.add_door(RETAIL, (296, 152, 312, 216), RETAIL, (60000, 60000))
    with pytest.raises(CreatorError, match="no door"):
        maps.add_door("map:0000", (0, 0, 8, 8), RETAIL, (144, 160))
    assert source_digest(project.directory) == before and not maps.can_undo
