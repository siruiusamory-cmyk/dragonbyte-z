"""Donor-derived dialogue portraits, resolved by the donor engine's own joins.

LOG1-BUU-DIALOGUE-BACKPORT-001. This is the shipping copy of the donor extraction
C measured: the same joins, the same codec, none of the research-only imports. It
exists so the authoring pipeline is usable through the SDK alone (`tools.webfoot`
may not import `tools.research`).

The resolution is structural, never a guessed index:

  appearance record (+0x00 name slot, +0x08 portrait slot)
    -> the donor image's own text pointer table, for the displayed name
    -> the portrait pointer array, whose base is read back from the accessor's
       literal pool word rather than hard-coded
    -> a Webfoot container decoded by this toolkit's own codec

The donor image is opened read-only and its digest is checked against the
fingerprint every payload's provenance records, so a different dump is refused
before a byte is extracted. Nothing here writes anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import struct
from typing import Mapping

from .binary import GBA_ROM_BASE
from .formats import webfoot_lz

DONOR_BF_SHA256 = "940ad5f01db4465b8877dfe739510cbf34f4ea3d390f3df13519808bc36f059e"

APPEARANCE_TABLE_FILE_OFFSET = 0x74D380
APPEARANCE_RECORD_COUNT = 232
APPEARANCE_RECORD_SIZE = 0x10

TEXT_TABLE_FILE_OFFSET = 0x6BCE8

PORTRAIT_ARRAY_POOL_WORD = 0x08012194
PORTRAIT_SLOT_FIRST = 8
PORTRAIT_SLOT_LAST = 162

PORTRAIT_W, PORTRAIT_H, PORTRAIT_BYTES = 64, 64, 64 * 64

PORTRAIT_TRANSFORM = "bf-portrait-unpack/v1"


class DonorResourceError(ValueError):
    """The donor image is not the measured one, or a slot does not resolve."""


@dataclass(frozen=True, slots=True)
class Appearance:
    index: int
    file_offset: int
    name_slot: int
    portrait_slot: int
    sprite_id: int
    name: str


@dataclass(frozen=True, slots=True)
class Portrait:
    name: str
    portrait_slot: int
    container_file_offset: int
    payload: bytes
    donor_sha256: str
    donor_span: str
    transform: str

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()


def load_donor(path: str | Path, expected: str = DONOR_BF_SHA256) -> tuple[bytes, str]:
    """The donor image, or a refusal naming both digests."""
    data = Path(path).read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise DonorResourceError(
            f"donor image {path} is {actual}, this module is measured against "
            f"{expected}"
        )
    return data, actual


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _rom_offset(value: int, data: bytes, where: str) -> int:
    if not GBA_ROM_BASE <= value < GBA_ROM_BASE + len(data):
        raise DonorResourceError(f"{where} is not a ROM pointer: 0x{value:08X}")
    return value - GBA_ROM_BASE


def text_slot(data: bytes, slot: int) -> str:
    """UTF-16LE string `slot` through the donor's own pointer table."""
    pointer = _u32(data, TEXT_TABLE_FILE_OFFSET + 4 * slot)
    offset = _rom_offset(pointer, data, f"text slot {slot}")
    end = offset
    while end + 1 < len(data) and _u16(data, end) != 0:
        end += 2
    return data[offset:end].decode("utf-16-le")


def appearance_records(data: bytes) -> tuple[Appearance, ...]:
    rows = []
    for index in range(APPEARANCE_RECORD_COUNT):
        offset = APPEARANCE_TABLE_FILE_OFFSET + APPEARANCE_RECORD_SIZE * index
        name_slot = _u16(data, offset)
        rows.append(
            Appearance(
                index=index,
                file_offset=offset,
                name_slot=name_slot,
                portrait_slot=_u32(data, offset + 8),
                sprite_id=_u32(data, offset + 4),
                name=text_slot(data, name_slot),
            )
        )
    return tuple(rows)


def portrait_array_base(data: bytes) -> int:
    base = _u32(data, PORTRAIT_ARRAY_POOL_WORD - GBA_ROM_BASE)
    _rom_offset(base, data, f"pool word 0x{PORTRAIT_ARRAY_POOL_WORD:08X}")
    return base


def portrait_container_offset(data: bytes, slot: int) -> int:
    if not PORTRAIT_SLOT_FIRST <= slot <= PORTRAIT_SLOT_LAST:
        raise DonorResourceError(
            f"portrait slot {slot} is outside the measured run "
            f"{PORTRAIT_SLOT_FIRST}..{PORTRAIT_SLOT_LAST}"
        )
    pointer = _u32(data, portrait_array_base(data) - GBA_ROM_BASE + 4 * slot)
    return _rom_offset(pointer, data, f"portrait slot {slot}")


def portrait(data: bytes, name: str, *, slot: int | None = None) -> Portrait:
    """The one portrait `name` carries, or a refusal naming every candidate.

    A name carried by several portrait slots is refused rather than guessed at,
    because two art forms of one speaker are different payloads.
    """
    rows = [row for row in appearance_records(data)
            if row.name == name and row.portrait_slot]
    if not rows:
        raise DonorResourceError(f"no appearance record carries the name {name!r}")
    slots = sorted({row.portrait_slot for row in rows})
    if slot is None:
        if len(slots) != 1:
            raise DonorResourceError(
                f"{name!r} carries {len(slots)} portrait slots {slots}; name one"
            )
        slot = slots[0]
    if slot not in slots:
        raise DonorResourceError(f"{name!r} does not carry portrait slot {slot}: {slots}")
    offset = portrait_container_offset(data, slot)
    container = webfoot_lz.unpack(data, offset, maximum_output=len(data))
    if len(container.data) != PORTRAIT_BYTES:
        raise DonorResourceError(
            f"portrait slot {slot} decodes to {len(container.data)} bytes, not "
            f"{PORTRAIT_BYTES} (64x64 at 8bpp)"
        )
    donor_digest = hashlib.sha256(data).hexdigest()
    return Portrait(
        name=name,
        portrait_slot=slot,
        container_file_offset=offset,
        payload=container.data,
        donor_sha256=donor_digest,
        donor_span=f"0x{offset:06X}-0x{container.packed_end:06X}",
        transform=PORTRAIT_TRANSFORM,
    )


PALETTE_FILE_OFFSET = 0x5652C
PALETTE_ENTRIES = 256

LOW_BANK_ENTRIES = 128
OPAQUE_CAPACITY = LOW_BANK_ENTRIES - 1
ADAPTED_TRANSFORM = "bf-portrait-remap-low128/v1"
PALETTE_TRANSFORM = "bf-obj-palette-low128/v1"


@dataclass(frozen=True, slots=True)
class LowBank:
    """One shared donor-index -> low-half-bank map and the palette it implies."""

    palette: bytes
    remap: dict[int, int]
    painted: tuple[int, ...]
    opaque: tuple[int, ...]
    transparent: bool
    collapsed: dict[int, tuple[int, ...]]

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.palette).hexdigest()


def donor_palette(data: bytes, offset: int = PALETTE_FILE_OFFSET,
                  entries: int = PALETTE_ENTRIES) -> tuple[int, ...]:
    """The donor's global OBJ palette as raw BGR555 halfwords."""
    return tuple(_u16(data, offset + 2 * index) for index in range(entries))


def low_bank(pieces: Mapping[str, bytes], palette: tuple[int, ...], *,
             capacity: int = OPAQUE_CAPACITY) -> LowBank:
    """One donor-index -> slot map shared by every piece, refusing overflow.

    Transparency belongs to the donor INDEX, not to the colour: on the GBA only
    OBJ index 0 is transparent, so index 0 alone takes slot 0 and every other
    index stays opaque even when it paints the same BGR555 black. Opaque colours
    are deduplicated by value among themselves, so two opaque indices may share a
    slot above 0 but never reach it.
    """
    painted: set[int] = set()
    for payload in pieces.values():
        painted |= set(payload)
    if any(index >= PALETTE_ENTRIES for index in painted):
        raise DonorResourceError("a piece paints an index the donor palette does not define")

    transparent = 0 in painted
    by_colour: dict[int, list[int]] = {}
    for index in sorted(painted - {0}):
        by_colour.setdefault(palette[index] & 0x7FFF, []).append(index)
    if len(by_colour) > capacity:
        raise DonorResourceError(
            f"{len(by_colour)} opaque donor colours need {capacity} slots, overflow "
            f"{len(by_colour) - capacity}; this converter does not quantise art"
        )

    slots = {colour: 1 + position for position, colour in enumerate(sorted(by_colour))}
    remap = {index: slots[colour] for colour, indices in by_colour.items()
             for index in indices}
    if transparent:
        remap[0] = 0

    shared = [0] * LOW_BANK_ENTRIES
    for colour, slot in slots.items():
        shared[slot] = colour
    used = (max(remap.values()) + 1) if remap else 0
    payload = b"".join(struct.pack("<H", word) for word in shared[:used])
    return LowBank(
        palette=payload,
        remap=remap,
        painted=tuple(sorted(painted)),
        opaque=tuple(sorted(painted - {0})),
        transparent=transparent,
        collapsed={colour: tuple(indices) for colour, indices in by_colour.items()
                   if len(indices) > 1},
    )


def remap_payload(payload: bytes, remap: Mapping[int, int]) -> bytes:
    """Every donor index replaced by its shared slot; a missing one is a refusal."""
    try:
        return bytes(remap[value] for value in payload)
    except KeyError as error:
        raise DonorResourceError(
            f"donor index 0x{error.args[0]:02X} has no slot in the shared low bank"
        ) from error


def adapt_pieces(data: bytes, pieces: Mapping[str, bytes]) -> tuple[LowBank, dict[str, bytes]]:
    """The shared low bank and each piece remapped into it, still row-major.

    Tiling is the payload's own step, not the converter's: the shipped block walks
    the row-major raster into 8x8 order while it copies, so a pre-tiled payload
    would be tiled twice.
    """
    bank = low_bank(pieces, donor_palette(data))
    return bank, {name: remap_payload(payload, bank.remap)
                  for name, payload in pieces.items()}


BOX_FILE_OFFSET = 0x071758
BOX_W, BOX_H, BOX_BYTES = 160, 64, 160 * 64
BOX_TRANSFORM = "bf-box-remap-low128/v1"


@dataclass(frozen=True, slots=True)
class DonorBlob:
    payload: bytes
    file_offset: int
    donor_span: str

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()


def dialogue_box(data: bytes) -> DonorBlob:
    """The donor's primary dialogue box, decoded, with the span it came from."""
    container = webfoot_lz.unpack(data, BOX_FILE_OFFSET, maximum_output=len(data))
    if len(container.data) != BOX_BYTES:
        raise DonorResourceError(
            f"the donor box decodes to {len(container.data)} bytes, not {BOX_BYTES} "
            f"({BOX_W}x{BOX_H} at 8bpp)"
        )
    return DonorBlob(
        payload=container.data,
        file_offset=BOX_FILE_OFFSET,
        donor_span=f"0x{BOX_FILE_OFFSET:06X}-0x{container.packed_end:06X}",
    )


FONT_FILE_OFFSET = 0x6E05C
FONT_BYTES = 3598
FONT_SHA256 = "95e97071f6c0318d9eee0160d63300b6d3fb780c73a4a02c10a0f1cc605fd085"
FONT_TRANSFORM = "bf-font-raw/v1"


def dialogue_font(data: bytes) -> DonorBlob:
    """The donor's raw font span, or a refusal naming both digests."""
    payload = data[FONT_FILE_OFFSET:FONT_FILE_OFFSET + FONT_BYTES]
    if len(payload) != FONT_BYTES:
        raise DonorResourceError(
            f"the donor image ends inside the font span: {len(payload)} of {FONT_BYTES} bytes")
    actual = hashlib.sha256(payload).hexdigest()
    if actual != FONT_SHA256:
        raise DonorResourceError(
            f"the font span is {actual}, this module is measured against {FONT_SHA256}")
    return DonorBlob(
        payload=payload,
        file_offset=FONT_FILE_OFFSET,
        donor_span=f"0x{FONT_FILE_OFFSET:06X}-0x{FONT_FILE_OFFSET + FONT_BYTES:06X}",
    )

