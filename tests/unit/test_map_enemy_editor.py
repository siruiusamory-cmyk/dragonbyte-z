"""The Maps editor's enemy tool driven through its own widgets with no display.

A ROM is needed to open a project, so these skip cleanly when the canonical image
is absent, the way the application's other offscreen tests do.
"""

from __future__ import annotations

import os

import pytest

from tests.rom_support import canonical_rom_path, mutable_rom_copy
from tools.webfoot import enemy_types
from tools.webfoot import map_objects as mo
from tools.webfoot import story_flags as sf

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
QtCore = pytest.importorskip("PySide6.QtCore")

KEY = QtCore.Qt.ItemDataRole.UserRole

pytestmark = pytest.mark.skipif(
    canonical_rom_path() is None, reason="the canonical Buu's Fury ROM is not present"
)

DONOR = "enemy:434"
MAP = "map:0033"
CROWDED = "map:0134"
RETAIL_MAP = "map:0040"


@pytest.fixture(scope="module")
def rom(tmp_path_factory):
    return mutable_rom_copy(tmp_path_factory.mktemp("base"))


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def page(app, rom, tmp_path):
    from tools.creator.model.enemies import EnemyStudio
    from tools.creator.model.project import CreatorProject
    from tools.creator.ui.map_editor import MapEditor

    project = CreatorProject.create(rom, tmp_path / "Game", "Game")
    types = EnemyStudio(project.directory, rom)
    types.create(DONOR, "ghoul")
    sf.write_flags(project.directory, sf.assign(sf.Flags(), "met_ghoul", types.profile))
    editor = MapEditor()
    editor.set_project(project.directory, rom)
    editor.studio.enemy_types = types
    editor.select_map(MAP)
    editor.set_tool("enemies")
    return editor, project


def _choice(editor, key: str) -> int:
    return next(row for row in range(editor.enemy_choice_list.count())
                if editor.enemy_choice_list.item(row).data(KEY) == key)


def _place(editor, key: str, x: int, y: int) -> None:
    editor.enemy_choice_list.setCurrentRow(_choice(editor, key))
    editor.down(x, y)
    editor.up(x, y)


def _texts(editor) -> list[str]:
    found: list[str] = []
    for widget in editor.findChildren(QtWidgets.QWidget):
        text = getattr(widget, "text", None)
        if callable(text):
            try:
                found.append(text())
            except TypeError:
                continue
    for listing in (editor.enemy_list, editor.enemy_choice_list):
        found += [listing.item(row).text() for row in range(listing.count())]
    found += [editor.enemy_appears.itemText(row)
              for row in range(editor.enemy_appears.count())]
    return [text for text in found if text]


def test_map_editor_add_enemy_tool_places_and_reads_back(page):
    editor, project = page
    assert editor.enemy_choice_list.count() > 0
    _place(editor, "enemy:ghoul", 176, 152)
    assert [(item.key, item.name, item.x, item.y) for item in editor.map_enemies] == [
        ("made:enemy-1", "ghoul", 176, 152)]
    made = mo.read_document(project.directory)[MAP].made["enemy-1"]
    assert (made.type, made.x, made.y) == ("enemy:ghoul", 176, 152)
    assert editor.enemy_list.count() == 1 and editor.chosen_enemy == "made:enemy-1"
    assert editor.enemy_type.text() == "Type: ghoul"
    assert editor.hint.text() == "Added. Drag it where it belongs."


def test_map_editor_enemy_properties_edit_position_and_appears(page):
    editor, project = page
    _place(editor, "enemy:ghoul", 176, 152)
    editor.enemy_list.setCurrentRow(0)
    assert (editor.enemy_x.value(), editor.enemy_y.value()) == (176, 152)
    editor.enemy_x.setValue(200)
    editor.enemy_y.setValue(160)
    editor.enemy_x.editingFinished.emit()
    assert [(item.x, item.y) for item in editor.map_enemies] == [(200, 160)]
    editor.enemy_appears.setCurrentIndex(editor.enemy_appears.findData("met_ghoul"))
    made = mo.read_document(project.directory)[MAP].made["enemy-1"]
    assert (made.x, made.y, made.appears) == (200, 160, "met_ghoul")
    editor.enemy_appears.setCurrentIndex(editor.enemy_appears.findData("always"))
    assert mo.read_document(project.directory)[MAP].made["enemy-1"].appears == "always"


def test_map_editor_enemy_duplicate_and_remove(page):
    editor, project = page
    _place(editor, "enemy:ghoul", 176, 152)
    editor.duplicate_enemy()
    keys = [item.key for item in editor.map_enemies]
    assert keys == ["made:enemy-1", "made:enemy-2"] and editor.chosen_enemy == keys[1]
    assert sorted(mo.read_document(project.directory)[MAP].made) == ["enemy-1", "enemy-2"]
    editor.remove_enemy()
    assert [item.key for item in editor.map_enemies] == ["made:enemy-1"]
    editor.enemy_list.setCurrentRow(0)
    editor.remove_enemy()
    assert editor.map_enemies == [] and not (project.directory / mo.OBJECTS_FILE).is_file()


def test_map_editor_retail_enemy_shows_read_only_note(page):
    editor, _project = page
    editor.select_map(RETAIL_MAP)
    assert [item.key for item in editor.map_enemies] == ["game:1", "game:3"]
    editor.enemy_list.setCurrentRow(0)
    assert editor.enemy_type.text() == f"Type: {DONOR}"
    assert editor.enemy_note.text() == (
        "This enemy comes from the game and can be looked at, not changed.")
    assert not editor.enemy_x.isEnabled() and not editor.enemy_appears.isEnabled()
    editor.remove_enemy()
    assert "a retail placement cannot be moved" in editor.hint.text()
    assert [item.key for item in editor.map_enemies] == ["game:1", "game:3"]


def test_map_editor_enemy_count_status_wording(page):
    editor, _project = page
    assert "objects the map builds: 12 of 23" in editor.count_label.text()
    _place(editor, "enemy:ghoul", 176, 152)
    text = editor.count_label.text()
    assert text.startswith("Enemies: 1, objects the map builds: 13 of 23.")
    assert "conservative" in text
    assert "hardware" not in text.lower() and "engine limit" not in text.lower()


def test_map_editor_has_no_defeat_control(page):
    editor, _project = page
    _place(editor, "enemy:ghoul", 176, 152)
    editor.enemy_list.setCurrentRow(0)
    assert [text for text in _texts(editor) if "defeat" in text.lower()] == []


def test_map_editor_enemy_text_has_no_address(page):
    editor, _project = page
    _place(editor, "enemy:ghoul", 176, 152)
    editor.enemy_list.setCurrentRow(0)
    texts = _texts(editor)
    assert [text for text in texts if "0x" in text.lower()] == []
    names = [item.name for item in editor.map_enemies]
    names += [choice.name for choice in editor.studio.enemy_choices()]
    entry = enemy_types.read_types(editor.studio.directory, editor.studio.profile,
                                   editor.studio.image).entries["enemy:ghoul"]
    assert f"enemy:{entry.row}" not in names
    assert f"enemy:{entry.donor}" not in names
    assert "ghoul" in names
    editor.select_map(CROWDED)
    built = editor.count_label.text()
    assert "objects the map builds: 23 of 23." in built
