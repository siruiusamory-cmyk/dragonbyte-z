import hashlib
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")
QtGui = pytest.importorskip("PySide6.QtGui")

from tools.webfoot import build, scene
from tools.webfoot.profile import RomProfileCatalog
from tools.webfoot.project import ProjectMeta, write_project
from tools.webfoot.workbench import atlas_browser as ab
from tools.webfoot.workbench import build_panel as bp
from tools.webfoot.workbench import map_browser_tab as mbt
from tools.webfoot.workbench.app import MainWindow
from tools.webfoot.workbench.session import Session
from tests.unit.test_placement_types import types
from tests.unit.test_workbench_map_browser import (
    MAP,
    SLOT,
    _FakeEditor,
    _entry,
    _result,
    _target,
)
from tests.unit.test_workbench_state_and_errors import _chunk_images, stage_layout_edit
from tests.unit.test_workbench_warp_transitions import (
    image_bytes,
    project_meta,
    session_for,
)

EXITS = ("close", "open-rom", "open-project", "extract")
SELECTIONS = ("_source_select", "_trigger_select", "_behavior_select")


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture(scope="module")
def catalog():
    return RomProfileCatalog.load("config/roms.yaml")


@pytest.fixture
def staged_shell(qapp, catalog, monkeypatch, tmp_path):
    image = image_bytes()
    rom = tmp_path / "synthetic.gba"
    rom.write_bytes(image)
    project = tmp_path / "project"
    project.mkdir()
    write_project(project, project_meta(image), enemies=[], characters=[])
    session = session_for(image, project, selected_map="map:0000")
    session.rom_path = rom
    monkeypatch.setattr(
        mbt.mv, "read_map_index", lambda rom_image: (_entry(MAP, "Synthetic Map"),)
    )
    monkeypatch.setattr(
        mbt.mv, "render_map", lambda rom_image, index, **kwargs: _result(MAP)
    )
    monkeypatch.setattr(mbt.mv, "render_chunk_images", _chunk_images)
    fake = _FakeEditor(_target(), _result(MAP))
    monkeypatch.setattr(mbt, "MapLayoutEditor", lambda rom_image: fake)
    monkeypatch.setattr(ab, "MapLayoutEditor", lambda rom_image: fake, raising=False)
    window = MainWindow(session, catalog)
    window._on_rom_opened()
    return SimpleNamespace(
        window=window, session=session, fake=fake, project=project, image=image, rom=rom
    )


def _scene_support(monkeypatch, profile) -> None:
    monkeypatch.setattr(
        scene,
        "SCRIPT_EFFECTS",
        {
            profile.id: {
                "show_centered_sprite_text": {
                    "text_count": 1534,
                    "coordinate_ranges": {"x": (0, 239), "y": (0, 159)},
                }
            }
        },
    )
    monkeypatch.setattr(
        scene,
        "BEHAVIOR_TRIGGER_CONTRACTS",
        {
            profile.id: {
                "sha256": profile.sha256,
                "on_defeat": {
                    "placement_type": f"{profile.id}/placement_type:0001",
                    "required_classification": "CONFIRMED_ENEMY_STAT_LINK",
                    "binding": "placement_record_descriptor_pointer",
                    "evidence": "synthetic",
                },
            }
        },
    )


@pytest.fixture
def scene_shell(qapp, catalog, monkeypatch, tmp_path, types):
    profile = types.maps.profile
    _scene_support(monkeypatch, profile)
    project = tmp_path / "scene-project"
    project.mkdir()
    write_project(
        project,
        ProjectMeta(
            1,
            profile.id,
            profile.game,
            profile.sha256,
            len(types.maps.base_bytes),
            "staged-work-test",
        ),
        enemies=[],
        characters=[],
        maps=build._map_documents(types.maps),
    )
    session = Session(maps=types.maps)
    session.set_project(project)
    window = MainWindow(session, catalog)
    return SimpleNamespace(window=window, session=session, project=project)


def _project_files(project: Path) -> dict[str, tuple[int, str]]:
    return {
        path.relative_to(project).as_posix(): (
            path.stat().st_mtime_ns,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in sorted(project.rglob("*"))
        if path.is_file()
    }


def test_a_save_as_copy_leaves_the_staged_paint_unsaved_and_the_project_untouched(
    staged_shell, monkeypatch, tmp_path
):
    shell = staged_shell
    browser = stage_layout_edit(shell)
    assert browser.unsaved_edit_count() == 1
    before = _project_files(shell.project)
    copy = tmp_path / "copy.gba"
    monkeypatch.setattr(
        mbt.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(copy), "")),
    )
    shown: list[str] = []
    monkeypatch.setattr(
        mbt.QMessageBox, "information", lambda *args: shown.append(args[-1])
    )

    browser._on_save_as()

    assert browser.unsaved_edit_count() == 1, "a ROM copy does not save the project"
    assert browser._layout.written == {}, "only Apply moves the project baseline"
    assert _project_files(shell.project) == before, "no project file was written"
    assert not copy.exists(), "the tab writes no file itself"
    assert "stay in the project" in shown[0], shown[0]
    assert "Apply or Build writes them" in shown[0], shown[0]


def test_apply_to_project_clears_the_staged_paint_it_publishes(staged_shell, monkeypatch):
    shell = staged_shell
    browser = stage_layout_edit(shell)
    batches: list[dict] = []
    monkeypatch.setattr(
        mbt,
        "set_layout_cells",
        lambda project_dir, profile, image, batch: batches.append(batch) or True,
    )
    monkeypatch.setattr(mbt, "set_authored_chunk", lambda *args, **kwargs: False)
    monkeypatch.setattr(mbt, "set_layout_authored_cells", lambda *args, **kwargs: False)

    assert browser.apply_to_project() is True

    assert browser.unsaved_edit_count() == 0
    assert list(batches[0]) == [(MAP, SLOT, 0)], batches[0]
    assert isinstance(batches[0][(MAP, SLOT, 0)], int)


def _type_dialogue(shell) -> None:
    inspector = shell.window._inspector
    shell.session.selected_result = {"_mode": "decoded", "text": "a record"}
    inspector._target = SimpleNamespace(name="dialog 0")
    inspector._original = "the original line"
    inspector._project_replacement = None
    loader = inspector._loading_editor
    inspector._loading_editor = True
    inspector._edit.setText("typed but not applied")
    inspector._loading_editor = loader
    inspector._edit.setEnabled(True)


def test_an_unapplied_dialogue_value_makes_the_close_prompt_count_it(
    staged_shell, monkeypatch
):
    shell = staged_shell
    _type_dialogue(shell)
    assert shell.session.unsaved_edit_count() == 1
    asked = _answer(monkeypatch, QtWidgets.QMessageBox.StandardButton.Cancel)

    event = QtGui.QCloseEvent()
    shell.window.closeEvent(event)

    assert asked and "1 unsaved edit" in asked[0], asked
    assert "Apply to project" in asked[0], asked[0]
    assert not event.isAccepted()
    assert shell.window._inspector._edit.text() == "typed but not applied"


def test_an_unapplied_scene_form_value_makes_the_close_prompt_count_it(
    staged_shell, monkeypatch
):
    shell = staged_shell
    scene_tab = shell.window._scene
    scene_tab._name.setText("wolf")
    assert scene_tab._pos_low.maximum() != scene_tab._pos_low.value()
    scene_tab._pos_low.setValue(scene_tab._pos_low.maximum())
    assert shell.session.unsaved_edit_count() == 2
    asked = _answer(monkeypatch, QtWidgets.QMessageBox.StandardButton.Cancel)

    event = QtGui.QCloseEvent()
    shell.window.closeEvent(event)

    assert asked and "2 unsaved edit" in asked[0], asked
    assert not event.isAccepted()
    assert scene_tab._name.text() == "wolf"
    assert scene_tab._pos_low.value() == scene_tab._pos_low.maximum()


@pytest.mark.parametrize("selection", SELECTIONS)
def test_a_scene_selection_alone_is_staged_work_the_prompt_counts(
    scene_shell, monkeypatch, selection
):
    shell = scene_shell
    scene_tab = shell.window._scene
    control = getattr(scene_tab, selection)
    assert control.count() > 1, selection
    control.setCurrentIndex(1)
    assert shell.session.unsaved_edit_count() == 1, selection
    asked = _answer(monkeypatch, QtWidgets.QMessageBox.StandardButton.Cancel)

    event = QtGui.QCloseEvent()
    shell.window.closeEvent(event)

    assert asked and "1 unsaved edit" in asked[0], asked
    assert not event.isAccepted()
    assert control.currentIndex() == 1, selection


def test_a_script_value_stays_staged_when_the_behavior_changes(scene_shell):
    shell = scene_shell
    scene_tab = shell.window._scene
    scene_tab._script_text.setValue(3)
    authored = next(
        index
        for index in range(scene_tab._behavior_select.count())
        if isinstance(scene_tab._behavior_select.itemData(index), tuple)
    )

    scene_tab._behavior_select.setCurrentIndex(authored)

    assert scene_tab._form_values()["script_text"] == 3
    assert scene_tab._staged_edit_count() == 2, scene_tab._form_values()


def _staged_selections(scene_tab) -> tuple:
    return (
        scene_tab._source_select.currentData(),
        scene_tab._behavior_select.currentData(),
        scene_tab._trigger_select.currentData(),
        scene_tab._script_text.value(),
        scene_tab._staged_edit_count(),
    )


def test_a_repopulate_keeps_the_staged_selections_and_script_values(scene_shell):
    shell = scene_shell
    scene_tab = shell.window._scene
    authored = next(
        index
        for index in range(scene_tab._behavior_select.count())
        if isinstance(scene_tab._behavior_select.itemData(index), tuple)
    )
    scene_tab._behavior_select.setCurrentIndex(authored)
    scene_tab._script_text.setValue(3)
    scene_tab._source_select.setCurrentIndex(1)
    before = _staged_selections(scene_tab)
    assert before[0] == scene_tab._source_select.itemData(1)
    assert before[4] == 3

    shell.session.project_mutated()
    scene_tab.on_project_mutated()

    assert _staged_selections(scene_tab) == before
    assert scene_tab._script_widget.isEnabled()


@pytest.mark.parametrize("selection", SELECTIONS)
def test_a_selection_change_updates_the_indicator(scene_shell, selection):
    shell = scene_shell
    scene_tab = shell.window._scene
    emitted: list[object] = []
    scene_tab.dirtyChanged.connect(lambda: emitted.append(scene_tab._staged_edit_count()))

    getattr(scene_tab, selection).setCurrentIndex(1)

    assert emitted == [1], (selection, emitted)
    assert "1 unsaved" in shell.window.windowTitle()


def test_a_project_switch_discards_the_inspector_and_scene_drafts(
    staged_shell, monkeypatch, tmp_path
):
    shell = staged_shell
    session = shell.session
    _type_dialogue(shell)
    shell.window._scene._name.setText("wolf")
    monkeypatch.setattr(
        "tools.webfoot.workbench.inspector.dialogue_sdk.resolve_dialogue_target",
        lambda result, profile: SimpleNamespace(name="dialog 0"),
    )
    monkeypatch.setattr(
        "tools.webfoot.workbench.inspector.dialogue_sdk.get_dialogue_original",
        lambda *args, **kwargs: "the original line",
    )
    monkeypatch.setattr(
        "tools.webfoot.workbench.inspector.dialogue_sdk.get_dialogue_replacement",
        lambda *args, **kwargs: None,
    )
    other = tmp_path / "other"
    other.mkdir()

    session.set_project(other)
    shell.window._inspector.on_project_mutated()
    shell.window._scene.on_project_mutated()

    assert shell.window._inspector._edit.text() == "the original line"
    assert shell.window._scene._name.text() == ""
    assert session.unsaved_edit_count() == 0


def test_an_image_change_discards_the_inspector_and_scene_drafts(staged_shell):
    shell = staged_shell
    _type_dialogue(shell)
    shell.window._scene._name.setText("wolf")
    assert shell.session.unsaved_edit_count() == 2

    shell.window._inspector.on_session_changed()
    shell.window._scene.on_session_changed()

    assert shell.window._inspector._edit.text() == ""
    assert shell.window._scene._name.text() == ""
    assert shell.session.unsaved_edit_count() == 0


def _stage_every_provider(shell) -> None:
    stage_layout_edit(shell)
    warps = shell.window._maps.warps
    assert warps.select_source_map(0)
    assert warps.stage_destination(3)
    shell.window._graphics._palette_pending[7] = (10, 20, 30)
    shell.window._graphics._refresh_pending_ui()
    _type_dialogue(shell)
    shell.window._scene._name.setText("wolf")


def _every_provider_state(shell) -> tuple:
    browser = shell.window._maps.browser
    return (
        tuple(
            (edit.map_index, edit.layer_slot, edit.cell, edit.replacement)
            for edit in browser._editor.edits()
        ),
        tuple(sorted(browser._layout.written)),
        dict(shell.window._maps.warps._staged),
        dict(shell.window._graphics._palette_pending),
        shell.window._inspector._edit.text(),
        shell.window._scene._name.text(),
        shell.window._scene._pos_low.value(),
    )


def _answer(monkeypatch, button) -> list[str]:
    asked: list[str] = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "question",
        staticmethod(lambda *args, **kwargs: (asked.append(args[2]), button)[1]),
    )
    return asked


def _drive(exit_name: str, shell, monkeypatch, tmp_path, opened) -> bool:
    window = shell.window
    if exit_name == "close":
        event = QtGui.QCloseEvent()
        window.closeEvent(event)
        return event.isAccepted()
    if exit_name == "open-rom":
        monkeypatch.setattr(
            ab.QFileDialog,
            "getOpenFileName",
            staticmethod(lambda *args, **kwargs: (str(tmp_path / "other.gba"), "")),
        )
        monkeypatch.setattr(
            shell.session, "open_rom", lambda *args, **kwargs: opened.append("open")
        )
        window._open_rom()
        return opened == ["open"]
    other = tmp_path / "switched"
    other.mkdir(exist_ok=True)
    picked: list[str] = []
    monkeypatch.setattr(
        bp.QFileDialog,
        "getExistingDirectory",
        staticmethod(lambda *args, **kwargs: picked.append("picked") or str(other)),
    )
    if exit_name == "open-project":
        window._action_open_project.trigger()
    else:
        monkeypatch.setattr(
            bp.build_sdk,
            "extract_project",
            lambda *args, **kwargs: opened.append("extract"),
        )
        window._build.extract_project_dialog()
    return picked == ["picked"] and shell.session.project_dir == other


@pytest.mark.parametrize("exit_name", EXITS)
def test_cancel_in_every_exit_keeps_all_five_staged_providers(
    staged_shell, monkeypatch, tmp_path, exit_name
):
    shell = staged_shell
    _stage_every_provider(shell)
    before = _every_provider_state(shell)
    assert shell.session.unsaved_edit_count() == 5
    asked = _answer(monkeypatch, QtWidgets.QMessageBox.StandardButton.Cancel)

    performed = _drive(exit_name, shell, monkeypatch, tmp_path, [])

    assert asked, f"{exit_name} must ask before it discards staged work"
    assert "5 unsaved edit" in asked[0], asked[0]
    assert performed is False, f"{exit_name} must not navigate after Cancel"
    assert _every_provider_state(shell) == before
    assert shell.session.unsaved_edit_count() == 5


@pytest.mark.parametrize("exit_name", EXITS)
def test_discard_in_every_exit_performs_it_and_clears_every_provider(
    staged_shell, monkeypatch, tmp_path, exit_name
):
    shell = staged_shell
    _stage_every_provider(shell)
    assert shell.session.unsaved_edit_count() == 5
    asked = _answer(monkeypatch, QtWidgets.QMessageBox.StandardButton.Discard)

    performed = _drive(exit_name, shell, monkeypatch, tmp_path, [])

    assert asked, f"{exit_name} asked first"
    assert performed is True, f"{exit_name} must happen after Discard"
    if exit_name != "close":
        assert shell.session.unsaved_edit_count() == 0, exit_name
