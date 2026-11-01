"""Canonical-ROM evidence for the Legacy of Goku II authored-image route.

LG2-068 lane D, against the real image. The ROM-free companion is
``tests/unit/test_authored_image_lg2_route.py``; this module repeats the three
claims that only the retail bytes can settle:

* the 384-byte window the route is demonstrated in is uniform ``0xFF`` fill in the
  canonical LOG2 image, measured here rather than carried from another lane's report;
* two independent saves of one trivial declared change inside that window produce a
  byte-identical image and an identical digest;
* the emitted derivative reopens through ``verify_authored_image`` and reconstructs
  the canonical image from itself plus its own manifest.

It reads the canonical image and writes only inside pytest's temporary directory, and
it re-hashes the source after every save. It needs ``LOG2_CANONICAL_ROM`` (or a ROM at
the repository-relative default) and skips cleanly without one, so the ``rom`` gate
stays honest on a machine that has no copy.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from tools.webfoot import write as write_sdk
from tools.webfoot.authored_image import save_authored_image, verify_authored_image
from tools.webfoot.capability import Capability, packaged_contract

PROFILE_ID = "legacy_of_goku_ii_usa_rev0_204142e1"

WINDOW_FILE_OFFSET = 0x007FEA01
WINDOW_SIZE = 384

REASON = "LOG2 authored-image route"


def _rom_path() -> Path:
    return Path(
        os.environ.get(
            "LOG2_CANONICAL_ROM", "roms/Dragon Ball Z - Legacy of Goku II (U).gba"
        )
    )


def _profile():
    return packaged_contract(PROFILE_ID, Capability.TEXT_STRINGS)


@pytest.fixture(scope="module")
def canonical_rom() -> tuple[Path, bytes]:
    path = _rom_path()
    if not path.is_file():
        pytest.skip("canonical Legacy of Goku II ROM not configured locally")
    data = path.read_bytes()
    profile = _profile()
    assert hashlib.sha256(data).hexdigest() == profile.sha256, (
        f"{path} is not the canonical image profile {profile.id!r} names"
    )
    return path, data


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _change(data: bytes) -> write_sdk.ByteChange:
    offset = WINDOW_FILE_OFFSET
    return write_sdk.ByteChange(
        offset=offset,
        old=data[offset : offset + 1],
        new=b"\x00",
        owner="lg2:window:0001",
        reason=REASON,
    )


def _save(tmp_path: Path, data: bytes, name: str, canonical_sha256: str):
    source = tmp_path / "source.gba"
    if not source.exists():
        source.write_bytes(data)
    return save_authored_image(
        data,
        source_path=source,
        output_path=tmp_path / name,
        profile_id=PROFILE_ID,
        changes=[_change(data)],
        canonical_sha256=canonical_sha256,
        verify=lambda emitted, changes: tuple(change.new for change in changes),
    )


def test_the_window_is_uniform_fill_in_the_canonical_image(
    canonical_rom: tuple[Path, bytes], tmp_path: Path
) -> None:
    path, data = canonical_rom
    window = data[WINDOW_FILE_OFFSET : WINDOW_FILE_OFFSET + WINDOW_SIZE]
    assert len(window) == WINDOW_SIZE
    assert set(window) == {0xFF}
    assert _digest(path) == _profile().sha256


def test_two_independent_saves_produce_one_image_and_one_digest(
    canonical_rom: tuple[Path, bytes], tmp_path: Path
) -> None:
    path, data = canonical_rom
    canonical_sha256 = _profile().sha256
    first = _save(tmp_path, data, "run-1.gba", canonical_sha256)
    second = _save(tmp_path, data, "run-2.gba", canonical_sha256)
    assert not first.no_op
    assert first.output_sha256 == second.output_sha256
    assert first.output_path.read_bytes() == second.output_path.read_bytes()
    assert first.changed_offsets == (WINDOW_FILE_OFFSET,)
    assert first.manifest_path.read_text(encoding="utf-8") == second.manifest_path.read_text(
        encoding="utf-8"
    )
    assert _digest(path) == canonical_sha256


def test_the_derivative_reopens_and_reconstructs_the_canonical_image(
    canonical_rom: tuple[Path, bytes], tmp_path: Path
) -> None:
    path, data = canonical_rom
    profile = _profile()
    saved = _save(tmp_path, data, "out.gba", profile.sha256)
    emitted = saved.output_path.read_bytes()
    assert emitted[:WINDOW_FILE_OFFSET] == data[:WINDOW_FILE_OFFSET]
    assert emitted[WINDOW_FILE_OFFSET] == 0x00
    assert emitted[WINDOW_FILE_OFFSET + 1 :] == data[WINDOW_FILE_OFFSET + 1 :]

    reopened = verify_authored_image(
        saved.output_path,
        canonical_sha256=profile.sha256,
        canonical_size=profile.size,
        field_bytes=1,
        expected_reason=REASON,
        check_changes=lambda declared, canonical_image, image: tuple(
            change.owner for change in declared
        ),
    )
    assert reopened.profile_id == PROFILE_ID
    assert reopened.canonical_image == data
    assert hashlib.sha256(reopened.canonical_image).hexdigest() == profile.sha256
    assert _digest(path) == profile.sha256
