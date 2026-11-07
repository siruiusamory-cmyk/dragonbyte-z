"""The scene's node plan: derived from the image, bounded, content-free, persisted.

LOG1-BUU-DIALOGUE-BACKPORT-001. The text controller needs two facts per stage that
only the conversation graph knows: whether the stage starts a talk (open once) and
whether its ACTUAL successor is the terminal (close there). Retail computes both at
runtime; this project derives them at build time from the image's own record table
and ships addresses and flags only - no text, art or graph byte.

The pinned record values below were measured from the canonical image by walking
record 66's successors (11 stages, terminals 7 and 10 included, 9 talk stages) and
are re-derived here, so a derivation that starts matching `text + 0x100` windows, or
that assumes `s + 1` is the successor, fails by value.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import struct

import pytest

from tools.webfoot.commands.backport import (
    PLAN_TRANSFORM,
    PRESENTATION_PLAN_LABEL,
    BackportCommandError,
    _FIXUP_RESOURCES,
    _fixup_payload,
    emit_dialogue_plan,
)
from tools.webfoot.profile import RomProfileCatalog
from tools.webfoot.project import (
    PROJECT_FORMAT_VERSION,
    PatchDocument,
    ProjectMeta,
    read_patch_document,
    write_patch_document,
    write_project,
)
from tools.webfoot.scene_edits import (
    FLAG_FINAL,
    FLAG_TALK_START,
    PLAN_HEADER_BYTES,
    PLAN_RECORD_BYTES,
    dialogue_plan,
)

REPO = Path(__file__).resolve().parents[2]
DEFAULT_ROM = REPO / "roms" / "Dragon Ball Z - The Legacy of Goku (USA).gba"
LOG1_SHA256 = "3ba9919e26704b0f5fdc2bfabc7f7a0404c71413761d38abcd94224c3bd4b1b9"
PROFILE_ID = "legacy_of_goku_usa_a3c8c767"
PLAN_SHA256 = "a9271663ee4b8cae17fa038175eb4902e238971b9f0e8735df172bcfbeb9d2d2"

EXPECTED = (
    (0x0816492C, 0x0816496B, FLAG_TALK_START),
    (0x0816496C, 0x08164992, 0),
    (0x08164993, 0x0816499E, 0),
    (0x0816499F, 0x081649C4, 0),
    (0x081649C5, 0x08164A14, 0),
    (0x08164A15, 0x08164A6D, 0),
    (0x08164A6E, 0x08164A79, FLAG_FINAL),
    (0x08164A7A, 0x08164ABA, FLAG_TALK_START),
    (0x08164ABB, 0x08164ABF, FLAG_FINAL),
)


def _rom() -> Path | None:
    value = os.environ.get("WEBFOOT_LOG1_ROM")
    path = Path(value) if value else DEFAULT_ROM
    return path if path.is_file() else None


@pytest.fixture(scope="module")
def rom_path() -> Path:
    path = _rom()
    if path is None:
        pytest.skip("canonical LOG1 image not present locally")
    if hashlib.sha256(path.read_bytes()).hexdigest() != LOG1_SHA256:
        pytest.skip("the local LOG1 image is not the pinned one")
    return path


@pytest.fixture(scope="module")
def image() -> bytes:
    path = _rom()
    if path is None:
        pytest.skip("canonical LOG1 image not present locally")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != LOG1_SHA256:
        pytest.skip("the local LOG1 image is not the pinned one")
    return data


@pytest.fixture(scope="module")
def profile():
    catalog = RomProfileCatalog.load(REPO / "config" / "roms.yaml")
    return next(item for item in catalog.profiles if item.id == PROFILE_ID)


def _records(plan: bytes) -> tuple[int, int, tuple[tuple[int, int, int], ...]]:
    count, reserved = struct.unpack_from("<HH", plan, 0)
    records = tuple(
        struct.unpack_from("<IIBBH", plan, PLAN_HEADER_BYTES + PLAN_RECORD_BYTES * index)[:3]
        for index in range(count))
    return count, reserved, records


def test_the_plan_is_the_bounded_stage_list(image: bytes, profile) -> None:
    plan = dialogue_plan(image, profile)
    count, reserved, records = _records(plan)
    assert (count, reserved) == (len(EXPECTED), 0)
    assert PLAN_RECORD_BYTES % 4 == 0, "a u32 at an unaligned stride rotates on ARMv4T"
    assert len(plan) == PLAN_HEADER_BYTES + count * PLAN_RECORD_BYTES == 112
    assert records == EXPECTED
    for index in range(count):
        tail = plan[PLAN_HEADER_BYTES + PLAN_RECORD_BYTES * index + 9:
                    PLAN_HEADER_BYTES + PLAN_RECORD_BYTES * (index + 1)]
        assert tail == bytes(PLAN_RECORD_BYTES - 9), index


def test_the_plan_carries_no_proprietary_content(image: bytes, profile) -> None:
    plan = dialogue_plan(image, profile)
    assert hashlib.sha256(plan).hexdigest() == PLAN_SHA256
    printable = longest_printable_run(plan)
    assert printable < 6, f"{printable}-byte printable run: this is metadata, not text"
    for start, end, _flags in EXPECTED:
        assert start < end <= 0x0A000000
        assert end - start <= 4096


def test_the_fixup_binding_is_closed_and_data(image: bytes, profile) -> None:
    assert _FIXUP_RESOURCES["lifecycle_table"] == ("plan", None, None)
    assert _fixup_payload("plan", None) == PRESENTATION_PLAN_LABEL
    assert PLAN_TRANSFORM == "scene-node-metadata/v1"


def test_the_plan_persists_once_and_refuses_a_second_copy(image: bytes, profile,
                                                          tmp_path: Path) -> None:
    directory = tmp_path / "project"
    write_project(
        directory,
        ProjectMeta(
            format_version=PROJECT_FORMAT_VERSION, profile_id=profile.id,
            game=profile.game, base_rom_sha256=LOG1_SHA256,
            base_rom_size=len(image), name="plan-test"),
        enemies=[], characters=[],
    )
    write_patch_document(directory, PatchDocument())
    entry = emit_dialogue_plan(directory, image, profile)
    expected = dialogue_plan(image, profile)
    assert entry.label == PRESENTATION_PLAN_LABEL
    assert entry.source_class == "new" and entry.code is False
    assert (entry.size, entry.alignment) == (len(expected), 4)
    assert (directory / entry.file).read_bytes() == expected
    reloaded = read_patch_document(directory).payload(PRESENTATION_PLAN_LABEL)
    assert (reloaded.sha256, reloaded.size) == (
        hashlib.sha256(expected).hexdigest(), len(expected))
    with pytest.raises(BackportCommandError, match="already holds"):
        emit_dialogue_plan(directory, image, profile)


def longest_printable_run(data: bytes) -> int:
    longest = current = 0
    for byte in data:
        if 0x20 <= byte <= 0x7E:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def test_a_rehashed_tampered_plan_is_refused_by_validate_and_build(
        image: bytes, profile, rom_path: Path, tmp_path: Path) -> None:
    """A project-consistent forgery must still fail: the table is re-derived.

    The negative flips record 0's talk-start flag and moves its end pointer, then
    rewrites the payload's declared SHA256 so the document agrees with itself - the
    exact way a digest-only provenance check is laundered. Validation re-derives the
    table from the image's graph, reports the mismatch, and the build refuses before
    it writes any output.
    """
    import dataclasses

    from tools.webfoot.build import (
        ProjectValidationError,
        build_project,
        validate_project,
    )
    from tools.webfoot.project import ProjectFormatError

    directory = tmp_path / "project"
    write_project(
        directory,
        ProjectMeta(
            format_version=PROJECT_FORMAT_VERSION, profile_id=profile.id,
            game=profile.game, base_rom_sha256=LOG1_SHA256,
            base_rom_size=len(image), name="plan-tamper"),
        enemies=[], characters=[],
    )
    write_patch_document(directory, PatchDocument())
    entry = emit_dialogue_plan(directory, image, profile)
    forged = bytearray((directory / entry.file).read_bytes())
    forged[PLAN_HEADER_BYTES + 8] ^= FLAG_TALK_START
    forged[PLAN_HEADER_BYTES + 4:PLAN_HEADER_BYTES + 8] = (
        0x0816492C + 0x1000).to_bytes(4, "little")
    (directory / entry.file).write_bytes(bytes(forged))
    rehashed = dataclasses.replace(entry, sha256=hashlib.sha256(bytes(forged)).hexdigest())
    write_patch_document(directory, PatchDocument(
        (rehashed,), (), (), ()))

    problems = validate_project(directory, rom_path, _catalog()).problems
    assert any("lifecycle table" in problem for problem in problems), problems
    output = tmp_path / "refused.gba"
    with pytest.raises(ProjectValidationError, match="lifecycle table"):
        build_project(directory, rom_path, output, _catalog())
    assert not output.exists(), "a refused build must write no image"


def _catalog() -> RomProfileCatalog:
    return RomProfileCatalog.load(REPO / "config" / "roms.yaml")
