"""The window's menus, Help targets, About details, error dialog and Export Patch, offscreen."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from urllib.parse import unquote

import pytest

from tools.webfoot.patch import PatchError
from tools.webfoot.release_identity import PRODUCT_VERSION, identity_document

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

MENUS = {
    "File": ["New Project", "Open Project", "Save", None, "Export Patch...", None, "Exit"],
    "Project": ["Undo", "Redo", None, "Validate", "Build", "Play", None, "Choose Emulator"],
    "Help": ["User Guide", "Report a Problem", "Open Log Folder", None,
             "Third-Party Notices", "About Postboy Advance"],
}


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def window(app, tmp_path):
    from tools.creator.ui.main_window import MainWindow

    made = MainWindow("Postboy Advance", tmp_path / "settings", quiet=True,
                      identity=identity_document())
    yield made
    made.project = None
    made.close()


def _stub_project(directory: Path) -> SimpleNamespace:
    return SimpleNamespace(
        dirty=False, can_undo=False, can_redo=False, name="Game", directory=directory,
        rom_path=directory / "base.rom", output=directory / "build" / "Game.out",
        build_status=lambda: "none",
    )


def _menus(window) -> dict:
    return {
        top.text(): [None if item.isSeparator() else item.text() for item in top.menu().actions()]
        for top in window.menuBar().actions()
    }


def test_menu_bar_has_exactly_the_three_menus(window):
    assert _menus(window) == MENUS


def test_toolbar_actions_are_the_menu_actions(window):
    toolbar = window.findChild(QtWidgets.QToolBar, "main")
    shown = [item for top in window.menuBar().actions() for item in top.menu().actions()]
    tools = [item for item in toolbar.actions() if not item.isSeparator()]
    assert len(tools) == 9
    for action in tools:
        assert any(action is item for item in shown), action.text()
        assert window.actions_by_name[action.text()] is action


def test_export_patch_needs_a_project(window, tmp_path):
    export = window.actions_by_name["Export Patch"]
    assert not export.isEnabled()
    window.project = _stub_project(tmp_path / "Game")
    window.refresh_state()
    assert export.isEnabled()


def test_details_carry_the_version_and_no_home_path():
    from tools.creator.ui.front_door import details_text

    details = details_text(identity_document())
    assert PRODUCT_VERSION in details
    assert "Python" in details and "Qt" in details


def test_home_is_hidden_however_an_error_spells_it():
    from tools.creator.ui.front_door import without_home

    inside = Path.home() / "Game" / "project.json"
    for text in (
        str(inside),
        inside.as_posix(),
        str(FileNotFoundError(2, "No such file", str(inside))),
        str(inside).upper(),
    ):
        shown = without_home(text)
        assert Path.home().name.lower() not in shown.lower(), shown
        assert "~" in shown


def test_export_patch_sends_the_chosen_file_to_the_job(window, tmp_path, monkeypatch):
    import json

    from PySide6.QtCore import QProcess

    monkeypatch.setattr(QProcess, "start", lambda *_arguments: None)
    window.project = _stub_project(tmp_path / "Game")
    monkeypatch.setattr(window, "save", lambda: True)
    destination = tmp_path / "shared" / "Game.bps"

    window.export_patch(destination=destination)

    action, job = window._job
    assert action == "export"
    assert json.loads(Path(job).read_text(encoding="utf-8"))["output"] == str(destination)
    window._process, window._job = None, None


def test_issue_url_is_cut_from_the_top_and_hides_home():
    from tools.creator.ui.front_door import NEW_ISSUE_URL, NEVER_ATTACH, issue_url

    home = Path.home()
    frames = "".join(
        f'  File "{home / "work" / f"module{index}.py"}", line {index}, in step{index}\n'
        for index in range(2000)
    )
    trace = "Traceback (most recent call last):\n" + frames + "ValueError: LAST_FRAME\n"
    url = issue_url("Postboy Advance " + PRODUCT_VERSION, "ValueError: " + "x" * 500, trace)
    text = unquote(url)
    assert url.startswith(NEW_ISSUE_URL + "?title=")
    assert len(url) <= 6000
    assert "LAST_FRAME" in text and "step1999" in text and 'module0.py"' not in text
    assert NEVER_ATTACH in text
    assert str(home).lower() not in text.lower()
    assert "~" in text
    assert len(unquote(url.split("&body=")[0].split("title=")[1])) == 120


def _fail(message: str):
    try:
        raise ValueError(message)
    except ValueError:
        return sys.exc_info()


def test_excepthook_logs_and_stays_quiet(window, monkeypatch, caplog):
    from tools.creator.ui import front_door

    shown = []
    monkeypatch.setattr(front_door, "show_error", lambda *args: shown.append(args))
    hook = front_door.ErrorHook(window)
    with caplog.at_level(logging.ERROR, logger="postboy-advance"):
        hook(*_fail("boom"))
    assert [record.message for record in caplog.records] == ["unhandled error"]
    assert caplog.records[0].exc_info[0] is ValueError
    assert shown == []


def test_second_error_while_the_dialog_is_open_is_only_logged(window, monkeypatch, caplog):
    from tools.creator.ui import front_door

    window.quiet = False
    hook = front_door.ErrorHook(window)
    shown = []

    def dialog(*args):
        shown.append(args)
        hook(*_fail("second"))

    monkeypatch.setattr(front_door, "show_error", dialog)
    with caplog.at_level(logging.ERROR, logger="postboy-advance"):
        hook(*_fail("first"))
    window.quiet = True
    assert len(shown) == 1
    assert [str(record.exc_info[1]) for record in caplog.records] == ["first", "second"]
    assert not hook.showing


def test_help_actions_open_through_the_one_seam(window, monkeypatch, tmp_path):
    from tools.creator.ui import front_door

    opened = []
    monkeypatch.setattr(front_door, "open_url", opened.append)
    for name in ("User Guide", "Report a Problem", "Open Log Folder", "Third-Party Notices"):
        window.actions_by_name[name].trigger()
    guide, report, logs, notices = opened
    assert guide.toString() == (
        "https://github.com/siruiusamory-cmyk/postboy-advance/blob/master/docs/creator.md"
    )
    assert report.toString().startswith(front_door.NEW_ISSUE_URL + "?")
    assert Path(logs.toLocalFile()) == tmp_path / "settings" / "logs"
    assert Path(notices.toLocalFile()).name == "THIRD-PARTY-NOTICES.md"
    assert Path(notices.toLocalFile()).is_file()

    shown = []
    monkeypatch.setattr(QtWidgets.QMessageBox, "exec", lambda box: shown.append(box.text()))
    window.actions_by_name["About Postboy Advance"].trigger()
    assert PRODUCT_VERSION in shown[0] and "Mozilla Public License" in shown[0]


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (None, "never share the .gba file"),
        (PatchError("the source image changed while it was being read"), "changed while"),
        (PatchError("identical to its base ROM, so there is nothing to distribute"),
         "nothing to export yet"),
    ],
)
def test_export_patch_messages(window, monkeypatch, tmp_path, outcome, expected):
    from PySide6.QtCore import QProcess

    from tools.creator.model import jobs

    def fake_export(project, rom, output, catalog):
        if outcome is not None:
            raise outcome
        return SimpleNamespace(patch_path=Path(output))

    monkeypatch.setattr(jobs, "export_patch", fake_export)
    monkeypatch.setattr(jobs, "load_catalog", lambda _path: None)
    monkeypatch.setattr(jobs, "validate_project", lambda *_args: SimpleNamespace(problems=[]))
    project = _stub_project(tmp_path / "Game")
    destination = tmp_path / "Game.bps"
    job = jobs.write_job("export", project.directory, project.rom_path, destination)
    assert jobs.run_job(job) == 0
    window.project = project
    window._process, window._job = QProcess(window), ("export", job)
    window._finished(0)
    assert expected in window.messages[-1]
    if outcome is None:
        assert str(destination) in window.messages[-1]


def test_keyboard_interrupt_goes_to_the_default_hook(monkeypatch, caplog):
    from tools.creator.ui import front_door

    passed = []
    monkeypatch.setattr(sys, "__excepthook__", lambda *args: passed.append(args[0]))
    with caplog.at_level(logging.ERROR, logger="postboy-advance"):
        front_door.ErrorHook()(KeyboardInterrupt, KeyboardInterrupt(), None)
    assert passed == [KeyboardInterrupt]
    assert caplog.records == []
