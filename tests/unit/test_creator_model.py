"""Portable proofs of the creator application's model: no ROM and no display."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest

from tools.creator.model import settings as settings_module
from tools.creator.model.project import (
    CreatorProject,
    RomMissingError,
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
    (tmp_path / ".postboy").mkdir()
    (tmp_path / ".postboy" / "rom.json").write_text("{}", encoding="utf-8")
    assert source_digest(tmp_path) == before

    (tmp_path / "text" / "strings.toml").write_text("b", encoding="utf-8")
    assert source_digest(tmp_path) != before


def test_extracted_graphics_do_not_make_a_build_stale_until_they_are_edited(tmp_path):
    (tmp_path / "project.toml").write_text('[base]\nprofile_id = "p"\n', encoding="utf-8")
    (tmp_path / "text").mkdir()
    (tmp_path / "text" / "strings.toml").write_text("a", encoding="utf-8")
    before = source_digest(tmp_path)

    picture = b"extracted png bytes"
    assets = tmp_path / "graphics" / "assets"
    assets.mkdir(parents=True)
    (assets / "graphic_0776.png").write_bytes(picture)
    (tmp_path / "graphics" / "graphics.toml").write_text(
        '[graphics]\nprofile_id = "p"\n\n[asset."graphic:0776"]\n'
        'file = "graphics/assets/graphic_0776.png"\nwidth = 8\nheight = 8\n'
        f'bit_depth = 8\npacked_size = 4\npng_sha256 = "{hashlib.sha256(picture).hexdigest()}"\n',
        encoding="utf-8")
    assert source_digest(tmp_path) == before

    (assets / "graphic_0776.png").write_bytes(b"painted png bytes")
    assert source_digest(tmp_path) != before

    (assets / "graphic_0776.png").write_bytes(picture)
    assert source_digest(tmp_path) == before

    (tmp_path / "graphics" / "overrides.toml").write_text("[palette]\n", encoding="utf-8")
    assert source_digest(tmp_path) != before


def _manifest_row(identity, file, png, width=8):
    return (f'[asset."{identity}"]\nfile = "{file}"\nwidth = {width}\nheight = 8\n'
            f'bit_depth = 8\npacked_size = 4\npng_sha256 = "{hashlib.sha256(png).hexdigest()}"\n\n')


def test_a_hand_edit_of_the_graphics_manifest_that_changes_the_build_makes_it_stale(tmp_path):
    (tmp_path / "project.toml").write_text('[base]\nprofile_id = "p"\n', encoding="utf-8")
    assets = tmp_path / "graphics" / "assets"
    assets.mkdir(parents=True)
    first, second = b"extracted 1", b"extracted 2"
    (assets / "graphic_0001.png").write_bytes(first)
    (assets / "graphic_0002.png").write_bytes(b"painted 2")
    manifest = tmp_path / "graphics" / "graphics.toml"
    header = '[graphics]\nprofile_id = "p"\n\n'
    rows = {
        "graphic:0001": _manifest_row("graphic:0001", "graphics/assets/graphic_0001.png", first),
        "graphic:0002": _manifest_row("graphic:0002", "graphics/assets/graphic_0002.png", second),
    }

    def digest_with(header=header, **changed):
        manifest.write_text(header + "".join({**rows, **changed}.values()), encoding="utf-8")
        return source_digest(tmp_path)

    before = digest_with()
    assert digest_with() == before
    edited = rows["graphic:0002"]
    assert digest_with(**{"graphic:0002": edited.replace("width = 8", "width = 16")}) != before
    assert digest_with(**{"graphic:0001": rows["graphic:0001"].replace("graphic_0001", "graphic_0002")}) != before
    assert digest_with(**{"graphic:0001": _manifest_row("graphic:0001", "graphics/assets/graphic_0001.png", b"x")}) != before
    assert digest_with(**{"graphic:0003": _manifest_row("graphic:0003", "graphics/assets/graphic_0002.png", b"x")}) != before
    assert digest_with(header.replace('"p"', '"q"')) != before
    assert digest_with(header="[graphics]\n") != before
    rows.pop("graphic:0002")
    assert digest_with() != before
    rows["graphic:0002"] = edited
    assert digest_with() == before


def test_problems_are_told_in_creator_language_and_name_their_record():
    too_long = (
        "text:0010: encoded text needs 10002 bytes but its allocation is 18; "
        "9984 bytes too long. Relocation was planned but refused"
    )
    assert problem_record(too_long) == "text:0010"
    assert friendly_problem(too_long) == "This text is too long for the game to store. Shorten it."
    assert friendly_problem("text:0007: project is missing this string").startswith("Game text 7: ")
    assert problem_record("something else") == ""
    assert friendly_problem("something else") == "something else"


def test_the_version_flag_names_the_product_without_a_display():
    import subprocess
    import sys

    from tools.webfoot.release_identity import release_identity

    result = subprocess.run(
        [sys.executable, "-m", "tools.creator", "--version"],
        cwd=MODEL.parents[2],
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0 and result.stdout.strip() == release_identity().display


def test_the_built_rom_lands_in_the_projects_build_folder(tmp_path):
    assert output_path(tmp_path, "My: Game?") == tmp_path / "build" / "My_ Game_.gba"


def test_legacy_settings_are_copied_when_the_new_directory_is_absent(tmp_path):
    from tools.creator.app import adopt_legacy_settings

    legacy = tmp_path / "DragonByte Z"
    (legacy / "logs").mkdir(parents=True)
    (legacy / "settings.json").write_text('{"emulator": "mGBA.exe"}', encoding="utf-8")
    directory = tmp_path / "Postboy Advance"

    adopt_legacy_settings(directory, legacy)

    assert (directory / "settings.json").read_text(encoding="utf-8") == '{"emulator": "mGBA.exe"}'
    assert (directory / "logs").is_dir()
    assert (legacy / "settings.json").is_file()


def test_legacy_settings_are_not_copied_over_an_existing_directory(tmp_path):
    from tools.creator.app import adopt_legacy_settings

    legacy = tmp_path / ".dragonbyte-z"
    legacy.mkdir()
    (legacy / "settings.json").write_text("old", encoding="utf-8")
    directory = tmp_path / ".postboy-advance"
    directory.mkdir()

    adopt_legacy_settings(directory, legacy)

    assert list(directory.iterdir()) == []
    assert (legacy / "settings.json").read_text(encoding="utf-8") == "old"


def _project_with_local_directories(tmp_path, *names):
    (tmp_path / "project.toml").write_text("", encoding="utf-8")
    for name in names:
        (tmp_path / name).mkdir()
        (tmp_path / name / "recovery.json").write_text(name, encoding="utf-8")
    return tmp_path


def test_opening_a_project_renames_its_legacy_local_directory(tmp_path):
    project = _project_with_local_directories(tmp_path, ".dragonbyte")

    with pytest.raises(RomMissingError):
        CreatorProject.open(project)

    assert not (project / ".dragonbyte").exists()
    assert (project / ".postboy" / "recovery.json").read_text(encoding="utf-8") == ".dragonbyte"


def test_opening_a_project_leaves_an_existing_local_directory_alone(tmp_path):
    project = _project_with_local_directories(tmp_path, ".dragonbyte", ".postboy")

    with pytest.raises(RomMissingError):
        CreatorProject.open(project)

    assert (project / ".dragonbyte" / "recovery.json").read_text(encoding="utf-8") == ".dragonbyte"
    assert (project / ".postboy" / "recovery.json").read_text(encoding="utf-8") == ".postboy"


def test_a_legacy_local_directory_that_cannot_be_renamed_is_reported(tmp_path, monkeypatch):
    project = _project_with_local_directories(tmp_path, ".dragonbyte")

    def refuse(self, target):
        raise PermissionError("in use")

    monkeypatch.setattr(Path, "rename", refuse)

    with pytest.raises(Exception, match="Could not rename .dragonbyte to .postboy"):
        CreatorProject.open(project)

    assert (project / ".dragonbyte" / "recovery.json").is_file()
