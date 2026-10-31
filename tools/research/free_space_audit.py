"""TOOLKIT-011 bounded research report; never imported by production allocation.

The upstream tail is a candidate, not a free-region declaration. This report
cannot promote it, resolve numeric matches, or establish complete ROM ownership.
Run with an explicit canonical ROM path; stdout contains metadata only.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import struct

from tools.webfoot.binary import FileOffset, GbaRomAddress
from tools.webfoot.document import RomDocument
from tools.webfoot.entities import load_placement_types
from tools.webfoot.graphics import load_actor_sprites
from tools.webfoot.layout import RomRange
from tools.webfoot.profile import RomProfileCatalog, VerificationStatus
from tools.webfoot.rom import identify_rom


def candidate_report(image, span, owned, references):
    """Bounded byte-pattern and all-byte u32 audit, with no promotion output.

    owned records are annotations; overlaps are retained, not silently merged.
    references carry source, target and the existing evidence classification.
    Numeric observations stay separate because overlapping source windows cannot
    all be inserted into the production graph as authoritative fields.
    """
    span.validate(len(image))
    known_sources = {r['source'] for r in references}
    hits = []
    for source in range(len(image) - 3):
        raw = struct.unpack_from('<I', image, source)[0]
        try:
            target = GbaRomAddress(raw).to_file_offset(len(image))
        except ValueError:
            continue
        if span.contains(FileOffset(target)) and source not in known_sources:
            hits.append({'source': source, 'target': target,
                         'classification': 'CANDIDATE_REFERENCE',
                         'source_word_aligned': source % 4 == 0})
    inbound = [r for r in references if span.contains(FileOffset(r['target']))]
    overlaps = [r for r in owned if r['start'] < span.end and r['end'] > span.start.value]
    left = [r for r in owned if r['end'] <= span.start.value]
    right = [r for r in owned if r['start'] >= span.end]
    return {
        'status': 'CANDIDATE', 'start': span.start.value, 'end': span.end,
        'size': span.size, 'byte_histogram': dict(sorted(Counter(image[span.start.value:span.end]).items())),
        'neighbor_before': max(left, key=lambda r: (r['end'], r['start'], r['owner']), default=None),
        'neighbor_after': min(right, key=lambda r: (r['start'], r['end'], r['owner']), default=None),
        'known_overlaps': overlaps, 'known_inbound': inbound,
        'reference_counts': dict(sorted(Counter(r['classification'] for r in inbound + hits).items())),
        'candidate_word_aligned_count': sum(r['source_word_aligned'] for r in hits),
        'candidate_observations': hits,
        'reasons_candidate_only': [
            'Upstream copies the tail with INCBIN; no independent unused-section proof.',
            'Unresolved numeric observations are not whitelisted.',
            'Known ownership is incomplete; absent coverage is UNKNOWN, not free.',
            'Computed references, unknown container extents and signature uses are not ruled out.',
        ],
    }


def occupancy(size, owned):
    """Deterministic disjoint coverage, retaining all overlapping annotations."""
    events = {0: [], size: []}
    records = sorted(owned, key=lambda r: (r['start'], r['end'], r['kind'], r['owner']))
    for index, row in enumerate(records):
        RomRange(FileOffset(row['start']), row['end'] - row['start']).validate(size)
        events.setdefault(row['start'], []).append((index, True))
        events.setdefault(row['end'], []).append((index, False))
    active = set()
    result = []
    points = sorted(events)
    for start, end in zip(points, points[1:]):
        for index, entering in events[start]:
            if entering:
                active.add(index)
            else:
                active.remove(index)
        result.append({'start': start, 'end': end,
                       'annotations': sorted(active),
                       'coverage': 'KNOWN_ANNOTATION' if active else 'UNKNOWN'})
    return {'annotations': records, 'segments': result}


def build_model(path, catalog_path=None):
    """The shared annotation/reference model, so a second report cannot drift.

    TOOLKIT-028 verifies one narrow window of the same tail this audit bounds. It
    reuses THIS model rather than building its own, so its negatives are directly
    comparable with the positives recorded here. Returns the raw pieces; it makes
    no judgement and promotes nothing.

    Model selection is PER PROFILE, by exact identity. A profile this audit has no
    entry for is refused by name, so a game joins the proof only through a
    deliberate entry that carries its own evidence, never through another game's
    structures.
    """
    catalog = RomProfileCatalog.load(catalog_path or
                                     Path(__file__).resolve().parents[1] / 'webfoot/data/roms.yaml')
    identification = identify_rom(path, catalog)
    match = identification.profile_match
    if match.status is not VerificationStatus.VERIFIED:
        raise ValueError(f'audit requires a verified profile: {match.reason}; '
                         f'{list(match.mismatches)}')
    builder = model_builder(match.profile.id)
    return builder(path, catalog, identification)


def model_builder(profile_id):
    """The model builder for one exact profile id, or a refusal naming it.

    THE selection point: a profile this audit has no entry for is refused here, by
    name, so a game cannot be audited through another game's structures and adding
    one stays a deliberate edit to `MODEL_BUILDERS`.
    """
    builder = MODEL_BUILDERS.get(profile_id)
    if builder is None:
        raise ValueError(f'audit has no model for profile {profile_id!r}; '
                         f'declared models: {", ".join(sorted(MODEL_BUILDERS))}')
    return builder


def _declared_text(profile, image):
    """The profile's declared text pool, pointer table and pointer words.

    One reader for every modelled profile, so two reports cannot measure a text
    table differently. A profile that declares no text table contributes nothing
    rather than inheriting another game's pool.
    """
    text = profile.text_strings
    if text is None:
        return [], []
    owned = []
    for name, address, size in [('text_pool', text.pool_address, text.pool_size),
                                ('text_table', text.pointer_table_address, text.count * 4)]:
        start = address.to_file_offset(len(image))
        owned.append({'start': start, 'end': start + size,
                      'kind': 'declared_table', 'owner': name, 'status': 'DECLARED'})
    refs = []
    table_start = text.pointer_table_address.to_file_offset(len(image))
    for source in range(table_start, table_start + text.count * 4, 4):
        target = GbaRomAddress(struct.unpack_from('<I', image, source)[0]).to_file_offset(len(image))
        refs.append({'source': source, 'target': target, 'classification': 'CONFIRMED_REFERENCE'})
    return owned, refs


def _buu_model(path, catalog, identification):
    """Buu's Fury: the structures the canonical profile and its decomp declare."""
    profile = identification.profile_match.profile
    image = Path(path).read_bytes()
    RomDocument.from_bytes(image, profile)  # recheck bytes before profile access
    sprites = load_actor_sprites(image, identification)
    types = load_placement_types(path, catalog)
    if types.maps.base_bytes != image:
        raise ValueError('base changed during audit')
    documents = [sprites.reference_document(), types.reference_document()]
    owned = []
    refs = []
    for document in documents:
        for a in document.anchors:
            owned.append({'start': a.range.start.value, 'end': a.range.end,
                          'kind': a.kind, 'owner': a.owner, 'status': 'CONFIRMED'})
        for r in document.references:
            refs.append({'source': r.source.value, 'target': document.target_offset(r).value,
                         'classification': r.classification.value})
    for table_name in ('map_entries', 'enemy_stats', 'character_base_stats'):
        table = getattr(profile, table_name)
        start = table.address.to_file_offset(len(image))
        owned.append({'start': start, 'end': start + table.count * table.record_size,
                      'kind': 'declared_table', 'owner': table_name, 'status': 'DECLARED'})
    text_owned, text_refs = _declared_text(profile, image)
    owned += text_owned
    refs += text_refs
    for item in types.maps.slot_arrays():
        a = item.array
        owned.append({'start': a.file_offset, 'end': a.file_offset + len(a.original_bytes),
                      'kind': 'typed_map_slots' if item.is_typed else 'opaque_map_slots',
                      'owner': str(item.identity), 'status': 'CONFIRMED'})
    for r in types.maps.source_references():
        array = next(a.array for a in types.maps.slot_arrays() if a.identity.index == r.entry_index)
        refs.append({'source': array.file_offset + r.slot_index * 8 + 4,
                     'target': r.target_file_offset, 'classification': 'CONFIRMED_REFERENCE'})
    # Header/startup is explicitly assembled; arbitrary CODE-labelled INCBIN
    # areas are deliberately not misclassified as decoded executable coverage.
    owned.append({'start': 0, 'end': 0x158, 'kind': 'header_startup_code',
                  'owner': 'buusfury/asm/crt0.s', 'status': 'DECLARED'})
    span = RomRange(FileOffset(0x7B89A8), 0x800000 - 0x7B89A8)
    if identify_rom(path, catalog).hashes != identification.hashes:
        raise ValueError('canonical image changed during audit')
    model = {'image': image, 'owned': owned, 'references': refs, 'profile': profile,
             'tail': span}
    model['controls'] = lambda *_: positive_control_windows(model)
    return model


def _fill_tail(image, fill_byte=0xFF):
    """The image's trailing fill run, measured from the bytes rather than declared.

    This is the audit's scan extent, not free space: the seven checks decide that.
    It starts after the LAST non-fill byte, so a profile that names no tail still
    gets the one its own image has, and an image with no trailing fill run is
    refused rather than given an invented extent.
    """
    index = len(image) - 1
    if index < 0 or image[index] != fill_byte:
        raise ValueError('image has no trailing fill run to audit')
    while index >= 0 and image[index] == fill_byte:
        index -= 1
    start = index + 1
    return RomRange(FileOffset(start), len(image) - start)


LOG2_IMAGE_BASE = 0x08000000
LOG2_MAP_ENTRY_TABLE = 0x409368
LOG2_MAP_ENTRY_STRIDE = 0x38
LOG2_MAP_ENTRY_ROOT = 0x2C
LOG2_MAP_ROOT_EXTENT = 0x50
LOG2_MAP_ROOT_LAYERS = (0x14, 0x18, 0x1C, 0x20)
LOG2_MAP_ROOT_TILE_BANKS = 0x4C
LOG2_MAP_ROOT_TABLE_COUNT = 0x24
LOG2_MAP_ROOT_TABLE_BASE = 0x28
LOG2_MAP_ROOT_TABLE_STRIDE = 24
LOG2_MAP_FACTORY = 0x080056A1
LOG2_MAP_LAYER_COLUMNS = 0x15
LOG2_MAP_LAYER_CHUNKS = 0x18
LOG2_MAP_LAYER_ROWS = 0x14
LOG2_TILE_BANK_TABLE = 0x04DF574
LOG2_TILE_BANK_COUNT = 32
LOG2_TILE_BANK_ADDRESS = 0x084DF574
LOG2_MAP_ROOT_STREAM = 0x48
LOG2_SPRITE_TABLE = 0x3B4E74
LOG2_SPRITE_NULLS = 3
LOG2_SPRITE_COUNT = 154
LOG2_SPRITE_COUNT_FIELD = 0x04
LOG2_SPRITE_SLOTS = 0x4C
LOG2_SPRITE_SLOT_LIMIT = 64
LOG2_SPRITE_PIECE = 12
LOG2_SPRITE_PIECE_CONTAINER = 8
LOG2_FONT_TABLE = 0x28724
LOG2_FONT_CODES = 256
LOG2_FONT_EXTENT = 0x1FC
LOG2_ROSTER_TABLE = 0x6F8E40
LOG2_ROSTER_COUNT = 128
LOG2_ROSTER_STRIDE = 0x14
LOG2_ROSTER_STRING_FIELDS = (0, 4)
LOG2_OBJECTIVE_TABLE = 0x6D68DC
LOG2_OBJECTIVE_COUNT = 43
LOG2_OBJECTIVE_STRIDE = 0x10
LOG2_OBJECTIVE_TEXT = 0x0C
LOG2_TEXT_LIMIT = 2048
LOG2_TEXT_PRINTABLE = frozenset((9, 10, 13)) | frozenset(range(0x20, 0x7F))
LOG2_TABLE_KINDS = ('declared_table', 'map_entry_record', 'map_root', 'map_root_table',
                    'map_layer_record', 'tile_bank_table', 'sprite_directory',
                    'text_font_table', 'text_roster_table')


def _word(image, offset):
    return struct.unpack_from('<I', image, offset)[0]


def _address(image, address):
    if LOG2_IMAGE_BASE <= address < LOG2_IMAGE_BASE + len(image):
        return address - LOG2_IMAGE_BASE
    return None


def _container(image, address):
    site = _address(image, address)
    if site is None or site + 8 > len(image):
        return None
    kind, declared = struct.unpack_from('<II', image, site)
    return (kind, declared) if kind in (0, 1, 2) and 1 <= declared <= 0x100000 else None


def _row(start, size, kind, owner):
    return {'start': start, 'end': start + size, 'kind': kind, 'owner': owner,
            'status': 'CONFIRMED'}


def _ref(source, target):
    return {'source': source, 'target': target, 'classification': 'CONFIRMED_REFERENCE'}


def _unique(items, key):
    seen, kept = set(), []
    for item in items:
        identity = key(item)
        if identity in seen:
            continue
        seen.add(identity)
        kept.append(item)
    return kept


def _family(rows, refs, note):
    return {'rows': _unique(rows, lambda r: (r['start'], r['end'], r['kind'], r['owner'])),
            'refs': _unique(refs, lambda r: (r['source'], r['target'])),
            'note': note}


def _log2_map(image):
    """The four map-container families, walked from the readers' own fields.

    Map_Entries: the entry table at file 0x409368, stride 0x38, walked until its
    `+0x2C` word stops naming an image address. That field is the root pointer
    array (`ldr r0,[r0,#0x2c]` at 0x0800EB4C). Map_Root: the 0x50 B records those
    array elements name, each holding four layer pointers at `+0x14..+0x20`, a
    stream pointer at `+0x48` (`ldr r0,[r1,#0x48]` at 0x080050DA) and the tile-bank
    table at `+0x4C`. The four layer slots have no located reader; their content is
    the evidence - 1,294 of the 1,344 targets carry the dominant factory word
    0x080056A1 at +0x00. Map_RootTable: the row array the root's `+0x24` count and
    `+0x28` base name (`ldr r1,[r0,#0x24]` at 0x0800EB5A, `ldr r1,[r0,#0x28]` at
    0x0800EB2E), 24 B per row; that stride has no operand-size instruction and
    rests on 707 of 710 rows decoding as rect-consistent coordinate pairs. Map_Layer:
    the dominant records the root's four slots name, whose `+0x14`/`+0x15` byte
    counts bound the container pointer array at `+0x18` (`ldrb r6,[r5,#0x14]`,
    `ldrb r0,[r5,#0x15]`, `ldr r0,[r0,#0x18]` at 0x08005300). Sources:
    TABLE_LEDGER.csv rows Map_Entries, Map_Root, Map_Layer, Map_RootTable, and
    FORMAT_REUSE.md "The map container". The 50 layer records whose factory word is
    not 0x080056A1 carry no established extent and are reported, not owned.
    """
    rows, refs = [], []
    entries, offset = [], LOG2_MAP_ENTRY_TABLE
    while offset + LOG2_MAP_ENTRY_STRIDE <= len(image) and _address(
            image, _word(image, offset + LOG2_MAP_ENTRY_ROOT)) is not None:
        entries.append(offset)
        offset += LOG2_MAP_ENTRY_STRIDE
    rows.append(_row(LOG2_MAP_ENTRY_TABLE, LOG2_MAP_ENTRY_STRIDE * len(entries),
                     'map_entry_record', 'map_entries'))
    bases = []
    for site in entries:
        target = _address(image, _word(image, site + LOG2_MAP_ENTRY_ROOT))
        bases.append(target)
        refs.append(_ref(site + LOG2_MAP_ENTRY_ROOT, target))
    roots, layers, chunk_words = set(), {}, []
    for base in sorted(set(bases)):
        later = [other for other in bases if other > base]
        limit = min(later) if later else base + LOG2_MAP_ROOT_EXTENT
        cursor = base
        while cursor + 4 <= limit:
            site = _address(image, _word(image, cursor))
            if site is None or site + LOG2_MAP_ROOT_EXTENT > len(image):
                break
            if _word(image, site + LOG2_MAP_ROOT_TILE_BANKS) != LOG2_TILE_BANK_ADDRESS:
                break
            roots.add(site)
            refs.append(_ref(cursor, site))
            cursor += 4
    table_rows = []
    for site in sorted(roots):
        rows.append(_row(site, LOG2_MAP_ROOT_EXTENT, 'map_root', 'map_root'))
        for field in LOG2_MAP_ROOT_LAYERS:
            target = _address(image, _word(image, site + field))
            if target is not None:
                refs.append(_ref(site + field, target))
                layers[target] = _word(image, target)
        refs.append(_ref(site + LOG2_MAP_ROOT_TILE_BANKS,
                         _address(image, _word(image, site + LOG2_MAP_ROOT_TILE_BANKS))))
        stream = _address(image, _word(image, site + LOG2_MAP_ROOT_STREAM))
        if stream is not None:
            refs.append(_ref(site + LOG2_MAP_ROOT_STREAM, stream))
        base = _address(image, _word(image, site + LOG2_MAP_ROOT_TABLE_BASE))
        if base is None:
            continue
        refs.append(_ref(site + LOG2_MAP_ROOT_TABLE_BASE, base))
        count = _word(image, site + LOG2_MAP_ROOT_TABLE_COUNT)
        if 0 < count <= 0x1000 and base + LOG2_MAP_ROOT_TABLE_STRIDE * count <= len(image):
            table_rows.append(_row(base, LOG2_MAP_ROOT_TABLE_STRIDE * count,
                                   'map_root_table', 'map_root_table'))
    rows += table_rows
    others, dominant, nulls = 0, 0, 0
    for site in sorted(layers):
        if layers[site] != LOG2_MAP_FACTORY:
            others += 1
            continue
        count = image[site + LOG2_MAP_LAYER_ROWS] * image[site + LOG2_MAP_LAYER_COLUMNS]
        size = LOG2_MAP_LAYER_CHUNKS + 4 * count
        if site + size > len(image):
            others += 1
            continue
        rows.append(_row(site, size, 'map_layer_record', 'map_layer'))
        dominant += 1
        for index in range(count):
            chunk_words.append(site + LOG2_MAP_LAYER_CHUNKS + 4 * index)
    chunk_resolved = 0
    for source in chunk_words:
        target = _address(image, _word(image, source))
        if target is None:
            nulls += 1
        else:
            chunk_resolved += 1
            refs.append(_ref(source, target))
    note = ('%d/%d entry words, %d roots (%d layer slots all resolved, %d stream words, '
            '%d tile-bank words, %d root-table bases), %d root-table rows, %d dominant '
            'layer records, %d/%d chunk slots resolved with %d null cells, %d '
            'other-factory layer records not owned'
            % (len(entries), len(entries), len(roots), len(roots) * 4, len(roots),
               len(roots), len(table_rows), len(table_rows), dominant, chunk_resolved,
               len(chunk_words), len(chunk_words) - chunk_resolved, others))
    return _family(rows, refs, note)


def _log2_banks(image):
    """TileBank_Table: the 32-word map bank table, each word a kind-1 container.

    The table is 32 words at file 0x04DF574 (address 0x084DF574); the loader reads
    it through the map root's `+0x4C` word (`lsls r0,r0,#2` at 0x08005146,
    `ldr r1,[r1,#0x4c]` at 0x08005148, decode at 0x0800514E). Source:
    TABLE_LEDGER.csv row TileBank_Table and FORMAT_REUSE.md "The tile banks".

    TileBank_Character is NOT modelled: its three instances are not locatable from
    the bytes. The character loader at 0x080072C4 takes its container from
    record+0x28 to +0x2C to +0x4 and its destination from VRAM 0x06010000, so it
    names no ROM base and no count, and 733 words image-wide are kind-1 headers
    declaring 4096 B. Any three of them would be a choice, not a measurement.
    """
    rows, refs = [], []
    rows.append(_row(LOG2_TILE_BANK_TABLE, 4 * LOG2_TILE_BANK_COUNT,
                     'tile_bank_table', 'tile_bank_table'))
    for index in range(LOG2_TILE_BANK_COUNT):
        source = LOG2_TILE_BANK_TABLE + 4 * index
        target = _address(image, _word(image, source))
        if target is not None:
            refs.append(_ref(source, target))
    return _family(rows, refs, '32 map banks; the count is measured, a longer valid run exists')


def _log2_sprites(image):
    """The sprite asset directory, its definitions and their 12-byte pieces.

    The directory is 154 structure pointers at file 0x3B4E74 after three null
    words; the resolver at 0x08009324 reads `0x083B4E74 + 4*id`. A definition
    carries a u32 slot count at `+0x04` and its slot array at `+0x4C`; each slot
    names a 12-byte piece whose `+8` word is a container header. A definition is
    owned only when its count is 1..64, every slot resolves inside the image and
    every piece's `+8` word is a container header; 134 of 154 pass and 20 are
    reported, never guessed. The record EXTENT is the weaker part of this row: the
    `0x4C + 4*count` formula has no operand-size instruction behind it and no
    located reader for `+0x04` or `+0x4C` exists inside 0x08009324..0x08009400, so
    the extent is SUPPORTED by the field content and by zero overlaps between the
    134 records, not proven by code. Sources: TABLE_LEDGER.csv row
    Sprite_Directory and FORMAT_REUSE.md "The sprite asset directory".
    """
    rows, refs = [], []
    rows.append(_row(LOG2_SPRITE_TABLE, 4 * (LOG2_SPRITE_NULLS + LOG2_SPRITE_COUNT),
                     'sprite_directory', 'sprite_directory'))
    pieces, rejected = {}, []
    for index in range(LOG2_SPRITE_COUNT):
        source = LOG2_SPRITE_TABLE + 4 * (LOG2_SPRITE_NULLS + index)
        site = _address(image, _word(image, source))
        if site is None:
            rejected.append(index)
            continue
        refs.append(_ref(source, site))
        count = _word(image, site + LOG2_SPRITE_COUNT_FIELD)
        size = LOG2_SPRITE_SLOTS + 4 * count
        if not 0 < count <= LOG2_SPRITE_SLOT_LIMIT or site + size > len(image):
            rejected.append(index)
            continue
        slots = [LOG2_SPRITE_SLOTS + 4 * slot for slot in range(count)]
        targets = [_address(image, _word(image, site + field)) for field in slots]
        if any(target is None or target + LOG2_SPRITE_PIECE > len(image)
               for target in targets):
            rejected.append(index)
            continue
        containers = [_word(image, target + LOG2_SPRITE_PIECE_CONTAINER) for target in targets]
        if any(_container(image, container) is None for container in containers):
            rejected.append(index)
            continue
        rows.append(_row(site, size, 'sprite_definition', 'sprite_definition'))
        for field, target, container in zip(slots, targets, containers):
            refs.append(_ref(site + field, target))
            refs.append(_ref(target + LOG2_SPRITE_PIECE_CONTAINER, _address(image, container)))
            pieces[target] = LOG2_SPRITE_PIECE
    for site in sorted(pieces):
        rows.append(_row(site, pieces[site], 'sprite_piece', 'sprite_piece'))
    return _family(rows, refs, '%d definitions owned, %d rejected by the field test'
                   % (LOG2_SPRITE_COUNT - len(rejected), len(rejected)))


def _log2_text(image):
    """Text_Strings: the font offset table, the roster table and their strings.

    The font table is 256 u16 record offsets at file 0x28724, read at 0x0801F744;
    the width is the u16 at the record's own offset and the advance is width+1.
    K-3956 promotes 508 B of that table and places the last 4 B inside the stored
    container that begins at 0x28920, so the owned extent is the 508 B the evidence
    pins rather than the full 512 B of codes. The roster table is 128 records of
    0x14 at file 0x6F8E40 whose `+0x00` and `+0x04` words are string pointers; the
    objective table's `+0x0C` word is a text pointer. A string is owned only when
    it terminates inside the image within 2048 bytes and every byte is printable by
    the routine's own test. Sources: TABLE_LEDGER.csv row Text_Strings,
    FORMAT_REUSE.md "The text", and K-3956 (the roster and objective record fields).
    """
    rows, refs = [], []
    offsets = [struct.unpack_from('<H', image, LOG2_FONT_TABLE + 2 * code)[0]
               for code in range(LOG2_FONT_CODES)]
    defined = [(code, value) for code, value in enumerate(offsets) if value]
    rows.append(_row(LOG2_FONT_TABLE, LOG2_FONT_EXTENT, 'text_font_table',
                     'text_font_table'))
    rows.append(_row(LOG2_ROSTER_TABLE, LOG2_ROSTER_STRIDE * LOG2_ROSTER_COUNT,
                     'text_roster_table', 'text_roster_table'))

    def measured(site):
        end = site
        while end < len(image) and image[end] != 0 and end - site < LOG2_TEXT_LIMIT:
            end += 1
        if end >= len(image) or image[end] != 0:
            return None
        if any(byte not in LOG2_TEXT_PRINTABLE for byte in image[site:end]):
            return None
        return end - site + 1

    strings = {}
    for index in range(LOG2_ROSTER_COUNT):
        for field in LOG2_ROSTER_STRING_FIELDS:
            source = LOG2_ROSTER_TABLE + LOG2_ROSTER_STRIDE * index + field
            site = _address(image, _word(image, source))
            if site is None:
                continue
            refs.append(_ref(source, site))
            size = measured(site)
            if size is not None:
                strings[site] = size
    for index in range(LOG2_OBJECTIVE_COUNT):
        source = LOG2_OBJECTIVE_TABLE + LOG2_OBJECTIVE_STRIDE * index + LOG2_OBJECTIVE_TEXT
        site = _address(image, _word(image, source))
        if site is None:
            continue
        refs.append(_ref(source, site))
        size = measured(site)
        if size is not None:
            strings[site] = size
    for site in sorted(strings):
        rows.append(_row(site, strings[site], 'text_string', 'text_string'))
    return _family(rows, refs, '%d defined font codes, %d strings'
                   % (len(defined), len(strings)))


def _log2_decoded(image):
    """Every LOG2 family this audit knows, decoded from the canonical bytes.

    Opcode_Stream is deliberately absent as a separate family: its 86 streams are
    the profile's own `scripts` slot words, already owned and referenced by that
    declaration (TOOLKIT-006, K-3956), so a second row would duplicate it.
    """
    return {'map_entries_and_layers': _log2_map(image),
            'tile_banks': _log2_banks(image),
            'sprite_directory': _log2_sprites(image),
            'text_strings': _log2_text(image)}


def log2_family_stats(image):
    """Per-family rows, owned bytes, references and distinct targets from the bytes.

    The report quotes these numbers, so they are measured by the same code that
    puts the rows into the model rather than counted by hand.
    """
    stats = {}
    for name, family in _log2_decoded(image).items():
        stats[name] = {
            'rows': len(family['rows']),
            'owned_bytes': sum(row['end'] - row['start'] for row in family['rows']),
            'references': len(family['refs']),
            'distinct_targets': len({row['target'] for row in family['refs']}),
            'note': family['note'],
        }
    return stats


def _log2_model(path, catalog, identification):
    """Legacy of Goku II: what this profile declares plus what its formats decode to.

    Sources for every row, all LOG2. The profile's `scripts` block cites TOOLKIT-006
    and docs/research/SCRIPT_VM.md with the native caller range 0x08004A86..0x08004AE4,
    and K-3956 reads the same 43 x 0x10 table at file 0x6D68DC with the bound
    `cmp r6,#0x2B` at 0x08004AE2 and the slots at +0x04 and +0x08 passed to the
    opcode interpreter at 0x08004A90 and 0x08004AB8. The text table's source is the
    profile's own TOOLKIT-005 evidence, read here by the shared reader. The header
    row is the LoG II decomp's own layout: `asm/buu.s` INCBINs file 0x0..0xC0 as
    `RomHeader`, `INCLUDE crt0.s` as `ROM_CRT0` at 0x080000C0 and INCBINs
    0x100..0x800000 as `ROM_REMAINDER` (scatter.ld). That is the LOG2 counterpart of
    Buu's `asm/crt0.s` owner, not that path re-used.

    Beyond the two declared structures the model carries every LOG2 family this
    image's own formats decode, each walked in `_log2_decoded` and each citing the
    LOG2 artifact it comes from: the four map-container families (TABLE_LEDGER.csv
    rows Map_Entries, Map_Root, Map_Layer, Map_RootTable and FORMAT_REUSE.md "The
    map container"), the tile-bank families (rows TileBank_Table and
    TileBank_Character, FORMAT_REUSE.md "The tile banks"), the sprite asset
    directory (row Sprite_Directory, FORMAT_REUSE.md "The sprite asset directory")
    and text storage (row Text_Strings, FORMAT_REUSE.md "The text", K-3956). The
    opcode-stream family needs no new row: its 86 streams ARE the `scripts` slot
    words the profile already declares (row Opcode_Stream, format_reuse.py's 539 B).

    Nothing is borrowed from Buu's Fury: no BF offset, stride, count, table base or
    record layout appears here, and the profile's BF-only structures
    (`actor_sprites`, `placement_types`, `map_entries`) stay absent rather than
    substituted. A family whose layout this image does not pin down contributes
    nothing and is reported instead.
    """
    profile = identification.profile_match.profile
    image = Path(path).read_bytes()
    RomDocument.from_bytes(image, profile)
    owned = []
    refs = []
    for family in profile.scripts or ():
        table_start = family.table_address.to_file_offset(len(image))
        pool_start = family.pool_address.to_file_offset(len(image))
        owned.append({'start': pool_start, 'end': pool_start + family.pool_size,
                      'kind': 'declared_table', 'owner': f'scripts_pool:{family.family}',
                      'status': 'DECLARED'})
        owned.append({'start': table_start, 'end': table_start + family.count * family.stride,
                      'kind': 'declared_table', 'owner': f'scripts_table:{family.family}',
                      'status': 'DECLARED'})
        for index in range(family.count):
            for slot in family.slots:
                source = table_start + index * family.stride + slot
                raw = struct.unpack_from('<I', image, source)[0]
                if raw == 0:
                    continue
                try:
                    target = GbaRomAddress(raw).to_file_offset(len(image))
                except ValueError as exc:
                    raise ValueError(
                        f'scripts:{family.family} slot word at 0x{source:06X} names '
                        f'0x{raw:08X}, which is not in this image') from exc
                refs.append({'source': source, 'target': target,
                             'classification': 'CONFIRMED_REFERENCE'})
    text_owned, text_refs = _declared_text(profile, image)
    owned += text_owned
    refs += text_refs
    for family in _log2_decoded(image).values():
        owned += family['rows']
        refs += family['refs']
    owned.append({'start': 0, 'end': 0x158, 'kind': 'header_startup_code',
                  'owner': 'legacyofgoku2-decomp-src/asm/buu.s', 'status': 'DECLARED'})
    if identify_rom(path, catalog).hashes != identification.hashes:
        raise ValueError('canonical image changed during audit')
    model = {'image': image, 'owned': owned, 'references': refs, 'profile': profile,
             'tail': _fill_tail(image)}
    model['controls'] = lambda *_: positive_control_windows(model, LOG2_TABLE_KINDS)
    return model


MODEL_BUILDERS = {
    'buus_fury_usa_rev0_01c1707f': _buu_model,
    'legacy_of_goku_ii_usa_rev0_204142e1': _log2_model,
}


def positive_control_windows(model, table_kinds=('declared_table',)):
    """Windows this project independently models as USED, for scanner controls.

    A negative result is evidence only if the SAME procedure returns a positive on
    live structures, so each control is derived from the model rather than picked
    by eye, and each names the specific check it must trip. A control that failed
    for some unrelated reason would prove nothing about the check it exercises, so
    the caller asserts the named checks, not merely a REJECTED verdict.

    One control per detection path the window proof depends on:

      * `header_startup`    - `bounds` and `fill`, on the declared header;
      * `declared_table`    - `known_overlap`, on the largest modelled table. The
                              kind set is a parameter so a model that has decoded
                              tables of its own can put the LARGEST of them under
                              the control; the default set is the only kind the
                              Buu's Fury model has, so its control is unchanged;
      * `referenced_target` - `known_inbound`, on the most-referenced target in
                              the production graph;
      * `candidate_target`  - `candidate_target`, on a window placed at an actual
                              TOOLKIT-011 candidate observation. That window is
                              `FF` fill inside the same tail, so `candidate_target`
                              is the only thing that can reject it - which is
                              precisely the discrimination the narrow proof rests on.
    """
    owned, refs, span = model['owned'], model['references'], model['tail']
    windows = [('header_startup', RomRange(FileOffset(0), 0x100), ('bounds', 'fill'))]

    table = max((r for r in owned if r['kind'] in table_kinds),
                key=lambda r: (r['end'] - r['start'], r['start']))
    windows.append((f"{table['kind']}:{table['owner']}",
                    RomRange(FileOffset(table['start']), 0x100), ('known_overlap',)))

    counts = Counter(r['target'] for r in refs)
    target = max(counts, key=lambda t: (counts[t], -t))
    windows.append((f'referenced_target:0x{target:06X}',
                    RomRange(FileOffset(target), 4), ('known_inbound',)))

    hits = candidate_report(model['image'], span, [], [])['candidate_observations']
    if hits:
        probe = min(h['target'] for h in hits)
        windows.append((f'candidate_target:0x{probe:06X}',
                        RomRange(FileOffset(probe), 4), ('candidate_target',)))
    return windows


def audit(path, catalog_path=None):
    catalog = RomProfileCatalog.load(catalog_path or
                                     Path(__file__).resolve().parents[1] / 'webfoot/data/roms.yaml')
    model = build_model(path, catalog_path=catalog_path)
    image, owned, refs, profile, span = (model['image'], model['owned'], model['references'],
                                         model['profile'], model['tail'])
    candidate = candidate_report(image, span, owned, refs)
    annotated = owned + [{'start': span.start.value, 'end': span.end,
                         'kind': 'candidate_tail', 'owner': 'upstream_tail', 'status': 'CANDIDATE'}]
    return {'profile_id': profile.id, 'base_sha256': profile.sha256,
            'candidate': candidate, 'occupancy': occupancy(len(image), annotated),
            'reference_model_count': len(refs),
            'verified_capacity': sum(f.range.size for f in profile.free_regions),
            'decision': 'NOT_PROMOTED',
            'limits': 'Partial typed ownership only; broad INCBINs remain semantically UNKNOWN.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.rom), indent=2, sort_keys=True))
