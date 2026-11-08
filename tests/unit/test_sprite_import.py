"""The sprite-import schema, adapter and budget, against synthetic fixtures.

Every image here is built in the test: no donor byte, no art and no real address is read
from a ROM, and the shapes are the ones the retail records were measured at rather than the
retail records themselves.
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Mapping

import pytest

from tools.webfoot import sprite_import as si
from tools.webfoot.binary import GBA_ROM_BASE
from tools.webfoot.formats import webfoot_lz

DONOR_SHA = "0" * 64
TARGET_SHA = "1" * 64
BOX = (16, 32)
WIDTH, HEIGHT = BOX
PIXELS = WIDTH * HEIGHT


class Fixture:
    """A synthetic image builder: allocations are file offsets, reads are GBA addresses."""

    def __init__(self, size: int = 0x4000) -> None:
        self.data = bytearray(size)
        self.cursor = 0x100

    def write(self, payload: bytes, align: int = 4) -> int:
        if self.cursor % align:
            self.cursor += align - (self.cursor % align)
        offset = self.cursor
        self.cursor += len(payload)
        assert self.cursor <= len(self.data), "the fixture image is too small"
        self.data[offset : offset + len(payload)] = payload
        return GBA_ROM_BASE + offset

    def poke_u32(self, address: int, value: int) -> None:
        offset = address - GBA_ROM_BASE
        self.data[offset : offset + 4] = value.to_bytes(4, "little", signed=False)

    def image(self, digest: str = DONOR_SHA) -> si.RomImage:
        return si.RomImage(path=Path("synthetic.gba"), sha256=digest, data=bytes(self.data))


def stored(payload: bytes) -> bytes:
    """One stored container holding the given palette indices."""
    return webfoot_lz.build_stored(payload)


def build_animation_donor(
    *,
    slots: int = 1,
    frames: int = 2,
    indices: bytes | None = None,
    hflip: bool = False,
    box: tuple[int, int] = BOX,
) -> tuple[Fixture, int]:
    """A donor in the animation family: definition, slot array, animations, frames, pieces."""
    fixture = Fixture()
    width, height = box
    pixels = (
        indices
        if indices is not None
        else bytes(value % 8 for value in range(width * height))
    )
    container = fixture.write(stored(pixels))
    definition = bytearray(si.SLOT_ARRAY_OFFSET["webfoot-animation"] + 4 * slots)
    definition[0] = slots
    for slot in range(slots):
        cell_addresses = []
        for _ in range(frames * 4):
            record = bytearray(si.FRAME_HEADER_BYTES + si.PIECE_RECORD_BYTES)
            record[0:4] = (1).to_bytes(4, "little")
            record[4] = 0
            record[5] = (256 - height) & 0xFF
            record[6] = width
            record[7] = height
            record[8] = 0
            record[9] = (256 - height) & 0xFF
            record[10] = width
            record[11] = height
            attributes = si.ATTR_COLOUR_256
            if hflip:
                attributes |= si.ATTR_HORIZONTAL_FLIP << 16
            record[12:16] = attributes.to_bytes(4, "little")
            record[16:20] = container.to_bytes(4, "little")
            cell_addresses.append(fixture.write(bytes(record)))
        animation = bytearray(4 + si.ANIMATION_FRAME_STRIDE * frames)
        animation[0:4] = frames.to_bytes(4, "little")
        for index, address in enumerate(cell_addresses):
            animation[4 + index * 4 : 8 + index * 4] = address.to_bytes(4, "little")
        offset = si.SLOT_ARRAY_OFFSET["webfoot-animation"] + slot * 4
        definition[offset : offset + 4] = fixture.write(bytes(animation)).to_bytes(4, "little")
    return fixture, fixture.write(bytes(definition))


def build_piece_run_donor(
    *, run_length: int = 3, box: tuple[int, int] = BOX
) -> tuple[Fixture, int]:
    """A donor in the piece-run family: four facing pointers, each a terminated run."""
    fixture = Fixture()
    width, height = box
    container = fixture.write(
        stored(bytes(value % 8 for value in range(width * height)))
    )
    definition = bytearray(si.SLOT_ARRAY_OFFSET["webfoot-piece-run"] + 16)
    definition_address = fixture.write(bytes(definition))
    for facing in range(4):
        records = bytearray()
        for index in range(run_length):
            record = bytearray(si.PIECE_RECORD_BYTES)
            record[0] = index
            record[1] = (256 - height) & 0xFF
            record[2] = width
            record[3] = height
            attributes = si.ATTR_COLOUR_256
            if facing == 3:
                attributes |= si.ATTR_HORIZONTAL_FLIP << 16
            record[4:8] = attributes.to_bytes(4, "little")
            record[8:12] = container.to_bytes(4, "little")
            records += record
        records += bytes(si.PIECE_RECORD_BYTES)
        address = fixture.write(bytes(records))
        fixture.poke_u32(
            definition_address + si.SLOT_ARRAY_OFFSET["webfoot-piece-run"] + 4 * facing,
            address,
        )
    return fixture, definition_address


def build_target(
    *,
    states: tuple[int, ...] = (0, 1),
    arts: tuple[int, ...] = (46,),
    box: tuple[int, int] = BOX,
) -> tuple[Fixture, dict[str, int]]:
    """A LOG1 target: an art table, one definition per art id, and populated state cells."""
    fixture = Fixture()
    width, height = box
    size, shape = si.cell_geometry(width, height)
    table = fixture.write(bytes(4 * 64))
    found: dict[str, int] = {"table": table}
    for art_id in arts:
        table_rows = bytearray(si.LOG1_STATE_BYTES * (max(states) + 1))
        cell_addresses = []
        for _state in states:
            for _facing in range(si.LOG1_FACINGS):
                record = bytearray(si.LOG1_CELL_BYTES)
                record[2:4] = (-24).to_bytes(2, "little", signed=True)
                record[4:6] = width.to_bytes(2, "little")
                record[6:8] = height.to_bytes(2, "little")
                record[8] = width * height // si.TILE_PIXELS
                record[10] = size
                record[11] = shape
                cell_addresses.append(fixture.write(bytes(record)))
        for row, state in enumerate(states):
            for facing in range(si.LOG1_FACINGS):
                offset = state * si.LOG1_STATE_BYTES + facing * 4
                table_rows[offset : offset + 4] = cell_addresses[
                    row * si.LOG1_FACINGS + facing
                ].to_bytes(4, "little")
        animation_table = fixture.write(bytes(table_rows))
        definition = bytearray(64)
        definition[si.LOG1_PALETTE_OFFSET : si.LOG1_PALETTE_OFFSET + 4] = (
            (GBA_ROM_BASE + 0x1000).to_bytes(4, "little")
        )
        definition[si.LOG1_ANIMATION_OFFSET : si.LOG1_ANIMATION_OFFSET + 4] = (
            animation_table.to_bytes(4, "little")
        )
        found[str(art_id)] = fixture.write(bytes(definition))
        fixture.poke_u32(table + art_id * 4, found[str(art_id)])
    return fixture, found


def make_document(
    definition: int,
    target: Mapping[str, int],
    *,
    family: str = "webfoot-animation",
    art_id: int = 46,
    animations: list | None = None,
    palette: dict | None = None,
    swap_in: dict | None = None,
    expected_definition: int | None = None,
    states: tuple[int, ...] = (0, 1),
    fallback_states: tuple[int, ...] = (),
) -> dict:
    target_block = {
        "game": "target",
        "sha256": TARGET_SHA,
        "art_table": target["table"],
        "art_id": art_id,
        "art_definition": target[str(art_id)]
        if expected_definition is None
        else expected_definition,
        "states": list(states),
    }
    if fallback_states:
        target_block["fallback_states"] = list(fallback_states)
    if swap_in is not None:
        target_block["swap_in"] = swap_in
    entry = {
        "id": "entry",
        "character": "Fixture",
        "donor": "donor",
        "definition": definition,
        "target": target_block,
        "animations": animations
        if animations is not None
        else [
            {
                "slot": 0,
                "classification": "authentic",
                "timing": {"class": "PLACEHOLDER"},
            }
        ],
    }
    if palette is not None:
        entry["palette"] = palette
    return {
        "schema": si.SCHEMA,
        "donors": {"donor": {"family": family, "sha256": DONOR_SHA}},
        "imports": [entry],
    }


def images(donor: Fixture, target: Fixture) -> dict[str, si.RomImage]:
    return {"donor": donor.image(DONOR_SHA), "target": target.image(TARGET_SHA)}


MEASURED = {
    "class": "MEASURED",
    "durations_video_frames": [8, 8],
    "published_frames": 2,
    "loop": "loop",
    "run_line": "synthetic-run",
}




def test_a_minimal_document_round_trips() -> None:
    _donor, definition = build_animation_donor()
    _target, arts = build_target()
    manifest = si.Manifest.from_document(make_document(definition, arts))
    assert manifest.schema == si.SCHEMA
    assert manifest.donors["donor"].family == "webfoot-animation"
    assert manifest.imports[0].definition == definition
    assert manifest.imports[0].target.art_id == 46


def test_an_unknown_key_is_refused() -> None:
    _donor, definition = build_animation_donor()
    _target, arts = build_target()
    raw = make_document(definition, arts)
    raw["imports"][0]["invented"] = 1
    with pytest.raises(si.SpriteImportError, match="unknown key"):
        si.Manifest.from_document(raw)


def test_a_wrong_schema_version_is_refused() -> None:
    _donor, definition = build_animation_donor()
    _target, arts = build_target()
    raw = make_document(definition, arts)
    raw["schema"] = "webfoot.sprite-import/2"
    with pytest.raises(si.SpriteImportError, match="schema"):
        si.Manifest.from_document(raw)


def test_a_classification_outside_the_three_statuses_is_refused() -> None:
    _donor, definition = build_animation_donor()
    _target, arts = build_target()
    raw = make_document(definition, arts)
    raw["imports"][0]["animations"][0]["classification"] = "borrowed"
    with pytest.raises(si.SpriteImportError, match="classification"):
        si.Manifest.from_document(raw)


def test_a_measured_label_without_its_run_line_is_refused() -> None:
    _donor, definition = build_animation_donor()
    _target, arts = build_target()
    raw = make_document(definition, arts)
    raw["imports"][0]["animations"][0]["timing"] = dict(MEASURED)
    del raw["imports"][0]["animations"][0]["timing"]["run_line"]
    with pytest.raises(si.SpriteImportError, match="MEASURED"):
        si.Manifest.from_document(raw)


def test_a_placeholder_may_not_carry_a_duration() -> None:
    _donor, definition = build_animation_donor()
    _target, arts = build_target()
    raw = make_document(definition, arts)
    raw["imports"][0]["animations"][0]["timing"] = {
        "class": "PLACEHOLDER",
        "durations_video_frames": [8],
    }
    with pytest.raises(si.SpriteImportError, match="PLACEHOLDER"):
        si.Manifest.from_document(raw)


def test_an_assumed_label_needs_the_owner_acceptance() -> None:
    _donor, definition = build_animation_donor()
    _target, arts = build_target()
    raw = make_document(definition, arts)
    raw["imports"][0]["animations"][0]["timing"] = {
        "class": "ASSUMED",
        "durations_video_frames": [8, 8],
        "published_frames": 2,
        "source": "a measured law applied by published-frame count",
    }
    with pytest.raises(si.SpriteImportError, match="ASSUMED"):
        si.Manifest.from_document(raw)


def test_explicit_frames_are_only_allowed_on_an_adapted_slot() -> None:
    _donor, definition = build_animation_donor()
    _target, arts = build_target()
    raw = make_document(definition, arts)
    raw["imports"][0]["animations"][0]["frames"] = [GBA_ROM_BASE + 0x400]
    with pytest.raises(si.SpriteImportError, match="only an adapted sequence"):
        si.Manifest.from_document(raw)


def test_a_state_outside_the_art_window_is_refused() -> None:
    _donor, definition = build_animation_donor()
    _target, arts = build_target()
    raw = make_document(definition, arts)
    raw["imports"][0]["target"]["states"] = [0, si.TARGET_STATE_LIMIT]
    with pytest.raises(si.SpriteImportError, match="window"):
        si.Manifest.from_document(raw)


def test_a_swapped_slot_needs_a_declared_source() -> None:
    _donor, definition = build_animation_donor()
    _target, arts = build_target()
    raw = make_document(
        definition, arts, swap_in={"status": "reuse", "source": "the art 46 reuse"}
    )
    manifest = si.Manifest.from_document(raw)
    assert manifest.imports[0].target.swap_in.status == "reuse"
    broken = make_document(definition, arts, swap_in={"status": "reuse", "source": "  "})
    with pytest.raises(si.SpriteImportError, match="non-empty"):
        si.Manifest.from_document(broken)


def test_an_undefined_status_is_refused_for_a_swapped_slot() -> None:
    _donor, definition = build_animation_donor()
    _target, arts = build_target()
    raw = make_document(
        definition, arts, swap_in={"status": "drawn", "source": "hand-made"}
    )
    with pytest.raises(si.SpriteImportError, match="status"):
        si.Manifest.from_document(raw)




def test_an_authentic_slot_yields_one_payload_per_direction_and_frame() -> None:
    donor, definition = build_animation_donor(frames=2)
    target, arts = build_target()
    manifest = si.Manifest.from_document(make_document(definition, arts))
    payloads = si.import_payloads(images(donor, target), manifest)["entry"]
    assert len(payloads) == 2 * 4
    assert {frame.direction for frame in payloads} == {0, 1, 2, 3}
    assert all(frame.cell.tiles == PIXELS // si.TILE_PIXELS for frame in payloads)
    assert all(len(frame.tiles) == PIXELS // 2 for frame in payloads)


def test_the_payload_matches_an_independent_decode_of_the_same_container() -> None:
    indices = bytes(value % 8 for value in range(PIXELS))
    donor, definition = build_animation_donor(frames=1, indices=indices)
    image = donor.image(DONOR_SHA)
    frames = si.donor_frames(image, "webfoot-animation", definition, 0, 0)
    assert len(frames) == 1
    got_piece, got_indices = si.frame_indices(image, frames[0])
    container = webfoot_lz.unpack(image.data, image.offset(got_piece.container))
    assert container.data == got_indices == indices

    payload = si.build_frame_payload(image, frames[0], slot=0, direction=0, frame_index=0)
    independent = bytearray(len(got_indices) // 2)
    for index in range(0, len(got_indices), 2):
        independent[index // 2] = got_indices[index] | (got_indices[index + 1] << 4)
    assert payload.tiles == bytes(independent)

    record = payload.cell.to_record(GBA_ROM_BASE + 0x3000)
    assert len(record) == si.LOG1_CELL_BYTES
    assert int.from_bytes(record[4:6], "little") == WIDTH
    assert record[8] == PIXELS // si.TILE_PIXELS
    assert int.from_bytes(record[12:16], "little") == GBA_ROM_BASE + 0x3000


def test_a_horizontal_flip_reaches_the_cell_attribute_byte() -> None:
    donor, definition = build_animation_donor(frames=1, hflip=True)
    image = donor.image(DONOR_SHA)
    payload = si.build_frame_payload(
        image,
        si.donor_frames(image, "webfoot-animation", definition, 0, 0)[0],
        slot=0,
        direction=0,
        frame_index=0,
    )
    assert payload.cell.horizontal_flip is True


def test_an_adapted_sequence_emits_exactly_the_listed_frames() -> None:
    donor, definition = build_animation_donor(frames=2)
    target, arts = build_target()
    image = donor.image(DONOR_SHA)
    slot_zero = si.donor_frames(image, "webfoot-animation", definition, 0, 0)
    addresses = [slot_zero[1].address, slot_zero[0].address]
    manifest = si.Manifest.from_document(
        make_document(
            definition,
            arts,
            animations=[
                {
                    "slot": 0,
                    "classification": "adapted",
                    "directions": [0],
                    "frames": addresses,
                    "timing": {"class": "PLACEHOLDER"},
                }
            ],
        )
    )
    payloads = si.import_payloads({"donor": image}, manifest)["entry"]
    assert [frame.donor_frame for frame in payloads] == addresses


def test_an_unused_slot_is_not_carried() -> None:
    donor, definition = build_animation_donor(slots=2, frames=1)
    target, arts = build_target()
    manifest = si.Manifest.from_document(
        make_document(
            definition,
            arts,
            animations=[
                {"slot": 0, "classification": "unused", "timing": {"class": "PLACEHOLDER"}},
                {"slot": 1, "classification": "authentic", "timing": {"class": "PLACEHOLDER"}},
            ],
        )
    )
    payloads = si.import_payloads({"donor": donor.image(DONOR_SHA)}, manifest)["entry"]
    assert {frame.slot for frame in payloads} == {1}
    assert len(payloads) == 4


def test_a_multipart_donor_frame_is_refused() -> None:
    donor, definition = build_animation_donor(frames=1)
    image = donor.image(DONOR_SHA)
    frame = si.donor_frames(image, "webfoot-animation", definition, 0, 0)[0]
    doubled = si.DonorFrame(
        address=frame.address,
        min_x=frame.min_x,
        min_y=frame.min_y,
        width=frame.width,
        height=frame.height,
        pieces=frame.pieces * 2,
    )
    with pytest.raises(si.SpriteImportError, match="multipart"):
        si.frame_indices(image, doubled)


def test_a_piece_run_resolves_per_facing_and_keeps_its_flip() -> None:
    donor, definition = build_piece_run_donor(run_length=3)
    image = donor.image(DONOR_SHA)
    lengths = [
        len(si.donor_frames(image, "webfoot-piece-run", definition, 0, facing))
        for facing in range(4)
    ]
    assert lengths == [3, 3, 3, 3]
    assert si.donor_frames(image, "webfoot-piece-run", definition, 0, 3)[0].pieces[
        0
    ].horizontal_flip
    upright = si.build_frame_payload(
        image,
        si.donor_frames(image, "webfoot-piece-run", definition, 0, 0)[0],
        slot=0,
        direction=0,
        frame_index=0,
    )
    mirrored = si.build_frame_payload(
        image,
        si.donor_frames(image, "webfoot-piece-run", definition, 0, 3)[0],
        slot=0,
        direction=3,
        frame_index=0,
    )
    assert upright.cell.horizontal_flip is False
    assert mirrored.cell.horizontal_flip is True


def test_a_piece_run_without_a_terminator_is_refused() -> None:
    fixture = Fixture()
    container = fixture.write(stored(bytes(PIXELS)))
    run = bytearray()
    for _ in range(3):
        record = bytearray(si.PIECE_RECORD_BYTES)
        record[2] = WIDTH
        record[3] = HEIGHT
        record[4:8] = si.ATTR_COLOUR_256.to_bytes(4, "little")
        record[8:12] = container.to_bytes(4, "little")
        run += record
    address = fixture.write(bytes(run))
    with pytest.raises(si.SpriteImportError, match="did not terminate"):
        si.read_piece_run(fixture.image(DONOR_SHA), address, limit=3)


def test_a_donor_frame_whose_container_contradicts_it_is_refused() -> None:
    donor, definition = build_animation_donor(frames=1)
    image = donor.image(DONOR_SHA)
    frame = si.donor_frames(image, "webfoot-animation", definition, 0, 0)[0]
    piece = frame.pieces[0]
    lying = si.DonorPiece(
        x=piece.x,
        y=piece.y,
        width=WIDTH * 2,
        height=HEIGHT * 2,
        attributes=piece.attributes,
        container=piece.container,
    )
    with pytest.raises(si.SpriteImportError, match="declares"):
        si.frame_indices(
            image,
            si.DonorFrame(
                address=frame.address,
                min_x=frame.min_x,
                min_y=frame.min_y,
                width=WIDTH * 2,
                height=HEIGHT * 2,
                pieces=(lying,),
            ),
        )


def test_a_palette_map_must_cover_every_index_the_frame_uses() -> None:
    indices = bytes(value % 4 for value in range(PIXELS))
    donor, definition = build_animation_donor(frames=1, indices=indices)
    image = donor.image(DONOR_SHA)
    frame = si.donor_frames(image, "webfoot-animation", definition, 0, 0)[0]
    with pytest.raises(si.SpriteImportError, match="bank slot"):
        si.build_frame_payload(
            image, frame, slot=0, direction=0, frame_index=0, palette_map={0: 0, 1: 1}
        )
    payload = si.build_frame_payload(
        image,
        frame,
        slot=0,
        direction=0,
        frame_index=0,
        palette_map={0: 0, 1: 1, 2: 2, 3: 3},
    )
    assert set(si.unpack_indices(payload.tiles, False)) == {0, 1, 2, 3}




def test_an_unmeasured_limit_reports_unknown_and_fails_the_document_closed() -> None:
    donor, definition = build_animation_donor(frames=2, indices=bytes(PIXELS))
    target, arts = build_target()
    manifest = si.Manifest.from_document(make_document(definition, arts))
    report = si.validate_budget(images(donor, target), manifest)
    tiles = report.imports[0].checks[0]
    assert tiles.name == "tiles per frame"
    assert tiles.verdict == si.VERDICT_UNKNOWN
    assert tiles.limit.established is False
    assert report.imports[0].checks[1].verdict == si.VERDICT_FITS
    assert report.ok is False
    assert si.report_lines(report)[-1].endswith(si.VERDICT_UNKNOWN)


def test_the_palette_budget_reports_the_figure_and_the_source_of_its_limit() -> None:
    wide = (
        bytes([0, 1, 2, 3, 16, 17, 18, 19, 32, 33, 34, 35, 48, 49, 50, 51, 64, 65, 66, 67])
        * 26
    )[:PIXELS]
    donor, definition = build_animation_donor(frames=1, indices=wide)
    target, arts = build_target()
    manifest = si.Manifest.from_document(make_document(definition, arts))
    report = si.validate_budget(images(donor, target), manifest)
    palette = report.imports[0].checks[2]
    assert palette.name == "palette indices per bank"
    assert palette.measured == 0
    assert palette.limit.value == 15
    assert "index 0" in palette.limit.source
    partition = report.imports[0].checks[7]
    assert partition.name == "piece partition"
    assert partition.verdict == si.VERDICT_OVER
    assert partition.measured == report.imports[0].carried_frames
    assert "cannot be split" in partition.detail
    assert report.verdict == si.VERDICT_OVER


def test_a_declared_state_the_image_does_not_populate_is_refused() -> None:
    donor, definition = build_animation_donor(frames=1, indices=bytes(PIXELS))
    target, arts = build_target(states=(0,))
    manifest = si.Manifest.from_document(
        make_document(definition, arts, states=(0, 1))
    )
    with pytest.raises(si.SpriteImportError, match="does not populate"):
        si.validate_budget(images(donor, target), manifest)


def test_a_fallback_state_keeps_the_target_art_and_is_reported() -> None:
    donor, definition = build_animation_donor(frames=1, indices=bytes(PIXELS))
    target, arts = build_target(states=(0, 1, 2, 6))
    manifest = si.Manifest.from_document(
        make_document(definition, arts, states=(0, 1), fallback_states=(2, 6))
    )
    report = si.validate_budget(images(donor, target), manifest)
    entry = report.imports[0]
    assert entry.fallback_states == (2, 6)
    assert entry.populated_states == (0, 1)
    lines = "\n".join(si.report_lines(report))
    assert "LOG1-FALLBACK states 2, 6 (keep the target's own art)" in lines


def test_a_state_declared_as_both_donor_and_fallback_is_refused() -> None:
    target, arts = build_target(states=(0, 1))
    with pytest.raises(si.SpriteImportError, match="never both"):
        si.Manifest.from_document(
            make_document(1, arts, states=(0, 1), fallback_states=(1,))
        )


def test_a_fallback_state_the_image_does_not_populate_is_refused() -> None:
    donor, definition = build_animation_donor(frames=1, indices=bytes(PIXELS))
    target, arts = build_target(states=(0,))
    manifest = si.Manifest.from_document(
        make_document(definition, arts, states=(0,), fallback_states=(7,))
    )
    with pytest.raises(si.SpriteImportError, match="does not populate"):
        si.validate_budget(images(donor, target), manifest)


def test_the_frame_palette_depth_is_the_worst_single_frame_not_the_union() -> None:
    width, height = BOX
    sparse = bytes([1, 0] * (width * height // 2))
    wide = bytes([(2 if index % 2 == 0 else 3) for index in range(width * height)])
    donor, definition = build_animation_donor(frames=1, indices=sparse)
    target, arts = build_target(states=(0,))
    manifest = si.Manifest.from_document(make_document(definition, arts, states=(0,)))
    report = si.validate_budget(images(donor, target), manifest)
    assert report.imports[0].frame_palette_depth == 1
    other, other_definition = build_animation_donor(frames=1, indices=wide)
    manifest = si.Manifest.from_document(
        make_document(other_definition, arts, states=(0,))
    )
    report = si.validate_budget(images(other, target), manifest)
    assert report.imports[0].frame_palette_depth == 2


def test_a_slot_carried_past_the_target_art_states_is_reported_as_not_fitting() -> None:
    donor, definition = build_animation_donor(slots=2, frames=1, indices=bytes(PIXELS))
    target, arts = build_target(states=(0,))
    manifest = si.Manifest.from_document(
        make_document(
            definition,
            arts,
            states=(0,),
            animations=[
                {"slot": 0, "classification": "authentic", "timing": {"class": "PLACEHOLDER"}},
                {"slot": 1, "classification": "authentic", "timing": {"class": "PLACEHOLDER"}},
            ],
        )
    )
    report = si.validate_budget(images(donor, target), manifest)
    states = report.imports[0].checks[4]
    assert states.name == "target art states"
    assert states.verdict == si.VERDICT_OVER
    assert states.measured == 2
    assert states.limit.value == 1


def test_a_target_art_slot_holding_another_definition_is_reported() -> None:
    donor, definition = build_animation_donor(frames=1, indices=bytes(PIXELS))
    target, arts = build_target(arts=(46, 47))
    manifest = si.Manifest.from_document(
        make_document(definition, arts, art_id=47, expected_definition=GBA_ROM_BASE + 0x10)
    )
    report = si.validate_budget(images(donor, target), manifest)
    slot = report.imports[0].checks[3]
    assert slot.name == "target art slot"
    assert slot.verdict == si.VERDICT_OVER


def test_the_art_47_swap_in_reuses_the_art_46_payload() -> None:
    donor, definition = build_animation_donor(frames=1, indices=bytes(PIXELS))
    target, arts = build_target(arts=(46, 47))
    shared = si.Manifest.from_document(
        make_document(
            definition,
            arts,
            art_id=47,
            swap_in={"status": "reuse", "source": "the art 46 import"},
        )
    )
    plain = si.Manifest.from_document(make_document(definition, arts, art_id=46))
    both = images(donor, target)
    reused = si.import_payloads(both, shared)["entry"]
    original = si.import_payloads(both, plain)["entry"]
    assert shared.imports[0].target.swap_in is not None
    assert shared.imports[0].target.swap_in.source == "the art 46 import"
    assert [frame.tiles for frame in reused] == [frame.tiles for frame in original]




def test_an_image_with_the_wrong_digest_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "image.gba"
    path.write_bytes(bytes(16))
    with pytest.raises(si.SpriteImportError, match="pinned"):
        si.RomImage.open(path, "f" * 64)


def test_reading_an_image_leaves_it_byte_identical(tmp_path: Path) -> None:
    donor, definition = build_animation_donor(frames=1)
    path = tmp_path / "image.gba"
    path.write_bytes(bytes(donor.data))
    before = sha256(path.read_bytes()).hexdigest()
    image = si.RomImage.open(path, before)
    si.donor_frames(image, "webfoot-animation", definition, 0, 0)
    assert sha256(path.read_bytes()).hexdigest() == before


def test_a_manifest_loads_from_a_json_file(tmp_path: Path) -> None:
    _donor, definition = build_animation_donor(frames=1)
    _target, arts = build_target()
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(make_document(definition, arts)), encoding="utf-8")
    assert si.load_manifest(path).imports[0].identity == "entry"


@pytest.mark.parametrize("box", sorted(si.CELL_ATTRIBUTE_SIZE_AND_SHAPE))
def test_a_built_cell_carries_the_measured_attribute_pair_for_its_box(box) -> None:
    donor, definition = build_animation_donor(frames=1, box=box)
    image = donor.image(DONOR_SHA)
    payload = si.build_frame_payload(
        image,
        si.donor_frames(image, "webfoot-animation", definition, 0, 0)[0],
        slot=0,
        direction=0,
        frame_index=0,
    )
    size, shape = si.CELL_ATTRIBUTE_SIZE_AND_SHAPE[box]
    assert (payload.cell.width, payload.cell.height) == box
    assert payload.cell.attributes == (0, size, shape)
    assert payload.cell.tiles == box[0] * box[1] // si.TILE_PIXELS


def test_a_flip_still_only_touches_the_first_attribute_byte() -> None:
    donor, definition = build_animation_donor(frames=1, hflip=True)
    image = donor.image(DONOR_SHA)
    payload = si.build_frame_payload(
        image,
        si.donor_frames(image, "webfoot-animation", definition, 0, 0)[0],
        slot=0,
        direction=0,
        frame_index=0,
    )
    size, shape = si.cell_geometry(16, 32)
    assert payload.cell.attributes == (si.LOG1_CELL_HORIZONTAL_FLIP, size, shape)


def test_the_measured_table_is_the_target_images_own() -> None:
    measured = {
        (16, 32): (2, 2),
        (32, 16): (2, 1),
        (32, 32): (2, 0),
        (32, 64): (3, 2),
        (64, 32): (3, 1),
    }
    for box, pair in measured.items():
        assert si.CELL_ATTRIBUTE_SIZE_AND_SHAPE[box] == pair, box
    for (width, height), (size, shape) in si.CELL_ATTRIBUTE_SIZE_AND_SHAPE.items():
        long_side = max(width, height)
        assert size == long_side.bit_length() - 4, (width, height, size)
        expected_shape = 0 if width == height else (1 if width > height else 2)
        assert shape == expected_shape, (width, height, shape)


def test_a_box_the_table_does_not_know_fails_closed_by_name() -> None:
    with pytest.raises(si.SpriteImportError, match="24x16"):
        si.cell_geometry(24, 16)
    assert si.cell_geometry(16, 16) == (1, 0)
    assert si.cell_geometry(16, 8) == (1, 1)
    assert si.cell_geometry(8, 16) == (1, 2)
    assert si.cell_geometry(8, 8) == (0, 0)


def test_a_log2_adapted_slot_is_read_with_the_piece_run_reader() -> None:
    donor, definition = build_piece_run_donor(run_length=3)
    target, arts = build_target()
    image = donor.image(DONOR_SHA)
    facing = si.donor_slot_address(image, "webfoot-piece-run", definition, 0, 0)
    addresses = [facing + index * si.PIECE_RECORD_BYTES for index in range(3)]
    manifest = si.Manifest.from_document(
        make_document(
            definition,
            arts,
            family="webfoot-piece-run",
            animations=[
                {
                    "slot": 0,
                    "classification": "adapted",
                    "directions": [0],
                    "frames": addresses,
                    "timing": {"class": "PLACEHOLDER"},
                }
            ],
        )
    )
    payloads = si.import_payloads({"donor": image}, manifest)["entry"]
    assert [frame.donor_frame for frame in payloads] == addresses
    assert all(frame.cell.attributes == (0, 2, 2) for frame in payloads)


def test_the_splitter_uses_the_fewest_legal_pieces() -> None:
    top = bytes([1, 2, 3, 4, 5, 6, 7, 8] * 2)
    bottom = bytes([9, 10, 11, 12, 13, 14, 15, 16] * 2)
    indices = top * 8 + bottom * 8
    pieces = si.split_frame(indices, 16, 16)
    assert [(piece.x, piece.y, piece.width, piece.height) for piece in pieces] == [
        (0, 0, 16, 8),
        (0, 8, 16, 8),
    ]
    assert [len(piece.colours) for piece in pieces] == [8, 8]
    assert si.split_frame(indices, 16, 16) == pieces


def test_a_frame_inside_one_bank_stays_one_piece() -> None:
    indices = bytes([(index % 15) + 1 for index in range(16 * 16)])
    pieces = si.split_frame(indices, 16, 16)
    assert len(pieces) == 1
    assert pieces[0].colours == tuple(range(1, 16))


def test_a_frame_that_cannot_partition_fails_closed_by_name() -> None:
    indices = bytes([(index % 16) + 1 for index in range(8 * 8)])
    with pytest.raises(si.SpriteImportError, match="16-colour cell at 0,0"):
        si.split_frame(indices, 8, 8)
    with pytest.raises(si.SpriteImportError, match="eight-pixel grid"):
        si.split_frame(bytes(12), 12, 12)


def test_a_piece_bank_byte_keeps_the_size_and_names_the_bank() -> None:
    for bank in range(16):
        value = si.cell_bank_attribute(2, bank)
        assert value & 0x3 == 2
        assert (value >> 2) & 0xF == bank
        assert value >> 6 == si.CELL_BANK_MODE
    with pytest.raises(si.SpriteImportError, match="sixteen-bank palette"):
        si.cell_bank_attribute(1, 16)


def test_piece_banks_are_numbered_in_first_appearance_order() -> None:
    first = si.FramePiece(0, 0, 8, 8, (1, 2))
    second = si.FramePiece(8, 0, 8, 8, (3, 4))
    banks = si.piece_bank_map([[first, second], [second, first]])
    assert banks == {(1, 2): 0, (3, 4): 1}