"""ROM-gated proof that a new map is edited on its own copy and keeps its place."""

from __future__ import annotations

import struct

import pytest

from tests.rom_support import canonical_rom_path, mutable_rom_copy
from tools.creator.model import jobs
from tools.creator.model.project import CreatorProject
from tools.dragonbyte.session import Session
from tools.webfoot import map_authoring as new_maps
from tools.webfoot import map_collision as collision
from tools.webfoot import map_paint, map_resize
from tools.webfoot import map_transition_removal as removal
from tools.webfoot import map_transitions as mt
from tools.webfoot.formats import map_graphics as mg
from tools.webfoot.formats.map_transitions import TransitionArrival, TransitionRegion

pytestmark = pytest.mark.skipif(
    canonical_rom_path() is None, reason="the canonical Buu's Fury ROM is not present"
)

DONOR = 33
ROWS = 452
BASE = 0x08000000


def _u32(image: bytes, at: int) -> int:
    return struct.unpack_from("<I", image, at)[0]


def _root_of(built: bytes, index: int) -> int:
    table = _u32(built, new_maps.BASE_POOL_FILE_OFFSET) - BASE
    return _u32(built, _u32(built, table + index * 0x38 + 0x2C) - BASE) - BASE


def _layer(built: bytes, root: int, slot: int) -> tuple[int, int, list[int]]:
    at = _u32(built, root + mg.ROOT_LAYER_SLOTS[slot]) - BASE
    columns, rows = built[at + mg.LAYER_CHUNK_X_OFFSET], built[at + mg.LAYER_CHUNK_Y_OFFSET]
    cells = [_u32(built, at + mg.LAYER_RECORD_HEADER_BYTES + 4 * cell) for cell in range(columns * rows)]
    return columns, rows, cells


@pytest.fixture
def setup(tmp_path):
    rom = mutable_rom_copy(tmp_path)
    session = Session()
    session.open_rom(rom)
    project = CreatorProject.create(rom, tmp_path / "Game", "Game")
    return rom, rom.read_bytes(), session.profile, project


def test_a_new_map_is_painted_and_resized_without_touching_its_donor(setup):
    rom, image, profile, project = setup
    donor_root = collision.root_address(image, profile, DONOR) - BASE
    new_maps.create_map(project.directory, image, profile, "arena", DONOR)
    content = new_maps.content_directory(project.directory, "arena")

    layer = map_paint.MapPainter(image, profile=profile).target(DONOR).layer(0)
    before = layer.ordinal_of(_layer(image, donor_root, 0)[2][0])
    ordinal = next(choice for choice in range(1, len(layer.vocabulary) + 1) if choice != before)
    assert map_paint.set_layout_cells(content, profile, image, {(DONOR, 0, 0): ordinal})
    resize = map_resize.MapResizer(image, profile=profile).resize(DONOR, 2, 5, 2, 1)
    assert map_resize.set_layer_resize(content, image, resize, profile=profile)

    result = jobs.run_blocking("build", project.directory, rom, project.output)
    assert result["ok"], result
    built = project.output.read_bytes()

    for slot in range(4):
        assert _layer(built, donor_root, slot) == _layer(image, donor_root, slot)
    assert built[donor_root:donor_root + new_maps.ROOT_SIZE] == image[donor_root:donor_root + new_maps.ROOT_SIZE]
    root = _root_of(built, ROWS)
    assert root != donor_root
    columns, rows, cells = _layer(built, root, 0)
    assert (columns, rows) == (4, 2) and cells[0] == layer.pointer(ordinal)
    assert cells[1:] == _layer(image, donor_root, 0)[2][1:]
    assert _layer(built, root, 2)[:2] == (5, 2)
    assert rom.read_bytes() == image


def _doors(built: bytes, root: int) -> list[bytes]:
    count, array = _u32(built, root + 0x40), _u32(built, root + 0x44) - BASE
    return [built[_u32(built, array + 4 * at) - BASE:][:24] for at in range(count)]


def test_doors_join_a_retail_map_and_a_new_map_and_an_inherited_door_is_removed(setup):
    rom, image, profile, project = setup
    donor_root = collision.root_address(image, profile, DONOR) - BASE
    arena = new_maps.create_map(project.directory, image, profile, "arena", DONOR)
    content = new_maps.content_directory(project.directory, "arena")
    template = mt.TransitionIdentity(mt.MapIdentity(DONOR), 0)

    def door(name, destination, region, arrival):
        identity = mt.CreatedTransitionIdentity(mt.MapIdentity(DONOR), name)
        return {identity: mt.TransitionCreation(
            identity, template, mt.MapIdentity(destination),
            TransitionRegion((region[0], region[2]), (region[1], region[3])),
            TransitionArrival(*arrival))}

    assert mt.set_transition_creations(
        project.directory, profile, image, door("to-arena", ROWS, (296, 152, 312, 216), (144, 160)))
    assert mt.set_transition_creations(
        content, profile, image, door("back", DONOR, (112, 152, 120, 216), (200, 160)))
    removal.set_removed(content, DONOR, 0, True)

    result = jobs.run_blocking("build", project.directory, rom, project.output)
    assert result["ok"], result
    built = project.output.read_bytes()

    retail = _doors(built, donor_root)
    assert retail[0] == _doors(image, donor_root)[0] and len(retail) == 2
    assert tuple(retail[1][0x11:0x13]) == arena.key
    assert struct.unpack_from("<4H", retail[1], 8) == (296, 152, 312, 216)
    inside = _doors(built, _root_of(built, ROWS))
    assert len(inside) == 1
    table = _u32(image, new_maps.BASE_POOL_FILE_OFFSET) - BASE
    assert inside[0][0x11:0x13] == image[table + DONOR * 0x38:table + DONOR * 0x38 + 2]
    assert struct.unpack_from("<4H", inside[0], 8) == (112, 152, 120, 216)

    removal.set_removed(project.directory, DONOR, 0, True)
    result = jobs.run_blocking("build", project.directory, rom, project.output)
    assert result["ok"], result
    built = project.output.read_bytes()
    assert [tuple(item[0x11:0x13]) for item in _doors(built, donor_root)] == [arena.key]
    assert rom.read_bytes() == image


def test_adding_and_renaming_maps_never_moves_a_map_already_there(setup):
    rom, image, profile, project = setup
    first = new_maps.create_map(project.directory, image, profile, "zeta", DONOR)
    second = new_maps.create_map(project.directory, image, profile, "alpha", 40)
    assert (first.slot, second.slot) == (0, 1) and first.key != second.key
    ordered = [item.name for item in new_maps.authored_maps(project.directory).ordered()]
    assert ordered == ["zeta", "alpha"]

    new_maps.rename_map(project.directory, "zeta", "arena", canonical_rows=ROWS)
    ordered = [item.name for item in new_maps.authored_maps(project.directory).ordered()]
    assert ordered == ["arena", "alpha"]
    assert new_maps.content_directory(project.directory, "arena").is_dir()
    assert not new_maps.content_directory(project.directory, "zeta").exists()
    with pytest.raises(new_maps.MapAuthoringError, match="already has a map"):
        new_maps.create_map(project.directory, image, profile, "alpha", DONOR)

    result = jobs.run_blocking("build", project.directory, rom, project.output)
    assert result["ok"], result
    built = project.output.read_bytes()
    table = _u32(built, new_maps.BASE_POOL_FILE_OFFSET) - BASE
    assert tuple(built[table + ROWS * 0x38:table + ROWS * 0x38 + 2]) == first.key
    assert tuple(built[table + (ROWS + 1) * 0x38:table + (ROWS + 1) * 0x38 + 2]) == second.key


def test_an_older_project_gains_slots_and_a_failed_rename_changes_nothing(setup):
    from tools.webfoot.project.model import (
        AuthoredMap, AuthoredMaps, ProjectValidationError, write_authored_maps)

    _rom, image, profile, project = setup
    key = new_maps.free_key(image, profile, AuthoredMaps())
    write_authored_maps(project.directory, AuthoredMaps({"cave": AuthoredMap("cave", DONOR, *key)}))
    identity = mt.CreatedTransitionIdentity(mt.MapIdentity(DONOR), "to-cave")
    assert mt.set_transition_creations(project.directory, profile, image, {
        identity: mt.TransitionCreation(
            identity, mt.TransitionIdentity(mt.MapIdentity(DONOR), 0), mt.MapIdentity(ROWS),
            TransitionRegion((296, 312), (152, 216)), TransitionArrival(144, 160))})

    new_maps.create_map(project.directory, image, profile, "arena", DONOR)
    held = new_maps.authored_maps(project.directory)
    assert [(item.name, item.slot) for item in held.ordered()] == [("cave", 0), ("arena", 1)]
    with pytest.raises(ProjectValidationError, match="give every map a slot"):
        AuthoredMaps({**held.maps, "loose": AuthoredMap("loose", DONOR, 0xFE, 1)})

    new_maps.content_directory(project.directory, "taken").mkdir()
    (new_maps.content_directory(project.directory, "taken") / "kept.txt").write_text("x")
    with pytest.raises(new_maps.MapAuthoringError, match="cannot rename"):
        new_maps.rename_map(project.directory, "arena", "taken", canonical_rows=ROWS)
    assert new_maps.authored_maps(project.directory) == held
    assert new_maps.content_directory(project.directory, "arena").is_dir()
