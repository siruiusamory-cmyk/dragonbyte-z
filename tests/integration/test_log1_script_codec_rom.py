"""DBZ-008: the 18 LOG1 script families through the production load path.

Every claim here is measured against the canonical image, named by
``WEBFOOT_LOG1_ROM`` or found at the default ``roms/`` path. The activation-record
codec's operand widths are pinned to the image's own flags table, and each record
must re-encode byte for byte.
"""

import hashlib
import os
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from tools.webfoot.capability import Capability, capabilities
from tools.webfoot.data.script_specs import OPCODE_SETS
from tools.webfoot.formats.script_vm import (
    Entry, ScriptError, assemble, decode_record, disassemble, encode_record)
from tools.webfoot.profile import RomProfileCatalog
from tools.webfoot.scripts import load_scripts, script_families

SHA = '3ba9919e26704b0f5fdc2bfabc7f7a0404c71413761d38abcd94224c3bd4b1b9'
PROFILE = 'legacy_of_goku_usa_a3c8c767'
ENCODING = 'flag_fields_log1_v1'
FLAGS = 0x08142386
LOCAL = 'roms/Dragon Ball Z - The Legacy of Goku (USA).gba'
FAMILIES = 18
START_SLOTS = 282
DISTINCT_STARTS = 282
SEGMENTS = 17332
POOL_BYTES = 118634


def _rom_path():
    path = Path(os.environ.get('WEBFOOT_LOG1_ROM', LOCAL))
    if not path.is_file():
        pytest.skip(f'canonical LOG1 image not present; set WEBFOOT_LOG1_ROM or place it at {LOCAL}')
    return path


@pytest.fixture(scope='module')
def rom():
    path = _rom_path()
    before = path.read_bytes()
    if hashlib.sha256(before).hexdigest() != SHA:
        pytest.skip(f'{path} is not the canonical LOG1 image')
    yield path
    assert hashlib.sha256(path.read_bytes()).hexdigest() == SHA


@pytest.fixture(scope='module')
def image(rom):
    return rom.read_bytes()


@pytest.fixture(scope='module')
def catalog():
    return RomProfileCatalog.load('config/roms.yaml')


@pytest.fixture(scope='module')
def declared(catalog):
    profile = next(item for item in catalog.profiles if item.id == PROFILE)
    return profile.scripts


def _pool(image, item):
    start = item.pool_address.to_file_offset(len(image))
    return image[start:start + item.pool_size]


def _families(image, catalog, declared):
    for item in declared:
        yield item, load_scripts(_rom_path(), catalog, item.family)


def test_all_declared_families_load_through_the_production_path(image, catalog, declared):
    """SC1: 18 of 18 families validate and load through `load_scripts`."""
    profile = next(item for item in catalog.profiles if item.id == PROFILE)
    assert Capability.SCRIPTS in capabilities(profile)
    assert len(script_families(_rom_path(), catalog)) == FAMILIES
    passed = 0
    for item in declared:
        corpus = load_scripts(_rom_path(), catalog, item.family)
        assert not corpus.ir.opaque
        assert len(corpus.ir.entries) == item.count
        assert len(corpus.ir.records) == item.count
        assert corpus.ir.extent == item.pool_size
        assert assemble(corpus.ir) == _pool(image, item)
        passed += 1
        print(f'{item.family} table=0x{item.table_address.raw:08X} count={item.count} '
              f'stride={item.stride} slots={item.slots} '
              f'pool=0x{item.pool_address.raw:08X} pool_size={item.pool_size} PASS')
    print(f'families passed={passed} failed={FAMILIES - passed}')
    assert passed == FAMILIES


def test_the_record_population_is_the_measured_census(image, catalog, declared):
    """SC2: 282 start slots, 282 distinct starts, tiled pools, no cross overlap."""
    slots = 0
    starts = set()
    segments = 0
    spans = []
    for ordinal, (item, corpus) in enumerate(_families(image, catalog, declared)):
        table = item.table_address.to_file_offset(len(image))
        pointers = [struct.unpack_from('<I', image, table + item.stride * index)[0]
                    for index in range(item.count)]
        pool = item.pool_address.raw
        assert min(pointers) == pool
        assert len(set(pointers)) == item.count
        assert all(pointer - pool < item.pool_size for pointer in pointers)
        record_starts = sorted(record.offset for record in corpus.ir.records)
        assert record_starts == sorted(pointer - pool for pointer in pointers)
        assert [record.encoded_length for record in corpus.ir.records] == [
            next_start - start for start, next_start in
            zip(record_starts, record_starts[1:] + [item.pool_size])]
        slots += item.count
        starts.update(pointer for pointer in pointers)
        segments += sum(len(record.segments) for record in corpus.ir.records)
        spans.append((pool, pool + item.pool_size))
    for left in range(len(spans)):
        for right in range(left + 1, len(spans)):
            assert not (spans[left][0] < spans[right][1] and spans[right][0] < spans[left][1])
    print(f'start slots={slots} distinct starts={len(starts)} segments={segments} '
          f'pool bytes={sum(size - start for start, size in spans)}')
    assert slots == START_SLOTS
    assert len(starts) == DISTINCT_STARTS
    assert segments == SEGMENTS
    assert sum(size - start for start, size in spans) == POOL_BYTES


def test_declared_pool_sizes_are_decoder_derived_not_table_minus_pool(image, catalog, declared):
    """SC2: every declared pool_size is the span of the decoded records."""
    differing = []
    padding = 0
    for item, corpus in _families(image, catalog, declared):
        table = item.table_address.to_file_offset(len(image))
        first = min(record.offset for record in corpus.ir.records)
        last = max(record.offset + record.encoded_length for record in corpus.ir.records)
        derived = last - first
        naive = table - item.pool_address.to_file_offset(len(image))
        gap = image[item.pool_address.to_file_offset(len(image)) + last:table]
        assert item.pool_size == derived
        assert set(gap) <= {0}
        padding += len(gap)
        if derived != naive:
            differing.append((item.family, derived, naive, len(gap), gap.hex()))
    for family, derived, naive, size, gap in differing:
        print(f'{family} derived={derived} naive={naive} difference={naive - derived} '
              f'padding={gap}')
    print(f'families where the naive span is larger={len(differing)} '
          f'names={[entry[0] for entry in differing]} total padding={padding}')
    assert [entry[0] for entry in differing] == [
        'descriptor00', 'descriptor01', 'descriptor03', 'descriptor04', 'descriptor06',
        'descriptor07', 'descriptor09', 'descriptor10', 'descriptor11', 'descriptor12',
        'descriptor13', 'descriptor14', 'descriptor16']
    assert [entry[3] for entry in differing] == [1, 2, 3, 1, 2, 2, 3, 3, 3, 3, 1, 1, 3]
    assert padding == 28


def test_a_record_start_is_not_the_interpreter_stream_pointer(image, catalog):
    """SC3: 0x0854B55D is the record; 0x0854B55E is record + 1, the stream pointer."""
    item = next(entry for entry in
                next(profile for profile in catalog.profiles
                     if profile.id == PROFILE).scripts if entry.family == 'descriptor15')
    pool = _pool(image, item)
    start = item.pool_address.raw
    table = item.table_address.to_file_offset(len(image))
    assert struct.unpack_from('<I', image, table)[0] == start == 0x0854B55D
    assert image[0x0854B55D - 0x08000000] == 0x40
    assert image[0x0854B55E - 0x08000000] == 0x81
    first = decode_record(pool, 0, OPCODE_SETS[ENCODING])
    assert first.activations == 0x40
    assert len(first.segments) == 64
    assert first.encoded_length == 0x21A
    assert start + first.encoded_length == 0x0854B777
    assert struct.unpack_from('<I', image, table + 4)[0] == 0x0854B777
    assert image[0x0854B777 - 0x08000000] == 0x10
    assert image[0x0854B778 - 0x08000000] == 0x81
    with pytest.raises(ScriptError):
        decode_record(pool, 1, OPCODE_SETS[ENCODING])


def test_every_record_round_trips_byte_identically(image, catalog, declared):
    """SC4: attempted = identical + rejected, and nothing decodes differently."""
    spec = OPCODE_SETS[ENCODING]
    attempted = identical = rejected = 0
    for item, corpus in _families(image, catalog, declared):
        start = item.pool_address.to_file_offset(len(image))
        for record in corpus.ir.records:
            attempted += 1
            raw = encode_record(record, spec)
            stored = image[start + record.offset:start + record.offset + record.encoded_length]
            if raw == stored:
                identical += 1
            else:
                rejected += 1
    print(f'records attempted={attempted} identical={identical} rejected={rejected}')
    assert attempted == START_SLOTS
    assert rejected == 0
    assert identical + rejected == attempted


def test_the_declared_operand_flags_are_the_images_own_table(image):
    """The width model is evidence, not a constant: it is the ROM's flags table."""
    assert OPCODE_SETS[ENCODING].operand_flags == image[FLAGS - 0x08000000:
                                                      FLAGS - 0x08000000 + 16]
    assert OPCODE_SETS[ENCODING].instructions == ()


def test_ambiguous_reinterpretation_is_refused(image, catalog, declared):
    """SC5: a shifted start or a truncated pool raises instead of decoding."""
    item = declared[15]
    pool = _pool(image, item)
    spec = OPCODE_SETS[ENCODING]
    entries = tuple(Entry(f'root:{index:03d}', record.offset)
                    for index, record in enumerate(
                        load_scripts(_rom_path(), catalog, item.family).ir.records))
    with pytest.raises(ScriptError):
        disassemble(pool[:-1], entries, spec)
    shifted = tuple(Entry(entry.identity, entry.offset + 1) for entry in entries)
    with pytest.raises(ScriptError):
        disassemble(pool, shifted, spec)
    with pytest.raises(ScriptError, match='outside extent'):
        decode_record(pool, len(pool), spec)


def test_event_show_refuses_a_record_family_cleanly(rom):
    """F1: `event show` on a record corpus refuses by name instead of raising KeyError.

    The verb builds a block index from `corpus.ir.blocks`, which a record corpus
    does not have, so before the guard this run exited 1 with `KeyError: 0` and a
    traceback. The assertions below fail on that traceback, on that exit code and
    on an empty stderr, so a reintroduced lookup crash cannot pass.
    """
    identity = f'{PROFILE}:descriptor15:00:slot00'
    completed = subprocess.run(
        [sys.executable, '-B', '-m', 'tools.webfoot', 'event', 'show', str(rom),
         identity, '--family', 'descriptor15'],
        capture_output=True, text=True,
        cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    print(f'exit={completed.returncode} stdout={completed.stdout!r} '
          f'stderr={completed.stderr.strip()!r}')
    assert completed.returncode == 2
    assert completed.stdout == ''
    assert 'Traceback' not in completed.stderr
    assert 'KeyError' not in completed.stderr
    assert 'descriptor15' in completed.stderr
    assert ENCODING in completed.stderr
    assert 'no instruction blocks' in completed.stderr
