"""ROM-gated proof that an authored collision grid reaches the built image's roots."""

from __future__ import annotations

import pytest

from tests.rom_support import canonical_rom_path, mutable_rom_copy
from tools.creator.model import jobs
from tools.creator.model.project import CreatorProject
from tools.dragonbyte.session import Session
from tools.webfoot import map_collision as collision
from tools.webfoot.formats import map_collision as fmt
from tools.webfoot.map_authoring import apply_authored_maps
from tools.webfoot.project.model import AuthoredMap, AuthoredMaps

pytestmark = pytest.mark.skipif(
    canonical_rom_path() is None, reason="the canonical Buu's Fury ROM is not present"
)

MAP = 33
ROOT = 0x0829B494


def _authored_grid(base: bytes) -> bytes:
    walled = fmt.with_cells(base, [(31, y) for y in range(fmt.GRID_CELLS)], False)
    return fmt.with_cells(walled, [(x, y) for x in range(10, 31) for y in range(14, 19)], True)


def test_authored_grids_are_packed_placed_and_named_by_the_right_roots(tmp_path):
    rom = mutable_rom_copy(tmp_path)
    image = rom.read_bytes()
    session = Session()
    session.open_rom(rom)
    profile = session.profile
    project = CreatorProject.create(rom, tmp_path / "Game", "Game")

    assert collision.root_address(image, profile, MAP) == ROOT
    base = collision.base_grid(image, profile, MAP, fmt.WALK)
    grid = _authored_grid(base)
    collision.set_grid(project.directory, collision.canonical_identity(MAP), fmt.WALK, grid)
    assert collision.read_collision(project.directory) == {"map:0033": {"walk": grid}}

    first = jobs.run_blocking("build", project.directory, rom, project.output)
    assert first["ok"], first
    built = project.output.read_bytes()
    assert fmt.read_grid(built, ROOT, fmt.WALK).grid == grid
    assert fmt.read_grid(built, ROOT, fmt.SECOND).grid == fmt.read_grid(image, ROOT, fmt.SECOND).grid
    assert rom.read_bytes() == image

    apply_authored_maps(project.directory, AuthoredMaps({"arena": AuthoredMap("arena", MAP, 0x17, 0x01)}))
    arena = fmt.with_cells(base, [(40, 20)], False)
    collision.set_grid(project.directory, collision.authored_identity("arena"), fmt.WALK, arena)
    collision.set_grid(project.directory, collision.canonical_identity(MAP), fmt.WALK, None)
    second = jobs.run_blocking("build", project.directory, rom, project.output)
    assert second["ok"], second
    built = project.output.read_bytes()
    assert fmt.read_grid(built, ROOT, fmt.WALK).grid == base
    payload = fmt.encode(arena)
    pointer = (0x08000000 + built.index(payload)).to_bytes(4, "little")
    assert built.count(pointer) == 1
    new_root = 0x08000000 + built.index(pointer) - fmt.WALK_GRID_ROOT_OFFSET
    assert new_root != ROOT
    assert fmt.read_grid(built, new_root, fmt.WALK).grid == arena
    assert fmt.read_grid(built, new_root, fmt.SECOND).grid == fmt.read_grid(image, ROOT, fmt.SECOND).grid

    collision.rename(project.directory, "arena", "ring")
    assert set(collision.read_collision(project.directory)) == {"map-new:ring"}
    stale = jobs.run_blocking("validate", project.directory, rom, project.output)
    assert not stale["ok"] and "ring" in str(stale)


def test_two_maps_on_one_root_cannot_hold_different_collision(tmp_path):
    rom = mutable_rom_copy(tmp_path)
    image = rom.read_bytes()
    session = Session()
    session.open_rom(rom)
    profile = session.profile
    shared = next(index for index in range(452) if collision.sharers(image, profile, index))
    other = collision.sharers(image, profile, shared)[0]
    grid = collision.base_grid(image, profile, shared, fmt.WALK)
    edits = {collision.canonical_identity(shared): {fmt.WALK: grid},
             collision.canonical_identity(other): {fmt.WALK: fmt.with_cells(grid, [(0, 0)], True)}}
    with pytest.raises(collision.MapCollisionEditError, match="same root"):
        collision.materialize_collision(image, profile, edits, {})
