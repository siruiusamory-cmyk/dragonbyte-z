"""The collision grid's cell arithmetic and container round trip, on synthetic data."""

from __future__ import annotations

import struct

import pytest

from tools.webfoot.formats import map_collision as mc
from tools.webfoot.formats.webfoot_lz import unpack

BLOCKED = bytes(mc.GRID_BYTES)


def test_a_cell_is_one_bit_of_the_engines_little_endian_row_words():
    grid = mc.with_cells(BLOCKED, [(37, 2)], True)
    word = struct.unpack_from("<I", grid, 2 * 32 + (37 >> 5) * 4)[0]
    assert word == 1 << (37 & 31)
    assert mc.walkable(grid, 37, 2) and not mc.walkable(grid, 36, 2)
    assert mc.with_cells(grid, [(37, 2)], False) == BLOCKED


def test_the_rectangle_test_matches_the_engine_rule():
    grid = mc.with_cells(BLOCKED, [(x, y) for x in range(4, 8) for y in range(4, 8)], True)
    assert mc.rectangle_allowed(grid, 32, 32, 48, 48)
    assert mc.rectangle_allowed(grid, 32, 32, 64, 64)
    assert not mc.rectangle_allowed(grid, 32, 32, 65, 48)
    assert not mc.rectangle_allowed(grid, 31, 32, 48, 48)
    assert not mc.rectangle_allowed(grid, -1, 32, 48, 48)
    everywhere = bytes([0xFF]) * mc.GRID_BYTES
    assert mc.rectangle_allowed(everywhere, 2032, 2032, 2048, 2048)
    assert not mc.rectangle_allowed(everywhere, 2032, 2032, 2049, 2048)


def test_an_encoded_grid_decodes_to_itself_and_is_read_back_through_a_root():
    grid = mc.with_cells(BLOCKED, [(x, 20) for x in range(256)], True)
    payload = mc.encode(grid)
    assert unpack(payload, 0).data == grid

    image = bytearray(0x400)
    image[0x100:0x100 + len(payload)] = payload
    struct.pack_into("<I", image, 0x40 + mc.WALK_GRID_ROOT_OFFSET, 0x08000100)
    stored = mc.read_grid(bytes(image), 0x08000040, mc.WALK)
    assert stored.grid == grid and stored.pointer_offset == 0x74 and stored.container_offset == 0x100
    with pytest.raises(mc.MapCollisionError):
        mc.read_grid(bytes(image), 0x08000040, mc.SECOND)


def test_wrong_sizes_and_cells_are_refused():
    with pytest.raises(mc.MapCollisionError):
        mc.walkable(b"\0" * 10, 0, 0)
    with pytest.raises(mc.MapCollisionError):
        mc.with_cells(BLOCKED, [(256, 0)], True)
    with pytest.raises(mc.MapCollisionError):
        mc.encode(b"\0" * 8191)
