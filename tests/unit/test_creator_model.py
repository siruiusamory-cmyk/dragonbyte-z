"""Portable proofs of the creator application's model: no ROM and no display."""

from __future__ import annotations

import ast
from pathlib import Path

from tools.creator.model import settings as settings_module
from tools.creator.model.project import (
    friendly_problem,
    output_path,
    problem_record,
    source_digest,
)
from tools.creator.model.settings import AppSettings, launch_emulator

MODEL = Path(__file__).resolve().parents[2] / "tools" / "creator" / "model"


def test_the_model_layer_imports_no_qt():
    for module in MODEL.glob("*.py"):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        names = [
            name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for name in ([node.module or ""] if isinstance(node, ast.ImportFrom) else [alias.name for alias in node.names])
        ]
        assert not [name for name in names if name.startswith("PySide6")], module.name


def test_the_emulator_is_configured_once_and_remembered(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_module, "DEFAULT_EMULATORS", ())
    assert AppSettings.load(tmp_path).emulator_path() is None

    emulator = tmp_path / "mGBA.exe"
    emulator.write_bytes(b"")
    settings = AppSettings(emulator=str(emulator))
    settings.remember_project(tmp_path / "My Game")
    settings.save(tmp_path)

    loaded = AppSettings.load(tmp_path)
    assert loaded.emulator_path() == emulator
    assert loaded.recent == [str((tmp_path / "My Game").resolve())]
    (tmp_path / settings_module.SETTINGS_FILE).write_text("not json", encoding="utf-8")
    assert AppSettings.load(tmp_path) == AppSettings()


def test_play_starts_the_emulator_with_the_built_rom(tmp_path, monkeypatch):
    started = []
    monkeypatch.setattr(
        settings_module.subprocess, "Popen", lambda command, cwd: started.append((command, cwd))
    )

    launch_emulator(tmp_path / "mGBA.exe", tmp_path / "build" / "My Game.gba")

    assert started == [
        ([str(tmp_path / "mGBA.exe"), str(tmp_path / "build" / "My Game.gba")], str(tmp_path))
    ]


def test_a_build_goes_stale_when_an_authored_file_changes_and_only_then(tmp_path):
    (tmp_path / "text").mkdir()
    (tmp_path / "text" / "strings.toml").write_text("a", encoding="utf-8")
    before = source_digest(tmp_path)

    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "out.gba").write_bytes(b"rom")
    (tmp_path / ".dragonbyte").mkdir()
    (tmp_path / ".dragonbyte" / "rom.json").write_text("{}", encoding="utf-8")
    assert source_digest(tmp_path) == before

    (tmp_path / "text" / "strings.toml").write_text("b", encoding="utf-8")
    assert source_digest(tmp_path) != before


def test_problems_are_told_in_creator_language_and_name_their_record():
    too_long = (
        "text:0010: encoded text needs 10002 bytes but its allocation is 18; "
        "9984 bytes too long. Relocation was planned but refused"
    )
    assert problem_record(too_long) == "text:0010"
    assert friendly_problem(too_long) == (
        "This text is too long for the game to store: it is 9984 bytes over. Shorten it."
    )
    assert friendly_problem("text:0007: project is missing this string").startswith("Game text 7: ")
    assert problem_record("something else") == ""
    assert friendly_problem("something else") == "something else"


def test_the_built_rom_lands_in_the_projects_build_folder(tmp_path):
    assert output_path(tmp_path, "My: Game?") == tmp_path / "build" / "My_ Game_.gba"
