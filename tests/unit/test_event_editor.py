"""The Events tab: every character step added through the editor and read back.

Driven through the real widgets with no display, the way the rest of the
application's offscreen tests are. A ROM is needed to open a project, so these
skip cleanly when the canonical image is absent.
"""

from __future__ import annotations

import os

import pytest

from tests.rom_support import canonical_rom_path, mutable_rom_copy
from tools.webfoot import events as sdk

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

pytestmark = pytest.mark.skipif(
    canonical_rom_path() is None, reason="the canonical Buu's Fury ROM is not present"
)


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_the_editor_adds_and_reads_back_every_character_step(app, tmp_path):
    from tools.creator.model.maps import MapStudio
    from tools.creator.model.project import CreatorProject
    from tools.creator.ui.event_editor import EventEditor

    rom = mutable_rom_copy(tmp_path)
    project = CreatorProject.create(rom, tmp_path / "Game", "Game")
    maps = MapStudio(project.directory, rom)
    road = "map:0033"
    people = [item for item in maps.characters(road) if item.editable and not item.removed]
    donor = maps.character_choices()[0]
    elder = maps.add_character(road, donor.donor_map, donor.donor_slot, 200, 152)
    maps.rename_character(road, elder, "Elder")

    editor = EventEditor()
    editor.set_project(project.directory, rom, project.output)
    editor.pick_name = lambda _title, _text: "Scene"
    editor.new_event()
    key = editor.key
    maps.set_says(road, people[0].key, key)
    editor.refresh()

    def document():
        return sdk.read_document(project.directory)[key].steps

    editor.select(key)
    editor.add_step("walk")
    who, x, y, speed = [widget for _kind, _at, widget in editor._inputs]
    who.setCurrentIndex(max(who.findData(f"{road}/{elder}"), 0))
    x.setValue(200)
    y.setValue(152)
    speed.setCurrentIndex(speed.findData(200))
    assert editor.apply_step()
    assert document()[1] == ("walk", f"{road}/{elder}", 200, 152, 200)

    editor.add_step("face")
    direction = editor._inputs[1][2]
    direction.setCurrentIndex(direction.findData("left"))
    assert editor.apply_step()
    assert document()[2] == ("face", sdk.PLAYER, "left")

    editor.add_step("face toward")
    subject, target = editor._inputs[0][2], editor._inputs[1][2]
    subject.setCurrentIndex(max(subject.findData(f"{road}/{elder}"), 0))
    target.setCurrentIndex(max(target.findData(f"{road}/{people[0].key}"), 0))
    assert editor.apply_step()
    assert document()[3] == ("face toward", f"{road}/{elder}", f"{road}/{people[0].key}")

    editor.add_step("wait")
    editor._inputs[0][2].setValue(30)
    assert editor.apply_step()
    assert document()[4] == ("wait", 30)

    editor.add_step("together")
    editor.add_step("walk")
    inside = editor._inputs[0][2]
    inside.setCurrentIndex(max(inside.findData(f"{road}/{people[0].key}"), 0))
    editor._inputs[1][2].setValue(64)
    editor._inputs[2][2].setValue(64)
    assert editor.apply_step()
    editor.add_step("face")
    editor._inputs[1][2].setCurrentIndex(editor._inputs[1][2].findData("right"))
    assert editor.apply_step()
    steps = document()
    assert steps[5] == ("together",) and steps[-1] == ("end_together",)
    assert steps[6][0] == "walk" and steps[7][0] == "face" and len(steps) == 9

    before = document()
    editor.select(key, 4)
    editor.move_step(-1)
    assert document()[3] == ("wait", 30)
    editor.undo()
    assert document() == before
    editor.redo()
    moved = document()
    assert moved != before
    editor.select(key, 3)
    editor.remove_step()
    assert len(document()) == len(moved) - 1
    editor.undo()
    assert document() == moved

    known = set(sdk.read_document(project.directory))
    editor.duplicate()
    copied = set(sdk.read_document(project.directory)) - known
    assert len(copied) == 1
    assert sdk.read_document(project.directory)[copied.pop()].steps == moved

    editor.select(key, len(document()) - 1)
    editor.add_step("lie down")
    editor.add_step("stand up")
    assert document()[-2:] == (("lie down",), ("stand up",))


def test_clicking_the_map_sets_where_a_walk_step_goes(app, tmp_path):
    from tools.creator.model.events import EventStudio
    from tools.creator.model.maps import MapStudio
    from tools.creator.model.project import CreatorProject
    from tools.creator.ui.map_editor import MapEditor

    rom = mutable_rom_copy(tmp_path)
    project = CreatorProject.create(rom, tmp_path / "Game", "Game")
    maps = MapStudio(project.directory, rom)
    road = "map:0033"
    person, other = [item for item in maps.characters(road)
                     if item.editable and not item.removed][:2]
    events = EventStudio(project.directory, rom)
    talk = events.new_event("Scene")
    events._set_steps(talk, (("say", 0, "Watch."),
                             ("walk", f"{road}/{person.key}", 8, 8),
                             ("walk", f"{road}/{other.key}", 8, 8, 50)))
    maps.set_says(road, person.key, talk)

    editor = MapEditor()
    editor.set_project(project.directory, rom)
    editor.events = events
    editor.select_map(road)
    editor.set_tool("regions")
    choices = editor._region_choices()
    first = next(choice for choice, title in choices if choice[0] == "walk")
    assert [choice for choice, _title in choices if choice[0] == "walk"] == [
        ("walk", talk, 1), ("walk", talk, 2)]

    editor.pick_region = lambda _choices: first
    editor.down(120, 96)
    editor.up(120, 96)
    steps = sdk.read_document(project.directory)[talk].steps
    assert steps[1] == ("walk", f"{road}/{person.key}", 120, 96)

    editor.pick_region = lambda _choices: ("walk", talk, 2)
    editor.down(64, 40)
    editor.up(64, 40)
    steps = sdk.read_document(project.directory)[talk].steps
    assert steps[2] == ("walk", f"{road}/{other.key}", 64, 40, 50)
