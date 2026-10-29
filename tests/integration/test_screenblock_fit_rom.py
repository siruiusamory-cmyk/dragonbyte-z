"""The screenblock fit against the retained positive controls.

DRAGONBYTE-FINE-001 G2-2. The fit is believed only after it reproduces the two
numbers an earlier ticket measured independently (fine-research.md R2-1): the
retail map-40 capture at 1019/1024 and the authored post-return capture at
1001/1024 with 23 zero-strip residuals in physical column 31.

Set WEBFOOT_FINE001_CONTROLS to the retained `matched` capture directory of
MAP-CHUNK-AUTHORING-001 to run these; without it, or without the canonical image,
the module skips and says nothing about the fit.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from tests.rom_support import canonical_rom_bytes
from tools.research.screenblock_fit import fit, read_screenblock
from tools.webfoot.formats import map_graphics as mg
from tools.webfoot.packaged import packaged_profile

MAP = 40
LAYER = 1
AUTHORED_SHA256 = "5c51ece754fbe7b3d54b872a94fbe4404dfa4b7e350d3c11f26c5a6c6f0675a0"


def controls() -> Path:
    value = os.environ.get("WEBFOOT_FINE001_CONTROLS")
    if not value:
        pytest.skip("WEBFOOT_FINE001_CONTROLS names no retained capture directory")
    directory = Path(value)
    if not (directory / "retail").is_dir() or not (directory / "authored").is_dir():
        pytest.skip(f"{directory} holds no retail/ and authored/ capture pair")
    return directory


def layer_of(image: bytes):
    profile = packaged_profile()
    reader = mg.MapGraphicsReader(image, profile)
    entry = mg.read_map_entries(reader)[MAP]
    return reader, mg.read_layers(reader, entry.root_address)[LAYER]


def plane(image: bytes) -> tuple[int, ...]:
    reader, layer = layer_of(image)
    return mg.stitch_dominant_entries(reader, layer)


def geometry(image: bytes) -> tuple[int, int]:
    _reader, layer = layer_of(image)
    return layer.chunk_x * 32, layer.chunk_y * 32


def test_the_retail_capture_reproduces_the_earlier_measurement():
    capture = read_screenblock(controls() / "retail" / "snapshot_006_bg1.bin")
    canonical = canonical_rom_bytes()
    values = plane(canonical)
    width, height = geometry(canonical)
    result = fit(capture, values, width, height)
    assert result.origin == (0, 1)
    assert result.matched == 1019
    assert result.holes == 5
    assert result.others == 0
    assert result.settled is True


def test_the_retail_run_stays_in_the_measured_matched_band():
    canonical = canonical_rom_bytes()
    values = plane(canonical)
    width, height = geometry(canonical)
    scores = []
    for index in range(7):
        path = controls() / "retail" / f"snapshot_{index:03d}_bg1.bin"
        if not path.is_file():
            continue
        result = fit(read_screenblock(path), values, width, height)
        if result.origin == (0, 1):
            scores.append(result.matched)
    assert scores, "no retail capture fitted the window origin"
    assert min(scores) >= 1018 and max(scores) <= 1021


def test_the_authored_post_return_capture_reproduces_the_earlier_measurement():
    directory = controls()
    image_path = directory.parent / "derivative" / "chunkauth001-authored.gba"
    if not image_path.is_file():
        pytest.skip(f"the retained authored image {image_path} is absent")
    authored = image_path.read_bytes()
    assert hashlib.sha256(authored).hexdigest() == AUTHORED_SHA256
    values = plane(authored)
    width, height = geometry(authored)
    capture = read_screenblock(directory / "authored" / "snapshot_005_bg1.bin")
    result = fit(capture, values, width, height)
    assert result.origin == (0, 1)
    assert result.matched == 1001
    assert result.holes == 23
    assert result.others == 0
    assert result.settled is True
    assert all(residual.physical_column == 31 for residual in result.residuals)


def test_the_authored_capture_is_not_the_canonical_plane():
    directory = controls()
    image_path = directory.parent / "derivative" / "chunkauth001-authored.gba"
    if not image_path.is_file():
        pytest.skip(f"the retained authored image {image_path} is absent")
    canonical = canonical_rom_bytes()
    values = plane(canonical)
    width, height = geometry(canonical)
    capture = read_screenblock(directory / "authored" / "snapshot_005_bg1.bin")
    result = fit(capture, values, width, height)
    assert result.matched < 700
    assert result.others > 0
    assert result.settled is False
