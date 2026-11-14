"""The Enemies tab driven through its own widgets with no display.

A ROM is needed to open a project, so these skip cleanly when the canonical
image is absent, the way the application's other offscreen tests do.
"""

from __future__ import annotations

import os

import pytest

from tests.rom_support import canonical_rom_path, mutable_rom_copy
from tools.webfoot import enemy_types, map_objects as mo

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

pytestmark = pytest.mark.skipif(
    canonical_rom_path() is None, reason="the canonical Buu's Fury ROM is not present"
)

DONOR = "enemy:434"


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def page(app, tmp_path):
    from tools.creator.model.project import CreatorProject
    from tools.creator.ui.enemy_editor import EnemyEditor

    rom = mutable_rom_copy(tmp_path)
    project = CreatorProject.create(rom, tmp_path / "Game", "Game")
    editor = EnemyEditor()
    editor.set_project(project.directory, rom)
    editor.pick_donor = lambda _rows: DONOR
    editor.pick_name = lambda _title, _text: "Cave Wolf"
    return editor, project


def _texts(editor) -> list[str]:
    found: list[str] = []
    for widget in editor.findChildren(QtWidgets.QWidget):
        text = getattr(widget, "text", None)
        if callable(text):
            try:
                found.append(text())
            except TypeError:
                continue
    for listing in (editor.game_list, editor.list):
        found += [listing.item(row).text() for row in range(listing.count())]
    found += [editor.look.itemText(row) for row in range(editor.look.count())]
    return [text for text in found if text]


def _row_of(editor) -> tuple[int, int]:
    entry = enemy_types.read_types(
        editor.studio.directory, editor.studio.profile,
        editor.studio.image).entries["enemy:cave-wolf"]
    return entry.row, entry.donor


def test_enemies_page_builds_both_groups(page):
    editor, _project = page
    assert editor.game_list.count() == 125
    assert editor.list.count() == 0
    assert editor.pool.text() == "Your enemies (0 of 16)"
    assert "Game enemies" in editor.game_header.text()
    editor.new_enemy()
    assert (editor.list.count(), editor.key) == (1, "enemy:cave-wolf")
    assert editor.pool.text() == "Your enemies (1 of 16)"


def test_enemies_page_creates_edits_and_reads_back(page):
    editor, project = page
    editor.new_enemy()
    editor._inputs["hp"].setValue(900)
    editor._inputs["experience"].setValue(500)
    assert editor.apply()
    document = (project.directory / enemy_types.TYPES_FILE).read_text(encoding="utf-8")
    assert "hp = 900" in document and "experience = 500" in document
    row = editor.studio.project()[0]
    assert (row.name, row.hp, row.experience, row.donor) == (
        "cave-wolf", 900, 500, DONOR)
    assert editor.look.currentData() == 209
    assert editor.look.currentText() == "sprite:0209"
    assert editor.problem.text() == ""


def test_enemies_page_refusals_are_shown(page):
    editor, project = page
    for index in range(16):
        editor.studio.create(DONOR, f"spare-{index}")
    editor.refresh()
    editor.new_enemy()
    assert "All 16 rows the base game never names are taken." in editor.problem.text()
    assert editor.list.count() == 16
    mo.place_enemy(project.directory, "map:0033", "ghoul", "enemy:spare-0", 176, 152)
    editor.refresh()
    editor.select("enemy:spare-0")
    editor.delete()
    assert "is named by maps/objects.toml" in editor.problem.text()
    assert editor.list.count() == 16


def test_enemies_page_note_about_appearance_panel(page):
    editor, _project = page
    assert "does not appear in the game's appearance panel" in editor.note.text()


def test_enemies_page_reports_a_damaged_type_document(page):
    editor, project = page
    path = project.directory / enemy_types.TYPES_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('[type."enemy:ghost"]\nrow = 3\ndonor = 86\nraw = "00"\n', encoding="utf-8")
    editor.refresh()
    assert "not one of the 16 rows the base game never names" in editor.problem.text()
    assert editor.list.count() == 0


def test_enemies_page_has_no_address_text(page):
    editor, _project = page
    editor.new_enemy()
    row, donor = _row_of(editor)
    texts = _texts(editor)
    assert [text for text in texts if "0x" in text.lower()] == []
    assert [text for text in texts if "row" in text.lower()] == []
    assert editor.key == "enemy:cave-wolf"
    assert editor.title.text() == "cave-wolf"
    assert editor.name.text() == "cave-wolf"
    assert editor.based_on.text() == DONOR
    assert f"enemy:{row}" not in texts
    assert f"enemy:{donor}" not in texts
    assert DONOR in texts
