"""Re-derive one tile and one frame record per approved donor, from the images.

WHAT THIS PROVES. The adapter's own decode is checked against a second, older reader:
``tools.export.canonical``, which this module does not use. For each approved donor the test
re-reads one frame record and one tile's index stream through that reader and compares them
with the adapter's output, and for the LOG1 target it checks one art cell against the
published decode.

WHAT IT DOES NOT PROVE. No pixel orientation and no runtime behaviour: this is a static
comparison of two decoders over the same bytes.

The images are read in place from paths this test never writes, and each is checked against
the digest the manifest pins before a byte is used.
"""

from __future__ import annotations

import os
from hashlib import sha256
from pathlib import Path

import pytest

from tools.export import canonical as canon
from tools.webfoot import sprite_import as si
from tools.webfoot.binary import GBA_ROM_BASE

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFESTS = REPOSITORY_ROOT / "config" / "sprite-imports"

IMAGES = {
    "buus-fury": (
        "WEBFOOT_BUU_ROM",
        Path("roms") / "Dragon Ball Z - Buu's Fury (U).gba",
        "940ad5f01db4465b8877dfe739510cbf34f4ea3d390f3df13519808bc36f059e",
    ),
    "legacy-of-goku": (
        "WEBFOOT_LOG1_ROM",
        Path("roms") / "Dragon Ball Z - The Legacy of Goku (USA).gba",
        "3ba9919e26704b0f5fdc2bfabc7f7a0404c71413761d38abcd94224c3bd4b1b9",
    ),
    "legacy-of-goku-2": (
        "WEBFOOT_LOG2_ROM",
        Path("roms") / "Dragon Ball Z - The Legacy of Goku II (USA).gba",
        "6e6c370c339ec9171cb1956adf837a0d342a197f78964882ef46c3086656ff75",
    ),
}

DONOR_MANIFESTS = (
    ("goku-base.json", "buus-fury"),
    ("goku-super-saiyan.json", "buus-fury"),
    ("roshi.json", "buus-fury"),
    ("krillin-art46.json", "legacy-of-goku-2"),
)


def image_path(key: str) -> Path:
    """The pinned path for one image, or a skip when it is not on this machine."""
    variable, relative, expected = IMAGES[key]
    candidate = Path(os.environ.get(variable, "")) if os.environ.get(variable) else None
    path = candidate if candidate and candidate.is_file() else REPOSITORY_ROOT / relative
    if not path.is_file():
        pytest.skip(f"{key} image not present locally; set {variable} to its path")
    digest = sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        pytest.skip(f"{key} image at {path} is not the pinned image (sha256 {digest})")
    return path


def opened(key: str) -> si.RomImage:
    return si.RomImage.open(image_path(key), IMAGES[key][2])


def manifest(name: str) -> si.Manifest:
    return si.load_manifest(MANIFESTS / name)


@pytest.mark.parametrize("name,donor_key", DONOR_MANIFESTS)
def test_one_frame_record_matches_the_canonical_reader(name: str, donor_key: str) -> None:
    document = manifest(name)
    entry = document.imports[0]
    family = document.donors[entry.donor].family
    adapter = opened(entry.donor)
    reference = canon.Rom(Path(image_path(entry.donor)).read_bytes())

    animation = entry.animations[0]
    frames = si.donor_frames(adapter, family, entry.definition, animation.slot, 0)
    assert frames, "the first carried slot resolves no frame"
    mine = frames[0]

    if family == "webfoot-animation":
        address = si.donor_slot_address(adapter, family, entry.definition, animation.slot, 0)
        cell = canon.read_animation(reference, address).cell_address(0, 0)
        theirs = canon.read_frame(reference, cell)
    else:
        address = si.donor_slot_address(adapter, family, entry.definition, animation.slot, 0)
        theirs = None
        assert mine.address == address
        reference_piece = si.read_piece(adapter, address)
        assert (mine.pieces[0].x, mine.pieces[0].y) == (reference_piece.x, reference_piece.y)
        assert (mine.pieces[0].width, mine.pieces[0].height) == (
            reference_piece.width,
            reference_piece.height,
        )
        assert mine.pieces[0].container == reference_piece.container

    if theirs is not None:
        assert (mine.min_x, mine.min_y) == (theirs.min_x, theirs.min_y)
        assert (mine.width, mine.height) == (theirs.width, theirs.height)
        assert len(mine.pieces) == theirs.piece_count
        pairs = zip(mine.pieces, theirs.pieces, strict=True)
        for mine_piece, their_piece in pairs:
            assert (mine_piece.x, mine_piece.y) == (their_piece.x, their_piece.y)
            assert (mine_piece.width, mine_piece.height) == (
                their_piece.dim_0,
                their_piece.dim_1,
            )
            assert mine_piece.attributes == their_piece.attributes
            assert mine_piece.container == their_piece.graphics_address


@pytest.mark.parametrize("name,donor_key", DONOR_MANIFESTS)
def test_one_tile_matches_an_independent_container_decode(name: str, donor_key: str) -> None:
    document = manifest(name)
    entry = document.imports[0]
    family = document.donors[entry.donor].family
    adapter = opened(entry.donor)
    reference = canon.Rom(Path(image_path(entry.donor)).read_bytes())

    animation = entry.animations[0]
    frame = si.donor_frames(adapter, family, entry.definition, animation.slot, 0)[0]
    piece, indices = si.frame_indices(adapter, frame)

    if family == "webfoot-animation":
        container = canon.read_graphic(
            reference,
            piece.container,
            piece.width,
            piece.height,
            piece.colour_256,
        )
        theirs = container.payload
    else:
        theirs = reference.container(piece.container).data

    assert theirs == indices
    tile = indices[: si.TILE_PIXELS]
    assert len(tile) == si.TILE_PIXELS
    assert sha256(tile).hexdigest() == sha256(theirs[: si.TILE_PIXELS]).hexdigest()

    frames = si.donor_frames(adapter, family, entry.definition, animation.slot, 0)
    assert len(frames) == len(si.donor_frames(adapter, family, entry.definition,
                                             animation.slot, 0))
    built = None
    for candidate in frames:
        piece_candidate, indices_candidate = si.frame_indices(adapter, candidate)
        distinct = sorted({value for value in indices_candidate if value})
        if len(distinct) <= si.MAX_BANK_SLOT:
            palette_map = {0: 0}
            palette_map.update(
                {value: slot + 1 for slot, value in enumerate(distinct)}
            )
            built = (candidate, piece_candidate, palette_map)
            break
    if built is None:
        with pytest.raises(si.SpriteImportError, match="four-bit slot"):
            si.build_frame_payload(
                adapter, frame, slot=animation.slot, direction=0, frame_index=0
            )
        return
    candidate, piece_candidate, palette_map = built
    payload = si.build_frame_payload(
        adapter,
        candidate,
        slot=animation.slot,
        direction=0,
        frame_index=0,
        palette_map=palette_map,
    )
    assert payload.cell.tiles == (
        piece_candidate.width * piece_candidate.height // si.TILE_PIXELS
    )
    assert len(payload.tiles) == piece_candidate.width * piece_candidate.height // 2


def test_the_log1_target_art_cells_match_the_published_decode() -> None:
    adapter = opened("legacy-of-goku")
    document = manifest("krillin-art46.json")
    entry = document.imports[0]
    art = si.read_log1_art(
        adapter, entry.target.art_table, entry.target.art_id, tuple(entry.target.states)
    )
    assert art.definition == entry.target.art_definition
    first = art.states[0][0]
    assert (first.x, first.y, first.width, first.height, first.tiles) == (0, -24, 16, 32, 8)
    assert art.states[0][3].horizontal_flip is True
    assert art.states[0][0].horizontal_flip is False


def test_every_shipped_manifest_reports_its_measured_figures() -> None:
    """The shipped manifests' verdicts are the ones the report quotes, re-measured here."""
    document = manifest("goku-base.json")
    entry = document.imports[0]
    report = si.validate_budget(
        {entry.donor: opened(entry.donor), entry.target.game: opened(entry.target.game)},
        document,
    )
    checks = {check.name: check for check in report.imports[0].checks}
    assert checks["tiles per frame"].measured == 16
    assert checks["oam entries per frame"].measured == 1
    assert checks["palette indices per bank"].measured == 33
    assert checks["target art slot"].verdict == si.VERDICT_FITS
    assert checks["target art states"].measured == 20
    assert checks["target art states"].limit.value == 14
    assert report.verdict == si.VERDICT_OVER


def test_a_wrong_digest_is_refused_before_a_byte_is_used() -> None:
    path = image_path("legacy-of-goku")
    with pytest.raises(si.SpriteImportError, match="pinned"):
        si.RomImage.open(path, "0" * 64)
