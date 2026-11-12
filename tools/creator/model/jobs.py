"""Validate and Build as child-process jobs, so an SDK failure cannot end the editor.

The parent writes a job file and starts this program again with ``--sdk-job``.
The child does the work and writes a result file. A child that dies leaves no
result, which the parent reports as a failed job.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

from tools.webfoot import events
from tools.webfoot.build import build_project, validate_project
from tools.webfoot.catalog import load_catalog

from .library import write_library
from .project import (
    BUILD_STATE,
    _read_json,
    _write_json,
    friendly_problem,
    problem_record,
    source_digest,
)

JOB_FLAG = "--sdk-job"
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def job_command(job: Path) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, JOB_FLAG, str(job)]
    return [sys.executable, "-m", "tools.creator", JOB_FLAG, str(job)]


def job_directory() -> str | None:
    return None if getattr(sys, "frozen", False) else str(REPOSITORY_ROOT)


def write_job(action: str, project: Path, rom: Path, output: Path) -> Path:
    job = Path(project) / ".dragonbyte" / f"{action}-job.json"
    result = job.with_name(f"{action}-result.json")
    result.unlink(missing_ok=True)
    _write_json(
        job,
        {
            "action": action,
            "project": str(project),
            "rom": str(rom),
            "output": str(output),
            "result": str(result),
        },
    )
    return job


def read_result(job: Path, exit_code: int | None = None) -> dict:
    document = _read_json(job) or {}
    result = _read_json(Path(document.get("result", ""))) if document else None
    if result is None:
        return {
            "ok": False,
            "problems": [],
            "error": (
                "The job stopped before it finished"
                + (f" (exit code {exit_code})" if exit_code is not None else "")
                + ". Your project is unchanged. Try again."
            ),
        }
    return result


def run_blocking(action: str, project: Path, rom: Path, output: Path) -> dict:
    job = write_job(action, project, rom, output)
    finished = subprocess.run(job_command(job), cwd=job_directory(), check=False)
    return read_result(job, finished.returncode)


def _problems(messages) -> list[dict]:
    return [
        {"record": problem_record(message), "message": friendly_problem(message)}
        for message in messages
    ]


def _run(job: dict) -> dict:
    project, rom, output = Path(job["project"]), Path(job["rom"]), Path(job["output"])
    if job["action"] == "library":
        return write_library(rom, project)
    catalog = load_catalog(None)
    report = validate_project(project, rom, catalog)
    result = {"ok": report.passed, "problems": _problems(report.problems), "error": ""}
    if job["action"] != "build" or not report.passed:
        return result
    output.parent.mkdir(parents=True, exist_ok=True)
    pending = output.with_name(output.name + ".pending")
    pending.unlink(missing_ok=True)
    build_project(project, rom, pending, catalog, manifest_path=None)
    os.replace(pending, output)
    trace = events.trace_path(pending)
    events.trace_path(output).unlink(missing_ok=True)
    if trace.exists():
        os.replace(trace, events.trace_path(output))
    sha256 = hashlib.sha256(output.read_bytes()).hexdigest()
    _write_json(
        project / BUILD_STATE,
        {"digest": source_digest(project), "output": output.name, "sha256": sha256},
    )
    return {**result, "output": str(output), "sha256": sha256}


def run_job(job_path: Path) -> int:
    """The child's whole life: run one job, write its result, exit 0 if it ran."""
    job = json.loads(Path(job_path).read_text(encoding="utf-8"))
    try:
        result = _run(job)
    except Exception as exc:
        result = {
            "ok": False,
            "problems": _problems([str(exc)]),
            "error": "",
            "trace": traceback.format_exc(),
        }
    _write_json(Path(job["result"]), result)
    return 0
