"""The whole authoring loop, driven through the real window and reported as JSON.

It calls the same slots the toolbar calls, on the real window, with a real ROM,
and saves a screenshot at every step. It runs identically from source and from
the packaged executable, which is what proves the package carries everything.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest

from .model.project import RECOVERY_FILE, CreatorProject

RECORD = "text:0010"
JOB_TIMEOUT_MS = 120_000


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _wait_for_job(window) -> dict:
    loop = QEventLoop()
    outcome: dict = {}
    connection = window.job_finished.connect(
        lambda _action, result: (outcome.update(result), loop.quit())
    )
    QTimer.singleShot(JOB_TIMEOUT_MS, loop.quit)
    loop.exec()
    window.job_finished.disconnect(connection)
    return outcome


def run_selftest(app, window, options) -> int:
    workdir = Path(options.workdir)
    shots = workdir / "screenshots"
    shots.mkdir(parents=True, exist_ok=True)
    steps: list[dict] = []
    rom_before = _sha256(options.rom)

    def step(name: str, passed: bool, detail: str = "") -> None:
        app.processEvents()
        shot = shots / f"{len(steps) + 1:02d}-{name}.png"
        window.grab().save(str(shot))
        steps.append({"step": name, "passed": bool(passed), "detail": detail, "screenshot": shot.name})

    def edit(text: str) -> bool:
        window.editor.select(RECORD)
        window.editor.editor.setPlainText(text)
        return window.editor.apply_pending()

    step("launch", window.isVisible() and window.project is None)
    directory = workdir / "Self Test"
    step("new-project", window.create_project(options.rom, directory, "Self Test"), str(directory))
    project = window.project
    original = project.record(RECORD).original

    step("edit-text", edit("DBZ Test") and project.dirty, f"{original!r} -> 'DBZ Test'")
    window.undo()
    undone = project.record(RECORD).text == original
    window.redo()
    step("undo-redo", undone and project.record(RECORD).text == "DBZ Test")
    saved = window.save() and 'text = "DBZ Test"' in (directory / "text" / "strings.toml").read_text(encoding="utf-8")
    step("save", saved and not project.dirty)

    window.editor.editor.setFocus()
    QTest.keyClicks(window.editor.editor, "Go ")
    typed = window.editor.apply_pending() and project.record(RECORD).text == "Go DBZ Test"
    QTest.keySequence(window.editor.editor, QKeySequence(QKeySequence.StandardKey.Undo))
    QTest.keySequence(window.editor.editor, QKeySequence(QKeySequence.StandardKey.Redo))
    QTest.keySequence(window.editor.editor, QKeySequence(QKeySequence.StandardKey.Redo))
    QTest.keySequence(window.editor.editor, QKeySequence(QKeySequence.StandardKey.Undo))
    step(
        "keyboard-type-and-undo",
        typed
        and project.record(RECORD).text == "DBZ Test"
        and not project.dirty
        and not window.messages,
        project.record(RECORD).text,
    )

    window.build()
    first = _wait_for_job(window)
    step("build", bool(first.get("ok")) and project.build_status() == "current", json.dumps(first))

    played = True
    if options.play_seconds:
        window.play()
        deadline = time.monotonic() + options.play_seconds
        while time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.05)
        emulator = window.emulator_process
        played = emulator is not None and emulator.poll() is None
        step("play", played, f"emulator pid {getattr(emulator, 'pid', None)}")
        if emulator is not None:
            emulator.terminate()

    edit("DBZ Test 2")
    step("edit-again", project.build_status() == "outdated")
    window.build()
    second = _wait_for_job(window)
    step(
        "rebuild",
        bool(second.get("ok")) and second.get("sha256") != first.get("sha256"),
        json.dumps(second),
    )

    edit("{broken")
    step("validation-feedback", "control code" in window.editor.feedback.text(), window.editor.feedback.text())
    edit("Unsaved after a crash")
    recovery = (directory / RECOVERY_FILE).is_file()
    reopened = CreatorProject.open(directory)
    step("recovery-file", recovery and reopened.recovered.get(RECORD) == "Unsaved after a crash")

    step("source-rom-unchanged", _sha256(options.rom) == rom_before, rom_before)
    report = {
        "title": window.windowTitle(),
        "passed": all(item["passed"] for item in steps),
        "steps": steps,
        "messages": window.messages,
        "output": str(project.output),
    }
    Path(options.selftest).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    window.project.discard_recovery()
    window.project = None
    window.close()
    return 0 if report["passed"] else 1
