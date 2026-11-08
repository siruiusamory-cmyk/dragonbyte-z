"""Import a donor actor sprite set into a Legacy of Goku actor art slot.

WHAT THIS IS. A versioned manifest names one donor definition, the animation slots to
carry and the Legacy of Goku art slot they target. This module reads those frames out of
the donor image in place, converts them into the LOG1 art record shape at native 1:1, and
reports whether the result fits what LOG1 can draw. It opens an image read-only and has no
write path at all, so it cannot damage an original; a decoded payload exists in memory.

WHAT IT DOES NOT DO. No engine hook, no animation-table patch, no projectile or combat
change, no derivative image. Those are phase 3 and need their own roadmap row; this module
stops at a validated payload.

EVIDENCE CLASSES. A structural fact here is either READ FROM BYTES at run time (a donor
record graph, a target art record, an index census) or declared in the manifest and quoted
from tracked research. Budget ceilings are owned by this module and never by the manifest,
so a manifest cannot widen its own budget; a ceiling this project has not measured is
recorded as unmeasured, its check reports UNKNOWN, and the document verdict then fails
closed instead of passing.

THE TWO DONOR FAMILIES, AND WHY THE DIFFERENCE IS DATA. The two donor images do not share
one record shape, and the difference is measured rather than assumed:

* ``webfoot-animation`` (Buu's Fury): a definition's slot array holds animation objects; an
  animation holds a frame count and four directional cell pointers per frame; a cell names
  a frame record; a frame record holds one or more pieces, each naming a container.
* ``webfoot-piece-run`` (Legacy of Goku II): a definition's slot array holds, per group and
  facing, a run of bare piece records that ends at a record whose width or height is zero.
  There is no frame record and no frame count: the run is a piece pool, so a duration list
  must never be checked against its length.

THE TARGET. A LOG1 art definition carries a palette pointer and an animation table of four
facing cell pointers per state. A cell record is sixteen bytes and its pixels are four bits
per pixel in GBA tile order. The payload built here is exactly that cell record plus its
tile bytes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from tools.webfoot.binary import GbaRomAddress, UINT32_MAX
from tools.webfoot.formats import webfoot_lz

SCHEMA = "webfoot.sprite-import/1"

CLASSIFICATIONS = ("authentic", "adapted", "unused")
TIMING_CLASSES = ("MEASURED", "STATIC-DERIVED", "ASSUMED", "PLACEHOLDER")
DONOR_FAMILIES = ("webfoot-animation", "webfoot-piece-run")
SWAP_IN_STATUSES = ("reuse", "pending")

VERDICT_FITS = "FITS"
VERDICT_OVER = "DOES NOT FIT"
VERDICT_UNKNOWN = "UNKNOWN"
_SEVERITY = {VERDICT_FITS: 0, VERDICT_UNKNOWN: 1, VERDICT_OVER: 2}

SLOT_ARRAY_OFFSET = {"webfoot-animation": 84, "webfoot-piece-run": 76}
SLOT_STRIDE = {"webfoot-animation": 4, "webfoot-piece-run": 16}
SLOT_COUNT_OFFSET: dict[str, int | None] = {
    "webfoot-animation": 0,
    "webfoot-piece-run": None,
}

ANIMATION_FRAME_STRIDE = 16
FRAME_HEADER_BYTES = 8
PIECE_RECORD_BYTES = 12
LOG1_CELL_BYTES = 16
LOG1_PALETTE_OFFSET = 36
LOG1_ANIMATION_OFFSET = 40
LOG1_STATE_BYTES = 16
LOG1_FACINGS = 4
LOG1_TILE_BYTES = 32
TILE_PIXELS = 64
ATTR_HORIZONTAL_FLIP = 1 << 12
ATTR_COLOUR_256 = 1 << 13
LOG1_CELL_HORIZONTAL_FLIP = 8
MAX_DONOR_FRAMES = 64
TARGET_STATE_LIMIT = 17
MAX_DONOR_INDEX = 255
MAX_BANK_SLOT = 15
CELL_ATTRIBUTE_SIZE_AND_SHAPE: dict[tuple[int, int], tuple[int, int]] = {
    (16, 32): (2, 2),
    (32, 16): (2, 1),
    (32, 32): (2, 0),
    (32, 64): (3, 2),
    (64, 32): (3, 1),
}


def cell_geometry(width: int, height: int) -> tuple[int, int]:
    """The attribute byte 1 and byte 2 pair the target image uses for this box.

    Measured, not derived: a sweep of all eighty-four art definitions in the canonical
    Legacy of Goku image finds five box sizes and one pair for each. A box outside that
    sweep is refused by name rather than given an invented OBJ size and shape, and a
    sixteen-by-sixteen cell is not in the sweep because no art in the image draws one.
    """
    try:
        return CELL_ATTRIBUTE_SIZE_AND_SHAPE[(width, height)]
    except KeyError:
        known = ", ".join(f"{w}x{h}" for w, h in sorted(CELL_ATTRIBUTE_SIZE_AND_SHAPE))
        raise SpriteImportError(
            f"a {width}x{height} cell has no measured attribute pair; the target image's "
            f"arts carry {known}, so this box would need a measurement of its own"
        ) from None


class SpriteImportError(ValueError):
    """Raised when a manifest, an image or a decoded record cannot be trusted."""




@dataclass(frozen=True, slots=True)
class RomImage:
    """An immutable in-place view of one image, pinned by digest.

    There is no write method. The digest is re-checked on open, so a path that now holds a
    different image is refused instead of silently decoded.
    """

    path: Path
    sha256: str
    data: bytes

    @classmethod
    def open(cls, path: str | Path, expected_sha256: str) -> "RomImage":
        resolved = Path(path)
        if not resolved.is_file():
            raise SpriteImportError(f"image {resolved} is not a readable file")
        data = resolved.read_bytes()
        digest = sha256(data).hexdigest()
        if digest != expected_sha256.lower():
            raise SpriteImportError(
                f"image {resolved} has sha256 {digest}, not the pinned {expected_sha256}"
            )
        return cls(path=resolved, sha256=digest, data=data)

    @property
    def size(self) -> int:
        return len(self.data)

    def offset(self, address: int) -> int:
        return GbaRomAddress(address).to_file_offset(self.size)

    def span(self, address: int, size: int) -> bytes:
        start = self.offset(address)
        if size < 0 or start + size > self.size:
            raise SpriteImportError(
                f"{size} bytes at {address:#010x} run past the {self.size}-byte image"
            )
        return self.data[start : start + size]

    def u8(self, address: int) -> int:
        return self.span(address, 1)[0]

    def s8(self, address: int) -> int:
        return int.from_bytes(self.span(address, 1), "little", signed=True)

    def u16(self, address: int) -> int:
        return int.from_bytes(self.span(address, 2), "little")

    def s16(self, address: int) -> int:
        return int.from_bytes(self.span(address, 2), "little", signed=True)

    def u32(self, address: int) -> int:
        return int.from_bytes(self.span(address, 4), "little")




@dataclass(frozen=True, slots=True)
class DonorPiece:
    """One piece of a donor frame: its offset, extents, attributes and container."""

    x: int
    y: int
    width: int
    height: int
    attributes: int
    container: int

    @property
    def colour_256(self) -> bool:
        return bool(self.attributes & ATTR_COLOUR_256)

    @property
    def horizontal_flip(self) -> bool:
        return bool((self.attributes >> 16) & ATTR_HORIZONTAL_FLIP)

    @property
    def pixels(self) -> int:
        return self.width * self.height


@dataclass(frozen=True, slots=True)
class DonorFrame:
    """One donor frame: its record address, box and pieces."""

    address: int
    min_x: int
    min_y: int
    width: int
    height: int
    pieces: tuple[DonorPiece, ...]


def read_donor_frame(image: RomImage, address: int) -> DonorFrame:
    """Read a frame record: a piece count, a box header, then the pieces."""
    count = image.u32(address)
    if not 1 <= count <= 16:
        raise SpriteImportError(
            f"frame at {address:#010x} declares {count} pieces, outside 1..16"
        )
    image.span(address, FRAME_HEADER_BYTES + count * PIECE_RECORD_BYTES)
    pieces = []
    for index in range(count):
        base = address + FRAME_HEADER_BYTES + index * PIECE_RECORD_BYTES
        pieces.append(
            DonorPiece(
                x=image.s8(base),
                y=image.s8(base + 1),
                width=image.u8(base + 2),
                height=image.u8(base + 3),
                attributes=image.u32(base + 4),
                container=image.u32(base + 8),
            )
        )
    return DonorFrame(
        address=address,
        min_x=image.s8(address + 4),
        min_y=image.s8(address + 5),
        width=image.u8(address + 6),
        height=image.u8(address + 7),
        pieces=tuple(pieces),
    )


def read_piece(image: RomImage, address: int) -> DonorPiece:
    """Read one bare piece record, the shape a Legacy of Goku II run stores."""
    image.span(address, PIECE_RECORD_BYTES)
    return DonorPiece(
        x=image.s8(address),
        y=image.s8(address + 1),
        width=image.u8(address + 2),
        height=image.u8(address + 3),
        attributes=image.u32(address + 4),
        container=image.u32(address + 8),
    )


def read_piece_run(image: RomImage, address: int, limit: int = MAX_DONOR_FRAMES) -> tuple[DonorPiece, ...]:
    """Read a terminated run of bare pieces.

    The run ends at the first record whose width or height is zero; that terminator is the
    only bound the format carries, so a run that never terminates is refused rather than
    read past its table.
    """
    pieces = []
    for index in range(limit):
        piece = read_piece(image, address + index * PIECE_RECORD_BYTES)
        if piece.width == 0 or piece.height == 0:
            if not pieces:
                raise SpriteImportError(f"piece run at {address:#010x} is empty")
            return tuple(pieces)
        pieces.append(piece)
    raise SpriteImportError(
        f"piece run at {address:#010x} did not terminate within {limit} records"
    )


def _require_family(family: str) -> str:
    if family not in DONOR_FAMILIES:
        raise SpriteImportError(
            f"donor family {family!r} is not one of {', '.join(DONOR_FAMILIES)}"
        )
    return family


def donor_slot_address(
    image: RomImage, family: str, definition: int, slot: int, direction: int = 0
) -> int:
    """The pointer a family stores for one direction slot of a definition.

    The two families place their direction words differently and this is where that is
    stated: an animation family's slot stride is four bytes and its four direction words
    live inside the animation object, while a piece-run family's stride is sixteen bytes
    and its four facing words are the stride itself, so the direction is an offset within
    the slot rather than a field of whatever the slot names.
    """
    _require_family(family)
    count_offset = SLOT_COUNT_OFFSET[family]
    if count_offset is not None:
        count = image.u8(definition + count_offset)
        if not 0 <= slot < count:
            raise SpriteImportError(
                f"{family} definition {definition:#010x} declares {count} slots, "
                f"so slot {slot} does not exist"
            )
    within_slot = 4 * direction if family == "webfoot-piece-run" else 0
    address = image.u32(
        definition
        + SLOT_ARRAY_OFFSET[family]
        + slot * SLOT_STRIDE[family]
        + within_slot
    )
    if address == 0:
        raise SpriteImportError(
            f"{family} definition {definition:#010x} slot {slot} direction {direction} "
            "holds a null pointer"
        )
    return address


def single_piece_frame(image: RomImage, address: int) -> DonorFrame:
    """One bare piece read as a whole frame, the shape a piece-run family publishes."""
    piece = read_piece(image, address)
    return DonorFrame(
        address=address,
        min_x=piece.x,
        min_y=piece.y,
        width=piece.width,
        height=piece.height,
        pieces=(piece,),
    )


def donor_frames(
    image: RomImage,
    family: str,
    definition: int,
    slot: int,
    direction: int,
    frames: Sequence[int] | None = None,
) -> tuple[DonorFrame, ...]:
    """The frames one slot and direction resolve to, or the explicit list given.

    An explicit list is how an adapted sequence names donor frames: those addresses are
    read as frame records exactly as a resolved slot's would be, so an adaptation may
    reorder or repeat donor frames but can never introduce a frame the donor does not hold.
    """
    if frames is not None:
        _require_family(family)
        if family == "webfoot-piece-run":
            return tuple(single_piece_frame(image, address) for address in frames)
        return tuple(read_donor_frame(image, address) for address in frames)
    if not 0 <= direction < LOG1_FACINGS:
        raise SpriteImportError(f"direction {direction} is outside 0..3")
    address = donor_slot_address(image, family, definition, slot, direction)
    if family == "webfoot-animation":
        count = image.u32(address)
        if not 1 <= count <= MAX_DONOR_FRAMES:
            raise SpriteImportError(
                f"animation at {address:#010x} declares {count} frames, outside "
                f"1..{MAX_DONOR_FRAMES}"
            )
        return tuple(
            read_donor_frame(
                image, image.u32(address + 4 + frame * ANIMATION_FRAME_STRIDE + direction * 4)
            )
            for frame in range(count)
        )
    return tuple(
        single_piece_frame(image, address + index * PIECE_RECORD_BYTES)
        for index, _ in enumerate(read_piece_run(image, address))
    )


def carried_frames(
    image: RomImage, family: str, definition: int, animations: Iterable["Animation"]
) -> tuple[DonorFrame, ...]:
    """Every donor frame an import carries, in slot and direction order."""
    collected: list[DonorFrame] = []
    for animation in animations:
        if animation.classification == "unused" and animation.frames is None:
            continue
        for direction in animation.directions:
            collected.extend(
                donor_frames(image, family, definition, animation.slot, direction,
                             animation.frames)
            )
    return tuple(collected)




@dataclass(frozen=True, slots=True)
class Log1Cell:
    """One LOG1 art cell record, the payload this module builds."""

    x: int
    y: int
    width: int
    height: int
    tiles: int
    attributes: tuple[int, int, int]

    @property
    def horizontal_flip(self) -> bool:
        return bool(self.attributes[0] & LOG1_CELL_HORIZONTAL_FLIP)

    def to_record(self, tiles_address: int) -> bytes:
        """Serialise the sixteen-byte record the engine reads, with its tile pointer."""
        if len(self.attributes) != 3:
            raise SpriteImportError("a LOG1 cell carries exactly three attribute bytes")
        if not 0 <= tiles_address <= UINT32_MAX:
            raise SpriteImportError(f"{tiles_address} is not a 32-bit address")
        record = bytearray(LOG1_CELL_BYTES)
        record[0:2] = int(self.x).to_bytes(2, "little", signed=True)
        record[2:4] = int(self.y).to_bytes(2, "little", signed=True)
        record[4:6] = int(self.width).to_bytes(2, "little")
        record[6:8] = int(self.height).to_bytes(2, "little")
        record[8] = self.tiles
        record[9:12] = bytes(self.attributes)
        record[12:16] = int(tiles_address).to_bytes(4, "little")
        return bytes(record)


@dataclass(frozen=True, slots=True)
class Log1Art:
    """One LOG1 art definition and the state cells the manifest names in it."""

    art_id: int
    definition: int
    palette: int
    animation_table: int
    states: Mapping[int, tuple[Log1Cell, ...]]


def read_log1_art(
    image: RomImage, art_table: int, art_id: int, states: Sequence[int]
) -> Log1Art:
    """Read one LOG1 art definition and the named states of its animation table.

    Only the states the manifest names are read, and each must be populated. Reading a
    guessed window instead would let unrelated bytes masquerade as a state.
    """
    if not states:
        raise SpriteImportError("a target declares no state to read")
    definition = image.u32(art_table + art_id * 4)
    if definition == 0:
        raise SpriteImportError(
            f"art table {art_table:#010x} holds a null definition for art {art_id}"
        )
    palette = image.u32(definition + LOG1_PALETTE_OFFSET)
    animation_table = image.u32(definition + LOG1_ANIMATION_OFFSET)
    if animation_table == 0:
        raise SpriteImportError(
            f"art {art_id} definition {definition:#010x} holds a null animation table"
        )
    populated: dict[int, tuple[Log1Cell, ...]] = {}
    for state in states:
        if not 0 <= state < 256:
            raise SpriteImportError(f"art state {state} is outside a byte-sized index")
        cells = tuple(
            image.u32(animation_table + state * LOG1_STATE_BYTES + facing * 4)
            for facing in range(LOG1_FACINGS)
        )
        if not any(cells):
            raise SpriteImportError(
                f"art {art_id} state {state} holds no facing cell, so the manifest names "
                "a state this image does not populate"
            )
        populated[state] = tuple(
            Log1Cell(
                x=image.s16(cell),
                y=image.s16(cell + 2),
                width=image.u16(cell + 4),
                height=image.u16(cell + 6),
                tiles=image.u8(cell + 8),
                attributes=(image.u8(cell + 9), image.u8(cell + 10), image.u8(cell + 11)),
            )
            for cell in cells
        )
    return Log1Art(
        art_id=art_id,
        definition=definition,
        palette=palette,
        animation_table=animation_table,
        states=populated,
    )




def unpack_indices(payload: bytes, colour_256: bool) -> bytes:
    """Container payload to one palette index per pixel, in the order it is stored."""
    if colour_256:
        return payload
    unpacked = bytearray(len(payload) * 2)
    for index, value in enumerate(payload):
        unpacked[2 * index] = value & MAX_BANK_SLOT
        unpacked[2 * index + 1] = value >> 4
    return bytes(unpacked)


def pack_indices(indices: bytes) -> bytes:
    """One four-bit index per pixel, back to the packed bytes the target stores."""
    if len(indices) % 2:
        raise SpriteImportError("a four-bit payload needs an even pixel count")
    packed = bytearray(len(indices) // 2)
    for index in range(0, len(indices), 2):
        low, high = indices[index], indices[index + 1]
        if low > MAX_BANK_SLOT or high > MAX_BANK_SLOT:
            raise SpriteImportError(
                f"palette index {max(low, high)} does not fit a four-bit slot"
            )
        packed[index // 2] = low | (high << 4)
    return bytes(packed)


def frame_indices(image: RomImage, frame: DonorFrame) -> tuple[DonorPiece, bytes]:
    """One donor frame's pixels as palette indices, refusing what LOG1 cannot hold.

    The refusal is the point: a LOG1 cell carries one tile pointer and one tile count, so a
    multipart donor frame cannot be expressed at all, and a container whose declared size
    contradicts its own piece extents is not the frame it claims to be.
    """
    if len(frame.pieces) != 1:
        raise SpriteImportError(
            f"frame at {frame.address:#010x} holds {len(frame.pieces)} pieces; a LOG1 "
            "cell carries one tile pointer, so a multipart frame cannot be imported"
        )
    piece = frame.pieces[0]
    container = webfoot_lz.unpack(image.data, image.offset(piece.container))
    expected = piece.pixels if piece.colour_256 else piece.pixels // 2
    if container.declared_size != expected:
        raise SpriteImportError(
            f"container at {piece.container:#010x} declares {container.declared_size} "
            f"bytes but its piece declares {piece.width}x{piece.height} at "
            f"{8 if piece.colour_256 else 4}bpp ({expected} bytes)"
        )
    indices = unpack_indices(container.data, piece.colour_256)
    if len(indices) != piece.pixels:
        raise SpriteImportError(
            f"frame at {frame.address:#010x} decodes {len(indices)} pixels, not "
            f"{piece.pixels}"
        )
    return piece, indices


def map_indices(indices: bytes, palette_map: Mapping[int, int]) -> bytes:
    """Apply an explicit donor-index to bank-slot map, refusing an uncovered index."""
    missing = sorted({value for value in indices if value not in palette_map})
    if missing:
        raise SpriteImportError(
            f"{len(missing)} donor palette index(es) have no declared bank slot, lowest "
            f"{missing[0]}; a manifest that wants this art must declare palette.map"
        )
    mapped = bytearray(len(indices))
    for index, value in enumerate(indices):
        slot = palette_map[value]
        if not 0 <= slot <= MAX_BANK_SLOT:
            raise SpriteImportError(f"bank slot {slot} is outside a sixteen-colour bank")
        mapped[index] = slot
    return bytes(mapped)


@dataclass(frozen=True, slots=True)
class FramePayload:
    """One frame in the LOG1 record shape: its cell and its packed tile bytes."""

    slot: int
    direction: int
    frame_index: int
    donor_frame: int
    cell: Log1Cell
    tiles: bytes

    @property
    def tiles_sha256(self) -> str:
        return sha256(self.tiles).hexdigest()


def build_frame_payload(
    image: RomImage,
    frame: DonorFrame,
    *,
    slot: int,
    direction: int,
    frame_index: int,
    palette_map: Mapping[int, int] | None = None,
) -> FramePayload:
    """Convert one donor frame into a LOG1 cell plus its tile bytes, at native size."""
    piece, indices = frame_indices(image, frame)
    if palette_map is not None:
        indices = map_indices(indices, palette_map)
    size, shape = cell_geometry(piece.width, piece.height)
    attributes = (
        LOG1_CELL_HORIZONTAL_FLIP if piece.horizontal_flip else 0,
        size,
        shape,
    )
    return FramePayload(
        slot=slot,
        direction=direction,
        frame_index=frame_index,
        donor_frame=frame.address,
        cell=Log1Cell(
            x=piece.x,
            y=piece.y,
            width=piece.width,
            height=piece.height,
            tiles=piece.pixels // TILE_PIXELS,
            attributes=attributes,
        ),
        tiles=pack_indices(indices),
    )


def import_payloads(
    images: Mapping[str, RomImage], document: "Manifest"
) -> dict[str, tuple[FramePayload, ...]]:
    """Every carried frame of every import, keyed by import identity.

    ``images`` is keyed by the donor key each import names, so one document may import from
    more than one image without either path leaking into the manifest.
    """
    result: dict[str, tuple[FramePayload, ...]] = {}
    for entry in document.imports:
        image = images[entry.donor]
        payloads: list[FramePayload] = []
        for animation in entry.animations:
            if animation.classification == "unused" and animation.frames is None:
                continue
            for direction in animation.directions:
                for index, frame in enumerate(
                    donor_frames(
                        image,
                        document.donor(entry.donor).family,
                        entry.definition,
                        animation.slot,
                        direction,
                        animation.frames,
                    )
                ):
                    payloads.append(
                        build_frame_payload(
                            image,
                            frame,
                            slot=animation.slot,
                            direction=direction,
                            frame_index=index,
                            palette_map=entry.palette_map,
                        )
                    )
        result[entry.identity] = tuple(payloads)
    return result




def _require(document: Mapping[str, Any], key: str, where: str) -> Any:
    if key not in document:
        raise SpriteImportError(f"{where} is missing the required key {key!r}")
    return document[key]


def _reject_unknown(document: Mapping[str, Any], allowed: Iterable[str], where: str) -> None:
    unknown = sorted(set(document) - set(allowed))
    if unknown:
        raise SpriteImportError(f"{where} carries unknown key(s) {', '.join(unknown)}")


def _as_int(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SpriteImportError(f"{where} must be an integer, not {type(value).__name__}")
    return value


def _as_address(value: Any, where: str) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            parsed = int(value, 0)
        except ValueError as exc:
            raise SpriteImportError(f"{where} is not an integer address: {value!r}") from exc
        if parsed < 0:
            raise SpriteImportError(f"{where} is negative: {value!r}")
        return parsed
    raise SpriteImportError(f"{where} must be an address string or integer")


def _as_choice(value: Any, choices: Sequence[str], where: str) -> str:
    if value not in choices:
        raise SpriteImportError(f"{where} is {value!r}, not one of {', '.join(choices)}")
    return value


@dataclass(frozen=True, slots=True)
class Timing:
    """How fast a carried animation plays, in the label its source gave it.

    The provenance label is never promoted here: a MEASURED row must carry the run line
    that measured it, an ASSUMED row must carry the acceptance that allowed it, and a
    PLACEHOLDER row may carry no duration at all.
    """

    classification: str
    durations_video_frames: tuple[int, ...] = ()
    published_frames: int | None = None
    loop: str | None = None
    run_line: str | None = None
    law: str | None = None
    owner_acceptance: str | None = None
    source: str | None = None

    @classmethod
    def from_document(cls, document: Mapping[str, Any], where: str) -> "Timing":
        _reject_unknown(
            document,
            (
                "class",
                "durations_video_frames",
                "published_frames",
                "loop",
                "run_line",
                "law",
                "owner_acceptance",
                "source",
            ),
            where,
        )
        classification = _as_choice(
            _require(document, "class", where), TIMING_CLASSES, f"{where}.class"
        )
        durations = tuple(
            _as_int(value, f"{where}.durations_video_frames")
            for value in document.get("durations_video_frames", ())
        )
        published = document.get("published_frames")
        if published is not None:
            published = _as_int(published, f"{where}.published_frames")
            if len(durations) != published:
                raise SpriteImportError(
                    f"{where} declares {published} published frames but "
                    f"{len(durations)} durations"
                )
        timing = cls(
            classification=classification,
            durations_video_frames=durations,
            published_frames=published,
            loop=document.get("loop"),
            run_line=document.get("run_line"),
            law=document.get("law"),
            owner_acceptance=document.get("owner_acceptance"),
            source=document.get("source"),
        )
        if classification == "MEASURED" and not (timing.run_line and durations):
            raise SpriteImportError(
                f"{where} is MEASURED, so it needs a run_line and at least one duration"
            )
        if classification == "STATIC-DERIVED" and not timing.law:
            raise SpriteImportError(f"{where} is STATIC-DERIVED, so it needs a law")
        if classification == "ASSUMED" and not (timing.owner_acceptance and timing.source):
            raise SpriteImportError(
                f"{where} is ASSUMED, so it needs the owner acceptance and its source"
            )
        if classification == "PLACEHOLDER":
            if durations or timing.run_line:
                raise SpriteImportError(
                    f"{where} is PLACEHOLDER, so it may carry neither a duration nor a "
                    "run line"
                )
        elif not durations:
            raise SpriteImportError(
                f"{where} is {classification}, so it needs at least one duration"
            )
        return timing

    def check_frame_count(self, frames: int, where: str) -> None:
        """A measured duration list may not be longer than the animation's own frames."""
        if len(self.durations_video_frames) > frames:
            raise SpriteImportError(
                f"{where} carries {len(self.durations_video_frames)} durations but the "
                f"donor animation holds only {frames} frames; a published-frame count may "
                "be shorter than the frame count, never longer"
            )


@dataclass(frozen=True, slots=True)
class Animation:
    """One carried donor slot, its directions and its timing label."""

    slot: int
    classification: str
    directions: tuple[int, ...]
    timing: Timing
    frames: tuple[int, ...] | None = None

    @classmethod
    def from_document(cls, document: Mapping[str, Any], where: str) -> "Animation":
        _reject_unknown(
            document, ("slot", "classification", "directions", "timing", "frames"), where
        )
        slot = _as_int(_require(document, "slot", where), f"{where}.slot")
        if slot < 0:
            raise SpriteImportError(f"{where}.slot is negative")
        classification = _as_choice(
            _require(document, "classification", where),
            CLASSIFICATIONS,
            f"{where}.classification",
        )
        directions = tuple(
            _as_int(value, f"{where}.directions")
            for value in document.get("directions", (0, 1, 2, 3))
        )
        if not directions:
            raise SpriteImportError(f"{where}.directions is empty")
        for direction in directions:
            if not 0 <= direction < LOG1_FACINGS:
                raise SpriteImportError(
                    f"{where}.directions names {direction}, outside 0..3"
                )
        frames = document.get("frames")
        if frames is not None:
            if classification != "adapted":
                raise SpriteImportError(
                    f"{where} lists explicit frames, which only an adapted sequence may do"
                )
            frames = tuple(_as_address(value, f"{where}.frames") for value in frames)
            if not frames:
                raise SpriteImportError(f"{where}.frames is empty")
        return cls(
            slot=slot,
            classification=classification,
            directions=directions,
            timing=Timing.from_document(
                _require(document, "timing", where), f"{where}.timing"
            ),
            frames=frames,
        )


@dataclass(frozen=True, slots=True)
class SwapIn:
    """A target art slot whose art is reused now and replaced later, never invented here."""

    status: str
    source: str

    @classmethod
    def from_document(cls, document: Mapping[str, Any], where: str) -> "SwapIn":
        _reject_unknown(document, ("status", "source"), where)
        status = _as_choice(
            _require(document, "status", where), SWAP_IN_STATUSES, f"{where}.status"
        )
        source = _require(document, "source", where)
        if not isinstance(source, str) or not source.strip():
            raise SpriteImportError(f"{where}.source must be a non-empty string")
        return cls(status=status, source=source)


@dataclass(frozen=True, slots=True)
class Target:
    """The LOG1 art slot an import writes into, and whether it holds borrowed art."""

    game: str
    sha256: str
    art_table: int
    art_id: int
    art_definition: int
    states: tuple[int, ...]
    fallback_states: tuple[int, ...] = ()
    swap_in: SwapIn | None = None

    @classmethod
    def from_document(cls, document: Mapping[str, Any], where: str) -> "Target":
        _reject_unknown(
            document,
            ("game", "sha256", "art_table", "art_id", "art_definition", "states",
             "fallback_states", "swap_in"),
            where,
        )
        states = tuple(
            _as_int(value, f"{where}.states")
            for value in _require(document, "states", where)
        )
        if not states:
            raise SpriteImportError(f"{where}.states is empty")
        if len(set(states)) != len(states):
            raise SpriteImportError(f"{where}.states repeats a state")
        fallback_states = tuple(
            _as_int(value, f"{where}.fallback_states")
            for value in document.get("fallback_states", ())
        )
        if len(set(fallback_states)) != len(fallback_states):
            raise SpriteImportError(f"{where}.fallback_states repeats a state")
        for name, named in (("states", states), ("fallback_states", fallback_states)):
            out_of_window = sorted(
                state for state in named if not 0 <= state < TARGET_STATE_LIMIT
            )
            if out_of_window:
                raise SpriteImportError(
                    f"{where}.{name} names {out_of_window}, outside the art's own state "
                    f"window 0..{TARGET_STATE_LIMIT - 1}; an art's animation table is "
                    "followed immediately by the next art's, so a state past the window is "
                    "a neighbour's"
                )
        overlap = sorted(set(states) & set(fallback_states))
        if overlap:
            raise SpriteImportError(
                f"{where}.fallback_states and .states both name {overlap}; a state either "
                "takes donor art or keeps the target's own, never both"
            )
        swap_in = document.get("swap_in")
        return cls(
            game=str(_require(document, "game", where)),
            sha256=str(_require(document, "sha256", where)).lower(),
            art_table=_as_address(
                _require(document, "art_table", where), f"{where}.art_table"
            ),
            art_id=_as_int(_require(document, "art_id", where), f"{where}.art_id"),
            art_definition=_as_address(
                _require(document, "art_definition", where), f"{where}.art_definition"
            ),
            states=states,
            fallback_states=fallback_states,
            swap_in=(
                SwapIn.from_document(swap_in, f"{where}.swap_in")
                if swap_in is not None
                else None
            ),
        )


@dataclass(frozen=True, slots=True)
class Import:
    """One character's carried animation set and the art slot it targets."""

    identity: str
    character: str
    donor: str
    definition: int
    target: Target
    animations: tuple[Animation, ...]
    palette_map: Mapping[int, int] | None = None
    notes: str | None = None

    @classmethod
    def from_document(cls, document: Mapping[str, Any], where: str) -> "Import":
        _reject_unknown(
            document,
            ("id", "character", "donor", "definition", "target", "animations",
             "palette", "notes"),
            where,
        )
        animations = tuple(
            Animation.from_document(item, f"{where}.animations[{index}]")
            for index, item in enumerate(_require(document, "animations", where))
        )
        if not animations:
            raise SpriteImportError(f"{where}.animations is empty")
        seen: set[int] = set()
        for animation in animations:
            if animation.slot in seen:
                raise SpriteImportError(f"{where} carries slot {animation.slot} twice")
            seen.add(animation.slot)
        return cls(
            identity=str(_require(document, "id", where)),
            character=str(_require(document, "character", where)),
            donor=str(_require(document, "donor", where)),
            definition=_as_address(
                _require(document, "definition", where), f"{where}.definition"
            ),
            target=Target.from_document(
                _require(document, "target", where), f"{where}.target"
            ),
            animations=animations,
            palette_map=_palette_map(document.get("palette"), f"{where}.palette"),
            notes=document.get("notes"),
        )


def _palette_map(document: Any, where: str) -> Mapping[int, int] | None:
    if document is None:
        return None
    if not isinstance(document, Mapping):
        raise SpriteImportError(f"{where} must be an object")
    _reject_unknown(document, ("map", "provenance"), where)
    raw = document.get("map")
    if raw is None:
        return None
    if not isinstance(raw, Mapping) or not raw:
        raise SpriteImportError(f"{where}.map must be a non-empty object")
    mapping: dict[int, int] = {}
    for key, value in raw.items():
        donor_index = _as_int(int(key) if isinstance(key, str) else key, f"{where}.map key")
        slot = _as_int(value, f"{where}.map[{key}]")
        if not 0 <= donor_index <= MAX_DONOR_INDEX:
            raise SpriteImportError(f"{where}.map key {donor_index} is not a palette index")
        if not 0 <= slot <= MAX_BANK_SLOT:
            raise SpriteImportError(
                f"{where}.map[{key}] is outside a sixteen-colour bank"
            )
        mapping[donor_index] = slot
    if mapping.get(0, 0) != 0:
        raise SpriteImportError(f"{where}.map must send donor index 0 to bank slot 0")
    return mapping


@dataclass(frozen=True, slots=True)
class Donor:
    """The image an import reads, pinned by digest, and its record family."""

    family: str
    sha256: str
    notes: str | None = None

    @classmethod
    def from_document(cls, document: Mapping[str, Any], where: str) -> "Donor":
        _reject_unknown(document, ("family", "sha256", "notes"), where)
        return cls(
            family=_as_choice(
                _require(document, "family", where), DONOR_FAMILIES, f"{where}.family"
            ),
            sha256=str(_require(document, "sha256", where)).lower(),
            notes=document.get("notes"),
        )


@dataclass(frozen=True, slots=True)
class Manifest:
    """A parsed import document: its donors, its imports and its schema version."""

    donors: Mapping[str, Donor]
    imports: tuple[Import, ...]
    schema: str = SCHEMA

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "Manifest":
        if not isinstance(document, Mapping):
            raise SpriteImportError("a manifest must be a JSON object")
        _reject_unknown(document, ("schema", "donors", "imports"), "manifest")
        schema = _require(document, "schema", "manifest")
        if schema != SCHEMA:
            raise SpriteImportError(
                f"manifest schema is {schema!r}; this build reads {SCHEMA!r}"
            )
        raw_donors = _require(document, "donors", "manifest")
        if not isinstance(raw_donors, Mapping) or not raw_donors:
            raise SpriteImportError("manifest.donors must be a non-empty object")
        donors = {
            str(key): Donor.from_document(value, f"manifest.donors[{key}]")
            for key, value in raw_donors.items()
        }
        imports = tuple(
            Import.from_document(item, f"manifest.imports[{index}]")
            for index, item in enumerate(_require(document, "imports", "manifest"))
        )
        if not imports:
            raise SpriteImportError("manifest.imports is empty")
        identities = {entry.identity for entry in imports}
        if len(identities) != len(imports):
            raise SpriteImportError("manifest imports do not have distinct ids")
        for entry in imports:
            if entry.donor not in donors:
                raise SpriteImportError(
                    f"import {entry.identity!r} names donor {entry.donor!r}, which the "
                    "manifest does not declare"
                )
        return cls(donors=donors, imports=imports, schema=schema)

    def donor(self, name: str) -> Donor:
        try:
            return self.donors[name]
        except KeyError as exc:
            raise SpriteImportError(f"no donor named {name!r} in this manifest") from exc


def load_manifest(path: str | Path) -> Manifest:
    """Read and validate a manifest document from disk."""
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    return Manifest.from_document(document)




@dataclass(frozen=True, slots=True)
class Limit:
    """One budget ceiling and the observation that established it.

    ``value`` is ``None`` when this project has not measured the ceiling. That is not a
    guess at a large number; it is the statement that the check cannot pass.
    """

    name: str
    value: int | None
    source: str

    @property
    def established(self) -> bool:
        return self.value is not None


LIMITS = (
    Limit(
        "tiles per frame",
        None,
        "UNMEASURED. LOG1 draws eight or sixteen tiles in one actor frame and performs no "
        "ceiling check against the end of object video memory, and that region is shared "
        "with every other actor and effect, so a per-frame ceiling has not been observed "
        "(025-report.md, lane B target-surface analysis).",
    ),
    Limit(
        "oam entries per frame",
        128,
        "One OAM entry is appended per actor piece with no bounds check, so the hard cap is "
        "the 1024-byte DMA flush, which is 128 entries (025-report.md, lane B).",
    ),
    Limit(
        "palette indices per bank",
        15,
        "A bank is sixteen colours and index 0 is the transparent slot in the art's own "
        "palette record, so fifteen indices are addressable per bank (025-report.md lane B "
        "allocator; LOGX sprite provenance, sixteen-entry palette with index 0 unused).",
    ),
)


@dataclass(frozen=True, slots=True)
class Check:
    """One resource, the figure measured against it, and the verdict."""

    name: str
    measured: int | None
    limit: Limit
    detail: str

    @property
    def verdict(self) -> str:
        if self.measured is None or not self.limit.established:
            return VERDICT_UNKNOWN
        return VERDICT_FITS if self.measured <= self.limit.value else VERDICT_OVER


@dataclass(frozen=True, slots=True)
class ImportReport:
    """Every check for one import, and the states of its target art slot."""

    identity: str
    character: str
    checks: tuple[Check, ...]
    carried_frames: int
    populated_states: tuple[int, ...]
    payload_status: str
    fallback_states: tuple[int, ...] = ()
    frame_palette_depth: int = 0

    @property
    def verdict(self) -> str:
        if not self.checks:
            return VERDICT_UNKNOWN
        return max((check.verdict for check in self.checks), key=_SEVERITY.__getitem__)

    @property
    def failures(self) -> tuple[Check, ...]:
        return tuple(check for check in self.checks if check.verdict != VERDICT_FITS)


@dataclass(frozen=True, slots=True)
class BudgetReport:
    """The document's verdict: the worst verdict its imports hold, never an average."""

    imports: tuple[ImportReport, ...]

    @property
    def verdict(self) -> str:
        if not self.imports:
            return VERDICT_UNKNOWN
        return max((entry.verdict for entry in self.imports), key=_SEVERITY.__getitem__)

    @property
    def ok(self) -> bool:
        return self.verdict == VERDICT_FITS


def limit_named(name: str) -> Limit:
    """The one limit with this name, so a check cannot invent a second ceiling."""
    for limit in LIMITS:
        if limit.name == name:
            return limit
    raise SpriteImportError(f"no limit named {name!r}; the table and the check disagree")


def palette_usage(frames: Sequence[DonorFrame], image: RomImage) -> tuple[int, ...]:
    """Every non-zero palette index the given donor frames use, sorted."""
    used: set[int] = set()
    for frame in frames:
        _, indices = frame_indices(image, frame)
        used.update(value for value in indices if value)
    return tuple(sorted(used))


def frame_palette_depth(
    frames: Sequence[DonorFrame], image: RomImage, palette_map: Mapping[int, int] | None = None
) -> int:
    """The most non-zero palette indices any one carried frame needs.

    A cell names at most one sixteen-colour bank, so this is the figure a per-frame bank
    has to satisfy; the union over every frame is what a single shared bank has to
    satisfy. Reporting both keeps the two questions apart.
    """
    worst = 0
    for frame in frames:
        _, indices = frame_indices(image, frame)
        used = {value for value in indices if value}
        if palette_map is not None:
            used = {palette_map[value] for value in used}
        worst = max(worst, len(used))
    return worst


def validate_budget(images: Mapping[str, RomImage], document: Manifest) -> BudgetReport:
    """Measure every carried frame against the budgets and report each verdict.

    Nothing here guesses a ceiling: a resource with no measured limit reports UNKNOWN with
    its figure, and the document verdict is the worst verdict it holds.
    """
    reports: list[ImportReport] = []
    for entry in document.imports:
        donor_image = images[entry.donor]
        target_image = images[entry.target.game]
        art = read_log1_art(
            target_image, entry.target.art_table, entry.target.art_id, entry.target.states
        )
        fallback = (
            read_log1_art(
                target_image,
                entry.target.art_table,
                entry.target.art_id,
                entry.target.fallback_states,
            )
            if entry.target.fallback_states
            else None
        )
        family = document.donor(entry.donor).family
        frames = carried_frames(donor_image, family, entry.definition, entry.animations)
        for animation in entry.animations:
            if animation.timing.published_frames is None or family != "webfoot-animation":
                continue
            address = donor_slot_address(donor_image, family, entry.definition, animation.slot)
            animation.timing.check_frame_count(
                donor_image.u32(address),
                f"import {entry.identity!r} slot {animation.slot}",
            )
        used = palette_usage(frames, donor_image)
        if entry.palette_map is not None:
            used = tuple(sorted({entry.palette_map[value] for value in used}))
        slots = [
            animation.slot
            for animation in entry.animations
            if animation.classification != "unused"
        ]
        checks = (
            Check(
                name="tiles per frame",
                measured=max(
                    (frame.width * frame.height // TILE_PIXELS for frame in frames),
                    default=0,
                ),
                limit=limit_named("tiles per frame"),
                detail="largest carried frame, at one four-bit tile per 64 pixels",
            ),
            Check(
                name="oam entries per frame",
                measured=max((len(frame.pieces) for frame in frames), default=0),
                limit=limit_named("oam entries per frame"),
                detail="one entry per rendered piece; a LOG1 cell holds one pointer",
            ),
            Check(
                name="palette indices per bank",
                measured=len(used),
                limit=limit_named("palette indices per bank"),
                detail="distinct non-zero indices the carried frames use",
            ),
            Check(
                name="target art slot",
                measured=0 if art.definition == entry.target.art_definition else 1,
                limit=Limit(
                    "target art slot",
                    0,
                    "the target image's art-definition run; the slot at the declared table "
                    "plus four times the art id must hold the definition this manifest "
                    "declares (read from bytes), so the allowance is zero mismatches",
                ),
                detail=f"art {entry.target.art_id} resolves to {art.definition:#010x}",
            ),
            Check(
                name="target art states",
                measured=len(slots),
                limit=Limit(
                    "target art states",
                    len(art.states),
                    f"art {entry.target.art_id}'s own animation table populates the "
                    f"{len(art.states)} state slots this manifest names, each verified "
                    "populated in the image; placing more is a writer question this phase "
                    "does not measure",
                ),
                detail=f"carried slots {', '.join(str(slot) for slot in slots)}",
            ),
        )
        reports.append(
            ImportReport(
                identity=entry.identity,
                character=entry.character,
                checks=checks,
                carried_frames=len(frames),
                populated_states=tuple(sorted(art.states)),
                payload_status=_payload_status(donor_image, family, entry),
                fallback_states=tuple(sorted(fallback.states)) if fallback else (),
                frame_palette_depth=frame_palette_depth(frames, donor_image, entry.palette_map),
            )
        )
    return BudgetReport(imports=tuple(reports))


def _payload_status(image: RomImage, family: str, entry: Import) -> str:
    """Whether a LOG1 payload could be built, and why not when it could not.

    A payload is only buildable once a palette map is declared, because a donor index above
    fifteen cannot fit a four-bit slot. Reporting the reason keeps an undecided palette out
    of the way of the measurements that do not depend on it.
    """
    if entry.palette_map is None:
        return "NOT BUILT: no palette map is declared, so no donor index above fifteen has a bank slot"
    for animation in entry.animations:
        if animation.classification == "unused" and animation.frames is None:
            continue
        for direction in animation.directions:
            for frame in donor_frames(
                image, family, entry.definition, animation.slot, direction, animation.frames
            ):
                try:
                    build_frame_payload(
                        image, frame, slot=animation.slot, direction=direction,
                        frame_index=0, palette_map=entry.palette_map,
                    )
                except SpriteImportError as exc:
                    return f"NOT BUILT: {exc}"
    return "built"




def load_images(
    document: Manifest, donor_rom: str | Path, target_rom: str | Path
) -> dict[str, RomImage]:
    """Open the donor and target images, each pinned to the digest the manifest states."""
    if len(document.donors) != 1:
        raise SpriteImportError(
            "one invocation reads one donor image; this manifest declares "
            f"{len(document.donors)}"
        )
    games = {entry.target.game for entry in document.imports}
    if len(games) != 1:
        raise SpriteImportError(
            f"one invocation reads one target image; this manifest names {len(games)}"
        )
    donor_name, donor = next(iter(document.donors.items()))
    game = next(iter(games))
    digest = {entry.target.sha256 for entry in document.imports if entry.target.game == game}
    if len(digest) != 1:
        raise SpriteImportError("imports targeting one game disagree about its digest")
    images = {donor_name: RomImage.open(donor_rom, donor.sha256)}
    images[game] = RomImage.open(target_rom, digest.pop())
    return images


def report_lines(report: BudgetReport) -> list[str]:
    """The report as plain lines, with each figure and the source of its limit."""
    lines: list[str] = []
    for entry in report.imports:
        lines.append(f"{entry.identity} ({entry.character}): {entry.verdict}")
        lines.append(
            f"  carried frames {entry.carried_frames}; target art states "
            f"{', '.join(str(state) for state in entry.populated_states)}"
        )
        lines.append(
            "  LOG1-FALLBACK states "
            + (", ".join(str(state) for state in entry.fallback_states) or "none")
            + " (keep the target's own art)"
        )
        lines.append(
            f"  palette depth: worst single frame needs {entry.frame_palette_depth} of the "
            "fifteen indices one bank addresses; a per-frame bank satisfies this, a single "
            "shared bank must satisfy the union above"
        )
        for check in entry.checks:
            limit = "UNKNOWN" if not check.limit.established else str(check.limit.value)
            measured = "n/a" if check.measured is None else str(check.measured)
            lines.append(f"  {check.name}: {check.verdict} measured {measured} limit {limit}")
            lines.append(f"  {check.detail}")
            lines.append(f"    limit source: {check.limit.source}")
        lines.append(f"  payload: {entry.payload_status}")
    lines.append(f"verdict: {report.verdict}")
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    """Validate a manifest against its images, and exit non-zero unless it fits."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m tools.webfoot.sprite_import",
        description="Validate a Webfoot sprite-import manifest against its images.",
    )
    parser.add_argument("manifest", help="path to a sprite-import manifest")
    parser.add_argument("--donor-rom", required=True, help="donor image path")
    parser.add_argument("--target-rom", required=True, help="target image path")
    arguments = parser.parse_args(argv)
    document = load_manifest(arguments.manifest)
    images = load_images(document, arguments.donor_rom, arguments.target_rom)
    report = validate_budget(images, document)
    for line in report_lines(report):
        print(line)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
