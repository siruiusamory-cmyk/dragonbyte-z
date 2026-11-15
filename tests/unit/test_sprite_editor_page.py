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
