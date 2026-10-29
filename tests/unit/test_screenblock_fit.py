"""Synthetic planes for the screenblock fit: origin recovery and residual classes.

DRAGONBYTE-FINE-001 G2-2. No ROM and no capture are needed here; the retained
positive controls are the integration member's job.
"""

from __future__ import annotations

import struct

import pytest

from tools.research.screenblock_fit import (
    ENTRIES,
    WINDOW,
    Residual,
    capture_from_plane,
    classify,
    describe,
    fit,
    rank,
    read_plane,
    read_screenblock,
)

WIDTH = 64
HEIGHT = 64


def plane_values(seed: int = 1) -> tuple[int, ...]:
    values = []
    state = seed
    for _ in range(WIDTH * HEIGHT):
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        values.append(((state >> 8) & 0x03FF) or 1)
    return tuple(values)


def hole_positions(capture: list[int], rows) -> list[int]:
    for row in rows:
        capture[row * WINDOW + (WINDOW - 1)] = 0
    return list(rows)


def test_a_capture_from_a_known_origin_fits_at_that_origin():
    plane = plane_values()
    capture = capture_from_plane(plane, WIDTH, HEIGHT, (7, 13))
    result = fit(capture, plane, WIDTH, HEIGHT)
    assert result.origin == (7, 13)
    assert result.matched == ENTRIES
    assert result.residuals == ()
    assert classify(result) == "exact"


def test_the_window_is_fitted_not_assumed():
    plane = plane_values(seed=7)
    capture = capture_from_plane(plane, WIDTH, HEIGHT, (0, 9))
    assert fit(capture, plane, WIDTH, HEIGHT).origin == (0, 9)
    at_origin = fit(capture, plane, WIDTH, HEIGHT).matched
    assert at_origin == ENTRIES
    assert rank(capture, plane, WIDTH, HEIGHT)[1].matched < at_origin


def test_the_fold_is_circular_on_both_axes():
    plane = plane_values(seed=3)
    capture = capture_from_plane(plane, WIDTH, HEIGHT, (0, 32))
    result = fit(capture, plane, WIDTH, HEIGHT)
    assert result.origin == (0, 32)
    assert result.matched == ENTRIES
    assert capture[0] == plane[32 * WIDTH]


def test_zero_holes_in_the_last_physical_column_are_their_own_class():
    plane = plane_values(seed=11)
    capture = list(capture_from_plane(plane, WIDTH, HEIGHT, (0, 0)))
    rows = hole_positions(capture, (0, 5, 19))
    result = fit(tuple(capture), plane, WIDTH, HEIGHT)
    assert result.origin == (0, 0)
    assert result.matched == ENTRIES - len(rows)
    assert result.holes == len(rows)
    assert result.others == 0
    assert result.settled is True
    assert classify(result) == "holes_only"
    assert [residual.physical_row for residual in result.residuals] == rows
    assert all(residual.physical_column == WINDOW - 1 for residual in result.residuals)


def test_a_zero_outside_the_last_column_is_not_a_hole():
    plane = plane_values(seed=13)
    capture = list(capture_from_plane(plane, WIDTH, HEIGHT, (2, 2)))
    capture[3 * WINDOW + 4] = 0
    result = fit(tuple(capture), plane, WIDTH, HEIGHT)
    assert result.matched == ENTRIES - 1
    assert result.holes == 0
    assert result.others == 1
    assert result.settled is False
    assert classify(result) == "contradicted"


def test_a_different_entry_at_the_target_position_is_contradicted():
    plane = plane_values(seed=17)
    capture = list(capture_from_plane(plane, WIDTH, HEIGHT, (0, 1)))
    index = 12 * WINDOW + 5
    capture[index] = (capture[index] + 1) & 0x03FF
    result = fit(tuple(capture), plane, WIDTH, HEIGHT)
    assert result.others == 1
    assert result.residuals[0].physical_row == 12
    assert result.residuals[0].physical_column == 5
    assert result.residuals[0].logical_x == 5
    assert result.residuals[0].logical_y == 12


def test_the_runner_up_is_reported_from_a_different_origin():
    plane = plane_values(seed=19)
    capture = capture_from_plane(plane, WIDTH, HEIGHT, (4, 4))
    ranked = rank(capture, plane, WIDTH, HEIGHT)
    assert ranked[0].matched == ENTRIES
    assert ranked[1].origin != ranked[0].origin
    assert describe(capture, plane, WIDTH, HEIGHT).startswith(
        "origin=(4,4) matched=1024/1024 runner_up="
    )


def test_rank_covers_every_admissible_origin():
    plane = plane_values(seed=23)
    capture = capture_from_plane(plane, WIDTH, HEIGHT, (0, 0))
    assert len(rank(capture, plane, WIDTH, HEIGHT)) == (
        (WIDTH - WINDOW + 1) * (HEIGHT - WINDOW + 1)
    )


def test_a_capture_of_the_wrong_length_is_refused():
    plane = plane_values()
    with pytest.raises(ValueError):
        fit((0,) * (ENTRIES - 1), plane, WIDTH, HEIGHT)


def test_a_plane_of_the_wrong_length_is_refused():
    capture = (0,) * ENTRIES
    with pytest.raises(ValueError):
        fit(capture, (0,) * (WIDTH * HEIGHT - 1), WIDTH, HEIGHT)


def test_a_plane_smaller_than_the_window_is_refused():
    with pytest.raises(ValueError):
        fit((0,) * ENTRIES, (0,) * 16, 4, 4)


def test_the_residual_hole_rule_names_what_it_excludes():
    residual = Residual(0, WINDOW - 1, 31, 0, 0, 5)
    assert residual.hole is True
    assert Residual(0, 0, 0, 0, 0, 5).hole is False
    assert Residual(0, WINDOW - 1, 31, 0, 7, 5).hole is False


def test_a_captured_block_is_read_as_halfwords(tmp_path):
    values = tuple((index * 37) & 0xFFFF for index in range(ENTRIES))
    path = tmp_path / "block.bin"
    path.write_bytes(struct.pack(f"<{ENTRIES}H", *values))
    assert read_screenblock(path) == values
    (tmp_path / "short.bin").write_bytes(b"\x00" * 8)
    with pytest.raises(ValueError):
        read_screenblock(tmp_path / "short.bin")


def test_a_stored_plane_is_read_as_halfwords(tmp_path):
    values = plane_values(seed=29)
    path = tmp_path / "plane.bin"
    path.write_bytes(struct.pack(f"<{len(values)}H", *values))
    assert read_plane(path) == values
    (tmp_path / "odd.bin").write_bytes(b"\x00" * 3)
    with pytest.raises(ValueError):
        read_plane(tmp_path / "odd.bin")
