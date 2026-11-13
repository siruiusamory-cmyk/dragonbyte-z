from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from tests.gates import REPOSITORY_ROOT, disconnect_disposable_hooks

SCRIPT = REPOSITORY_ROOT / "scripts" / "pre-push-gate.ps1"
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")

STUBCUSTOMIZE = '''import os
import sys

verb = list(getattr(sys, "orig_argv", sys.argv))[1:3]
with open(os.environ["STUB_CALLS"], "a", encoding="utf-8") as handle:
    handle.write(" ".join(verb) + "\\n")
sys.stdout.flush()
os._exit(int(os.environ.get("STUB_EXIT", "0")))
'''


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=guard@example.invalid", "-c", "user.name=guard", *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


@pytest.fixture
def gate(tmp_path):
    if os.name != "nt" or not POWERSHELL:
        pytest.skip("the pre-push gate is a PowerShell script and needs PowerShell")
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy2(SCRIPT, repo / "scripts" / "pre-push-gate.ps1")
    _git(repo, "init", "-q")
    disconnect_disposable_hooks(repo)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    stub = tmp_path / "stub"
    stub.mkdir()
    (stub / "sitecustomize.py").write_text(STUBCUSTOMIZE, encoding="utf-8")
    calls = tmp_path / "calls.txt"
    calls.write_text("", encoding="utf-8")

    def run(where: Path = repo, exit_code: str = "0", shas: tuple[str, ...] = ()):
        environment = dict(os.environ)
        environment.update({"PYTHONPATH": str(stub), "STUB_CALLS": str(calls), "STUB_EXIT": exit_code})
        return subprocess.run(
            [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             str(where / "scripts" / "pre-push-gate.ps1"), "-Python", sys.executable, *shas],
            capture_output=True,
            text=True,
            env=environment,
            timeout=120,
        )

    def stamp(where: Path = repo) -> Path:
        git_dir = Path(_git(where, "rev-parse", "--git-dir"))
        if not git_dir.is_absolute():
            git_dir = where / git_dir
        return git_dir / "pre-push-gate" / _git(where, "rev-parse", "HEAD")

    def ran() -> list[str]:
        return calls.read_text(encoding="utf-8").split()

    return repo, run, stamp, ran


def test_a_green_run_stamps_head_and_the_next_run_executes_nothing(gate):
    repo, run, stamp, ran = gate
    first = run()
    assert first.returncode == 0, first.stdout + first.stderr
    assert ran().count("pytest") == 1 and ran().count("tools.quality.architecture") == 1, ran()
    assert stamp().is_file(), first.stdout
    second = run()
    assert second.returncode == 0, second.stdout + second.stderr
    assert "already passed; skipped" in second.stdout, second.stdout
    assert ran().count("pytest") == 1, "the stamped run invoked the interpreter again"


def test_a_red_run_writes_no_stamp_and_runs_again(gate):
    repo, run, stamp, ran = gate
    red = run(exit_code="1")
    assert red.returncode == 1, red.stdout
    assert "pre-push-gate: FAIL" in red.stdout, red.stdout
    assert not stamp().exists()
    again = run(exit_code="1")
    assert again.returncode == 1 and ran().count("pytest") == 2, ran()


def test_a_modified_tracked_file_writes_no_stamp(gate):
    repo, run, stamp, ran = gate
    (repo / "scripts" / "pre-push-gate.ps1").write_bytes(SCRIPT.read_bytes() + b"\n")
    result = run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no stamp was written" in result.stdout, result.stdout
    assert not stamp().exists()


def test_a_new_commit_is_not_covered_by_the_previous_stamp(gate):
    repo, run, stamp, ran = gate
    assert run().returncode == 0
    old = stamp()
    (repo / "note.txt").write_text("next\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "next")
    result = run()
    assert result.returncode == 0, result.stdout
    assert ran().count("pytest") == 2, ran()
    assert old.is_file() and stamp().is_file() and stamp() != old


def test_a_linked_worktree_keeps_its_stamp_in_its_own_git_dir(gate, tmp_path):
    repo, run, stamp, ran = gate
    linked = tmp_path / "linked"
    _git(repo, "worktree", "add", "-q", "--detach", str(linked))
    result = run(linked)
    assert result.returncode == 0, result.stdout + result.stderr
    assert stamp(linked).is_file(), result.stdout
    assert "worktrees" in stamp(linked).parts, stamp(linked)
    assert not stamp(repo).exists()
    assert "already passed" in run(linked).stdout


def test_a_pushed_commit_that_is_not_head_and_has_no_stamp_is_refused(gate):
    repo, run, stamp, ran = gate
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "note.txt").write_text("next\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "next")
    result = run(shas=(base,))
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"REFUSED: pushed commit {base} is not the verified HEAD" in result.stdout, result.stdout
    assert ran() == [], ran()
    assert not stamp().exists()


def test_a_pushed_commit_with_a_stamp_is_accepted_without_running(gate):
    repo, run, stamp, ran = gate
    assert run().returncode == 0
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "note.txt").write_text("next\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "next")
    result = run(shas=(base,))
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"{base} already passed; verified by its stamp" in result.stdout, result.stdout
    assert ran().count("pytest") == 1, ran()
    assert not stamp().exists()


def test_a_pushed_head_is_gated_and_stamped(gate):
    repo, run, stamp, ran = gate
    head = _git(repo, "rev-parse", "HEAD")
    result = run(shas=(head,))
    assert result.returncode == 0, result.stdout + result.stderr
    assert ran().count("pytest") == 1, ran()
    assert stamp().is_file()


def test_a_branch_deletion_is_skipped(gate):
    repo, run, stamp, ran = gate
    result = run(shas=("0" * 40,))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "only branch deletions" in result.stdout, result.stdout
    assert ran() == [], ran()
    assert not stamp().exists()


def test_a_pushed_head_with_a_modified_tracked_file_is_refused_and_not_stamped(gate):
    repo, run, stamp, ran = gate
    head = _git(repo, "rev-parse", "HEAD")
    (repo / "scripts" / "pre-push-gate.ps1").write_bytes(SCRIPT.read_bytes() + b"\n")
    result = run(shas=(head,))
    assert result.returncode == 1, result.stdout + result.stderr
    assert "REFUSED" in result.stdout and "tracked files are modified" in result.stdout, result.stdout
    assert ran() == [], ran()
    assert not stamp().exists()
