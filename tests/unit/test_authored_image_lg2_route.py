"""The Legacy of Goku II authored-image route, pinned against its packaged profile.

LG2-068 lane D. The shared transaction in ``tools.webfoot.authored_image`` names no
game, so the question this module answers is what the route does when the profile it
is handed is the packaged Legacy of Goku II one: it saves, it reopens, it reconstructs
the canonical image from the derivative alone, and it leaves its destination untouched
when a save fails.

Nothing here reads a ROM and nothing here writes a declaration into the packaged
catalog: the image is synthetic and the 384-byte window is declared by a *test-local*
profile override (``_declaring_the_window``), which is the point - the route needs no
committed ``free_regions`` entry to work. ``tests/integration/test_authored_image_lg2_rom.py``
is the same demonstration against the real canonical image.

The region is stated once, below, and read from nowhere else: which 384 bytes are
licensed is a capacity question owned by another lane, and a later verdict must be
able to change one constant here rather than a scattered set.
"""

from __future__ import annotations

from dataclasses import replace
import hashlib
import os
from pathlib import Path

import pytest

from tools.webfoot import write as write_sdk
from tools.webfoot.allocation import (
    AllocationKind,
    AllocationRequest,
    InsufficientSpaceError,
    RegionClass,
    StorageModel,
    allocate,
)
from tools.webfoot.authored_image import (
    manifest_path_for,
    save_authored_image,
    verify_authored_image,
)
from tools.webfoot.binary import FileOffset
from tools.webfoot.capability import (
    Capability,
    CapabilityError,
    capabilities,
    packaged_contract,
    require,
)
from tools.webfoot.gba_header import GbaHeader
from tools.webfoot.hashing import RomHashes
from tools.webfoot.layout import AnchorId, FreeRegion, RomRange
from tools.webfoot.profile import ProfileMatch, RomProfile, VerificationStatus
from tools.webfoot.rom import RomIdentification

PROFILE_ID = "legacy_of_goku_ii_usa_rev0_204142e1"

WINDOW_FILE_OFFSET = 0x007FEA01
WINDOW_SIZE = 384

IMAGE_SIZE = 0x800000
BASE = bytes([0xFF]) * IMAGE_SIZE
CANONICAL_SHA256 = hashlib.sha256(BASE).hexdigest()
REASON = "LOG2 authored-image route"


def _profile() -> RomProfile:
    """The packaged Legacy of Goku II profile, read from the package, never a local file."""
    return packaged_contract(PROFILE_ID, Capability.TEXT_STRINGS)


def _declaring_the_window(profile: RomProfile) -> RomProfile:
    """A test-local declaration of the window: constructed here, committed nowhere."""
    region = FreeRegion(
        RomRange(FileOffset(WINDOW_FILE_OFFSET), WINDOW_SIZE),
        "LG2-068-D test-local declaration of the 384-byte window",
    )
    return replace(profile, free_regions=(region,))


def _window_change(offset: int = WINDOW_FILE_OFFSET,
                   base: bytes = BASE) -> write_sdk.ByteChange:
    return write_sdk.ByteChange(
        offset=offset,
        old=base[offset : offset + 1],
        new=b"\x00",
        owner="lg2:window:0001",
        reason=REASON,
    )


def _verify_hook(data: bytes, changes) -> tuple[bytes, ...]:
    return tuple(change.new for change in changes)


def _check_window_changes(declared, canonical_image, data):
    return tuple(change.owner for change in declared)


def _source(tmp_path: Path) -> Path:
    path = tmp_path / "source.gba"
    if not path.exists():
        path.write_bytes(BASE)
    return path


def _save(tmp_path: Path, changes, *, name: str = "out.gba", **overrides):
    arguments = dict(
        source_path=_source(tmp_path),
        output_path=tmp_path / name,
        profile_id=PROFILE_ID,
        changes=changes,
        canonical_sha256=CANONICAL_SHA256,
        verify=_verify_hook,
    )
    arguments.update(overrides)
    return save_authored_image(BASE, **arguments)




def test_two_independent_runs_produce_one_image_and_one_digest(tmp_path: Path) -> None:
    first = _save(tmp_path, [_window_change()], name="run-1.gba")
    second = _save(tmp_path, [_window_change()], name="run-2.gba")
    assert not first.no_op and not second.no_op
    assert first.output_sha256 == second.output_sha256
    assert first.output_size == second.output_size == IMAGE_SIZE
    assert first.output_path.read_bytes() == second.output_path.read_bytes()
    assert first.changed_offsets == second.changed_offsets == (WINDOW_FILE_OFFSET,)
    assert first.manifest_path.read_text(encoding="utf-8") == second.manifest_path.read_text(
        encoding="utf-8"
    )




def test_the_emitted_derivative_reopens_and_reconstructs_the_canonical_image(
    tmp_path: Path,
) -> None:
    saved = _save(tmp_path, [_window_change()])
    data = saved.output_path.read_bytes()
    assert data[:WINDOW_FILE_OFFSET] == BASE[:WINDOW_FILE_OFFSET]
    assert data[WINDOW_FILE_OFFSET] == 0x00
    assert data[WINDOW_FILE_OFFSET + 1 :] == BASE[WINDOW_FILE_OFFSET + 1 :]

    reopened = verify_authored_image(
        saved.output_path,
        canonical_sha256=CANONICAL_SHA256,
        canonical_size=IMAGE_SIZE,
        field_bytes=1,
        expected_reason=REASON,
        check_changes=_check_window_changes,
    )
    assert reopened.profile_id == PROFILE_ID
    assert reopened.output_sha256 == saved.output_sha256
    assert [change.offset for change in reopened.changes] == [WINDOW_FILE_OFFSET]
    assert reopened.changes[0].new == b"\x00"
    assert reopened.canonical_image == BASE
    assert hashlib.sha256(reopened.canonical_image).hexdigest() == CANONICAL_SHA256




def test_a_failed_image_publish_leaves_the_existing_destination_unchanged(
    tmp_path: Path, monkeypatch
) -> None:
    """The publish step itself fails against an existing regular file, not a directory."""
    destination = tmp_path / "out.gba"
    destination.write_bytes(b"the user's previous build")
    real_replace = os.replace

    def refusing_image_publish(source, target):
        if Path(target) == destination:
            raise OSError("destination refused")
        return real_replace(source, target)

    monkeypatch.setattr(os, "replace", refusing_image_publish)
    with pytest.raises(OSError):
        _save(tmp_path, [_window_change()], output_path=destination)
    assert destination.read_bytes() == b"the user's previous build"
    assert not manifest_path_for(destination).exists()
    assert list(tmp_path.glob("*webfoot-partial")) == []




def test_a_capability_the_log2_profile_does_not_declare_is_refused_by_name() -> None:
    """``capability.require`` is the mechanism; the declaration check refuses first."""
    profile = _profile()
    assert capabilities(profile) == (
        Capability.ENEMY_STATS,
        Capability.TEXT_STRINGS,
        Capability.SCRIPTS,
    )
    identification = RomIdentification(
        path=Path("stand-in.gba"),
        size=profile.size,
        hashes=RomHashes(crc32="", md5="", sha1="", sha256=""),
        header=GbaHeader.from_bytes(bytes(0xC0)),
        profile_match=ProfileMatch(
            status=VerificationStatus.VERIFIED,
            profile=profile,
            reason="stand-in match: the declaration check below runs before any byte identity",
        ),
    )
    with pytest.raises(CapabilityError) as excinfo:
        require(identification, Capability.MAP_ENTRIES, subsystem="map access")
    assert str(excinfo.value) == (
        "profile 'legacy_of_goku_ii_usa_rev0_204142e1' does not declare map_entries; "
        "map access is unavailable for this ROM"
    )




def _window_request(size: int = WINDOW_SIZE) -> AllocationRequest:
    return AllocationRequest(
        AnchorId("window-payload"),
        "lg2:window:0001",
        size,
        1,
        kind=AllocationKind.PLACEMENT_BODY,
    )


def test_an_allocation_outside_any_declared_log2_region_is_refused() -> None:
    profile = replace(_profile(), free_regions=(), generated_expansion=None)
    assert StorageModel.from_profile(profile).allocatable_regions() == ()
    with pytest.raises(InsufficientSpaceError) as excinfo:
        allocate(profile, [_window_request()])
    assert str(excinfo.value) == (
        "insufficient declared free space for window-payload (384 bytes, alignment 1, "
        "placement_body, canonical_only)"
    )


def test_the_window_declared_for_the_test_licenses_384_bytes_and_no_more() -> None:
    profile = _declaring_the_window(_profile())
    allocation = allocate(profile, [_window_request()])[0]
    assert (allocation.range.start.value, allocation.range.size) == (
        WINDOW_FILE_OFFSET,
        WINDOW_SIZE,
    )
    assert allocation.storage_class is RegionClass.VERIFIED_FREE
    with pytest.raises(InsufficientSpaceError):
        allocate(profile, [_window_request(WINDOW_SIZE + 1)])


def test_the_packaged_profile_declares_the_reviewed_window() -> None:
    region, = _profile().free_regions
    assert (region.range.start.value, region.range.size) == (
        WINDOW_FILE_OFFSET,
        WINDOW_SIZE,
    )
    assert region.range.start.value + region.range.size == 0x007FEB81


def test_the_committed_declaration_licenses_384_bytes_and_no_more() -> None:
    profile = _profile()
    allocation = allocate(profile, [_window_request()])[0]
    assert (allocation.range.start.value, allocation.range.size) == (
        WINDOW_FILE_OFFSET,
        WINDOW_SIZE,
    )
    assert allocation.storage_class is RegionClass.VERIFIED_FREE
    with pytest.raises(InsufficientSpaceError):
        allocate(profile, [_window_request(WINDOW_SIZE + 1)])


def test_declaring_a_free_region_does_not_grant_a_relocation_capability() -> None:
    profile = _profile()
    assert profile.free_regions
    assert profile.text_strings.relocatable is False
    assert "free_regions" not in {item.value for item in Capability}


def test_the_declaration_adds_no_capability_to_the_profile() -> None:
    """The free region grants nothing; the enemy table is a separate declaration."""
    assert {item.value for item in capabilities(_profile())} == {
        "enemy_stats",
        "text_strings",
        "scripts",
    }
