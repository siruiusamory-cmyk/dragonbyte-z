"""DBZ-008: the LOG1 activation-record codec, exercised on synthetic streams.

The real corpus is measured in `tests/integration/test_log1_script_codec_rom.py`.
These proofs need no ROM: they pin the operand-width model that makes the record
boundaries exact, and the closed failures a malformed stream must produce.
"""

import pytest

from tools.webfoot.data.script_specs import FLAG_FIELDS_LOG1_V1 as L
from tools.webfoot.data.script_specs import STACK_BE7_V1 as S
from tools.webfoot.formats.script_vm import (
    Entry, OpcodeSet, Record, ScriptError, assemble, decode_record, disassemble,
    encode_record)


def record(raw, offset=0):
    return decode_record(bytes(raw), offset, L)


def test_a_record_is_an_activation_count_then_that_many_terminated_segments():
    decoded = record([2, 0, 0])
    assert decoded == Record(0, 2, (b'', b''))
    assert decoded.encoded_length == 3
    assert encode_record(decoded, L) == bytes([2, 0, 0])


def test_an_operand_byte_of_zero_does_not_end_a_segment():
    """The walk is operand-aware; scanning for a 0x00 byte would split at 0x03."""
    decoded = record([1, 0x01, 0x01, 0x00, 0x00])
    assert decoded.segments == (b'\x01\x01\x00',)
    assert decoded.encoded_length == 5
    assert encode_record(decoded, L) == bytes([1, 0x01, 0x01, 0x00, 0x00])


def test_mode_zero_reads_its_flags_and_mode_one_inherits_them():
    raw = [1, 0x01, 0x01, 0xAA, 0x11, 0xBB, 0x00]
    decoded = record(raw)
    assert decoded.segments == (bytes([0x01, 0x01, 0xAA, 0x11, 0xBB]),)
    assert encode_record(decoded, L) == bytes(raw)


@pytest.mark.parametrize('mode', range(2, 16))
def test_every_static_mode_consumes_the_width_its_declared_flags_gate(mode):
    flags = L.operand_flags[mode]
    width = sum(2 if bit == 3 else 1 for bit in range(4) if flags & (1 << bit))
    raw = bytes([1, mode << 4 | 1]) + b'\x7f' * width + b'\x00'
    decoded = record(raw)
    assert decoded.segments == (raw[1:-1],)
    assert decoded.encoded_length == len(raw)
    assert encode_record(decoded, L) == raw


@pytest.mark.parametrize('raw,match', [
    (b'\x00', 'zero activation count'),
    (b'\x01', 'truncated'),
    (b'\x01\x01\x01', 'truncated'),
    (b'\x01\x11', 'inherits flags from no slot'),
    (b'\x01\x10', 'names no slot'),
    (b'\x31', 'truncated'),
])
def test_malformed_records_fail_closed(raw, match):
    with pytest.raises(ScriptError, match=match):
        record(raw)


def test_a_record_outside_the_extent_is_refused():
    with pytest.raises(ScriptError, match='outside extent'):
        record([2, 0, 0], offset=3)


def test_encode_refuses_a_record_its_own_activations_disagree_with():
    with pytest.raises(ScriptError, match='disagrees with its activation count'):
        encode_record(Record(0, 2, (b'',)), L)
    with pytest.raises(ScriptError, match='1 through 255'):
        encode_record(Record(0, 0, ()), L)


def test_the_record_grammar_is_declared_by_the_opcode_set_not_assumed():
    with pytest.raises(ScriptError, match='no activation-record grammar'):
        decode_record(b'\x01\x00', 0, S)
    with pytest.raises(ScriptError, match='declares no activation-record grammar'):
        encode_record(Record(0, 1, (b'',)), S)
    short = OpcodeSet('short_flags', (), grammar='activation_segments', operand_flags=b'\x00')
    with pytest.raises(ScriptError, match='16 modes are addressable'):
        decode_record(b'\x01\x00', 0, short)
    with pytest.raises(ScriptError, match='unknown record grammar'):
        disassemble(b'\x01\x00', (Entry('a', 0),), OpcodeSet('odd', (), grammar='odd'))


def test_records_tile_the_pool_and_uncovered_bytes_stay_opaque():
    raw = bytes([1, 0, 1, 0, 0xff])
    graph = disassemble(raw, (Entry('a', 0), Entry('b', 2)), L)
    assert [item.offset for item in graph.records] == [0, 2]
    assert graph.blocks == ()
    assert graph.opaque == ((4, b'\xff'),)
    assert assemble(graph) == raw


def test_a_pool_with_a_byte_no_record_covers_is_refused():
    raw = bytes([2, 0, 0, 0xff])
    graph = disassemble(raw, (Entry('a', 0),), L)
    with pytest.raises(ScriptError, match='unrepresented assembly bytes'):
        assemble(type(graph)(graph.opcode_set, graph.entries, graph.blocks,
                             graph.extent, (), graph.records))


def test_a_fully_covered_pool_round_trips_through_the_production_assembler():
    raw = bytes([1, 0x01, 0x01, 0x00, 0x00, 2, 0, 0])
    graph = disassemble(raw, (Entry('a', 0), Entry('b', 5)), L)
    assert not graph.opaque
    assert assemble(graph) == raw


def test_overlapping_record_starts_are_refused():
    raw = bytes([2, 2, 0, 0, 0])
    assert disassemble(raw, (Entry('a', 0),), L).records[0].encoded_length == 5
    with pytest.raises(ScriptError, match='overlapping records'):
        disassemble(raw, (Entry('a', 0), Entry('b', 1)), L)


def test_the_assembler_refuses_a_record_that_re_segments_its_own_bytes():
    raw = bytes([2, 0, 0])
    graph = disassemble(raw, (Entry('a', 0),), L)
    cut = Record(0, 1, (b'\x00',))
    with pytest.raises(ScriptError):
        assemble(type(graph)(graph.opcode_set, graph.entries, graph.blocks,
                             graph.extent, graph.opaque, (cut,)))


def test_no_opcode_is_named_or_given_a_meaning_for_the_log1_record_grammar():
    assert L.instructions == ()
    assert L.profiles == ('legacy_of_goku_usa_a3c8c767',)
    assert len(L.operand_flags) == 16


def test_the_instruction_grammar_sets_keep_their_defaults():
    """The record layer is opt-in; the two shipped instruction sets are untouched."""
    from tools.webfoot.data.script_specs import STACK_BE16_BUU_V1 as B
    for spec in (S, B):
        assert spec.grammar == 'opcode'
        assert spec.operand_flags == b''
        assert spec.instructions
