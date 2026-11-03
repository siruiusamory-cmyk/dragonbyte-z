
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterator

from ..binary import GBA_ROM_BASE as _GBA_ROM_BASE

# The RECORD SIZE below is format structure the codec enforces.
# The START/LAST/COUNT that follow are one game's measured extent, kept as the EVIDENCE it was verified against; no production caller uses them.
# A live read takes address, count and stride from profile.enemy_stats / profile.character_base_stats, which is the authority (CQA-15); relocating a live reader onto these constants would reintroduce the duplicate authority this note exists to prevent.

ENEMY_RECORD_SIZE = 0x1C

ENEMY_TABLE_START = 0x00711274

ENEMY_TABLE_LAST = 0x007121C4

ENEMY_RECORD_COUNT = 141


LOG2_ENEMY_RECORD_SIZE = 0x18

LOG2_ENEMY_HP_OFFSET = 0x04

LOG2_ENEMY_UNKNOWN_10_VALUES = (64, 96, 128)

LOG2_ENEMY_HP_OBSERVED_RANGE = (1, 10_200)


BASE_STAT_RECORD_SIZE = 0x12

BASE_STAT_TABLE_START = 0x006FDA4C

BASE_STAT_RECORD_COUNT = 9

BASE_STAT_NAMES = (
    "Goku",
    "Gohan",
    "Goten",
    "Trunks",
    "Vegeta",
    "Gotenks",
    "Vegito",
    "Gogeta",
    "Hercule",
)

#: The convention is BuusFuryToolkit's README ("ROM offset + 0x08000000"); the
#: value itself is `binary.GBA_ROM_BASE`, the one owner of window semantics.
GBA_ROM_BASE = _GBA_ROM_BASE


@dataclass(frozen=True)
class EnemyRecord:

    offset: int
    exp: int
    hp: int
    type_id: int
    level: int
    strength: int
    power: int
    endurance: int

    @property
    def gba_address(self) -> int:
        return self.offset + GBA_ROM_BASE


@dataclass(frozen=True)
class Log2EnemyRecord:
    """One LOG2 enemy stat record, carrying only the field with a proven reader.

    HP is the u32 at ``LOG2_ENEMY_HP_OFFSET``. Its source is measured, not
    inferred: the enemy constructor at ROM 0x0800E280 loads it with
    ``ldr r0,[r1,#4]`` at 0x0800E2E6 and stores it to ``[entity+0x188]`` with
    ``str r0,[r5,#8]`` at 0x0800E2EA, and a runtime sweep found entity
    0x0203BC28 caching record 41's address with live HP 130 matching
    ``u32[record+4]``.

    The record's other fields are deliberately absent rather than named.
    +0x00 is HP-shaped (0..60000 across the table) but no reader for it was
    found, so calling it a stat would be a guess; +0x08 likewise has no located
    reader. +0x0C, +0x0D and +0x0E are three separate u8 fields rather than one
    packed word - the scouter reader loads each with its own ``ldrb``, at
    ``[r6,#0xC]``, ``[r6,#0xD]`` and ``[r6,#0xE]`` - and +0x0F takes three
    measured values (0x26, 0x40, 0x80). +0x10 takes only three values, and
    +0x14 is a pointer to a descriptor whose words are code addresses. Naming a
    field here would make it editable, so only HP is named.
    """

    offset: int
    hp: int

    @property
    def gba_address(self) -> int:
        return self.offset + GBA_ROM_BASE


@dataclass(frozen=True)
class BaseStatRecord:

    offset: int
    level: int
    hp: int
    ep: int
    strength: int
    power: int
    endurance: int
    speed: int
    person: int
    technique_count: int

    @property
    def gba_address(self) -> int:
        return self.offset + GBA_ROM_BASE


def decode_enemy_record(data: bytes, offset: int) -> EnemyRecord:
    blob = data[offset : offset + ENEMY_RECORD_SIZE]
    if len(blob) < ENEMY_RECORD_SIZE:
        raise ValueError(f"short enemy record at {offset:#010x}")
    return EnemyRecord(
        offset=offset,
        exp=int.from_bytes(blob[0:3], "little"),
        hp=int.from_bytes(blob[4:7], "little"),
        type_id=int.from_bytes(blob[8:10], "little"),
        level=blob[12],
        strength=blob[13],
        power=blob[14],
        endurance=blob[15],
    )


def decode_log2_enemy_record(data: bytes, offset: int) -> Log2EnemyRecord:
    """Read LOG2's 0x18-byte enemy record. Only HP is decoded."""
    blob = data[offset : offset + LOG2_ENEMY_RECORD_SIZE]
    if len(blob) < LOG2_ENEMY_RECORD_SIZE:
        raise ValueError(f"short LOG2 enemy record at {offset:#010x}")
    return Log2EnemyRecord(
        offset=offset,
        hp=int.from_bytes(
            blob[LOG2_ENEMY_HP_OFFSET : LOG2_ENEMY_HP_OFFSET + 4], "little"
        ),
    )


def decode_base_stat_record(data: bytes, offset: int) -> BaseStatRecord:
    blob = data[offset : offset + BASE_STAT_RECORD_SIZE]
    if len(blob) < BASE_STAT_RECORD_SIZE:
        raise ValueError(f"short base-stat record at {offset:#010x}")
    return BaseStatRecord(
        offset=offset,
        level=blob[0],
        hp=int.from_bytes(blob[2:4], "little"),
        ep=int.from_bytes(blob[4:6], "little"),
        strength=blob[6],
        power=blob[7],
        endurance=blob[8],
        speed=blob[9],
        person=blob[10],
        technique_count=blob[11],
    )


def looks_like_enemy_record(data: bytes, offset: int) -> bool:
    blob = data[offset : offset + ENEMY_RECORD_SIZE]
    if len(blob) < ENEMY_RECORD_SIZE:
        return False
    if blob[3] != 0 or blob[7] != 0:
        return False
    exp = int.from_bytes(blob[0:3], "little")
    hp = int.from_bytes(blob[4:7], "little")
    if exp >= 400_000 or hp >= 400_000:
        return False
    return 0 < blob[12] <= 200


def looks_like_log2_enemy_record(data: bytes, offset: int) -> bool:
    """Whether 0x18 bytes at ``offset`` have the shape of a LOG2 enemy record.

    This is a positive structural test in its own right. It does not call,
    wrap or fall through to `looks_like_enemy_record`, and deliberately so:
    Buu's test is not a guard against these bytes. Measured against the
    canonical image, it ACCEPTS 109 of 109 LOG2 records, because a LOG2 record's
    u32 values at +0x00 and +0x04 are small enough to leave +0x03 and +0x07
    zero, satisfying both pad-byte gates by accident, while +0x0C lands in
    1..200 and satisfies the level gate too. It reads a 0x1C window over
    0x18-stride data and never checks stride, so it is loose here rather than
    strict, and a review measured 312 further 4-aligned offsets near the table
    that also pass it. Routing LOG2 bytes through the Buu codec would decode at
    stride 0x1C with a 3-byte HP and scatter writes across record boundaries,
    so `enemy_codec_for_record_size` - not this predicate and not Buu's - is the
    safety boundary that keeps the two apart.

    The three checks are what held across all 109 records of the verified
    table. HP at +0x04 within ``LOG2_ENEMY_HP_OBSERVED_RANGE`` is a DECLARED
    bound from the observed corpus, not a proven engine limit: nothing in the
    ROM was found to enforce it, and the u32 width bound that encode checks is
    separate from it. The +0x10 word being one of three measured values and
    +0x14 resolving inside the GBA ROM window are the discriminating checks,
    because a Buu record's bytes at those offsets are stat bytes rather than an
    enum value and a ROM pointer.
    """
    blob = data[offset : offset + LOG2_ENEMY_RECORD_SIZE]
    if len(blob) < LOG2_ENEMY_RECORD_SIZE:
        return False
    hp = int.from_bytes(blob[LOG2_ENEMY_HP_OFFSET : LOG2_ENEMY_HP_OFFSET + 4], "little")
    low, high = LOG2_ENEMY_HP_OBSERVED_RANGE
    if not low <= hp <= high:
        return False
    if int.from_bytes(blob[0x10:0x14], "little") not in LOG2_ENEMY_UNKNOWN_10_VALUES:
        return False
    descriptor = int.from_bytes(blob[0x14:0x18], "little")
    return GBA_ROM_BASE <= descriptor < GBA_ROM_BASE + 0x02000000


def iter_enemy_records(data: bytes) -> Iterator[EnemyRecord]:
    for offset in range(
        ENEMY_TABLE_START,
        ENEMY_TABLE_LAST + 1,
        ENEMY_RECORD_SIZE,
    ):
        yield decode_enemy_record(data, offset)


def iter_base_stat_records(data: bytes) -> Iterator[BaseStatRecord]:
    """Yield the 9 playable-character base-stat records. EVIDENCE ORACLE."""
    for index in range(BASE_STAT_RECORD_COUNT):
        offset = BASE_STAT_TABLE_START + index * BASE_STAT_RECORD_SIZE
        yield decode_base_stat_record(data, offset)


def find_enemy_by_hp(data: bytes, hp: int) -> list[EnemyRecord]:
    return [r for r in iter_enemy_records(data) if r.hp == hp]




ENEMY_DECODED_SPANS = (
    (0x00, 3, "exp"),
    (0x04, 3, "hp"),
    (0x08, 2, "type_id"),
    (0x0C, 1, "level"),
    (0x0D, 1, "strength"),
    (0x0E, 1, "power"),
    (0x0F, 1, "endurance"),
)

BASE_STAT_DECODED_SPANS = (
    (0x00, 1, "level"),
    (0x02, 2, "hp"),
    (0x04, 2, "ep"),
    (0x06, 1, "strength"),
    (0x07, 1, "power"),
    (0x08, 1, "endurance"),
    (0x09, 1, "speed"),
    (0x0A, 1, "person"),
    (0x0B, 1, "technique_count"),
)


class StatEncodeError(ValueError):
    """Raised when a stat value cannot fit the width the ROM gave it."""


class UnknownEnemyCodecError(ValueError):
    """Raised when no enemy record codec implements a declared record size."""


@dataclass(frozen=True)
class StatIdentity:
    """A within-profile identity: the same key names a different record in another profile."""

    kind: str
    key: int

    def __post_init__(self) -> None:
        if self.kind not in ("enemy", "character"):
            raise ValueError(f"unknown stat record kind: {self.kind!r}")
        if type(self.key) is not int or self.key < 0:
            raise ValueError("identity key must be a non-negative integer")

    def __str__(self) -> str:
        return f"{self.kind}:{self.key}"


def enemy_identity(record: EnemyRecord) -> StatIdentity:
    """A stable key: type ids are unique but only mostly ascending, so never a sort order or an array index."""
    return StatIdentity(kind="enemy", key=record.type_id)


def character_identity(index: int, count: int) -> StatIdentity:
    if type(index) is not int or not 0 <= index < count:
        raise ValueError(f"character index out of range: {index}")
    return StatIdentity(kind="character", key=index)


def character_alias(index: int, count: int) -> str:
    """A display alias only, never an identity: the names are INFERRED from the roster."""
    if count != len(BASE_STAT_NAMES):
        raise ValueError(
            f"no verified display roster for a profile declaring {count} character "
            f"records; the verified roster names are Buu's {len(BASE_STAT_NAMES)}"
        )
    if not 0 <= index < len(BASE_STAT_NAMES):
        raise ValueError(
            f"no verified display alias for character index {index}; the verified "
            f"roster is 0..{len(BASE_STAT_NAMES) - 1}"
        )
    return BASE_STAT_NAMES[index]


def _put_uint(buffer: bytearray, offset: int, width: int, value: int,
              field: str) -> None:
    if type(value) is not int:
        raise StatEncodeError(
            f"{field} must be an integer, got {type(value).__name__}"
        )
    maximum = (1 << (width * 8)) - 1
    if not 0 <= value <= maximum:
        raise StatEncodeError(
            f"{field}={value} does not fit an unsigned {width * 8}-bit field "
            f"(0..{maximum})"
        )
    buffer[offset : offset + width] = value.to_bytes(width, "little")


def encode_enemy_record(record: EnemyRecord, original: bytes) -> bytes:
    if len(original) != ENEMY_RECORD_SIZE:
        raise StatEncodeError(
            f"enemy record backing must be exactly {ENEMY_RECORD_SIZE} bytes; "
            f"got {len(original)}"
        )
    blob = bytearray(original)
    _put_uint(blob, 0x00, 3, record.exp, "exp")
    _put_uint(blob, 0x04, 3, record.hp, "hp")
    _put_uint(blob, 0x08, 2, record.type_id, "type_id")
    _put_uint(blob, 0x0C, 1, record.level, "level")
    _put_uint(blob, 0x0D, 1, record.strength, "strength")
    _put_uint(blob, 0x0E, 1, record.power, "power")
    _put_uint(blob, 0x0F, 1, record.endurance, "endurance")
    return bytes(blob)


def encode_log2_enemy_record(record: Log2EnemyRecord, original: bytes) -> bytes:
    """Rewrite only HP, preserving the record's other 20 bytes byte-for-byte.

    The preservation is structural rather than a promise kept by care: the
    original is copied and exactly the four bytes of the HP span are overwritten,
    so +0x00, +0x08, the four bytes at +0x0C..0x0F, the +0x10 enum and the +0x14
    descriptor pointer survive unread and unwritten. That is what makes HP-only
    authoring safe against a record whose other fields are unmeasured.
    """
    if len(original) != LOG2_ENEMY_RECORD_SIZE:
        raise StatEncodeError(
            f"LOG2 enemy record backing must be exactly "
            f"{LOG2_ENEMY_RECORD_SIZE} bytes; got {len(original)}"
        )
    blob = bytearray(original)
    _put_uint(blob, LOG2_ENEMY_HP_OFFSET, 4, record.hp, "hp")
    return bytes(blob)


LOG2_ENEMY_DECODED_SPANS = ((LOG2_ENEMY_HP_OFFSET, 4, "hp"),)


@dataclass(frozen=True)
class EnemyCodec:
    """The decode/encode/recognise trio for one enemy record format."""

    record_size: int
    decode: Callable[[bytes, int], object]
    encode: Callable[[object, bytes], bytes]
    looks_like: Callable[[bytes, int], bool]
    spans: tuple[tuple[int, int, str], ...]


BUUS_ENEMY_CODEC = EnemyCodec(
    ENEMY_RECORD_SIZE,
    decode_enemy_record,
    encode_enemy_record,
    looks_like_enemy_record,
    ENEMY_DECODED_SPANS,
)

LOG2_ENEMY_CODEC = EnemyCodec(
    LOG2_ENEMY_RECORD_SIZE,
    decode_log2_enemy_record,
    encode_log2_enemy_record,
    looks_like_log2_enemy_record,
    LOG2_ENEMY_DECODED_SPANS,
)

_ENEMY_CODECS = {
    codec.record_size: codec for codec in (BUUS_ENEMY_CODEC, LOG2_ENEMY_CODEC)
}


def enemy_codec_for_record_size(record_size: int) -> EnemyCodec:
    """Select the enemy codec a declared record size names.

    Record size is the selector because it is format structure the codec
    enforces, and it is declared data the profile already carries. Keying on a
    profile id or a game name instead would rebuild the coupling TOOLKIT-005
    removed, where one hard-coded constant authorised exactly one game.

    An unrecognised size raises. There is no default and no nearest match: a
    size no codec implements means the record layout is unverified, and reading
    it through the wrong codec would silently produce plausible nonsense.
    """
    try:
        return _ENEMY_CODECS[record_size]
    except KeyError:
        raise UnknownEnemyCodecError(
            f"no enemy record codec implements a {record_size:#x}-byte record; "
            f"implemented sizes: "
            f"{', '.join(f'{size:#x}' for size in sorted(_ENEMY_CODECS))}"
        ) from None


def encode_base_stat_record(record: BaseStatRecord, original: bytes) -> bytes:
    if len(original) != BASE_STAT_RECORD_SIZE:
        raise StatEncodeError(
            f"base-stat record backing must be exactly {BASE_STAT_RECORD_SIZE} "
            f"bytes; got {len(original)}"
        )
    blob = bytearray(original)
    _put_uint(blob, 0x00, 1, record.level, "level")
    _put_uint(blob, 0x02, 2, record.hp, "hp")
    _put_uint(blob, 0x04, 2, record.ep, "ep")
    _put_uint(blob, 0x06, 1, record.strength, "strength")
    _put_uint(blob, 0x07, 1, record.power, "power")
    _put_uint(blob, 0x08, 1, record.endurance, "endurance")
    _put_uint(blob, 0x09, 1, record.speed, "speed")
    _put_uint(blob, 0x0A, 1, record.person, "person")
    _put_uint(blob, 0x0B, 1, record.technique_count, "technique_count")
    return bytes(blob)
