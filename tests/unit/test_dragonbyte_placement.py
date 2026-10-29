"""Headless placement model: capture, preview, place, undo, redo and save.

DRAGONBYTE-PLACEMENT-001. The fixture is built from the SDK's own types with the
values measured from the canonical image for map 33 BG0 (a 4 x 2 chunk grid):
the eight cell pointers and the map's 28-entry chunk vocabulary. The sharing
census is the SDK's own measurement, and the project is written by the SDK's own
project writer, so nothing here needs a ROM.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from tests.gates import REPOSITORY_ROOT
from tools.dragonbyte.placement import (
    CapturedBlock,
    CapturedFeature,
    Destination,
    PlacementError,
    PlacementModel,
)
from tools.webfoot import map_paint as mp
from tools.webfoot.formats import map_graphics as mg
from tools.webfoot.project import (
    PROJECT_FORMAT_VERSION,
    ProjectMeta,
    read_project,
    write_project,
)

MAP33_BG0_CELL_POINTERS = (
    136943392,
    136943888,
    136944368,
    136944852,
    136945336,
    136945556,
    136945796,
    136946024,
)

MAP33_VOCABULARY = (
    (136943392, None),
    (136943888, None),
    (136944368, None),
    (136944852, None),
    (136945336, None),
    (136945556, None),
    (136945796, None),
    (136946024, None),
    (136946244, 1),
    (136946516, 1),
    (136946840, 1),
    (136947172, 1),
    (136947496, 1),
    (136947624, 2),
    (136947960, 2),
    (136948264, 2),
    (136948568, 2),
    (136948904, 2),
    (136949256, 2),
    (136949580, 2),
    (136949904, 2),
    (136950316, 3),
    (136950388, 3),
    (136950428, 3),
    (136950480, 3),
    (136950508, 3),
    (136950536, 3),
    (136950560, 3),
)

META = ProjectMeta(
    format_version=PROJECT_FORMAT_VERSION,
    profile_id="synthetic_exact",
    game="synthetic",
    base_rom_sha256="0" * 64,
    base_rom_size=0x100,
    name="placement-model",
)


def _bg0() -> mp.PaintLayer:
    cells = tuple(
        mp.PaintCell(
            cell=index,
            column=index % 4,
            row=index // 4,
            pointer=pointer,
            offset=0,
        )
        for index, pointer in enumerate(MAP33_BG0_CELL_POINTERS)
    )
    vocabulary = tuple(
        mp.PaintChunk(
            ordinal=ordinal,
            pointer=pointer,
            cell_count=MAP33_BG0_CELL_POINTERS.count(pointer),
            source_slot=slot,
        )
        for ordinal, (pointer, slot) in enumerate(MAP33_VOCABULARY, start=1)
    )
    return mp.PaintLayer(
        slot=0,
        classification="dominant",
        handler=mg.DOMINANT_LAYER_HANDLER,
        columns=4,
        rows=2,
        cells=cells,
        vocabulary=vocabulary,
        read_only_reason="",
    )


def _target() -> mp.PaintTarget:
    bg0 = _bg0()
    shared = replace(bg0, slot=1)
    read_only = mp.PaintLayer(
        slot=2,
        classification="static_graphical_screenblock",
        handler=0,
        columns=0,
        rows=0,
        cells=(),
        vocabulary=(),
        read_only_reason="a screen-entry layer, not the dominant chunk grid",
    )
    return mp.PaintTarget(map_index=33, name="Snakeway", slots=(bg0, shared, read_only))


SHARING = {(33, 0): (33,), (33, 1): (33, 39), (33, 2): (33,)}


def _files(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    directory = tmp_path / "project"
    write_project(directory, META, enemies=[], characters=[])
    return directory


@pytest.fixture()
def model(project: Path) -> PlacementModel:
    return PlacementModel.open(project, _target(), 0, SHARING)


def _two_by_two(model: PlacementModel) -> CapturedFeature:
    return model.capture(0, columns=2, rows=2)


def _refused(model, project, action, *fragments):
    cells = dict(model.project.layout.cells())
    files = _files(project)
    history = model.history_depth
    with pytest.raises(PlacementError) as excinfo:
        action()
    message = str(excinfo.value)
    for fragment in fragments:
        assert fragment in message
    assert dict(model.project.layout.cells()) == cells
    assert _files(project) == files
    assert model.history_depth == history
    return message


def test_the_project_opens_on_the_measured_map_33_bg0_layer(project):
    files = _files(project)
    model = PlacementModel.open(project, _target(), 0, SHARING)

    assert model.layer.editable
    assert (model.layer.columns, model.layer.rows) == (4, 2)
    assert model.layer.cell_count == 8
    assert model.target.map_index == 33
    assert model.dirty is False
    assert model.history_depth == 0
    assert _files(project) == files


def test_opening_a_read_only_layer_is_refused(project):
    files = _files(project)
    with pytest.raises(PlacementError) as excinfo:
        PlacementModel.open(project, _target(), 2, SHARING)
    message = str(excinfo.value)
    assert "is not editable" in message
    assert "a screen-entry layer, not the dominant chunk grid" in message
    assert _files(project) == files


def test_open_accepts_the_projects_own_base_image_digest(project):
    files = _files(project)
    model = PlacementModel.open(
        project, _target(), 0, SHARING, expected_base_sha256=META.base_rom_sha256
    )
    assert model.dirty is False
    assert _files(project) == files


def test_open_refuses_a_different_base_image_digest(project):
    files = _files(project)
    foreign = "1" * 64
    with pytest.raises(PlacementError) as excinfo:
        PlacementModel.open(
            project, _target(), 0, SHARING, expected_base_sha256=foreign
        )
    message = str(excinfo.value)
    assert "base image mismatch" in message
    assert META.base_rom_sha256 in message
    assert foreign in message
    assert _files(project) == files


def test_a_two_by_two_capture_records_four_pointers_and_its_source(model):
    feature = _two_by_two(model)
    assert feature.block_count == 4
    assert feature.map_index == 33
    assert feature.layer_slot == 0
    assert feature.cell == 0
    assert (feature.columns, feature.rows) == (2, 2)
    assert [block.pointer for block in feature.blocks] == [
        MAP33_BG0_CELL_POINTERS[0],
        MAP33_BG0_CELL_POINTERS[1],
        MAP33_BG0_CELL_POINTERS[4],
        MAP33_BG0_CELL_POINTERS[5],
    ]
    assert [block.ordinal for block in feature.blocks] == [1, 2, 5, 6]
    assert model.capture(0).blocks == (CapturedBlock(ordinal=1, pointer=MAP33_BG0_CELL_POINTERS[0]),)


def test_a_preview_changes_neither_memory_nor_disk(model, project):
    before = _files(project)
    plan = model.preview(_two_by_two(model), Destination(33, 0, 2))

    assert plan.count == 4
    assert dict(model.project.layout.cells()) == {}
    assert model.history_depth == 0
    assert model.dirty is False
    assert _files(project) == before


def test_a_placement_changes_exactly_the_four_destination_cells(model, project):
    before = _files(project)
    feature = _two_by_two(model)
    plan = model.place(feature, Destination(33, 0, 2))

    assert plan.count == 4
    assert dict(model.project.layout.cells()) == {
        (33, 0, 2): 1,
        (33, 0, 3): 2,
        (33, 0, 6): 5,
        (33, 0, 7): 6,
    }
    assert model.history_depth == 1
    assert model.dirty is True
    assert _files(project) == before
    pointers = model.effective_pointers()
    assert [pointers[cell] for cell in (2, 3, 6, 7)] == [
        block.pointer for block in feature.blocks
    ]
    assert [pointers[cell] for cell in (0, 1, 4, 5)] == [
        MAP33_BG0_CELL_POINTERS[0],
        MAP33_BG0_CELL_POINTERS[1],
        MAP33_BG0_CELL_POINTERS[4],
        MAP33_BG0_CELL_POINTERS[5],
    ]
    assert set(model.project.layout.maps) == {"map:0033"}
    assert set(model.project.layout.maps["map:0033"]) == {0}


def test_undo_restores_the_previous_pointers_and_redo_reapplies_them(model, project):
    before = _files(project)
    canonical = model.effective_pointers()
    model.place(_two_by_two(model), Destination(33, 0, 2))
    assert model.effective_pointers() != canonical

    model.undo()

    assert dict(model.project.layout.cells()) == {}
    assert model.effective_pointers() == canonical
    assert model.history_depth == 0
    assert model.dirty is False
    assert _files(project) == before

    model.redo()

    assert model.history_depth == 1
    assert model.dirty is True
    assert model.effective_pointers() != canonical
    assert _files(project) == before


def test_save_writes_only_the_four_cells_and_reopen_reproduces_them(model, project):
    before = _files(project)
    feature = _two_by_two(model)
    model.place(feature, Destination(33, 0, 2))

    assert model.save() == 1
    assert model.dirty is False

    after = _files(project)
    assert set(after) - set(before) == {"maps/layout.toml"}
    assert {key for key in before if after.get(key) != before[key]} == set()
    reopened = PlacementModel.open(project, _target(), 0, SHARING)
    assert dict(reopened.project.layout.cells()) == {
        (33, 0, 2): 1,
        (33, 0, 3): 2,
        (33, 0, 6): 5,
        (33, 0, 7): 6,
    }
    assert reopened.dirty is False
    pointers = reopened.effective_pointers()
    assert [pointers[cell] for cell in (2, 3, 6, 7)] == [
        block.pointer for block in feature.blocks
    ]
    assert read_project(project).layout.cells() == reopened.project.layout.cells()


def test_save_counts_the_placements_that_differ_from_the_saved_document(model, project):
    model.place(_two_by_two(model), Destination(33, 0, 2))
    model.place(model.capture(2), Destination(33, 0, 0))

    assert model.save() == 2
    assert model.dirty is False

    first_document = _files(project)["maps/layout.toml"]
    model.undo()

    assert model.save() == 1
    assert model.dirty is False
    assert (33, 0, 0) not in read_project(project).layout.cells()
    second_document = _files(project)["maps/layout.toml"]
    assert second_document != first_document


def test_a_no_op_placement_adds_no_history_entry(model):
    destination = Destination(33, 0, 2)
    feature = _two_by_two(model)
    model.place(feature, destination)

    assert model.place(feature, destination).count == 0
    assert model.history_depth == 1


def test_a_drag_stroke_is_one_entry_and_one_undo_reverses_both_positions(model):
    feature = model.capture(0)
    model.begin_stroke()
    model.place(feature, Destination(33, 0, 2))
    model.place(feature, Destination(33, 0, 6))
    model.end_stroke()

    assert model.history_depth == 1
    assert dict(model.project.layout.cells()) == {(33, 0, 2): 1, (33, 0, 6): 1}

    model.undo()

    assert model.history_depth == 0
    assert dict(model.project.layout.cells()) == {}


def test_a_placement_running_past_the_edge_is_refused(model, project):
    _refused(
        model,
        project,
        lambda: model.place(_two_by_two(model), Destination(33, 0, 3)),
        "2 of 4 blocks do not fit inside BG0.",
    )


def test_a_read_only_layer_is_refused_with_the_sdk_reason(model, project):
    _refused(
        model,
        project,
        lambda: model.place(_two_by_two(model), Destination(33, 2, 0)),
        "is not editable",
        "a screen-entry layer, not the dominant chunk grid",
    )


def test_a_destination_on_another_map_is_refused(model, project):
    _refused(
        model,
        project,
        lambda: model.place(_two_by_two(model), Destination(39, 0, 2)),
        "captured on map 33",
        "placement stays within one map",
    )


def test_a_destination_on_a_shared_layer_record_is_refused(model, project):
    _refused(
        model,
        project,
        lambda: model.place(_two_by_two(model), Destination(33, 1, 2)),
        "layer record shared with map 39",
        "change all of them",
    )


def test_a_chunk_the_destination_layer_may_not_use_is_refused(model, project):
    feature = CapturedFeature(
        map_index=33,
        layer_slot=0,
        cell=0,
        columns=1,
        rows=1,
        blocks=(CapturedBlock(ordinal=1, pointer=1),),
    )
    _refused(
        model,
        project,
        lambda: model.place(feature, Destination(33, 0, 2)),
        "not one BG0 of map 33 already uses",
        "0x00000001",
    )


def test_undo_with_empty_history_is_refused(model, project):
    _refused(model, project, model.undo, "nothing to undo")


def test_redo_with_nothing_to_redo_is_refused(model, project):
    _refused(model, project, model.redo, "nothing to redo")


def test_the_model_imports_no_gui_toolkit():
    source = (REPOSITORY_ROOT / "tools/dragonbyte/placement.py").read_text(
        encoding="utf-8"
    )
    assert not re.search(
        r"^\s*(?:from|import)\s+(?:PySide6|PyQt5|PyQt6|tkinter)\b", source, re.MULTILINE
    )
    code = (
        "import sys\n"
        "import tools.dragonbyte.placement\n"
        "gui = ('PySide6', 'PyQt5', 'PyQt6', 'tkinter')\n"
        "print(','.join(sorted({name for name in sys.modules "
        "if name.split('.')[0] in gui})))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert completed.stdout.strip() == ""
