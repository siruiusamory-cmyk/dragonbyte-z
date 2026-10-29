"""ROM-gated placement model against map 33 BG0, and the measured sharing guard.

DRAGONBYTE-PLACEMENT-001. The canonical image is only read; the project lives in
pytest's temporary directory. Skips cleanly when no canonical image is present.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.rom_support import (
    CANONICAL_ROM_SHA256,
    assert_canonical_unchanged,
    canonical_rom_bytes,
)
from tools.dragonbyte.placement import (
    CapturedBlock,
    CapturedFeature,
    Destination,
    PlacementError,
    PlacementModel,
    layer_record_sharing,
)
from tools.webfoot.map_paint import MapPainter
from tools.webfoot.packaged import packaged_profile
from tools.webfoot.project import (
    PROJECT_FORMAT_VERSION,
    ProjectMeta,
    read_project,
    write_project,
)

MAP = 33
LAYER = 0
SHARED_MAP = 166
SHARED_WITH = (166, 178, 206)


@pytest.fixture(scope="module")
def image() -> bytes:
    return canonical_rom_bytes()


@pytest.fixture(scope="module")
def profile():
    return packaged_profile()


@pytest.fixture(scope="module")
def painter(image, profile) -> MapPainter:
    return MapPainter(image, profile=profile)


@pytest.fixture(scope="module")
def sharing(image, profile):
    return layer_record_sharing(image, profile=profile)


@pytest.fixture()
def project(tmp_path: Path, image, profile) -> Path:
    directory = tmp_path / "project"
    meta = ProjectMeta(
        format_version=PROJECT_FORMAT_VERSION,
        profile_id=profile.id,
        game=profile.game,
        base_rom_sha256=CANONICAL_ROM_SHA256,
        base_rom_size=len(image),
        name="placement-rom",
    )
    write_project(directory, meta, enemies=[], characters=[])
    return directory


def _files(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def test_a_two_by_two_capture_saves_and_reopens_on_map_33_bg0(
    project, painter, sharing
):
    target = painter.target(MAP)
    model = PlacementModel.open(project, target, LAYER, sharing)
    assert model.layer.editable
    assert (model.layer.columns, model.layer.rows) == (4, 2)
    assert model.layer.cell_count == 8

    feature = model.capture(0, columns=2, rows=2)
    assert [block.ordinal for block in feature.blocks] == [1, 2, 5, 6]
    source = [block.pointer for block in feature.blocks]
    canonical = [cell.pointer for cell in model.layer.cells]
    before = _files(project)

    assert model.preview(feature, Destination(MAP, LAYER, 2)).count == 4
    assert _files(project) == before

    assert model.place(feature, Destination(MAP, LAYER, 2)).count == 4
    assert _files(project) == before
    pointers = model.effective_pointers()
    assert [pointers[cell] for cell in (2, 3, 6, 7)] == source
    assert [pointers[cell] for cell in (0, 1, 4, 5)] == [
        canonical[0],
        canonical[1],
        canonical[4],
        canonical[5],
    ]

    model.undo()
    assert dict(model.project.layout.cells()) == {}
    assert _files(project) == before
    model.redo()

    assert model.save() == 1
    after = _files(project)
    assert set(after) - set(before) == {"maps/layout.toml"}
    assert {key for key in before if after[key] != before[key]} == set()
    assert dict(read_project(project).layout.cells()) == {
        (MAP, LAYER, 2): 1,
        (MAP, LAYER, 3): 2,
        (MAP, LAYER, 6): 5,
        (MAP, LAYER, 7): 6,
    }

    reopened = PlacementModel.open(project, target, LAYER, sharing)
    assert dict(reopened.project.layout.cells()) == {
        (MAP, LAYER, 2): 1,
        (MAP, LAYER, 3): 2,
        (MAP, LAYER, 6): 5,
        (MAP, LAYER, 7): 6,
    }
    assert reopened.effective_pointers() == pointers
    assert reopened.dirty is False
    assert_canonical_unchanged()


def _refused(model, project, action, *fragments):
    cells = dict(model.project.layout.cells())
    files = _files(project)
    with pytest.raises(PlacementError) as excinfo:
        action()
    message = str(excinfo.value)
    for fragment in fragments:
        assert fragment in message
    assert dict(model.project.layout.cells()) == cells
    assert _files(project) == files
    return message


def test_the_measured_shared_record_and_every_other_refusal_fail_closed(
    project, painter, sharing
):
    target = painter.target(MAP)
    model = PlacementModel.open(project, target, LAYER, sharing)
    shared_target = painter.target(SHARED_MAP)
    shared_model = PlacementModel.open(project, shared_target, 0, sharing)
    assert sharing[(SHARED_MAP, 0)] == SHARED_WITH

    _refused(
        shared_model,
        project,
        lambda: shared_model.place(
            shared_model.capture(0), Destination(SHARED_MAP, 0, 2)
        ),
        "layer record shared with map 178, 206",
    )
    _refused(
        model,
        project,
        lambda: model.place(model.capture(0, columns=2, rows=2), Destination(MAP, LAYER, 3)),
        "2 of 4 blocks do not fit inside BG0.",
    )
    _refused(
        model,
        project,
        lambda: model.place(model.capture(0), Destination(39, LAYER, 2)),
        "captured on map 33",
    )
    _refused(
        shared_model,
        project,
        lambda: shared_model.place(
            shared_model.capture(0), Destination(SHARED_MAP, 1, 0)
        ),
        "is not editable",
        "an empty slot holding no layer",
    )
    foreign = captured_from(shared_target, model.layer)
    _refused(
        model,
        project,
        lambda: model.place(foreign, Destination(MAP, LAYER, 2)),
        "not in the map's existing chunks",
    )
    _refused(model, project, model.undo, "nothing to undo")
    _refused(model, project, model.redo, "nothing to redo")
    assert_canonical_unchanged()


def captured_from(shared_target, destination_layer) -> CapturedFeature:
    """A one-block feature whose pointer the destination map does not use."""
    pointer = shared_target.layer(0).cells[0].pointer
    assert pointer not in {chunk.pointer for chunk in destination_layer.vocabulary}
    return CapturedFeature(
        map_index=MAP,
        layer_slot=LAYER,
        cell=0,
        columns=1,
        rows=1,
        blocks=(CapturedBlock(ordinal=1, pointer=pointer),),
    )
