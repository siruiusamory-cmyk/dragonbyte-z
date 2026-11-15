"""The Library's sprite painter driven through its own widgets with no display."""

from __future__ import annotations

import os

import pytest

from tests.rom_support import canonical_rom_path, mutable_rom_copy

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

pytestmark = pytest.mark.skipif(
    canonical_rom_path() is None, reason="the canonical Buu's Fury ROM is not present"
)


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_sprite_38_is_painted_recoloured_undone_and_redone(app, tmp_path):
    from PySide6.QtCore import Qt
    from tools.creator.ui.main_window import MainWindow

    window = MainWindow("DragonByte Z", tmp_path / "settings", quiet=True)
    assert window.create_project(mutable_rom_copy(tmp_path), tmp_path / "Game", "Game")
    library = window.library
    library.stop()
    window.tabs.setCurrentWidget(library)
    item = QtWidgets.QListWidgetItem("sprite:0038")
    item.setData(Qt.ItemDataRole.UserRole, "sprite:0038")
    library.items.addItem(item)
    library.items.setCurrentItem(item)
    assert library.open_sprite_editor()
    panel = library.sprite_panel

    assert panel.frames.count() == 24 and panel.colours.count() > 1
    before = panel.editor.picture(panel.picture)[2]
    spot = next(i for i, value in enumerate(before) if value not in (0, panel.colour))
    panel.canvas.click(spot % 32, spot // 32)
    assert panel.editor.picture(panel.picture)[2][spot] == panel.colour
    assert window.project.dirty and window.actions_by_name["Undo"].isEnabled()

    panel.red.setValue(1)
    panel.green.setValue(2)
    panel.blue.setValue(3)
    panel.recolour()
    assert panel.editor.palette()[panel.colour] == (1, 2, 3)
    assert "not known" in panel.uses.text()

    window.undo()
    assert panel.editor.palette()[panel.colour] != (1, 2, 3)
    window.undo()
    assert panel.editor.picture(panel.picture)[2] == before
    window.redo()
    window.redo()
    assert panel.editor.picture(panel.picture)[2][spot] == panel.colour
    assert panel.editor.palette()[panel.colour] == (1, 2, 3)

    panel.canvas.click(500, 500)
    assert "outside the picture" in panel.message.text()
    window.close()


def test_a_stroke_after_reopening_a_sprite_is_its_own_undo_step(app, tmp_path):
    from PySide6.QtCore import Qt
    from tools.creator.ui.main_window import MainWindow

    window = MainWindow("DragonByte Z", tmp_path / "settings", quiet=True)
    assert window.create_project(mutable_rom_copy(tmp_path), tmp_path / "Game", "Game")
    library = window.library
    library.stop()
    window.tabs.setCurrentWidget(library)
    item = QtWidgets.QListWidgetItem("sprite:0038")
    item.setData(Qt.ItemDataRole.UserRole, "sprite:0038")
    library.items.addItem(item)
    library.items.setCurrentItem(item)

    assert library.open_sprite_editor()
    panel = library.sprite_panel
    before = panel.editor.picture(panel.picture)[2]
    spots = [i for i, value in enumerate(before) if value not in (0, panel.colour)][:3]
    first = spots[0]
    panel.canvas.click(first % 32, first // 32)
    library.close_sprite_editor()

    assert library.open_sprite_editor()
    panel = library.sprite_panel
    panel.canvas.click(spots[1] % 32, spots[1] // 32)
    panel.canvas.click(spots[2] % 32, spots[2] // 32, start=False)
    painted = panel.editor.picture(panel.picture)[2]
    assert all(painted[spot] == panel.colour for spot in spots)

    window.undo()
    undone = panel.editor.picture(panel.picture)[2]
    assert undone[first] == panel.colour
    assert undone[spots[1]] == before[spots[1]] and undone[spots[2]] == before[spots[2]]
    window.undo()
    window.redo()
    assert panel.editor.picture(panel.picture)[2][first] == panel.colour
    window.close()


def test_a_sprite_whose_manifest_points_outside_the_assets_shows_a_message(app, tmp_path):
    from PySide6.QtCore import Qt
    from tools.creator.ui.main_window import MainWindow

    window = MainWindow("DragonByte Z", tmp_path / "settings", quiet=True)
    assert window.create_project(mutable_rom_copy(tmp_path), tmp_path / "Game", "Game")
    library = window.library
    library.stop()
    window.tabs.setCurrentWidget(library)
    item = QtWidgets.QListWidgetItem("sprite:0038")
    item.setData(Qt.ItemDataRole.UserRole, "sprite:0038")
    library.items.addItem(item)
    library.items.setCurrentItem(item)
    assert library.open_sprite_editor()
    library.close_sprite_editor()

    manifest = tmp_path / "Game" / "graphics" / "graphics.toml"
    text = manifest.read_text(encoding="utf-8")
    assert 'file = "graphics/assets/' in text
    manifest.write_text(text.replace('file = "graphics/assets/', 'file = "../', 1),
                        encoding="utf-8")

    assert not library.open_sprite_editor()
    assert library.sprite_panel is None
    assert "not inside graphics/assets" in library.status.text()
    window.close()
