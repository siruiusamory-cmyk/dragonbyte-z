"""Fit a live BG screenblock capture to a map layer's logical screen-entry plane.

The engine fills a 32x32 screenblock from a map layer that can be wider and taller
than 32 tiles, and it folds the logical position into the block with `& 31` on both
axes (measured: DRAGONBYTE-FINE-001 g1, runtime-report.md G1-3, where physical rows
0..8 carry logical rows 32..40 at origin (0,9)). A comparison that folds one axis
only, or that assumes the window starts at the plane origin, reports a correct
capture as a mismatch: the same capture then reads 739/1024 against the plane it
actually draws.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

WINDOW = 32
ENTRIES = WINDOW * WINDOW


@dataclass(frozen=True, slots=True)
class Residual:
    """One physical screenblock entry that disagrees with the plane."""

    physical_row: int
    physical_column: int
    logical_x: int
    logical_y: int
    captured: int
    expected: int

    @property
    def hole(self) -> bool:
        """The engine's zero hole: an empty entry in the block's last column."""
        return self.captured == 0 and self.physical_column == WINDOW - 1


@dataclass(frozen=True, slots=True)
class Fit:
    origin: tuple[int, int]
    matched: int
    residuals: tuple[Residual, ...]

    @property
    def total(self) -> int:
        return ENTRIES

    @property
    def holes(self) -> int:
        return sum(1 for residual in self.residuals if residual.hole)

    @property
    def others(self) -> int:
        return len(self.residuals) - self.holes

    @property
    def settled(self) -> bool:
        """Every disagreement is an engine hole rather than a different entry."""
        return self.others == 0


def read_screenblock(path: str | Path) -> tuple[int, ...]:
    """Read a captured block as 1024 little-endian halfwords."""
    data = Path(path).read_bytes()
    if len(data) != ENTRIES * 2:
        raise ValueError(
            f"a screenblock capture is {ENTRIES * 2} bytes; got {len(data)}"
        )
    return tuple(data[index] | (data[index + 1] << 8)
                 for index in range(0, len(data), 2))


def read_plane(path: str | Path) -> tuple[int, ...]:
    """Read a stored logical plane as little-endian halfwords."""
    data = Path(path).read_bytes()
    if len(data) % 2:
        raise ValueError(f"a plane holds whole halfwords; got {len(data)} bytes")
    return tuple(data[index] | (data[index + 1] << 8)
                 for index in range(0, len(data), 2))


def capture_from_plane(plane: tuple[int, ...], width: int, height: int,
                       origin: tuple[int, int]) -> tuple[int, ...]:
    """The 32x32 block the engine folds `plane` into at `origin`."""
    ox, oy = origin
    if not 0 <= ox <= width - WINDOW or not 0 <= oy <= height - WINDOW:
        raise ValueError(f"origin {origin} is outside a {width}x{height} plane")
    values = [0] * ENTRIES
    for row in range(WINDOW):
        logical_y = oy + row
        for column in range(WINDOW):
            logical_x = ox + column
            values[(logical_y % WINDOW) * WINDOW + (logical_x % WINDOW)] = (
                plane[logical_y * width + logical_x]
            )
    return tuple(values)


def _score(capture: tuple[int, ...], plane: tuple[int, ...], width: int,
           height: int, origin: tuple[int, int]) -> Fit:
    ox, oy = origin
    residuals: list[Residual] = []
    matched = 0
    for row in range(WINDOW):
        logical_y = oy + row
        physical_y = logical_y % WINDOW
        for column in range(WINDOW):
            logical_x = ox + column
            physical_x = logical_x % WINDOW
            expected = plane[logical_y * width + logical_x]
            captured = capture[physical_y * WINDOW + physical_x]
            if expected == captured:
                matched += 1
            else:
                residuals.append(Residual(physical_y, physical_x, logical_x,
                                          logical_y, captured, expected))
    return Fit(origin=origin, matched=matched, residuals=tuple(residuals))


def rank(capture: tuple[int, ...], plane: tuple[int, ...], width: int,
         height: int) -> tuple[Fit, ...]:
    """Every admissible origin's fit, best first, ties broken by origin order."""
    if len(capture) != ENTRIES:
        raise ValueError(f"a capture is {ENTRIES} entries; got {len(capture)}")
    if len(plane) != width * height:
        raise ValueError(
            f"a {width}x{height} plane holds {width * height} entries; got {len(plane)}"
        )
    if width < WINDOW or height < WINDOW:
        raise ValueError(f"a {width}x{height} plane cannot hold a {WINDOW}x{WINDOW} window")
    fits = [
        _score(capture, plane, width, height, (ox, oy))
        for oy in range(height - WINDOW + 1)
        for ox in range(width - WINDOW + 1)
    ]
    fits.sort(key=lambda fit: (-fit.matched, fit.origin))
    return tuple(fits)


def fit(capture: tuple[int, ...], plane: tuple[int, ...], width: int,
        height: int) -> Fit:
    """The best origin for a capture against a plane."""
    return rank(capture, plane, width, height)[0]


def describe(capture: tuple[int, ...], plane: tuple[int, ...], width: int,
             height: int) -> str:
    """One line per comparison: origin, matched count, runner-up, residual classes."""
    ranked = rank(capture, plane, width, height)
    best = ranked[0]
    runner_up = ranked[1].matched if len(ranked) > 1 else None
    return (
        f"origin=({best.origin[0]},{best.origin[1]}) "
        f"matched={best.matched}/{best.total} runner_up={runner_up} "
        f"holes={best.holes} others={best.others}"
    )


def classify(fit_result: Fit) -> str:
    """The residual class a PASS/FAIL bar is written against."""
    if fit_result.matched == fit_result.total:
        return "exact"
    if fit_result.others:
        return "contradicted"
    return "holes_only"
