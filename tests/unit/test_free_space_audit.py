"""Synthetic research-only occupancy and candidate discipline."""
import struct

import pytest

from tools.research import free_space_audit
from tools.research.free_space_audit import (MODEL_BUILDERS, _buu_model, _fill_tail,
                                             _log2_model, candidate_report, model_builder,
                                             occupancy)
from tools.webfoot.binary import FileOffset
from tools.webfoot.layout import RomRange
from tools.webfoot.profile import ProfileConfigError, _free_regions


def test_fill_with_aligned_and_unaligned_candidates_is_never_promoted():
    image = bytearray(512)
    image[256:] = b'\xff' * 256
    struct.pack_into('<I', image, 16, 0x08000100)
    struct.pack_into('<I', image, 25, 0x08000120)
    report = candidate_report(bytes(image), RomRange(FileOffset(256), 256), [], [])
    assert report['status'] == 'CANDIDATE'
    assert report['candidate_word_aligned_count'] == 1
    assert report['reference_counts'] == {'CANDIDATE_REFERENCE': 2}
    assert report['byte_histogram'] == {255: 256}
    assert report['reasons_candidate_only']


def test_zero_hits_does_not_promote_fill():
    report = candidate_report(bytes(512), RomRange(FileOffset(256), 256), [], [])
    assert report['status'] == 'CANDIDATE'
    assert report['reference_counts'] == {}


def test_known_reference_class_and_neighbors_preserved():
    image = bytearray(512)
    struct.pack_into('<I', image, 16, 0x08000100)
    owned = [{'start': 16, 'end': 20, 'owner': 'table'},
             {'start': 400, 'end': 420, 'owner': 'other'}]
    ref = {'source': 16, 'target': 256, 'classification': 'DECLARED_REFERENCE'}
    report = candidate_report(bytes(image), RomRange(FileOffset(256), 64), owned, [ref])
    assert report['known_inbound'] == [ref]
    assert report['reference_counts'] == {'DECLARED_REFERENCE': 1}
    assert report['neighbor_before'] == owned[0]
    assert report['neighbor_after'] == owned[1]


def test_occupancy_retains_unknown_and_overlapping_annotations():
    rows = [{'start': 10, 'end': 30, 'kind': 'table', 'owner': 'A'},
            {'start': 20, 'end': 40, 'kind': 'graphic', 'owner': 'B'}]
    report = occupancy(64, rows)
    assert report == occupancy(64, list(reversed(rows)))
    assert sum(s['end'] - s['start'] for s in report['segments']) == 64
    assert report['segments'][0]['coverage'] == 'UNKNOWN'
    assert report['segments'][2]['annotations'] == [0, 1]
    assert report['segments'][-1]['coverage'] == 'UNKNOWN'


@pytest.mark.parametrize('status', ['CANDIDATE', 'CANDIDATE_REFERENCE', 'UNKNOWN'])
def test_candidate_cannot_be_parsed_as_production_free_space(status):
    with pytest.raises(ProfileConfigError, match='CONFIRMED'):
        _free_regions([{'file_offset': 256, 'size': 256, 'status': status,
                        'evidence': 'numeric scan and fill only'}], 512)


def test_out_of_bounds_candidate_refused():
    with pytest.raises(ValueError):
        candidate_report(bytes(512), RomRange(FileOffset(500), 20), [], [])


def test_model_selection_is_deliberate_and_names_an_unmodelled_profile():
    """A game joins the proof only through its own entry: no default, no borrowing."""
    assert MODEL_BUILDERS == {'buus_fury_usa_rev0_01c1707f': _buu_model,
                              'legacy_of_goku_ii_usa_rev0_204142e1': _log2_model}
    assert model_builder('legacy_of_goku_ii_usa_rev0_204142e1') is _log2_model
    assert model_builder('buus_fury_usa_rev0_01c1707f') is _buu_model
    with pytest.raises(ValueError, match='legacy_of_goku_usa_a3c8c767') as refusal:
        model_builder('legacy_of_goku_usa_a3c8c767')
    assert 'no model for profile' in str(refusal.value)
    assert 'buus_fury_usa_rev0_01c1707f' in str(refusal.value)


def test_fill_tail_is_measured_from_the_bytes_and_refused_when_absent():
    """The tail is the trailing fill run, not a declared number and not the image."""
    assert _fill_tail(bytes(b'\x00' * 0x100 + b'\xff' * 0x40)) == \
        RomRange(FileOffset(0x100), 0x40)
    with pytest.raises(ValueError, match='no trailing fill run'):
        _fill_tail(bytes(b'\x00' * 0x100))


def map_image():
    """A synthetic LOG2 image: two entries, two arrays, one root, one layer, one row."""
    image = bytearray(0x4000)
    base = free_space_audit.LOG2_IMAGE_BASE
    struct.pack_into('<I', image, 0x100 + 0x2C, base + 0x400)
    struct.pack_into('<I', image, 0x138 + 0x2C, base + 0x500)
    struct.pack_into('<I', image, 0x400, base + 0x900)
    struct.pack_into('<I', image, 0x500, base + 0x900)
    struct.pack_into('<I', image, 0x900 + 0x4C, base + 0x1000)
    struct.pack_into('<I', image, 0x900 + 0x48, base + 0xE00)
    struct.pack_into('<I', image, 0x900 + 0x28, base + 0x2000)
    struct.pack_into('<I', image, 0x900 + 0x24, 2)
    for field in (0x14, 0x18, 0x1C, 0x20):
        struct.pack_into('<I', image, 0x900 + field, base + 0xA00)
    struct.pack_into('<I', image, 0xA00, 0x080056A1)
    image[0xA14] = 2
    image[0xA15] = 1
    struct.pack_into('<I', image, 0xA18, base + 0x2800)
    struct.pack_into('<I', image, 0xA1C, base + 0x2900)
    return image


def test_map_walk_owns_only_what_its_fields_bound(monkeypatch):
    """The entry, root, root-table and dominant-layer rows follow the walk's guards."""
    monkeypatch.setattr(free_space_audit, 'LOG2_MAP_ENTRY_TABLE', 0x100)
    monkeypatch.setattr(free_space_audit, 'LOG2_TILE_BANK_ADDRESS',
                        free_space_audit.LOG2_IMAGE_BASE + 0x1000)
    family = free_space_audit._log2_map(bytes(map_image()))
    rows = {(row['kind'], row['start']): row['end'] - row['start'] for row in family['rows']}
    assert rows == {('map_entry_record', 0x100): 2 * 0x38,
                    ('map_root', 0x900): 0x50,
                    ('map_root_table', 0x2000): 48,
                    ('map_layer_record', 0xA00): 0x18 + 4 * 2}
    pairs = {(ref['source'], ref['target']) for ref in family['refs']}
    assert {(0x12C, 0x400), (0x164, 0x500), (0x400, 0x900), (0x500, 0x900),
            (0x914, 0xA00), (0x918, 0xA00), (0x91C, 0xA00), (0x920, 0xA00),
            (0x948, 0xE00), (0x94C, 0x1000), (0x928, 0x2000),
            (0xA18, 0x2800), (0xA1C, 0x2900)} == pairs


def test_map_walk_stops_at_a_word_that_is_not_a_root(monkeypatch):
    """A root-array word whose record does not close on the tile bank ends the array."""
    monkeypatch.setattr(free_space_audit, 'LOG2_MAP_ENTRY_TABLE', 0x100)
    monkeypatch.setattr(free_space_audit, 'LOG2_TILE_BANK_ADDRESS',
                        free_space_audit.LOG2_IMAGE_BASE + 0x1000)
    image = bytearray(map_image())
    struct.pack_into('<I', image, 0x94C, 0)
    family = free_space_audit._log2_map(bytes(image))
    assert [row['kind'] for row in family['rows']] == ['map_entry_record']
    assert {ref['target'] for ref in family['refs']} == {0x400, 0x500}


def test_sprite_walk_owns_a_definition_only_after_its_fields_validate(monkeypatch):
    """A definition whose slots do not resolve is reported, not owned."""
    monkeypatch.setattr(free_space_audit, 'LOG2_SPRITE_TABLE', 0x100)
    monkeypatch.setattr(free_space_audit, 'LOG2_SPRITE_COUNT', 2)
    image = bytearray(0x4000)
    base = free_space_audit.LOG2_IMAGE_BASE
    struct.pack_into('<I', image, 0x100 + 4 * 3, base + 0x800)
    struct.pack_into('<I', image, 0x100 + 4 * 4, base + 0x900)
    struct.pack_into('<I', image, 0x800 + 0x04, 2)
    struct.pack_into('<I', image, 0x800 + 0x4C, base + 0x1000)
    struct.pack_into('<I', image, 0x800 + 0x50, base + 0x1100)
    struct.pack_into('<I', image, 0x1000 + 8, base + 0x2000)
    struct.pack_into('<I', image, 0x1100 + 8, base + 0x2100)
    struct.pack_into('<I', image, 0x2000, 1)
    struct.pack_into('<I', image, 0x2000 + 4, 0x800)
    struct.pack_into('<I', image, 0x2100, 1)
    struct.pack_into('<I', image, 0x2100 + 4, 0x800)
    struct.pack_into('<I', image, 0x900 + 0x04, 4)
    struct.pack_into('<I', image, 0x900 + 0x4C, 0xDEADBEEF)
    family = free_space_audit._log2_sprites(bytes(image))
    rows = {(row['kind'], row['start']): row['end'] - row['start'] for row in family['rows']}
    assert rows == {('sprite_directory', 0x100): 4 * (3 + 2),
                    ('sprite_definition', 0x800): 0x4C + 4 * 2,
                    ('sprite_piece', 0x1000): 12,
                    ('sprite_piece', 0x1100): 12}
    assert family['note'] == '1 definitions owned, 1 rejected by the field test'
    pairs = {(ref['source'], ref['target']) for ref in family['refs']}
    assert {(0x10C, 0x800), (0x110, 0x900), (0x84C, 0x1000), (0x850, 0x1100),
            (0x1008, 0x2000), (0x1108, 0x2100)} == pairs


def test_text_walk_owns_only_strings_the_reader_test_admits(monkeypatch):
    """A pointer whose bytes are not a terminated printable run owns nothing."""
    monkeypatch.setattr(free_space_audit, 'LOG2_ROSTER_TABLE', 0x100)
    monkeypatch.setattr(free_space_audit, 'LOG2_ROSTER_COUNT', 2)
    monkeypatch.setattr(free_space_audit, 'LOG2_OBJECTIVE_COUNT', 0)
    monkeypatch.setattr(free_space_audit, 'LOG2_FONT_TABLE', 0x300)
    image = bytearray(0x4000)
    base = free_space_audit.LOG2_IMAGE_BASE
    struct.pack_into('<I', image, 0x100, base + 0x800)
    struct.pack_into('<I', image, 0x104, base + 0x810)
    struct.pack_into('<I', image, 0x114, base + 0x950)
    image[0x800:0x804] = b'Yes\0'
    image[0x810:0x813] = b'ab\x01'
    image[0x950:0x952] = b'\x01\x00'
    family = free_space_audit._log2_text(bytes(image))
    owned = {row['start']: row['end'] - row['start']
             for row in family['rows'] if row['kind'] == 'text_string'}
    assert owned == {0x800: 4}
    assert family['note'] == '0 defined font codes, 1 strings'
    assert {ref['target'] for ref in family['refs']} == {0x800, 0x810, 0x950}
    assert {row['kind']: row['end'] - row['start'] for row in family['rows']
            if row['kind'] != 'text_string'} == {'text_font_table': 0x1FC,
                                                 'text_roster_table': 0x28}
