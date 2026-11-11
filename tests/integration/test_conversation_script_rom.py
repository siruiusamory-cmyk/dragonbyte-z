"""The office conversation's own script, authored in place on the retail image.

ROM-gated on the user-supplied canonical image, like the other integration tests
that read canonical content. The numbers here are the measured layout: entry 0 of
the office conversation runs a fifteen-byte body, and the room it may use is
twenty-nine bytes, because the fifteen-byte body is followed by a second body its
forward branch reaches.

The last test is the flag's own evidence: the event corpus names two save flags,
and the authored one is not among them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.webfoot.binary import GBA_ROM_BASE
from tools.webfoot.build import build_project
from tools.webfoot.conversation_script import (
    ConversationScriptIdentity,
    plan_conversation_scripts,
)
from tools.webfoot.maps import load_maps
from tools.webfoot.placement_events import PlacementEvents
from tools.webfoot.profile import RomProfileCatalog
from tools.webfoot.project.model import AuthoredConversationScript


LOCAL_ROM = Path("roms/Dragon Ball Z - Buu's Fury (U).gba")
CATALOG = "config/roms.yaml"

CONVERSATION = 0x087809EC
ENTRY = 0
CODE = 0x78098F
ROOM = 29
FLAG = 228

PRIOR = ('push_byte 2', 'native_stack 27', 'push_byte 3', 'native_stack 28',
         'logical_and', 'branch_if_zero 6', 'push_byte 3', 'terminate')
BODY = ('set_save_flag 228', 'push_byte 2', 'native_stack 27', 'push_byte 3',
        'native_stack 28', 'logical_and', 'branch_if_zero 5', 'push_byte 3',
        'terminate', 'push_byte 125', 'native_stack 27', 'branch_if_zero 4',
        'push_byte 9', 'terminate')
AUTHORED = bytes.fromhex(
    '00e4 021d 0002 021b 0003 021c 04 130005 0003 11 007d 021b 130004 0009 11'
    .replace(' ', ''))
CANONICAL = bytes.fromhex(
    '0002 021b 0003 021c 04 130006 0003 11 11 007d 021b 130004 0009 11 000000'
    .replace(' ', ''))

BASE = """[project]
format_version = 1
name = "conversation-script"

[base]
profile_id = "buus_fury_usa_rev0_01c1707f"
game = "buus_fury"
sha256 = "940ad5f01db4465b8877dfe739510cbf34f4ea3d390f3df13519808bc36f059e"
size = 8388608
"""

DOCUMENT = (
    '[script."conversation:0x087809EC"]\n'
    '\n'
    '[script."conversation:0x087809EC"."0000"]\n'
    'prior_instructions = [' + ', '.join(f'"{line}"' for line in PRIOR) + ']\n'
    'instructions = [' + ', '.join(f'"{line}"' for line in BODY) + ']\n'
)


def require_rom():
    if not LOCAL_ROM.is_file():
        pytest.skip("user-supplied Buu's Fury ROM is not present")


@pytest.fixture
def rom():
    require_rom()
    return LOCAL_ROM


@pytest.fixture
def profile():
    return RomProfileCatalog.load(CATALOG).profiles[0]


def identity():
    return ConversationScriptIdentity(CONVERSATION, ENTRY)


def test_the_talk_script_has_twenty_nine_bytes_of_room_and_that_is_the_body(rom, profile):
    image = rom.read_bytes()
    application = plan_conversation_scripts(
        image, profile, {identity(): AuthoredConversationScript(PRIOR, BODY)})
    change = application.changes[0]
    assert change.offset == CODE
    assert change.old == CANONICAL
    assert change.new == AUTHORED
    assert len(change.new) == ROOM
    assert application.provenance[0].capacity == ROOM


def test_a_body_four_bytes_longer_than_the_room_is_refused(rom, profile):
    from tools.webfoot.conversation_script import ConversationScriptError
    image = rom.read_bytes()
    longer = BODY[:-1] + ('push_byte 1', 'native_stack 29', 'terminate')
    with pytest.raises(ConversationScriptError, match='room'):
        plan_conversation_scripts(
            image, profile, {identity(): AuthoredConversationScript(PRIOR, longer)})


def test_a_project_that_authors_it_builds_the_same_image_twice(rom, profile, tmp_path):
    project = tmp_path / "script-project"
    (project / "dialogue").mkdir(parents=True)
    (project / "project.toml").write_text(BASE, encoding="utf-8")
    (project / "dialogue" / "scripts.toml").write_text(DOCUMENT, encoding="utf-8")
    first = tmp_path / "first.gba"
    second = tmp_path / "second.gba"
    build_project(project, rom, first, RomProfileCatalog.load(CATALOG))
    build_project(project, rom, second, RomProfileCatalog.load(CATALOG))
    assert first.read_bytes() == second.read_bytes()
    canonical = rom.read_bytes()
    built = first.read_bytes()
    assert built[CODE:CODE + ROOM] == AUTHORED
    assert canonical[CODE:CODE + ROOM] == CANONICAL
    assert built[:CODE] == canonical[:CODE]
    assert built[CODE + ROOM:] == canonical[CODE + ROOM:]


def test_the_corpus_names_no_save_flag_reference_at_the_authored_flag(rom, profile):
    relationships = PlacementEvents(load_maps(rom, RomProfileCatalog.load(CATALOG)))
    references = relationships.operand_references()
    flags = sorted({reference.index for reference in references
                    if reference.kind == 'save_flag'})
    assert flags, "the corpus named no save flag at all, so it proves nothing"
    assert FLAG not in flags
    assert GBA_ROM_BASE + CODE == 0x0878098F
