"""ROM-gated proof: a LOG1 project reaches the image through the ONE build plan.

LOG1-BUU-DIALOGUE-BACKPORT-001. On the canonical Legacy of Goku image this proves
the two authored domains the SDK now carries for it:

* the seven scene slots (raw byte writes, bounded by the image's own slot lengths);
* allocated payloads plus their fixups (the new patch document).

and the four refusals that keep the admission narrow. The canonical image is read
only; every build writes a private temporary output and the original digest is
re-asserted at the end.

Skips cleanly when the image is absent.
"""

from __future__ import annotations

import dataclasses
import hashlib
import os
from pathlib import Path
import struct
from types import SimpleNamespace

import pytest

from tools.dragonbyte.rawbytes import RawEdits, write_raw_document
from tools.webfoot.commands.backport import donor_convert
from tools.webfoot.build import BuildError, build_project, validate_project
from tools.webfoot.profile import PatchSite, RomProfileCatalog
from tools.webfoot.project import (
    PROJECT_FORMAT_VERSION,
    PatchDocumentError,
    ProjectMeta,
    ProjectValidationError,
    decode_relative_thumb,
    read_patch_document,
    write_project,
)
from tools.webfoot.scene_edits import SceneTextError, plan_text_writes, read_scene

LOG1_SHA256 = "3ba9919e26704b0f5fdc2bfabc7f7a0404c71413761d38abcd94224c3bd4b1b9"
PROFILE_ID = "legacy_of_goku_usa_a3c8c767"
REPO = Path(__file__).resolve().parents[2]
DEFAULT_ROM = REPO / "roms" / "Dragon Ball Z - The Legacy of Goku (USA).gba"

LINES = {
    0: "Goku! You're looking stronger every time I see you!",
    1: "Thanks! I've been training nonstop!",
    2: "I can tell!",
    3: "So what've you been up to lately?",
    4: "Oh, you know me. Sun, sand, and a growing pile of magazines. Or so I thought!",
    5: "A few went missing! If you find any while you're out, bring them back to me, will you?",
    6: "You got it!",
}

PUBLISH_SITE = 0x530E
PUBLISH_GUARD = "fdf7a4f8"
DONOR_SHA256 = "940ad5f01db4465b8877dfe739510cbf34f4ea3d390f3df13519808bc36f059e"


def _rom_path() -> Path | None:
    value = os.environ.get("WEBFOOT_LOG1_ROM")
    if value and Path(value).is_file():
        return Path(value)
    return DEFAULT_ROM if DEFAULT_ROM.is_file() else None


@pytest.fixture(scope="module")
def rom() -> Path:
    path = _rom_path()
    if path is None:
        pytest.skip("canonical Legacy of Goku image not present locally")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != LOG1_SHA256:
        pytest.skip(f"local LOG1 image is not canonical (sha256 {digest})")
    return path


def _catalog() -> RomProfileCatalog:
    return RomProfileCatalog.load(REPO / "config" / "roms.yaml")


def _project(tmp_path: Path, rom: Path) -> Path:
    directory = tmp_path / "project"
    write_project(
        directory,
        ProjectMeta(
            format_version=PROJECT_FORMAT_VERSION,
            profile_id=PROFILE_ID,
            game="legacy_of_goku",
            base_rom_sha256=LOG1_SHA256,
            base_rom_size=rom.stat().st_size,
            name="log1-buu-dialogue-backport-001",
        ),
        enemies=[],
        characters=[],
    )
    return directory


def _bf_path() -> Path | None:
    value = os.environ.get("WEBFOOT_BF_ROM")
    if value and Path(value).is_file():
        return Path(value)
    default = REPO / "roms" / "Dragon Ball Z - Buu's Fury (U).gba"
    return default if default.is_file() else None


@pytest.fixture(scope="module")
def bf() -> Path:
    path = _bf_path()
    if path is None:
        pytest.skip("canonical Buu's Fury image not present locally")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != DONOR_SHA256:
        pytest.skip(f"local Buu's Fury image is not canonical (sha256 {digest})")
    return path


def test_donor_convert_builds_one_shared_bank_and_leaves_the_document_stable(
    rom: Path, bf: Path, tmp_path: Path
) -> None:
    """Two runs of the same command must not move a payload or change a byte."""
    project = _project(tmp_path, rom)
    args = SimpleNamespace(
        project=project,
        donor=bf,
        name=["Master Roshi", "Goku"],
        slot=[97, 57],
        box=True,
        palette_label="bf-obj-palette-low128",
    )
    first = donor_convert(args)
    document = project / "patch" / "edits.toml"
    written = document.read_bytes()
    assert donor_convert(args) == first
    assert document.read_bytes() == written

    emitted = {item["label"]: item for item in first["payloads"]}
    assert emitted["bf-obj-palette-low128"]["payload_sha256"] == (
        "c3f7c6058ae1aad44fc5e90f12442cef664172fafd27b8d4b94c6267ddfe83b3")
    assert emitted["master-roshi"]["payload_sha256"] == (
        "a7d194888d2797a1a0b9cea054a71831cf2e388a57bef5669be529d345dd9a47")
    assert emitted["goku"]["payload_sha256"] == (
        "85a31e9d745b07fd7912fd5daa6d0002b8c18debf92c217a1c055b1e3073d874")
    assert emitted["bf-box"]["payload_sha256"] == (
        "9738c017fd0784fac5c30d732d3a28e584bbae230bd5eaf5dff09c304e1225d9")

    bank = (project / "assets" / "bf-obj-palette-low128.bin").read_bytes()
    entries = len(bank) // 2
    shared = struct.unpack(f"<{entries}H", bank)
    assert entries == emitted["bf-obj-palette-low128"]["entries"] < 128
    assert shared[0] == 0x0000
    assert shared[1] == 0x0000
    assert emitted["bf-obj-palette-low128"]["opaque_slots_used"] <= 127

    manifest_payloads = [
        payload for payload in read_patch_document(project).payloads
    ]
    assert [payload.label for payload in manifest_payloads] == [
        "bf-obj-palette-low128", "master-roshi", "goku", "bf-box"]


def _assert_canonical_unchanged(rom: Path) -> None:
    assert hashlib.sha256(rom.read_bytes()).hexdigest() == LOG1_SHA256




def test_the_scene_resolves_from_the_image_and_every_slot_is_full(rom: Path):
    profile = next(p for p in _catalog().profiles if p.id == PROFILE_ID)
    scene = read_scene(rom.read_bytes(), profile)
    assert [node.index for node in scene.nodes] == [0, 1, 2, 3, 4, 5, 6]
    assert [node.capacity for node in scene.nodes] == [63, 38, 11, 37, 79, 88, 11]
    assert [node.next_node for node in scene.nodes] == [1, 2, 3, 4, 5, 6, 7]


def test_the_seven_authored_lines_change_only_their_own_slots(rom: Path, tmp_path: Path):
    profile = next(p for p in _catalog().profiles if p.id == PROFILE_ID)
    image = rom.read_bytes()
    project = _project(tmp_path, rom)
    writes = plan_text_writes(image, profile, LINES)
    write_raw_document(project, RawEdits(bytes_by_offset=writes))

    output = tmp_path / "out.gba"
    result = build_project(project, rom, output, _catalog())
    emitted = output.read_bytes()

    assert len(writes) == 7
    differing = [index for index, (before, after) in enumerate(zip(image, emitted))
                 if before != after]
    allowed = {offset + index for offset, new in writes.items()
               for index in range(len(new))}
    assert set(differing) <= allowed
    for node in read_scene(image, profile).nodes:
        written = emitted[node.text_offset:node.text_offset + node.capacity]
        expected = LINES[node.index].encode("ascii").ljust(node.capacity, b" ")
        assert written == expected
        assert emitted[node.text_offset + node.capacity] == 0
    assert result.manifest.patch_payloads == ()
    _assert_canonical_unchanged(rom)


def test_an_overlong_line_is_refused_before_any_write(rom: Path):
    profile = next(p for p in _catalog().profiles if p.id == PROFILE_ID)
    with pytest.raises(SceneTextError, match="does not fit"):
        plan_text_writes(rom.read_bytes(), profile, {2: "I can tell! And more words."})


def test_a_raw_write_outside_the_declared_scene_is_refused(rom: Path, tmp_path: Path):
    project = _project(tmp_path, rom)
    write_raw_document(project, RawEdits(bytes_by_offset={0x100000: b"\xAA"}))
    with pytest.raises(ProjectValidationError, match="outside every declared scene slot"):
        build_project(project, rom, tmp_path / "out.gba", _catalog())
    assert not (tmp_path / "out.gba").exists()
    _assert_canonical_unchanged(rom)




def test_a_payload_lands_in_a_declared_window_with_its_origin_in_the_manifest(
        rom: Path, tmp_path: Path):
    image = rom.read_bytes()
    profile = next(p for p in _catalog().profiles if p.id == PROFILE_ID)
    project = _project(tmp_path, rom)
    assets = project / "assets"
    assets.mkdir()
    holder = bytes(16)
    portrait = bytes(range(32))
    (assets / "holder.bin").write_bytes(holder)
    (assets / "portrait.bin").write_bytes(portrait)
    (project / "patch").mkdir()
    (project / "patch" / "edits.toml").write_text(
        "[[payload]]\n"
        'label = "a-compat"\n'
        'file = "assets/holder.bin"\n'
        'source_class = "new"\n'
        'origin_note = "compatibility block, authored here"\n'
        f'sha256 = "{hashlib.sha256(holder).hexdigest()}"\n'
        'transform = "log1-compat/v1"\n'
        "alignment = 4\n"
        "code = true\n\n"
        "[[payload]]\n"
        'label = "b-portrait"\n'
        'file = "assets/portrait.bin"\n'
        'source_class = "transferred"\n'
        'origin_note = "BF portrait slot 97"\n'
        f'sha256 = "{hashlib.sha256(portrait).hexdigest()}"\n'
        f'donor_sha256 = "{DONOR_SHA256}"\n'
        'donor_span = "0x6B880C-0x6B980C"\n'
        'transform = "bf-portrait-unpack/v1"\n'
        "alignment = 4\n\n"
        "[[pointer]]\n"
        'in = "a-compat"\n'
        "at = 4\n"
        'target = "b-portrait"\n'
        'origin_note = "portrait address"\n',
        encoding="utf-8",
    )

    output = tmp_path / "out.gba"
    result = build_project(project, rom, output, _catalog())
    emitted = output.read_bytes()

    manifest = result.manifest.to_json()
    recorded = {entry["label"]: entry for entry in manifest["patch_payloads"]}
    assert set(recorded) == {"a-compat", "b-portrait"}
    compat = recorded["a-compat"]
    assert compat["source_class"] == "new" and compat["donor_sha256"] is None
    portrait_entry = recorded["b-portrait"]
    assert portrait_entry["source_class"] == "transferred"
    assert portrait_entry["donor_sha256"] == DONOR_SHA256
    assert portrait_entry["donor_span"] == "0x6B880C-0x6B980C"
    assert portrait_entry["transform"] == "bf-portrait-unpack/v1"

    region = next(r for r in profile.free_regions
                  if r.range.start.value <= compat["allocated_range"]["file_offset"]
                  and compat["allocated_range"]["file_offset"]
                  + compat["allocated_range"]["size"] <= r.range.end)
    offset = compat["allocated_range"]["file_offset"]
    assert emitted[offset:offset + 4] == holder[:4]
    assert emitted[offset + 8:offset + 16] == holder[8:]
    assert emitted[offset + 4:offset + 8] == \
        portrait_entry["allocated_rom_address"].to_bytes(4, "little")
    assert region is not None
    _assert_canonical_unchanged(rom)


def test_a_pointer_into_a_payload_carries_the_thumb_bit_for_code(rom: Path, tmp_path: Path):
    """The shape a fixed-size compatibility block needs: zeroed words, written by the SDK."""
    project = _project(tmp_path, rom)
    assets = project / "assets"
    assets.mkdir()
    block = bytes(8)
    code = bytes([0x70, 0x47])
    (assets / "block.bin").write_bytes(block)
    (assets / "code.bin").write_bytes(code)
    (project / "patch").mkdir()
    (project / "patch" / "edits.toml").write_text(
        "[[payload]]\n"
        'label = "block"\n'
        'file = "assets/block.bin"\n'
        'source_class = "new"\n'
        'origin_note = "compatibility block with one zeroed pointer word"\n'
        f'sha256 = "{hashlib.sha256(block).hexdigest()}"\n'
        'transform = "identity"\n'
        "alignment = 4\n"
        "code = true\n\n"
        "[[payload]]\n"
        'label = "helper"\n'
        'file = "assets/code.bin"\n'
        'source_class = "new"\n'
        'origin_note = "two-byte helper"\n'
        f'sha256 = "{hashlib.sha256(code).hexdigest()}"\n'
        'transform = "identity"\n'
        "alignment = 4\n"
        "code = true\n\n"
        "[[pointer]]\n"
        'in = "block"\n'
        "at = 4\n"
        'target = "helper"\n'
        'origin_note = "the block reads this word"\n',
        encoding="utf-8",
    )

    output = tmp_path / "out.gba"
    result = build_project(project, rom, output, _catalog())
    recorded = {entry["label"]: entry for entry in
                result.manifest.to_json()["patch_payloads"]}
    offset = recorded["block"]["allocated_range"]["file_offset"] + 4
    word = int.from_bytes(output.read_bytes()[offset:offset + 4], "little")
    assert word == recorded["helper"]["allocated_rom_address"] | 1
    _assert_canonical_unchanged(rom)


def _catalog_with_extra_site(kind: str, site: int) -> RomProfileCatalog:
    """The real catalogue, with one extra authorised retail seam for one test.

    The seam policy admits two retail offsets, so a test that exercises a LATER
    refusal (the ARMv4T branch range) authorises its own site here rather than
    weakening the policy every build is held to.
    """
    catalog = _catalog()
    profile = next(p for p in catalog.profiles if p.id == PROFILE_ID)
    widened = dataclasses.replace(
        profile,
        patch_sites=tuple(profile.patch_sites or ()) + (
            PatchSite(kind=kind, site=site, base=None, evidence="test-only declaration"),
        ),
    )
    return RomProfileCatalog([widened if p.id == PROFILE_ID else p
                              for p in catalog.profiles])


def test_an_unrelated_retail_site_is_refused_by_validate_and_by_build(
        rom: Path, tmp_path: Path):
    """Matching expect bytes are not an authorisation: only the declared seams are.

    The site below carries real bytes of the same method table (the +0x0C word), so
    a guard that only compared ``expect`` would accept it. The profile authorises
    two retail offsets and this is neither.
    """
    project = _project(tmp_path, rom)
    (project / "assets").mkdir()
    block = bytes(16)
    (project / "assets" / "block.bin").write_bytes(block)
    (project / "patch").mkdir()
    (project / "patch" / "edits.toml").write_text(
        "[[payload]]\n"
        'label = "block"\n'
        'file = "assets/block.bin"\n'
        'source_class = "new"\n'
        'origin_note = "compatibility block"\n'
        f'sha256 = "{hashlib.sha256(block).hexdigest()}"\n'
        'transform = "identity"\n'
        "alignment = 4\n"
        "code = true\n\n"
        "[[relative]]\n"
        "site = 0x00ef34\n"
        'expect = "116cffff"\n'
        "base = 0x0800ef28\n"
        'target = "block"\n'
        'origin_note = "the neighbouring table word, which this project may not write"\n',
        encoding="utf-8",
    )

    report = validate_project(project, rom, _catalog())
    assert any("authorises no relative entry at file 0x00EF34" in problem
               for problem in report.problems), report.problems

    output = tmp_path / "out.gba"
    with pytest.raises((BuildError, ProjectValidationError)) as refused:
        build_project(project, rom, output, _catalog())
    assert "authorises no relative entry" in str(refused.value)
    assert not output.exists()
    assert not output.with_name(output.name + ".dragonbyte.json").exists()
    _assert_canonical_unchanged(rom)


def test_a_direct_branch_from_the_real_dialogue_site_is_refused_by_range(
        rom: Path, tmp_path: Path):
    project = _project(tmp_path, rom)
    assets = project / "assets"
    assets.mkdir()
    code = bytes(16)
    (assets / "code.bin").write_bytes(code)
    (project / "patch").mkdir()
    (project / "patch" / "edits.toml").write_text(
        "[[payload]]\n"
        'label = "trampoline"\n'
        'file = "assets/code.bin"\n'
        'source_class = "new"\n'
        'origin_note = "compatibility block"\n'
        f'sha256 = "{hashlib.sha256(code).hexdigest()}"\n'
        'transform = "log1-compat/v1"\n'
        "alignment = 4\n"
        "code = true\n\n"
        "[[hook]]\n"
        f"site = 0x{PUBLISH_SITE:X}\n"
        f'expect = "{PUBLISH_GUARD}"\n'
        'target = "trampoline"\n'
        'origin_note = "publish site"\n',
        encoding="utf-8",
    )
    with pytest.raises(ProjectValidationError, match="Thumb BL range"):
        build_project(project, rom, tmp_path / "out.gba",
                      _catalog_with_extra_site("hook", PUBLISH_SITE))
    assert not (tmp_path / "out.gba").exists()
    _assert_canonical_unchanged(rom)


def test_a_project_that_authors_nothing_is_refused(rom: Path, tmp_path: Path):
    project = _project(tmp_path, rom)
    with pytest.raises(BuildError, match="declares no extractable content"):
        build_project(project, rom, tmp_path / "out.gba", _catalog())



RELATIVE_SITE = 0xEF30
RELATIVE_GUARD = "5964ffff"
RELATIVE_BASE = 0x0800EF28


def test_a_relative_entry_reaches_a_clean_compatibility_block(rom: Path, tmp_path: Path):
    """The 24-byte wrapper stand-in: code placed and the method word repointed."""
    profile = next(p for p in _catalog().profiles if p.id == PROFILE_ID)
    project = _project(tmp_path, rom)
    assets = project / "assets"
    assets.mkdir()
    code = bytes(24)
    (assets / "wrapper.bin").write_bytes(code)
    (project / "patch").mkdir()
    (project / "patch" / "edits.toml").write_text(
        "[[payload]]\n"
        'label = "wrapper"\n'
        'file = "assets/wrapper.bin"\n'
        'source_class = "new"\n'
        'origin_note = "behaviour-preserving wrapper stand-in"\n'
        f'sha256 = "{hashlib.sha256(code).hexdigest()}"\n'
        'transform = "log1-compat/v1"\n'
        "alignment = 4\n"
        "code = true\n\n"
        "[[relative]]\n"
        f"site = 0x{RELATIVE_SITE:X}\n"
        f'expect = "{RELATIVE_GUARD}"\n'
        f"base = 0x{RELATIVE_BASE:X}\n"
        'target = "wrapper"\n'
        'origin_note = "NPC table +0x08 draw method"\n',
        encoding="utf-8",
    )
    output = tmp_path / "out.gba"
    result = build_project(project, rom, output, _catalog())
    emitted = output.read_bytes()
    image = rom.read_bytes()

    entry = result.manifest.to_json()["patch_payloads"][0]
    block = entry["allocated_rom_address"]
    word = emitted[RELATIVE_SITE:RELATIVE_SITE + 4]
    assert image[RELATIVE_SITE:RELATIVE_SITE + 4] == bytes.fromhex(RELATIVE_GUARD)
    assert decode_relative_thumb(word, RELATIVE_BASE) == block + 1
    assert emitted[block - 0x08000000:block - 0x08000000 + 24] == code
    _assert_canonical_unchanged(rom)


def test_the_relative_encoder_reproduces_three_retail_table_entries(rom: Path):
    """Discriminating check: the representation is the engine's own, not ours.

    The NPC page table at 0x0800EF28 and the other page table at 0x0800F094 both
    store signed offsets the consumer adds to the table base. Encoding the retail
    targets from the measured bases must reproduce the canonical words byte for
    byte; anything else means the representation is wrong, whichever entry is live.
    """
    from tools.webfoot.project import encode_relative_thumb

    image = rom.read_bytes()
    cases = (
        (0xEF30, 0x0800EF28, 0x08005381),
        (0xEF44, 0x0800EF28, 0x08005393),
        (0xF09C, 0x0800F094, 0x08004E77),
    )
    for site, base, target in cases:
        assert encode_relative_thumb(target, base) == image[site:site + 4], hex(site)
    _assert_canonical_unchanged(rom)
