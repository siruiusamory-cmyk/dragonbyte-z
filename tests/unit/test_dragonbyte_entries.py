"""Headless 8x8 screen-entry editing: capture, stamp, undo, redo and save.

DRAGONBYTE-FINE-001. The fixture is built from the SDK's own paint types with a
synthetic 4 x 2 chunk grid (map 33 BG0) and synthetic canonical chunk bodies, so
nothing here needs a ROM: the entry planes, the assembled ordinal count and the
missing-ordinal set are supplied as plain values.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.gates import REPOSITORY_ROOT
from tools.dragonbyte.entries import (
    EntryDestination,
    EntryModel,
    EntrySelection,
    EntrySources,
    EntryTemplate,
    entry_sources,
)
from tools.dragonbyte.placement import PlacementError
from tools.webfoot import map_paint as mp
from tools.webfoot.formats import map_graphics as mg
from tools.webfoot.project import (
    PROJECT_FORMAT_VERSION,
    AuthoredChunk,
    AuthoredChunkEntry,
    AuthoredChunks,
    LayoutEdits,
    ProjectMeta,
    read_project,
    write_project,
)

MAP = 33
SIDE = 32
ENTRIES = SIDE * SIDE
ASSEMBLED = 600
MISSING = frozenset({599})
COLUMNS = 4
ROWS = 2
WIDTH = COLUMNS * SIDE
HEIGHT = ROWS * SIDE

META = ProjectMeta(
    format_version=PROJECT_FORMAT_VERSION,
    profile_id="synthetic_exact",
    game="synthetic",
    base_rom_sha256="0" * 64,
    base_rom_size=0x100,
    name="entry-model",
)

SHARING = {(MAP, 0): (MAP,), (MAP, 1): (MAP, 39), (MAP, 2): (MAP,)}


def _body(layer: int, cell: int) -> tuple[int, ...]:
    return tuple(
        (index * 7 + cell * 13 + layer * 29) % (ASSEMBLED - 1)
        | (mg.TILE_ENTRY_BIT_10 if index % 11 == 0 else 0)
        for index in range(ENTRIES)
    )


def _sources() -> EntrySources:
    bodies = {
        (MAP, layer, cell): EntryTemplate(
            template=f"map:{MAP:04d}/layer:{layer}/chunk:{cell + 1}",
            body=_body(layer, cell),
        )
        for layer in (0, 1)
        for cell in range(COLUMNS * ROWS)
    }
    return EntrySources(bodies=bodies, assembled={MAP: ASSEMBLED}, missing={MAP: MISSING})


def _layer(slot: int) -> mp.PaintLayer:
    cells = tuple(
        mp.PaintCell(
            cell=index,
            column=index % COLUMNS,
            row=index // COLUMNS,
            pointer=0x1000 + slot * 0x100 + index,
            offset=0,
        )
        for index in range(COLUMNS * ROWS)
    )
    vocabulary = tuple(
        mp.PaintChunk(
            ordinal=index + 1,
            pointer=cell.pointer,
            cell_count=1,
            source_slot=None,
        )
        for index, cell in enumerate(cells)
    )
    return mp.PaintLayer(
        slot=slot,
        classification="dominant",
        handler=mg.DOMINANT_LAYER_HANDLER,
        columns=COLUMNS,
        rows=ROWS,
        cells=cells,
        vocabulary=vocabulary,
        read_only_reason="",
    )


def _target() -> mp.PaintTarget:
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
    return mp.PaintTarget(map_index=MAP, name="Synthetic", slots=(_layer(0), _layer(1), read_only))


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
def model(project: Path) -> EntryModel:
    return EntryModel.open(project, _target(), 0, SHARING, _sources())


def _open(project: Path, layer_slot: int = 0, sources: EntrySources | None = None) -> EntryModel:
    return EntryModel.open(
        project, _target(), layer_slot, SHARING, sources if sources is not None else _sources()
    )


def _plane(model: EntryModel) -> tuple[int, ...]:
    return model.capture_entries(0, 0, WIDTH, HEIGHT).entries


def _expected(plane: tuple[int, ...], selection: EntrySelection, destination: EntryDestination) -> tuple[int, ...]:
    out = list(plane)
    for row in range(selection.rows):
        for column in range(selection.columns):
            out[(destination.y + row) * WIDTH + destination.x + column] = selection.entries[
                row * selection.columns + column
            ]
    return tuple(out)


def _refused(model: EntryModel, project: Path, action, *fragments):
    cells = dict(model.project.layout.cells())
    chunks = dict(model.project.chunks.chunks)
    files = _files(project)
    history = model.history_depth
    with pytest.raises(PlacementError) as excinfo:
        action()
    message = str(excinfo.value)
    for fragment in fragments:
        assert fragment in message
    assert dict(model.project.layout.cells()) == cells
    assert dict(model.project.chunks.chunks) == chunks
    assert _files(project) == files
    assert model.history_depth == history
    return message


def test_a_single_entry_placement_changes_exactly_one_8x8_tile(model):
    before = _plane(model)
    selection = model.capture_entries(0, 0, 1, 1)
    plan = model.place_entries(selection, EntryDestination(MAP, 0, 1, 1))

    assert plan.entries_changed == 1
    assert plan.cells == (0,)
    assert _plane(model) == _expected(before, selection, EntryDestination(MAP, 0, 1, 1))
    assert model.history_depth == 1


def test_a_rectangle_is_stamped_and_every_other_entry_is_carried_verbatim(model):
    before = _plane(model)
    selection = model.capture_entries(4, 4, 8, 8)
    destination = EntryDestination(MAP, 0, 12, 20)
    plan = model.place_entries(selection, destination)

    assert plan.cells == (0,)
    assert len(plan.chunks) == 1
    assert plan.entries_changed == sum(
        1
        for index in range(selection.count)
        if selection.entries[index]
        != before[(destination.y + index // 8) * WIDTH + destination.x + index % 8]
    )
    assert _plane(model) == _expected(before, selection, destination)


def test_a_placement_crossing_a_chunk_boundary_authors_one_body_per_cell(model):
    before = _plane(model)
    selection = model.capture_entries(28, 28, 8, 8)
    destination = EntryDestination(MAP, 0, 36, 28)
    plan = model.place_entries(selection, destination)

    assert plan.cells == (1, 5)
    assert len(plan.chunks) == 2
    assert set(model.project.layout.cells()) == {(MAP, 0, 1), (MAP, 0, 5)}
    assert set(model.project.layout.cells().values()) == set(plan.chunks)
    assert _plane(model) == _expected(before, selection, destination)


def test_a_capture_of_an_edited_area_returns_what_was_placed(model):
    selection = model.capture_entries(28, 28, 8, 8)
    destination = EntryDestination(MAP, 0, 36, 28)
    model.place_entries(selection, destination)

    captured = model.capture_entries(36, 28, 8, 8)

    assert captured.entries == selection.entries
    assert (captured.map_index, captured.layer_slot) == (MAP, 0)


def test_undo_and_redo_restore_exact_entries_across_a_chunk_boundary(model, project):
    before = _plane(model)
    files = _files(project)
    selection = model.capture_entries(28, 28, 8, 8)
    destination = EntryDestination(MAP, 0, 36, 28)
    model.place_entries(selection, destination)
    placed = _plane(model)
    assert placed != before

    model.undo()

    assert _plane(model) == before
    assert dict(model.project.layout.cells()) == {}
    assert dict(model.project.chunks.chunks) == {}
    assert model.history_depth == 0
    assert model.dirty is False
    assert _files(project) == files

    model.redo()

    assert _plane(model) == placed
    assert model.history_depth == 1
    assert model.dirty is True
    assert _files(project) == files


def test_unchanged_neighbours_cells_and_layers_keep_their_entries(model, project):
    before = _plane(model)
    sibling = _plane(_open(project, 1))
    selection = model.capture_entries(28, 28, 8, 8)
    destination = EntryDestination(MAP, 0, 36, 28)
    model.place_entries(selection, destination)

    after = _plane(model)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            inside = destination.x <= x < destination.x + 8 and destination.y <= y < destination.y + 8
            if not inside:
                assert after[y * WIDTH + x] == before[y * WIDTH + x]
    assert {key[1] for key in model.project.layout.cells()} == {0}
    assert set(model.project.chunks.chunks) <= set(
        value for value in model.project.layout.cells().values() if isinstance(value, str)
    )

    model.save()

    assert _plane(_open(project, 1)) == sibling
    assert _plane(_open(project, 0)) == after


def test_flip_bits_are_carried_verbatim(model):
    selection = model.capture_entries(28, 28, 8, 8)
    assert any(entry & mg.TILE_ENTRY_BIT_10 for entry in selection.entries)
    destination = EntryDestination(MAP, 0, 4, 4)
    model.place_entries(selection, destination)

    placed = model.capture_entries(4, 4, 8, 8).entries

    for source, stored in zip(selection.entries, placed):
        assert stored & (mg.TILE_ENTRY_BIT_10 | mg.TILE_ENTRY_BIT_11) == source & (
            mg.TILE_ENTRY_BIT_10 | mg.TILE_ENTRY_BIT_11
        )


def test_a_capture_outside_the_plane_is_refused(model, project):
    _refused(model, project, lambda: model.capture_entries(WIDTH - 4, 0, 8, 8), "outside BG0's")


def test_a_destination_outside_the_plane_is_refused(model, project):
    _refused(
        model,
        project,
        lambda: model.place_entries(
            model.capture_entries(0, 0, 8, 8), EntryDestination(MAP, 0, WIDTH - 4, 0)
        ),
        "runs past BG0's",
    )


def test_an_ordinal_past_the_assembled_block_is_refused(model, project):
    selection = EntrySelection(MAP, 0, 0, 0, 1, 1, (ASSEMBLED,))
    _refused(
        model,
        project,
        lambda: model.place_entries(selection, EntryDestination(MAP, 0, 0, 0)),
        "assembled character block of 600 ordinals",
    )


def test_an_ordinal_with_no_source_tile_is_refused(model, project):
    selection = EntrySelection(MAP, 0, 0, 0, 1, 1, (599,))
    _refused(
        model,
        project,
        lambda: model.place_entries(selection, EntryDestination(MAP, 0, 0, 0)),
        "assembles with no source tile",
    )


def test_an_entry_with_palette_bits_is_refused(model, project):
    selection = EntrySelection(MAP, 0, 0, 0, 1, 1, (0x1005,))
    _refused(
        model,
        project,
        lambda: model.place_entries(selection, EntryDestination(MAP, 0, 0, 0)),
        "palette bank 1",
        "unverified",
    )


def test_a_destination_on_a_shared_layer_record_is_refused(project):
    shared = _open(project, 1)
    _refused(
        shared,
        project,
        lambda: shared.place_entries(
            shared.capture_entries(0, 0, 1, 1), EntryDestination(MAP, 1, 2, 0)
        ),
        "layer record shared with map 39",
    )


def test_a_non_editable_layer_is_refused(model, project):
    selection = EntrySelection(MAP, 2, 0, 0, 1, 1, (1,))
    _refused(
        model,
        project,
        lambda: model.place_entries(selection, EntryDestination(MAP, 2, 0, 0)),
        "is not editable",
        "a screen-entry layer, not the dominant chunk grid",
    )


def test_a_destination_on_another_map_or_layer_is_refused(model, project):
    selection = model.capture_entries(0, 0, 1, 1)
    _refused(
        model,
        project,
        lambda: model.place_entries(selection, EntryDestination(39, 0, 0, 0)),
        "captured on map 33",
        "stays within one map",
    )
    _refused(
        model,
        project,
        lambda: model.place_entries(selection, EntryDestination(MAP, 1, 0, 0)),
        "captured on BG0",
        "stays on the layer it came from",
    )


def test_an_unresolvable_authored_value_is_refused(tmp_path):
    directory = tmp_path / "unresolvable"
    write_project(
        directory,
        META,
        enemies=[],
        characters=[],
        layout=LayoutEdits(maps={f"map:{MAP:04d}": {0: {0: "chunk:bad"}}}),
        chunks=AuthoredChunks(
            chunks={
                "chunk:bad": AuthoredChunk(
                    identity="chunk:bad",
                    template=f"map:{MAP:04d}/layer:0/chunk:99",
                    entries=(AuthoredChunkEntry(row=0, column=0, prior=0, entry=1),),
                )
            }
        ),
    )
    model = _open(directory)

    _refused(
        model,
        directory,
        lambda: model.capture_entries(0, 0, 1, 1),
        "not a canonical chunk",
    )


def test_a_no_op_placement_reports_nothing_and_adds_no_history_entry(model):
    selection = model.capture_entries(4, 4, 8, 8)
    destination = EntryDestination(MAP, 0, 4, 4)

    plan = model.place_entries(selection, destination)

    assert plan.entries_changed == 0
    assert plan.cells == ()
    assert plan.chunks == ()
    assert model.history_depth == 0
    assert dict(model.project.layout.cells()) == {}


def test_save_writes_both_documents_and_reopen_reproduces_every_entry(model, project):
    before = _files(project)
    before_plane = _plane(model)
    selection = model.capture_entries(28, 28, 8, 8)
    destination = EntryDestination(MAP, 0, 36, 28)
    model.place_entries(selection, destination)
    placed = _plane(model)

    assert model.save() == 1
    assert model.dirty is False

    after = _files(project)
    assert set(after) - set(before) == {"maps/layout.toml", "maps/chunks.toml"}
    assert {key for key in before if after.get(key) != before[key]} == set()
    reopened = _open(project)
    assert _plane(reopened) == placed
    assert _plane(reopened) != before_plane
    assert dict(read_project(project).layout.cells()) == dict(model.project.layout.cells())
    assert dict(read_project(project).chunks.chunks) == dict(model.project.chunks.chunks)


def test_two_independent_runs_produce_byte_identical_documents(tmp_path):
    documents = []
    for name in ("first", "second"):
        directory = tmp_path / name
        write_project(directory, META, enemies=[], characters=[])
        model = _open(directory)
        model.place_entries(
            model.capture_entries(28, 28, 8, 8), EntryDestination(MAP, 0, 36, 28)
        )
        model.save()
        documents.append(_files(directory))
    assert documents[0] == documents[1]


def test_each_authored_chunk_records_its_template_and_its_edits(model):
    selection = model.capture_entries(28, 28, 8, 8)
    destination = EntryDestination(MAP, 0, 36, 28)
    plan = model.place_entries(selection, destination)

    for identity, cell in zip(plan.chunks, plan.cells):
        chunk = model.project.chunks.get(identity)
        assert chunk is not None
        assert chunk.identity.startswith(f"chunk:e{MAP:04d}-0-{cell}-")
        assert chunk.template == f"map:{MAP:04d}/layer:0/chunk:{cell + 1}"
        assert chunk.entries
        for edit in chunk.entries:
            assert edit.entry == _plane(model)[
                ((cell // COLUMNS) * SIDE + edit.row) * WIDTH
                + (cell % COLUMNS) * SIDE
                + edit.column
            ]
            assert edit.entry != edit.prior


def test_the_entry_model_imports_no_gui_toolkit():
    source = (REPOSITORY_ROOT / "tools/dragonbyte/entries.py").read_text(encoding="utf-8")
    assert not re.search(
        r"^\s*(?:from|import)\s+(?:PySide6|PyQt5|PyQt6|tkinter)\b", source, re.MULTILINE
    )
    code = (
        "import sys\n"
        "import tools.dragonbyte.entries\n"
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
