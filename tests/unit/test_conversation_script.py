"""DIALOGUE-SCRIPT-AUTHORING-001: the effect, the body, and the measured room.

Nothing here reads a ROM: the planner is exercised over a synthetic image whose
layout is the office conversation's shape (an array of record pointers, one
record running code, room measured to the array's next record). The canonical
image's own numbers are asserted by the ROM-gated integration test beside this
one.
"""

from __future__ import annotations

import pytest

from tools.webfoot.authored_placements import AuthoredBehaviorError, _expand_semantic_source
from tools.webfoot.binary import GBA_ROM_BASE
from tools.webfoot.conversation_script import (
    ConversationScriptError,
    ConversationScriptIdentity,
    plan_conversation_scripts,
)
from tools.webfoot.data.script_effects import SCRIPT_EFFECTS
from tools.webfoot.data.script_specs import OPCODE_SETS
from tools.webfoot.formats.script_vm import ScriptError, assemble_source
from tools.webfoot.map_render import canonical_profile
from tools.webfoot.project.model import AuthoredConversationScript, ConversationScripts

PROFILE = 'buus_fury_usa_rev0_01c1707f'
BUU = OPCODE_SETS['stack_be16_buu_v1']

ARRAY = 0x100
RECORD = 0x200
NEXT_RECORD = 0x220
CODE = RECORD + 3
PRIOR = ('push_byte 2', 'terminate')
ROOM = NEXT_RECORD - CODE


def image(kind=0, later=NEXT_RECORD, body=bytes.fromhex('000211')):
    data = bytearray(0x400)
    data[ARRAY:ARRAY + 4] = (GBA_ROM_BASE + RECORD).to_bytes(4, 'little')
    if later is not None:
        data[ARRAY + 4:ARRAY + 8] = (GBA_ROM_BASE + later).to_bytes(4, 'little')
    data[RECORD:RECORD + 2] = (0).to_bytes(2, 'little')
    data[RECORD + 2] = kind
    data[CODE:CODE + len(body)] = body
    return bytes(data)


def filling(count):
    return ('set_save_flag 3', 'push_byte 2') + ('push_byte 0',) * count + ('terminate',)


def body_of_room(room):
    return filling((room - 7) // 2)


def identity():
    return ConversationScriptIdentity(GBA_ROM_BASE + ARRAY, 0)


def script(body, prior=PRIOR):
    return AuthoredConversationScript(prior, body)


@pytest.fixture
def profile():
    return canonical_profile()


def test_set_save_flag_expands_to_one_push_and_the_set_flag_slot(profile):
    assert _expand_semantic_source(('set_save_flag 228',), profile, 'owner') == (
        'push_byte 228', 'native_stack 29')
    effect = SCRIPT_EFFECTS[PROFILE]['set_save_flag']
    assert (effect['native_opcode'], effect['native_slot']) == ('native_stack', 29)
    assert effect['native_handler_raw'] == 0x080007E6
    assert effect['stack'] == {'pops': 1, 'pushes': 0}


def test_the_flag_operand_is_bounded_by_the_one_byte_push(profile):
    for line in ('set_save_flag 256', 'set_save_flag -1'):
        with pytest.raises(AuthoredBehaviorError, match='declared'):
            _expand_semantic_source((line,), profile, 'owner')
    with pytest.raises(AuthoredBehaviorError, match='one flag number'):
        _expand_semantic_source(('set_save_flag',), profile, 'owner')


def test_the_expanded_pair_leaves_the_vm_stack_as_it_found_it():
    assert assemble_source(('push_byte 228', 'native_stack 29', 'terminate'),
                           BUU) == bytes.fromhex('00e4021d 11'.replace(' ', ''))
    pushes = BUU.lookup(0x00).stack
    assert pushes == (0, 1)
    assert SCRIPT_EFFECTS[PROFILE]['set_save_flag']['stack']['pops'] == pushes[1]


def test_a_branching_body_is_encoded_with_a_big_endian_displacement():
    assert assemble_source(
        ('push_byte 1', 'push_byte 2', 'branch_if_zero 2', 'terminate'),
        BUU) == bytes.fromhex('0001000213000211')
    with pytest.raises(ScriptError, match='two-byte'):
        assemble_source(('branch_if_zero 0x10000', 'terminate'), BUU)


def test_the_authored_body_replaces_the_measured_room_exactly(profile):
    body = body_of_room(ROOM)
    application = plan_conversation_scripts(image(), profile, {identity(): script(body)})
    change = application.changes[0]
    assert len(change.old) == len(change.new) == ROOM
    assert change.old[:3] == bytes.fromhex('000211')
    assert change.new[:6] == bytes.fromhex('0003021d0002')
    assert change.offset == CODE
    assert change.owner == identity().value == 'conversation:0x08000100/entry:0'
    assert change.reason == 'authored conversation script'
    provenance = application.provenance[0]
    assert (provenance.capacity, provenance.authored_bytes) == (ROOM, ROOM)


def test_a_body_that_does_not_fill_the_room_is_refused(profile):
    assert len(plan_conversation_scripts(image(), profile,
                                         {identity(): script(body_of_room(ROOM))}
                                         ).changes[0].new) == ROOM
    for body in (filling(13), filling(10)):
        with pytest.raises(ConversationScriptError, match='room'):
            plan_conversation_scripts(image(), profile, {identity(): script(body)})


def test_a_body_that_does_not_end_in_a_terminate_is_refused(profile):
    body = body_of_room(ROOM - 1) + ('push_byte 0',)
    with pytest.raises(ConversationScriptError):
        plan_conversation_scripts(image(), profile, {identity(): script(body)})


def test_a_stale_prior_is_refused_rather_than_rewritten(profile):
    stale = ('push_byte 9', 'terminate')
    with pytest.raises(ConversationScriptError, match='different image'):
        plan_conversation_scripts(image(), profile,
                                  {identity(): script(body_of_room(ROOM), stale)})


def test_a_record_kind_that_runs_no_code_block_is_refused(profile):
    with pytest.raises(ConversationScriptError, match='locates a code block only for kinds'):
        plan_conversation_scripts(image(kind=5), profile,
                                  {identity(): script(body_of_room(ROOM))})


def test_a_conversation_with_no_later_record_has_no_measurable_room(profile):
    with pytest.raises(ConversationScriptError, match='not measurable'):
        plan_conversation_scripts(image(later=None), profile,
                                  {identity(): script(body_of_room(ROOM))})


def test_an_entry_that_names_no_record_is_refused(profile):
    with pytest.raises(ConversationScriptError, match='no record pointer'):
        plan_conversation_scripts(
            image(), profile,
            {ConversationScriptIdentity(GBA_ROM_BASE + ARRAY, 3): script(PRIOR)})


def test_the_document_holds_two_instruction_lists_per_entry():
    document = {'script': {'conversation:0x087809EC': {
        '0000': {'prior_instructions': list(PRIOR),
                 'instructions': list(body_of_room(ROOM))}}}}
    scripts = ConversationScripts.from_document(document, 'where')
    assert scripts.edits() == {('conversation:0x087809EC', 0): script(body_of_room(ROOM))}
    assert scripts.to_document() == document
    assert not ConversationScripts().is_empty() is False


def test_a_malformed_script_document_is_refused():
    with pytest.raises(Exception, match='conversation identity'):
        ConversationScripts.from_document({'script': {'office': {}}}, 'where')
    with pytest.raises(Exception, match='unknown key'):
        ConversationScripts.from_document({'script': {'conversation:0x087809EC': {
            '0000': {'prior_instructions': list(PRIOR), 'instructions': ['terminate'],
                     'raw': '00'}}}}, 'where')
    with pytest.raises(Exception, match='non-empty list'):
        ConversationScripts.from_document({'script': {'conversation:0x087809EC': {
            '0000': {'prior_instructions': [], 'instructions': ['terminate']}}}}, 'where')
    with pytest.raises(Exception, match='entry index'):
        ConversationScripts.from_document({'script': {'conversation:0x087809EC': {
            'first': {'prior_instructions': list(PRIOR),
                      'instructions': ['terminate']}}}}, 'where')
