"""ROM-gated 8x8 screen-entry editing: fixtures, ordinal bounds, sharing, save.

DRAGONBYTE-FINE-001. The canonical image is only read; every read goes through a
private copy in the pytest temporary directory, and the canonical image's digest
is verified before and after the module. Skips cleanly without the image.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from tests.rom_support import (
    CANONICAL_ROM_SHA256,
    assert_canonical_unchanged,
    canonical_rom_path,
    mutable_rom_copy,
)
from tools.dragonbyte.entries import (
    EntryDestination,
    EntryModel,
    EntrySelection,
    entry_sources,
)
from tools.dragonbyte.placement import PlacementError, layer_record_sharing
from tools.webfoot import map_chunk
from tools.webfoot.formats import map_graphics as mg
from tools.webfoot.map_paint import MapPainter
from tools.webfoot.packaged import packaged_profile
from tools.webfoot.project import (
    PROJECT_FORMAT_VERSION,
    ProjectMeta,
    write_project,
)

MAP33 = 33
MAP40 = 40
MAP_SHARED = 166
SIDE = mg.CHUNK_SIDE_TILES

FIXTURES = (
    (MAP33, 0, (4, 4), (12, 20), 18),
    (MAP33, 0, (28, 28), (36, 28), 60),
    (MAP40, 1, (4, 4), (12, 20), 37),
    (MAP40, 1, (28, 28), (36, 28), 53),
)


@pytest.fixture(scope="module")
def image(tmp_path_factory) -> bytes:
    canonical = canonical_rom_path()
    if canonical is None:
        pytest.skip("canonical Buu's Fury ROM not present locally")
    before = sha256(canonical.read_bytes()).hexdigest()
    if before != CANONICAL_ROM_SHA256:
        pytest.skip(
            "local ROM is not the canonical profile these offsets target "
            f"(sha256 {before})"
        )
    data = mutable_rom_copy(tmp_path_factory.mktemp("rom")).read_bytes()
    assert sha256(data).hexdigest() == CANONICAL_ROM_SHA256
    return data


@pytest.fixture(scope="module", autouse=True)
def _canonical_digest_holds(image):
    assert_canonical_unchanged()
    yield
    assert_canonical_unchanged()


@pytest.fixture(scope="module")
def profile():
    return packaged_profile()


@pytest.fixture(scope="module")
def painter(image, profile) -> MapPainter:
    return MapPainter(image, profile=profile)


@pytest.fixture(scope="module")
def sharing(image, profile):
    return layer_record_sharing(image, profile=profile)


@pytest.fixture(scope="module")
def sources(image, profile):
    cache: dict[int, object] = {}

    def load(map_index: int):
        if map_index not in cache:
            cache[map_index] = entry_sources(image, map_index, profile=profile)
        return cache[map_index]

    return load


@pytest.fixture()
def project(tmp_path: Path, image, profile) -> Path:
    directory = tmp_path / "project"
    meta = ProjectMeta(
        format_version=PROJECT_FORMAT_VERSION,
        profile_id=profile.id,
        game=profile.game,
        base_rom_sha256=CANONICAL_ROM_SHA256,
        base_rom_size=len(image),
        name="entry-rom",
    )
    write_project(directory, meta, enemies=[], characters=[])
    return directory


def _open(project: Path, map_index: int, layer_slot: int, painter, sharing, sources):
    return EntryModel.open(
        project,
        painter.target(map_index),
        layer_slot,
        sharing,
        sources(map_index),
        expected_base_sha256=CANONICAL_ROM_SHA256,
    )


def _files(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def _plane(model: EntryModel) -> tuple[int, ...]:
    layer = model.layer
    return model.capture_entries(0, 0, layer.columns * SIDE, layer.rows * SIDE).entries


def _overlay(plane, selection, destination, width):
    out = list(plane)
    for row in range(selection.rows):
        for column in range(selection.columns):
            out[(destination.y + row) * width + destination.x + column] = selection.entries[
                row * selection.columns + column
            ]
    return tuple(out)


@pytest.mark.parametrize("map_index, layer_slot, source, destination, changed", FIXTURES)
def test_the_measured_fixture_rectangles_place_and_undo(
    project, painter, sharing, sources, map_index, layer_slot, source, destination, changed
):
    model = _open(project, map_index, layer_slot, painter, sharing, sources)
    width = model.layer.columns * SIDE
    before = _plane(model)
    selection = model.capture_entries(source[0], source[1], 8, 8)
    target = EntryDestination(map_index, layer_slot, destination[0], destination[1])

    plan = model.place_entries(selection, target)

    assert plan.entries_changed == changed
    assert _plane(model) == _overlay(before, selection, target, width)

    model.undo()

    assert _plane(model) == before
    assert dict(model.project.layout.cells()) == {}
    assert dict(model.project.chunks.chunks) == {}
    assert_canonical_unchanged()


def test_a_referenced_but_not_displayed_ordinal_is_accepted(
    project, painter, sharing, sources, image, profile
):
    model = _open(project, MAP40, 1, painter, sharing, sources)
    displayed = set(map_chunk.ChunkAuthor(image, profile=profile).vocabulary(MAP40, 1))
    usable = model.entry_vocabulary()
    ordinal = min(usable - displayed)

    plan = model.place_entries(
        EntrySelection(MAP40, 1, 0, 0, 1, 1, (ordinal,)),
        EntryDestination(MAP40, 1, 12, 20),
    )

    assert plan.entries_changed == 1
    assert model.capture_entries(12, 20, 1, 1).entries == (ordinal,)
    assert ordinal not in displayed
    assert_canonical_unchanged()


def test_an_ordinal_with_no_source_tile_is_refused(project, painter, sharing, sources, image, profile):
    model = _open(project, MAP40, 1, painter, sharing, sources)
    reader = mg.MapGraphicsReader(image, profile)
    root = mg.read_map_entries(reader)[MAP40].root_address
    first = mg.assemble_map_char_block(reader, root)[0]
    block = mg.assemble_map_char_block(
        reader, root, require_referenced=tuple(range(first.tile_count))
    )[0]
    missing = block.missing_tile_indices[0]
    files = _files(project)
    history = model.history_depth

    with pytest.raises(PlacementError) as excinfo:
        model.place_entries(
            EntrySelection(MAP40, 1, 0, 0, 1, 1, (missing,)),
            EntryDestination(MAP40, 1, 0, 0),
        )

    assert "no source tile" in str(excinfo.value)
    assert _files(project) == files
    assert model.history_depth == history
    assert dict(model.project.layout.cells()) == {}
    assert_canonical_unchanged()


def test_an_ordinal_past_the_assembled_block_is_refused(project, painter, sharing, sources):
    model = _open(project, MAP33, 0, painter, sharing, sources)
    files = _files(project)

    with pytest.raises(PlacementError) as excinfo:
        model.place_entries(
            EntrySelection(MAP33, 0, 0, 0, 1, 1, (587,)),
            EntryDestination(MAP33, 0, 0, 0),
        )

    assert "assembled character block of 587 ordinals" in str(excinfo.value)
    assert _files(project) == files
    assert model.history_depth == 0
    assert_canonical_unchanged()


def test_the_measured_shared_layer_record_is_refused(project, painter, sharing, sources):
    assert sharing[(MAP_SHARED, 0)] == (MAP_SHARED, 178, 206)
    model = _open(project, MAP_SHARED, 0, painter, sharing, sources)
    selection = model.capture_entries(0, 0, 1, 1)
    files = _files(project)

    with pytest.raises(PlacementError) as excinfo:
        model.place_entries(selection, EntryDestination(MAP_SHARED, 0, 2, 0))

    assert "layer record shared with map 178, 206" in str(excinfo.value)
    assert _files(project) == files
    assert model.history_depth == 0
    assert_canonical_unchanged()


@pytest.mark.parametrize("map_index, layer_slot", ((MAP33, 0), (MAP40, 1)))
def test_save_reopen_keeps_every_entry_and_every_other_layer(
    project, painter, sharing, sources, map_index, layer_slot
):
    model = _open(project, map_index, layer_slot, painter, sharing, sources)
    width = model.layer.columns * SIDE
    before = _plane(model)
    target_map = painter.target(map_index)
    others = {
        slot: _plane(_open(project, map_index, slot, painter, sharing, sources))
        for slot in range(len(target_map.slots))
        if slot != layer_slot and target_map.layer(slot).editable
    }
    selection = model.capture_entries(28, 28, 8, 8)
    target = EntryDestination(map_index, layer_slot, 36, 28)
    model.place_entries(selection, target)
    expected = _overlay(before, selection, target, width)

    assert model.save() == 1
    assert model.dirty is False

    reopened = _open(project, map_index, layer_slot, painter, sharing, sources)
    assert _plane(reopened) == expected
    assert dict(reopened.project.layout.cells()) == dict(model.project.layout.cells())
    assert dict(reopened.project.chunks.chunks) == dict(model.project.chunks.chunks)
    for slot, plane in others.items():
        assert _plane(_open(project, map_index, slot, painter, sharing, sources)) == plane
    assert_canonical_unchanged()
