"""A project names a dialogue record by its own selector and decoded start.

ROM-gated on the user-supplied canonical image. The same anchor resolves in the
canonical image and in a derivative this build produced, because the authoring
operation splices at the record's end and leaves its start where it was.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.webfoot.build import build_project
from tools.webfoot.compressed_dialogue import (
    CompressedDialogueError,
    read_original_text,
    target_for_anchor,
)
from tools.webfoot.profile import RomProfileCatalog


LOCAL_ROM = Path("roms/Dragon Ball Z - Buu's Fury (U).gba")
CATALOG = "config/roms.yaml"

ASSISTANT_SELECTOR = 0
ASSISTANT_START = 0x91B4
ASSISTANT_HANDLE = 0x0A723680
ASSISTANT_LENGTH = 166
OPENING = "Sir, you can't go this way!"
AUTHORED = "A Saiyan got you, Goku. King Kai waits. Go."

BASE = """[project]
format_version = 1
name = "anchor-test"

[base]
profile_id = "buus_fury_usa_rev0_01c1707f"
game = "buus_fury"
sha256 = "940ad5f01db4465b8877dfe739510cbf34f4ea3d390f3df13519808bc36f059e"
size = 8388608
"""


def require_rom() -> None:
    if not LOCAL_ROM.is_file():
        pytest.skip("user-supplied Buu's Fury ROM is not present")


@pytest.fixture
def rom():
    require_rom()
    return LOCAL_ROM


@pytest.fixture
def profile():
    return RomProfileCatalog.load(CATALOG).profiles[0]


def test_the_anchor_resolves_the_record_the_office_actually_plays(rom, profile):
    canonical = rom.read_bytes()
    target = target_for_anchor(canonical, profile, ASSISTANT_SELECTOR, ASSISTANT_START)
    assert target.name == f"record:0:0x{ASSISTANT_START:04X}"
    assert target.packed_handle == ASSISTANT_HANDLE
    assert target.decoded_length == ASSISTANT_LENGTH
    assert read_original_text(canonical, profile, target).startswith(OPENING)


def test_an_anchor_with_no_record_is_refused(rom, profile):
    canonical = rom.read_bytes()
    with pytest.raises(CompressedDialogueError):
        target_for_anchor(canonical, profile, ASSISTANT_SELECTOR, 0x1)


def test_a_project_authors_that_record_and_the_build_emits_it(rom, profile, tmp_path):
    project = tmp_path / "anchor-project"
    (project / "dialogue").mkdir(parents=True)
    (project / "project.toml").write_text(BASE, encoding="utf-8")
    (project / "dialogue" / "replacements.toml").write_text(
        f'[dialogue."record:{ASSISTANT_SELECTOR}:0x{ASSISTANT_START:04X}"]\n'
        f'text = "{AUTHORED}"\n',
        encoding="utf-8",
    )
    first = tmp_path / "first.gba"
    second = tmp_path / "second.gba"
    build_project(project, rom, first, RomProfileCatalog.load(CATALOG))
    build_project(project, rom, second, RomProfileCatalog.load(CATALOG))
    assert first.read_bytes() == second.read_bytes()

    built = first.read_bytes()
    reread = target_for_anchor(built, profile, ASSISTANT_SELECTOR, ASSISTANT_START)
    assert read_original_text(built, profile, reread) == AUTHORED
    assert built[0x7809B7] == rom.read_bytes()[0x7809B7]
