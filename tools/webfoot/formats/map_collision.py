"""Buu's Fury map collision grids: the engine's own walkability bitmaps.

Every map root names two Webfoot containers. Each decodes to 8192 bytes: 256
rows of 32 bytes, one bit per 8x8 pixel cell. Cell ``(x, y)`` is bit ``x & 31``
of the little-endian word at ``y * 32 + (x >> 5) * 4``, which is bit ``x & 7`` of
the byte at ``y * 32 + (x >> 3)``. A set bit means a mover may stand there; a
clear bit blocks it. The engine's test routine reads exactly
this and also blocks any rectangle outside 0..2048 pixels.

The grid at root ``+0x34`` guards character movement: the player's position
commit tests it before every write. The grid at root ``+0x38``
is tested by 22 other call sites whose movers are not yet named, so it is called
the second grid here and nothing more.

Evidence: DRAGONBYTE-Z-APP-003, runtime trace and an authored grid obeyed by the
running engine.
"""

from __future__ import annotations

from dataclasses import dataclass
import struct

from ..binary import GBA_ROM_BASE
from .webfoot_lz import ContainerError, pack, unpack, validate_retail_termination

CELL_PIXELS = 8
GRID_CELLS = 256
ROW_BYTES = GRID_CELLS // 8
GRID_BYTES = GRID_CELLS * ROW_BYTES
WALK_GRID_ROOT_OFFSET = 0x34
SECOND_GRID_ROOT_OFFSET = 0x38
WALK = "walk"
SECOND = "second"
ROOT_OFFSETS = {WALK: WALK_GRID_ROOT_OFFSET, SECOND: SECOND_GRID_ROOT_OFFSET}


class MapCollisionError(ValueError):
    """A grid, cell or root that is not what the engine's collision reader takes."""


def _check_cell(x: int, y: int) -> None:
    if type(x) is not int or type(y) is not int or not (0 <= x < GRID_CELLS and 0 <= y < GRID_CELLS):
        raise MapCollisionError(f"cell ({x!r}, {y!r}) is outside the {GRID_CELLS}x{GRID_CELLS} grid")


def _check_grid(grid: bytes) -> None:
    if not isinstance(grid, (bytes, bytearray)) or len(grid) != GRID_BYTES:
        raise MapCollisionError(f"a collision grid is exactly {GRID_BYTES} bytes")


def walkable(grid: bytes, x: int, y: int) -> bool:
    _check_grid(grid)
    _check_cell(x, y)
    return bool(grid[y * ROW_BYTES + (x >> 3)] >> (x & 7) & 1)


def with_cells(grid: bytes, cells, allowed: bool) -> bytes:
    """A copy of the grid with every listed (x, y) cell made walkable or blocked."""
    _check_grid(grid)
    edited = bytearray(grid)
    for x, y in cells:
        _check_cell(x, y)
        index, bit = y * ROW_BYTES + (x >> 3), 1 << (x & 7)
        edited[index] = edited[index] | bit if allowed else edited[index] & ~bit
    return bytes(edited)


def rectangle_allowed(grid: bytes, left: int, top: int, right: int, bottom: int) -> bool:
    """The engine's own rectangle test, in pixels, as the engine performs it."""
    _check_grid(grid)
    limit = GRID_CELLS * CELL_PIXELS
    if left < 0 or top < 0 or right > limit or bottom > limit:
        return False
    for y in range(top >> 3, (bottom + 7) >> 3):
        for x in range(left >> 3, (right + 7) >> 3):
            if not grid[y * ROW_BYTES + (x >> 3)] >> (x & 7) & 1:
                return False
    return True


def encode(grid: bytes) -> bytes:
    """The grid as a container the retail loader accepts."""
    _check_grid(grid)
    payload = pack(bytes(grid))
    try:
        validate_retail_termination(payload)
    except ContainerError as exc:
        raise MapCollisionError(f"the packed grid would not load in the game: {exc}") from exc
    return payload


@dataclass(frozen=True, slots=True)
class StoredGrid:
    """One grid as the image holds it: where its pointer is and what it decodes to."""

    which: str
    pointer_offset: int
    container_offset: int
    packed_end: int
    grid: bytes


def read_grid(image: bytes, root_address: int, which: str) -> StoredGrid:
    """Decode one of a map root's two grids, or refuse a root that has none."""
    if which not in ROOT_OFFSETS:
        raise MapCollisionError(f"there is no collision grid called {which!r}")
    pointer_offset = root_address - GBA_ROM_BASE + ROOT_OFFSETS[which]
    if not 0 <= pointer_offset <= len(image) - 4:
        raise MapCollisionError(f"map root {root_address:#010x} lies outside the image")
    pointer = struct.unpack_from("<I", image, pointer_offset)[0]
    if not GBA_ROM_BASE <= pointer < GBA_ROM_BASE + len(image):
        raise MapCollisionError(
            f"map root {root_address:#010x} names no {which} collision grid ({pointer:#010x})"
        )
    try:
        container = unpack(image, pointer - GBA_ROM_BASE)
    except ContainerError as exc:
        raise MapCollisionError(f"the {which} collision grid does not decode: {exc}") from exc
    if len(container.data) != GRID_BYTES:
        raise MapCollisionError(
            f"the {which} collision grid decodes to {len(container.data)} bytes, not {GRID_BYTES}"
        )
    return StoredGrid(which, pointer_offset, pointer - GBA_ROM_BASE, container.packed_end, container.data)
