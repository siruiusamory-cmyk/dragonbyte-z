"""ROM-gated proof that `scene init --presentation` composes the declared payload set.

LOG1-BUU-DIALOGUE-BACKPORT-001. A verified LOG1 image, the verified donor image and the
owner's dialogue JSON go in; a project whose payloads, seams, fixups and text are
ordinary documents comes out. No lab script, no offset typed by a person.

Composition is per declaration - `sites.toml`, `box-sites.toml`, `text-sites.toml`, in
that order - and a fixup word is bound by the payload its declaration NAMES, never by
which payload happens to contain the offset. Two facts follow:

* all three declarations name their words, so the shipped set composes into one project
  (`test_the_shipped_declaration_set_composes_every_payload_and_seam`);
* the composition is DOCUMENTS ONLY. No test here emits an image from the live
  declaration package: lane A is still correcting the assembly package, and only a
  frozen package may be built. `test_the_palette_fixup_must_declare_the_extent...` still
  refuses a metadata form that would let the block over-read its bank.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

import tools.webfoot.commands.backport as backport
from tools.webfoot.commands.backport import BackportCommandError, scene_init
from tools.webfoot.profile import RomProfileCatalog
from tools.webfoot.project import read_patch_document

REPO = Path(__file__).resolve().parents[2]
DEFAULT_ROM = REPO / "roms" / "Dragon Ball Z - The Legacy of Goku (USA).gba"
DEFAULT_BF = REPO / "roms" / "Dragon Ball Z - Buu's Fury (U).gba"
LOG1_SHA256 = "3ba9919e26704b0f5fdc2bfabc7f7a0404c71413761d38abcd94224c3bd4b1b9"
DONOR_SHA256 = "940ad5f01db4465b8877dfe739510cbf34f4ea3d390f3df13519808bc36f059e"
PROFILE_ID = "legacy_of_goku_usa_a3c8c767"
RELATIVE_BASE = 0x0800EF28

LINES = {
    0: "Goku! You're looking stronger every time I see you!",
    1: "Thanks! I've been training nonstop!",
    2: "I can tell!",
    3: "So what've you been up to lately?",
    4: "Oh, you know me. Sun, sand, and a growing pile of magazines. Or so I thought!",
    5: "A few went missing! If you find any while you're out, bring them back to me, will you?",
    6: "You got it!",
}


def _image(env: str, default: Path) -> Path | None:
    value = os.environ.get(env)
    path = Path(value) if value else default
    return path if path.is_file() else None


@pytest.fixture(scope="module")
def rom() -> Path:
    path = _image("WEBFOOT_LOG1_ROM", DEFAULT_ROM)
    if path is None or hashlib.sha256(path.read_bytes()).hexdigest() != LOG1_SHA256:
        pytest.skip("canonical Legacy of Goku image not present locally")
    return path


@pytest.fixture(scope="module")
def bf() -> Path:
    path = _image("WEBFOOT_BF_ROM", DEFAULT_BF)
    if path is None or hashlib.sha256(path.read_bytes()).hexdigest() != DONOR_SHA256:
        pytest.skip("canonical Buu's Fury image not present locally")
    return path


def _catalog() -> RomProfileCatalog:
    return RomProfileCatalog.load(REPO / "config" / "roms.yaml")


def _composed(tmp_path: Path, rom: Path, bf: Path | None) -> Path:
    dialogue = tmp_path / "dialogue.json"
    dialogue.write_text(json.dumps({"nodes": [{"node": node, "text": text}
                                              for node, text in LINES.items()]}),
                        encoding="utf-8")
    project = tmp_path / "fresh" / "project"
    scene_init(SimpleNamespace(project=project, rom=rom, name="initializer-test",
                               presentation=bf, dialogue=dialogue))
    return project


def test_scene_init_composes_lane_b_and_binds_its_three_words_to_the_portrait(
        rom: Path, bf: Path, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(backport, "PRESENTATION_DECLARATIONS", ("sites.toml",))
    project = _composed(tmp_path, rom, bf)
    document = read_patch_document(project)
    assert [payload.label for payload in document.payloads] == [
        "bf-obj-palette-low128", "master-roshi", "goku", "bf-box",
        "bf-presentation", "bf-portrait",
    ]
    assert document.payload("bf-portrait").size == 472
    assert {payload.label for payload in document.payloads if payload.code} == {
        "bf-presentation", "bf-portrait"}
    assert [(relative.site, relative.base, relative.target)
            for relative in document.relatives] == [
        (0xEF30, RELATIVE_BASE, "bf-presentation")]
    assert [(pointer.site, pointer.target) for pointer in document.pointers
            if pointer.site is not None] == [(0x11490, "bf-portrait")]
    assert [(pointer.container, pointer.at, pointer.target, pointer.state)
            for pointer in document.pointers if pointer.container] == [
        ("bf-portrait", 0x1CC, "master-roshi", "data"),
        ("bf-portrait", 0x1D0, "goku", "data"),
        ("bf-portrait", 0x1D4, "bf-obj-palette-low128", "data"),
    ]
    assert hashlib.sha256(rom.read_bytes()).hexdigest() == LOG1_SHA256


def test_the_shipped_declaration_set_composes_every_payload_and_seam(
        rom: Path, bf: Path, tmp_path: Path):
    """The three declarations compose into ONE project; no image is emitted here.

    Documents only, on purpose: lane A is still correcting the assembly package and only
    a frozen package may be built. This is the readiness check - it fails if a
    declaration stops naming its words, if a declared payload becomes unreachable, if a
    seam loses its target, or if the shared box surface stops being shared by the box
    and the text payload.
    """
    project = _composed(tmp_path, rom, bf)
    document = read_patch_document(project)
    assert [payload.label for payload in document.payloads] == [
        "bf-obj-palette-low128", "master-roshi", "goku", "bf-box", "bf-font",
        "bf-dialogue-plan", "bf-portrait", "bf-box-geometry", "bf-box-strips",
        "bf-box-window", "bf-text",
    ]
    sizes = {payload.label: payload.size for payload in document.payloads}
    assert (sizes["bf-obj-palette-low128"], sizes["master-roshi"], sizes["bf-box"],
            sizes["bf-font"], sizes["bf-dialogue-plan"]) == (156, 4096, 10240, 3598, 112)
    assert {payload.label for payload in document.payloads if payload.code} == {
        "bf-portrait", "bf-box-geometry", "bf-box-strips", "bf-box-window", "bf-text"}
    assert [(relative.site, relative.base, relative.target)
            for relative in document.relatives] == [
        (0xEF30, RELATIVE_BASE, "bf-box-window"),
        (0xEF44, RELATIVE_BASE, "bf-text")]
    assert [(pointer.site, pointer.target) for pointer in document.pointers
            if pointer.site is not None] == [(0x11490, "bf-box-strips"),
                                             (0x11480, "bf-box-geometry")]
    assert [(pointer.container, pointer.target, pointer.state)
            for pointer in document.pointers if pointer.container] == [
        ("bf-portrait", "master-roshi", "data"),
        ("bf-portrait", "goku", "data"),
        ("bf-portrait", "bf-obj-palette-low128", "data"),
        ("bf-box-strips", "bf-box", "data"),
        ("bf-box-strips", "bf-portrait", "thumb"),
        ("bf-box-strips", "bf-obj-palette-low128", "data"),
        ("bf-box-strips", "bf-dialogue-plan", "data"),
        ("bf-text", "bf-box", "data"),
        ("bf-text", "bf-font", "data"),
        ("bf-text", "bf-dialogue-plan", "data"),
    ]
    assert not (project / "assets" / "presentation.bin").exists()
    bank = (project / "assets" / "bf-obj-palette-low128.bin").read_bytes()
    assert len(bank) == 156
    assert backport._bank_slot(bank, 0x7FFF) == 77, (
        "the emitted bank must hold white in exactly one slot; lane A's text payload "
        "inks 77, and a donor palette index is not a target slot")
    assert hashlib.sha256(rom.read_bytes()).hexdigest() == LOG1_SHA256


def test_the_palette_fixup_must_declare_the_extent_the_block_copies(
        rom: Path, bf: Path, tmp_path: Path, monkeypatch):
    """156 B (39 words) is the required read extent, not an upper bound.

    The portrait block copies exactly 39 words out of the shared bank, so a declaration
    that allows more than that lets a longer bank ship and the copy drop colours the art
    uses. The permissive `declared >= payload` reading is gone: the composition now
    requires equality and refuses the 256-byte form this file used to declare.
    """
    source = backport.PRESENTATION_SOURCE
    copy = tmp_path / "declarations"
    copy.mkdir()
    for name in ("sites.toml", "presentation.bin", "portrait.bin"):
        shutil.copy(source / name, copy / name)
    declared = (copy / "sites.toml").read_text(encoding="utf-8")
    assert "bytes = 156" in declared
    (copy / "sites.toml").write_text(declared.replace("bytes = 156", "bytes = 256"),
                                     encoding="utf-8")
    monkeypatch.setattr(backport, "PRESENTATION_SOURCE", copy)
    monkeypatch.setattr(backport, "PRESENTATION_DECLARATIONS", ("sites.toml",))
    with pytest.raises(BackportCommandError,
                       match="declares 256 bytes, 'bf-obj-palette-low128' is 156"):
        _composed(tmp_path, rom, bf)
    assert hashlib.sha256(rom.read_bytes()).hexdigest() == LOG1_SHA256


def test_the_composed_project_carries_the_approved_lines(rom: Path, bf: Path,
                                                         tmp_path: Path, monkeypatch):
    monkeypatch.setattr(backport, "PRESENTATION_DECLARATIONS", ("sites.toml",))
    project = _composed(tmp_path, rom, bf)
    raw = (project / "raw" / "bytes.toml").read_text(encoding="utf-8")
    offsets = (0x16492C, 0x16496C, 0x164993, 0x16499F, 0x1649C5, 0x164A15, 0x164A6E)
    written = [line for line in raw.splitlines() if line.startswith("0x")]
    assert len(written) == 7
    for offset in offsets:
        assert any(line.startswith(f"0x{offset:06x}") for line in written)


def test_dialogue_without_a_presentation_is_refused(rom: Path, tmp_path: Path):
    dialogue = tmp_path / "dialogue.json"
    dialogue.write_text(json.dumps({"nodes": [{"node": 0, "text": LINES[0]}]}),
                        encoding="utf-8")
    with pytest.raises(BackportCommandError, match="needs --presentation"):
        scene_init(SimpleNamespace(project=tmp_path / "project", rom=rom,
                                   name=None, presentation=None, dialogue=dialogue))
