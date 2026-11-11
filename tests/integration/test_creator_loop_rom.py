"""ROM-gated proofs of the creator application's loop: Open, Edit, Save, Build, Revise.

Every test works on a private copy of the canonical image and skips cleanly when
the image is absent. Nothing ROM-derived is committed.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from tests.rom_support import canonical_rom_path, mutable_rom_copy
from tools.creator.model import jobs
from tools.creator.model.project import (
    BUILD_DIRECTORY,
    RECOVERY_FILE,
    CreatorError,
    CreatorProject,
    RomMissingError,
    check_rom,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RECORD = "text:0010"

pytestmark = pytest.mark.skipif(
    canonical_rom_path() is None, reason="the canonical Buu's Fury ROM is not present"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture
def rom(tmp_path) -> Path:
    return mutable_rom_copy(tmp_path)


@pytest.fixture
def project(tmp_path, rom) -> CreatorProject:
    return CreatorProject.create(rom, tmp_path / "My Game", "My Game")


def test_the_retail_rom_is_verified_and_another_file_is_refused(tmp_path, rom):
    assert check_rom(rom).compatible
    other = tmp_path / "other.gba"
    other.write_bytes(b"\0" * 4096)
    refused = check_rom(other)
    assert not refused.compatible and refused.detail
    assert not check_rom(tmp_path / "absent.gba").compatible


def test_a_new_project_is_a_folder_and_the_rom_is_only_read(tmp_path, rom):
    before = _sha256(rom)
    project = CreatorProject.create(rom, tmp_path / "My Game", "My Game")

    assert (project.directory / "project.toml").is_file()
    assert project.name == "My Game"
    assert project.build_status() == "none"
    assert not list(project.directory.rglob("*.gba"))
    assert _sha256(rom) == before
    with pytest.raises(CreatorError, match="already has files"):
        CreatorProject.create(rom, project.directory, "Again")


def test_text_is_found_edited_saved_and_still_there_after_reopening(project):
    record = project.record(RECORD)
    assert record.editable and record.original == "New Game"
    assert "New Game" in record.description

    project.set_text(RECORD, "Begin Quest")
    assert project.dirty
    project.save()
    assert not project.dirty

    reopened = CreatorProject.open(project.directory)
    assert reopened.record(RECORD).text == "Begin Quest"
    assert reopened.record(RECORD).changed
    assert not reopened.recovered


def test_spoken_dialogue_is_listed_read_only_with_its_reason(project):
    spoken = [row for row in project.records() if not row.editable]

    assert spoken and all(row.note for row in spoken)
    with pytest.raises(CreatorError, match="read-only"):
        project.set_text(spoken[0].key, "anything")


def test_undo_and_redo_step_one_edit(project):
    project.set_text(RECORD, "Begin Quest")
    project.undo()
    assert project.record(RECORD).text == "New Game" and not project.dirty
    project.redo()
    assert project.record(RECORD).text == "Begin Quest" and project.can_undo


def test_each_edit_is_its_own_undo_step_even_across_a_save(project):
    project.set_text(RECORD, "Second")
    project.save()
    project.set_text(RECORD, "Third")
    project.set_text(RECORD, "Fourth")

    project.undo()
    assert project.record(RECORD).text == "Third" and project.dirty
    project.undo()
    assert project.record(RECORD).text == "Second" and not project.dirty
    project.undo()
    assert project.record(RECORD).text == "New Game" and project.dirty


def test_checking_one_record_never_changes_the_answer_for_another(project):
    long_text = "y" * 127
    assert project.problem_with("text:0011", long_text) == ""

    for _keystroke in range(3):
        project.problem_with(RECORD, "x" * 127)
    project.set_text(RECORD, "x" * 127)
    project.undo()

    assert project.problem_with("text:0011", long_text) == ""


def test_discarding_returns_the_project_exactly_as_saved(project):
    project.set_text(RECORD, "Kept")
    project.save()
    project.set_text(RECORD, "Discard me")

    fresh = project.discard_changes()

    assert fresh.record(RECORD).text == "Kept"
    assert not fresh.dirty and not fresh.can_undo and not fresh.recovered
    assert not (fresh.directory / RECOVERY_FILE).exists()


def test_a_recovery_entry_the_game_cannot_store_is_left_out(project):
    (project.directory / RECOVERY_FILE).write_text(
        '{"text": {"text:0010": "{oops", "text:0011": "Fine"}}', encoding="utf-8"
    )
    reopened = CreatorProject.open(project.directory)

    reopened.restore_recovery()

    assert reopened.record(RECORD).text == "New Game"
    assert reopened.record("text:0011").text == "Fine"


def test_text_the_game_cannot_store_is_refused_at_the_edit(project):
    assert "control code" in project.problem_with(RECORD, "{oops")
    with pytest.raises(CreatorError, match="too long"):
        project.set_text(RECORD, "x" * 20000)
    assert project.record(RECORD).text == "New Game" and not project.dirty


def test_unsaved_edits_survive_a_killed_process(project, rom):
    script = (
        "import os, sys; from pathlib import Path;"
        "from tools.creator.model.project import CreatorProject;"
        "p = CreatorProject.open(Path(sys.argv[1]));"
        "p.set_text('text:0010', 'Typed before the crash'); os._exit(9)"
    )
    killed = subprocess.run(
        [sys.executable, "-c", script, str(project.directory)], cwd=REPOSITORY_ROOT
    )
    assert killed.returncode == 9

    reopened = CreatorProject.open(project.directory)
    assert reopened.recovered == {RECORD: "Typed before the crash"}
    assert reopened.record(RECORD).text == "New Game"
    reopened.restore_recovery()
    assert reopened.record(RECORD).text == "Typed before the crash" and reopened.dirty
    reopened.save()
    assert not (project.directory / RECOVERY_FILE).exists()
    assert CreatorProject.open(project.directory).record(RECORD).text == "Typed before the crash"


def test_a_project_whose_rom_moved_asks_for_it_and_refuses_the_wrong_one(tmp_path, project, rom):
    moved = tmp_path / "moved.gba"
    shutil.move(rom, moved)
    with pytest.raises(RomMissingError):
        CreatorProject.open(project.directory)
    assert CreatorProject.open(project.directory, moved).rom_path == moved
    with pytest.raises(CreatorError, match="not a DragonByte Z project"):
        CreatorProject.open(tmp_path)


def test_build_is_deterministic_tracks_staleness_and_never_touches_the_rom(project, rom):
    before = _sha256(rom)
    project.set_text(RECORD, "Begin Quest")
    project.save()

    assert jobs.run_blocking("validate", project.directory, rom, project.output)["ok"]
    assert project.build_status() == "none"
    first = jobs.run_blocking("build", project.directory, rom, project.output)
    assert first["ok"] and Path(first["output"]).parent.name == BUILD_DIRECTORY
    assert _sha256(project.output) == first["sha256"] != before
    assert project.build_status() == "current"

    second = jobs.run_blocking("build", project.directory, rom, project.output)
    assert second["sha256"] == first["sha256"]

    project.set_text(RECORD, "Begin Quest 2")
    assert project.build_status() == "outdated"
    project.save()
    assert project.build_status() == "outdated"
    third = jobs.run_blocking("build", project.directory, rom, project.output)
    assert third["ok"] and third["sha256"] != first["sha256"]
    assert project.build_status() == "current"
    assert _sha256(rom) == before


def test_a_failed_build_names_the_record_and_keeps_the_last_good_rom(project, rom):
    good = jobs.run_blocking("build", project.directory, rom, project.output)
    strings = project.directory / "text" / "strings.toml"
    source = strings.read_text(encoding="utf-8")
    broken = source.replace('[text."text:0010"]\ntext = "New Game"\n', "")
    assert broken != source
    strings.write_text(broken, encoding="utf-8")

    failed = jobs.run_blocking("build", project.directory, rom, project.output)

    assert not failed["ok"] and "output" not in failed
    assert failed["problems"][0]["record"] == RECORD
    assert "Game text 10" in failed["problems"][0]["message"]
    assert _sha256(project.output) == good["sha256"]
    assert strings.read_text(encoding="utf-8") == broken


def test_an_interrupted_build_leaves_a_project_that_builds_again(project, rom):
    pending = project.output.with_name(project.output.name + ".pending")
    pending.parent.mkdir(parents=True)
    pending.write_bytes(b"half a rom")
    job = jobs.write_job("build", project.directory, rom, project.output)

    assert "stopped before it finished" in jobs.read_result(job, 1)["error"]
    assert jobs.run_blocking("build", project.directory, rom, project.output)["ok"]
    assert not pending.exists()


def test_the_first_scene_reference_project_opens_and_builds_reproducibly(tmp_path, rom):
    directory = tmp_path / "first-scene"
    shutil.copytree(REPOSITORY_ROOT / "examples" / "first-scene", directory)
    project = CreatorProject.open(directory, rom)

    first = jobs.run_blocking("build", directory, rom, project.output)
    second = jobs.run_blocking("build", directory, rom, project.output)

    assert first["ok"] and first["sha256"] == second["sha256"]


def test_the_whole_loop_runs_through_the_real_window(tmp_path, rom):
    pytest.importorskip("PySide6")
    steps = _selftest([sys.executable, "-m", "tools.creator"], tmp_path, rom, REPOSITORY_ROOT)

    assert {"keyboard-type-and-undo", "play", "rebuild"} <= steps


def _selftest(command: list[str], tmp_path: Path, rom: Path, cwd: Path) -> set[str]:
    """Run the loop with a stand-in emulator; return the steps, all of which passed."""
    work = tmp_path / "work"
    emulator = tmp_path / "emulator.cmd"
    emulator.write_text("@ping -n 8 127.0.0.1 >nul\n", encoding="utf-8")
    (work / "settings").mkdir(parents=True)
    (work / "settings" / "settings.json").write_text(
        json.dumps({"emulator": str(emulator)}), encoding="utf-8"
    )
    report = tmp_path / "report.json"
    finished = subprocess.run(
        [
            *command,
            "--selftest", str(report), "--rom", str(rom), "--workdir", str(work),
            "--play-seconds", "2",
        ],
        cwd=cwd,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        timeout=300,
    )
    document = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}
    assert finished.returncode == 0 and document.get("passed"), document
    return {step["step"] for step in document["steps"]}


def test_the_packaged_executable_starts_and_runs_the_whole_loop(tmp_path, rom):
    executable = REPOSITORY_ROOT / "build" / "packaged" / "DragonByte Z" / "DragonByte Z.exe"
    if not executable.is_file():
        pytest.skip("no packaged build; run scripts/build-dragonbyte-z.ps1")

    assert "play" in _selftest([str(executable)], tmp_path, rom, tmp_path)
