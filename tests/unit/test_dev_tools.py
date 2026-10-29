"""The developer tools' guards: citations, commit messages, the probe worktree.

Each tool exists because a measured failure cost a session, so each guard drives its
own failure rather than asserting that the tool exists.

TWO LAYERS, because CI is Linux and always will be. A `.ps1` tool cannot execute
there, so its behavioural guard skips on a host without PowerShell and a TEXT guard
(a pure-Python assertion over the script's own bytes, the pattern RETRO-ENV-001
established in tests/unit/test_ticket_worktree_setup.py) runs everywhere and pins
the invariant the behaviour depends on. The behavioural proof for a `.ps1` tool is
a Windows run, recorded in the ticket's report; the text guard is the regression
net in CI. The Python tools (check_citations, merge_mr, review_queue_index) keep
real behaviour tests that run on Linux, and there is no skip in them.

The skip is proved rather than assumed: test_the_behavioural_powershell_tests_skip
makes the lookup absent and asserts the tests SKIP instead of failing.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from tests.gates import disconnect_disposable_hooks

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.dev import check_citations as cc  # noqa: E402
from tools.dev import merge_mr as mm  # noqa: E402

COMMIT_MSG = REPOSITORY_ROOT / "tools" / "dev" / "commit_msg.ps1"
PROBE_WORKTREE = REPOSITORY_ROOT / "tools" / "dev" / "probe_worktree.ps1"
SWEEP = REPOSITORY_ROOT / "tools" / "dev" / "worktree_owners.ps1"
CUTTER = REPOSITORY_ROOT / "scripts" / "new-ticket-worktree.ps1"


def _powershell() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell")


def _require_powershell() -> str:
    """The host, or a named skip. CI is Linux, where a `.ps1` cannot run."""
    shell = _powershell()
    if shell is None:
        pytest.skip(
            "no PowerShell host on this platform, so the .ps1 tool cannot be "
            "executed; the text guards in this file hold its invariants in CI and "
            "the behaviour is proved on Windows"
        )
    return shell


def _require_windows_powershell() -> str:
    """Windows PowerShell 5.1 by name, for the one test about ITS BOM behaviour.

    `pwsh` is not the same shell: it has `-Encoding utf8NoBOM` and its `utf8` writes
    no byte-order mark, so a probe that preferred `pwsh` would find no failure to
    reproduce and fail its own assertion on a machine that has it.
    """
    shell = shutil.which("powershell.exe") or shutil.which("powershell")
    if shell is None or "powershell.exe" not in Path(shell).name.lower():
        pytest.skip(
            "Windows PowerShell 5.1 is not on this platform; this test asserts the "
            "BOM behaviour of that shell specifically"
        )
    return shell


def _require_python() -> None:
    if not Path(sys.executable).exists():
        pytest.skip("this interpreter is not on disk, so it cannot be run as a child")


# --- B4: check_citations -----------------------------------------------------


@pytest.fixture
def cited_tree(tmp_path: Path) -> dict:
    """A tree with one known-good citation, one moved symbol and one orphan."""
    root = tmp_path / "root"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "alpha.py").write_text(
        "\n".join(
            [
                "def first():",
                "    return 1",
                "",
                "def keep_me():",
                "    return 2",
                "",
                "# padding",
                "def last():",
                "    return 3",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "pkg" / "beta.py").write_text("X = 1\n", encoding="utf-8")
    return {"root": root}


def test_a_citation_whose_symbol_is_on_the_line_resolves(cited_tree):
    text = "`pkg/alpha.py:4` `keep_me` is defined there.\n"
    findings = cc.check(text, cited_tree["root"], cited_tree["root"])
    assert [f["state"] for f in findings] == ["RESOLVES"], findings


def test_a_citation_whose_symbol_moved_reports_the_new_line(cited_tree):
    """The measured case: the debt node's site had moved and nothing said so."""
    text = "`pkg/alpha.py:2` `keep_me` is defined there.\n"
    findings = cc.check(text, cited_tree["root"], cited_tree["root"])
    assert [f["state"] for f in findings] == ["MOVED"], findings
    assert "4" in findings[0]["why"], findings


def test_a_symbol_nowhere_in_the_file_is_an_orphan(cited_tree):
    text = "`pkg/alpha.py:2` `gone_forever` was defined there.\n"
    findings = cc.check(text, cited_tree["root"], cited_tree["root"])
    assert [f["state"] for f in findings] == ["ORPHAN"], findings


def test_a_line_past_the_end_of_the_file_is_an_orphan(cited_tree):
    """The ledger row's shape: three citations in a file that has since grown."""
    text = "`pkg/alpha.py:7849` names the `_saved` state.\n"
    findings = cc.check(text, cited_tree["root"], cited_tree["root"])
    assert [f["state"] for f in findings] == ["ORPHAN"], findings
    assert "past the end" in findings[0]["why"], findings


def test_a_path_that_does_not_exist_is_an_orphan(cited_tree):
    text = "`workbench/app.py:251-256` `on_project_mutated`\n"
    findings = cc.check(text, cited_tree["root"], cited_tree["root"])
    assert [f["state"] for f in findings] == ["ORPHAN"], findings
    assert "no such file" in findings[0]["why"], findings


def test_a_bare_filename_resolves_when_the_tree_has_exactly_one(cited_tree):
    text = "`beta.py:1` `X` is set there.\n"
    findings = cc.check(text, cited_tree["root"], cited_tree["root"])
    assert [f["state"] for f in findings] == ["RESOLVES"], findings


def test_a_citation_with_no_named_symbol_only_checks_the_extent(cited_tree):
    """`editors.py:345-378` names nothing, so the answer is the extent alone."""
    text = "`pkg/alpha.py:1-9` is the whole file.\n"
    findings = cc.check(text, cited_tree["root"], cited_tree["root"])
    assert [f["state"] for f in findings] == ["RESOLVES"], findings
    assert "no symbol named" in findings[0]["why"], findings


def test_prose_that_is_not_a_citation_is_not_reported(cited_tree):
    text = "The player is at gba:1 and the maps:440 count is published.\n"
    assert cc.check(text, cited_tree["root"], cited_tree["root"]) == []


def test_a_release_word_in_backticks_is_not_read_as_a_symbol(cited_tree):
    """`Merged` is prose, not an identifier: reading it as one invented findings."""
    text = "`pkg/alpha.py:1` `Merged`\n"
    findings = cc.check(text, cited_tree["root"], cited_tree["root"])
    assert [f["state"] for f in findings] == ["RESOLVES"], findings


def test_the_checker_exits_non_zero_for_orphans_only_when_asked(tmp_path: Path):
    _require_python()
    document = tmp_path / "prose.md"
    document.write_text("`missing/nothing.py:3` `gone`\n", encoding="utf-8")
    quiet = subprocess.run(
        [sys.executable, "-m", "tools.dev.check_citations", str(document)],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
    )
    failing = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.dev.check_citations",
            "--fail-on-orphan",
            str(document),
        ],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
    )
    assert quiet.returncode == 0, quiet.stdout + quiet.stderr
    assert failing.returncode == 1, failing.stdout + failing.stderr
    assert "ORPHAN" in failing.stdout


def test_the_checker_requires_an_explicit_target():
    _require_python()
    result = subprocess.run(
        [sys.executable, "-m", "tools.dev.check_citations"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, "a whole-tree default is the noise this avoids"


# --- B9a: commit_msg.ps1 -----------------------------------------------------


def _commit_msg(*args: str) -> subprocess.CompletedProcess:
    shell = _require_powershell()
    return subprocess.run(
        [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(COMMIT_MSG), *args],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
    )


def test_the_message_writer_writes_no_byte_order_mark():
    """`Set-Content -Encoding utf8` writes one; it has broken line 1 before."""
    _require_powershell()
    message = 'Subject with "quotes" and an apostrophe: it does not split'
    result = _commit_msg("-Message", message, "-NoCommit")
    assert result.returncode == 0, result.stdout + result.stderr
    path = Path(result.stdout.split("message written: ", 1)[1].split(" (no BOM", 1)[0])
    try:
        raw = path.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), raw[:3]
        assert raw.decode("utf-8") == message, (
            "the message must survive verbatim: quotes, apostrophe and all")
    finally:
        path.unlink(missing_ok=True)


def test_the_writer_refuses_an_empty_message():
    _require_powershell()
    for empty in ("", "   "):
        result = _commit_msg("-Message", empty, "-NoCommit")
        assert result.returncode != 0, result.stdout + result.stderr
        assert "empty" in (result.stdout + result.stderr)


def test_the_no_bom_claim_is_driven_to_failure():
    """The premise of the tool, watched failing: `utf8` writes the marker.

    Same shape as the retro's measurement: write the same message the other way and
    read the first three bytes. Windows PowerShell 5.1 by name, because `pwsh`'s
    `utf8` writes no mark and would find nothing to reproduce.
    """
    shell = _require_windows_powershell()
    target = Path(tempfile.gettempdir()) / "dev-tools-test-bom.txt"
    script = target.with_suffix(".ps1")
    script.write_text(
        f"Set-Content -LiteralPath '{target}' -Value 'subject' -Encoding utf8\n",
        encoding="utf-8",
    )
    try:
        result = subprocess.run(
            [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert target.read_bytes().startswith(b"\xef\xbb\xbf"), (
            "the failure the tool exists to prevent did not reproduce, so the "
            "no-BOM guard proves nothing")
    finally:
        target.unlink(missing_ok=True)
        script.unlink(missing_ok=True)


# --- the .ps1 invariants, as TEXT (this is what runs in Linux CI) -------------


def test_the_message_writer_keeps_the_no_bom_spelling():
    """The bytes-level invariant a Linux runner can still check.

    `[System.IO.File]::WriteAllText` with `UTF8Encoding($false)` is the whole
    mechanism. `Set-Content -Encoding utf8` appears ONCE, in the comment that names
    the defect: an executable occurrence is what the guard forbids, so the assertion
    is on the argument form rather than on the words.
    """
    text = COMMIT_MSG.read_text(encoding="utf-8")
    assert "[System.IO.File]::WriteAllText($MessageFile, $Message" in text
    assert "New-Object System.Text.UTF8Encoding($false)" in text
    assert "-LiteralPath $MessageFile -Value" not in text
    assert re.search(r"^\s*Set-Content[^\n]*-Encoding\s+utf8\s*$", text, re.M) is None
    assert "-Encoding utf8NoBOM" not in text
    assert "throw 'commit_msg.ps1: the message is empty" in text


def test_the_bom_failure_probe_names_the_shell_whose_utf8_writes_a_mark():
    """`pwsh` is not that shell, so a probe that preferred it would fail itself."""
    text = Path(__file__).read_text(encoding="utf-8")
    assert 'shutil.which("powershell.exe")' in text


def test_the_sweep_keeps_the_clean_filter_and_the_three_classes():
    """`--stdin` skips the clean filter and made every file look `authored`."""
    text = SWEEP.read_text(encoding="utf-8")
    # The path form applies the clean filter; the piped form does not.
    assert "hash-object -- $relative" in text
    assert "hash-object --stdin" not in text
    for classification in ("carries-master", "authored", "conflicted"):
        assert f"'{classification}'" in text
    assert "'cat-file', '-e'" in text


def test_the_cutter_ends_with_its_own_exit_code():
    assert CUTTER.read_text(encoding="utf-8").rstrip().endswith("exit 0")


def test_the_probe_refuses_with_both_digests():
    text = PROBE_WORKTREE.read_text(encoding="utf-8")
    assert "Get-FileHash -Algorithm SHA256 -LiteralPath" in text
    assert "source sha256" in text
    assert "copy   sha256" in text
    assert "MISMATCH" in text
    assert "exit 3" in text


@pytest.mark.skipif(
    _powershell() is not None,
    reason="the skip path is only reachable on a host without PowerShell",
)
def test_every_powershell_behavioural_guard_skips_without_a_host(monkeypatch):
    """Prove the skip, not just write it: remove the lookup and assert SKIP.

    Without this, a wrong edit to the skip helper would fail on Linux CI and pass
    on this machine, which is the worst direction. With it, the Linux path is
    exercised here.
    """
    monkeypatch.setattr(shutil, "which", lambda name, *args, **kwargs: None)
    assert _powershell() is None
    for call in (
        _require_powershell,
        _require_windows_powershell,
    ):
        with pytest.raises(pytest.skip.Exception) as caught:
            call()
        assert "no PowerShell host" in str(caught.value) or "Windows PowerShell" in str(
            caught.value
        )


def test_the_launcher_file_declares_the_same_skip_shape():
    """The launcher's guard must skip rather than fail on a host without PowerShell."""
    text = (REPOSITORY_ROOT / "tests" / "unit" / "test_mgba_extra_script.py").read_text(
        encoding="utf-8"
    )
    assert "def _require_host() -> str:" in text
    assert "pytest.skip(" in text[text.index("def _require_host") : text.index("def test_omitting")]
    assert "if shutil.which(\"pwsh\") is None and shutil.which(\"powershell\") is None:" in text


SKIP_PLUGIN = """
import shutil as _shutil

_real_which = _shutil.which


def _no_powershell(name, *args, **kwargs):
    if str(name).lower() in {"pwsh", "powershell", "powershell.exe"}:
        return None
    return _real_which(name, *args, **kwargs)


_shutil.which = _no_powershell
"""


def test_the_behavioural_powershell_tests_skip_rather_than_fail(tmp_path: Path):
    """The Linux path, exercised here: make the lookup absent and run them.

    A real subprocess with `shutil.which` neutered is the only way to see the skip
    happen, because these tests find a host on this machine. Without this, the skip
    could be broken for months and only Linux CI would know.
    """
    _require_python()
    plugin = tmp_path / "no_powershell.py"
    plugin.write_text(SKIP_PLUGIN, encoding="utf-8")
    nodes = [
        "tests/unit/test_dev_tools.py::test_the_message_writer_writes_no_byte_order_mark",
        "tests/unit/test_dev_tools.py::test_the_writer_refuses_an_empty_message",
        "tests/unit/test_dev_tools.py::test_the_probe_worktree_copies_and_verifies_when_the_bytes_match",
    ]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *nodes,
            "-q",
            "-p",
            "no:cacheprovider",
            "--no-header",
            "-p",
            "no_powershell",
        ],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(tmp_path)},
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "3 skipped" in output, output
    # pytest prints "reported, never failed" in every summary, so the check is for a
    # FAILED node id rather than for the word.
    assert "FAILED " not in output, output
    assert "ERROR " not in output, output



# --- B5: the QA probe's --rom flag -------------------------------------------


def test_the_qa_probe_resolves_a_named_rom_without_reading_an_image(tmp_path: Path):
    """A worktree has no `roms/`, so the probe has to be told where the image is.

    No image is opened: the flag's contract is the resolved path, which the harness
    only ever reads when a state runs.
    """
    image = tmp_path / "some-image.gba"
    image.write_bytes(b"not really a rom, and never read")
    sys.path.insert(0, str(REPOSITORY_ROOT))
    from tools.qa import visual_pass_capture as vpc

    original = vpc.ROM
    try:
        assert vpc.main(["--rom", str(image), "--list"]) == 0
        assert vpc.ROM == image
    finally:
        vpc.ROM = original


def test_the_qa_probe_refuses_a_rom_path_that_is_not_a_file(tmp_path: Path, capsys):
    from tools.qa import visual_pass_capture as vpc

    # argparse's own error path: it prints the refusal and exits 2.
    with pytest.raises(SystemExit) as excinfo:
        vpc.main(["--rom", str(tmp_path / "absent.gba"), "--list"])
    assert excinfo.value.code == 2
    assert "--rom names no file" in capsys.readouterr().err


def test_the_qa_probe_still_defaults_to_the_env_override():
    """The env override is the half that already existed; the flag is the other."""
    source = (REPOSITORY_ROOT / "tools" / "qa" / "visual_pass_capture.py").read_text(
        encoding="utf-8"
    )
    assert '"DBZ_QA_ROM"' in source
    assert '"DBZ_QA_ATLAS_DIR"' in source
    assert "ROM = args.rom" in source


# --- B7: the review-queue index ----------------------------------------------


def test_the_review_queue_index_is_read_only_over_the_queue(tmp_path: Path):
    """It lives outside the repository, so this is the only guard it can have.

    The queue is redirected to a fixture directory: the real one belongs to other
    lanes and must not be read or written by a test.
    """
    queue = tmp_path / "review-queue"
    (queue / "requests").mkdir(parents=True)
    (queue / "results").mkdir()
    (queue / "claimed").mkdir()
    (queue / "requests" / "TICKET-001-20261012-010000.json").write_text(
        json.dumps(
            {
                "review_id": "TICKET-001-20261012-010000",
                "ticket": "TICKET-001",
                "review_sha": "a" * 40,
                "worktree": r"C:\worktrees\example",
            }
        ),
        encoding="utf-8",
    )
    (queue / "claimed" / "TICKET-001-20261012-010000").write_text("", encoding="utf-8")
    (queue / "results" / "TICKET-001-20261012-010000.md").write_text("PASS\n", encoding="utf-8")
    before = {
        p.relative_to(queue): p.read_bytes()
        for p in queue.rglob("*")
        if p.is_file()
    }
    from tools.dev import review_queue_index as rqi

    report = rqi.build(queue)
    assert [row["review_id"] for row in report["requests"]] == ["TICKET-001-20261012-010000"]
    row = report["requests"][0]
    assert row["claimed"] is True
    assert row["verdict"] == "PASS"
    assert row["age_hours"] is not None
    after = {
        p.relative_to(queue): p.read_bytes()
        for p in queue.rglob("*")
        if p.is_file()
    }
    assert before == after, "the index must not write into the queue"


def test_the_review_queue_index_default_path_is_outside_the_repository():
    from tools.dev import review_queue_index as rqi

    assert "review-queue" in str(rqi.DEFAULT_QUEUE)
    assert REPOSITORY_ROOT not in rqi.DEFAULT_QUEUE.parents


def test_the_queue_verdict_is_the_last_line_not_the_first_word(tmp_path: Path):
    """The reviewer's bite: prose saying PASS above a BLOCKED verdict read as PASS.

    Every result file in this project ends with its verdict line, so that line is
    the answer and nothing above it is.
    """
    from tools.dev import review_queue_index as rqi

    result = tmp_path / "TICKET-001-20261012-010000.md"
    result.write_text(
        "- SC1: the earlier round PASSed on a different SHA\n"
        "- SC2: this one did not\n"
        "\n"
        "BLOCKED\n",
        encoding="utf-8",
    )
    assert rqi.verdict_of(result) == "BLOCKED"
    result.write_text("PASS\n", encoding="utf-8")
    assert rqi.verdict_of(result) == "PASS"
    assert rqi.verdict_of(None) is None


def test_a_negative_age_is_labelled_not_printed_bare():
    from tools.dev import review_queue_index as rqi

    assert rqi.age_label(2.5) == "2.5h"
    assert rqi.age_label(None) == "?"
    label = rqi.age_label(-1.5)
    assert label.startswith("in the future")
    assert "-1.5h" not in label


# --- B9b: the pinned-SHA merge wrapper ---------------------------------------


REPO = mm.DEFAULT_REPO
SHA = "a" * 40


class _FakeGh:
    def __init__(
        self,
        merges: list[tuple[int, str]],
        lands_on: list[int],
        closes_on: list[int] | None = None,
        moves_head_after: int | None = None,
        checks: tuple[int, str] | None = None,
    ):
        self.checks = checks if checks is not None else (1, "no checks reported on this branch")
        self.state = {"state": "OPEN", "headRefOid": SHA, "mergeCommit": None}
        self.calls: list[list[str]] = []
        self.merges = merges
        self.lands_on = lands_on
        self.closes_on = closes_on or []
        self.moves_head_after = moves_head_after
        self.merge_number = 0
        self.reads = 0

    def pr_view(self, pr: str, repo: str):
        self.calls.append(["view", repo])
        self.reads += 1
        if self.moves_head_after is not None and self.reads == self.moves_head_after:
            self.state = {**self.state, "headRefOid": "b" * 40}
        return subprocess.CompletedProcess(
            ["gh", "pr", "view", pr], 0, json.dumps(self.state), ""
        )

    def pr_checks(self, pr: str, repo: str):
        returncode, output = self.checks
        return subprocess.CompletedProcess(["gh", "pr", "checks", pr], returncode, output, "")

    def merge(self, pr: str, repo: str, sha: str):
        self.calls.append(["merge", pr, repo, sha])
        if sha.lower() != self.state["headRefOid"].lower():
            return subprocess.CompletedProcess(
                ["gh", "pr", "merge", pr],
                1,
                "",
                "the head does not match --match-head-commit",
            )
        self.merge_number += 1
        index = self.merge_number - 1
        returncode, text = self.merges[min(index, len(self.merges) - 1)]
        if self.merge_number in self.lands_on:
            self.state = {
                "state": "MERGED",
                "headRefOid": self.state["headRefOid"],
                "mergeCommit": {"oid": "f" * 40},
            }
        if self.merge_number in self.closes_on:
            self.state = {**self.state, "state": "CLOSED"}
        return subprocess.CompletedProcess(
            ["gh", "pr", "merge", pr], returncode, text, text
        )


def _fake(merges, lands_on, **kwargs) -> _FakeGh:
    return _FakeGh(merges, lands_on, **kwargs)


def _gate(
    tmp_path: Path,
    sha: str = SHA,
    verdict: str = "PASS",
    digest: str | None = None,
) -> Path:
    path = tmp_path / "record.txt"
    text = (
        "local-ci record\n"
        f"sha            : {sha}\n"
        f"verdict        : {verdict}\n"
    )
    path.write_text(text, encoding="utf-8")
    if digest != "absent":
        recorded = digest or hashlib.sha256(path.read_bytes()).hexdigest()
        path.with_suffix(".sha256").write_text(recorded + "\n", encoding="utf-8")
    return path


def _review(tmp_path: Path, sha: str = SHA, verdict: str = "PASS") -> Path:
    path = tmp_path / "review.md"
    path.write_text(f"- SC1: inspected {sha}\n\n{verdict}\n", encoding="utf-8")
    return path


def _clean_git():
    return lambda command: subprocess.CompletedProcess(["git", *command], 0, "", "")


def _land(tmp_path: Path, gh, **kwargs):
    sha = kwargs.pop("sha", SHA)
    review = kwargs.pop("review", None) or _review(tmp_path, sha=sha)
    gate = kwargs.pop("gate", None) or _gate(tmp_path, sha=sha)
    git_run = kwargs.pop("git_run", None) or _clean_git()
    return mm.merge("240", sha, gh, REPO, tmp_path, review, gate, git_run=git_run, **kwargs)


def test_a_merge_that_lands_is_reported_merged_even_when_gh_exits_non_zero(tmp_path):
    gh = _fake([(1, "error: exit status 1")], [1])
    outcome = _land(tmp_path, gh)
    assert outcome.status == "merged", outcome.as_dict()
    assert len(outcome.attempts) == 1
    assert outcome.attempts[0].had_effect is True


def test_a_transient_failure_with_no_effect_is_retried_once_and_then_merged(tmp_path):
    gh = _fake([(1, "HTTP 503 Service Unavailable"), (0, "merged")], [2])
    outcome = _land(tmp_path, gh)
    assert outcome.status == "merged", outcome.as_dict()
    assert len(outcome.attempts) == 2
    assert outcome.attempts[0].had_effect is False
    assert outcome.attempts[1].had_effect is True


def test_a_deterministic_refusal_is_not_retried(tmp_path):
    gh = _fake([(1, "HTTP 405 Pull Request is not mergeable")] * 2, [])
    outcome = _land(tmp_path, gh)
    assert outcome.status == "refused", outcome.as_dict()
    assert len(outcome.attempts) == 1, "a 4xx is the server answering, not a flake"
    assert "no server-side effect" in outcome.detail


def test_a_real_failure_with_no_effect_is_not_retried(tmp_path):
    gh = _fake([(1, "remote: something went wrong")] * 3, [])
    outcome = _land(tmp_path, gh)
    assert outcome.status == "refused", outcome.as_dict()
    assert len(outcome.attempts) == 1
    assert "no server-side effect" in outcome.detail


def test_a_pipeline_number_is_not_a_transient_status(tmp_path):
    gh = _fake([(1, "pipeline 5030 failed")] * 3, [])
    outcome = _land(tmp_path, gh)
    assert outcome.status == "refused", outcome.as_dict()
    assert len(outcome.attempts) == 1, "a job number is not an HTTP status"


def test_a_pull_request_number_is_not_a_transient_status(tmp_path):
    gh = _fake([(1, "pull request 503 is closed")] * 3, [])
    outcome = _land(tmp_path, gh)
    assert outcome.status == "refused", outcome.as_dict()
    assert len(outcome.attempts) == 1, "a PR number is not an HTTP status"


def test_a_closed_pull_request_is_not_a_merge(tmp_path):
    gh = _fake([(1, "boom")], [], closes_on=[1])
    outcome = _land(tmp_path, gh)
    assert outcome.status == "refused", outcome.as_dict()
    assert outcome.attempts[0].had_effect is False
    assert "no server-side effect" in outcome.detail


def test_a_head_that_moved_after_the_check_is_refused_before_the_retry(tmp_path):
    gh = _fake([(1, "HTTP 503 Service Unavailable")] * 2, [], moves_head_after=3)
    outcome = _land(tmp_path, gh)
    assert outcome.status == "refused", outcome.as_dict()
    assert len(outcome.attempts) == 2, outcome.as_dict()
    assert outcome.attempts[1].error == "the PR's head is no longer the pinned SHA"
    assert outcome.sha_mismatch is True


def test_the_exit_code_is_four_for_a_head_that_is_not_the_pinned_sha(tmp_path):
    before_any_merge = _fake([(0, "merged")], [1])
    assert mm.main(
        ["--pr", "240", "--sha", "b" * 40, "--repository", str(tmp_path),
         "--gate", str(_gate(tmp_path, sha="b" * 40)),
         "--review", str(_review(tmp_path, sha="b" * 40))],
        api=before_any_merge,
        git_run=_clean_git(),
    ) == 4

    real_failure = _fake([(1, "remote: something went wrong")] * 2, [])
    assert mm.main(
        ["--pr", "240", "--sha", SHA, "--repository", str(tmp_path),
         "--gate", str(_gate(tmp_path)), "--review", str(_review(tmp_path))],
        api=real_failure,
        git_run=_clean_git(),
    ) == 3


def test_a_head_that_moved_before_the_first_merge_is_refused_without_a_merge(tmp_path):
    gh = _fake([(0, "merged")], [1], moves_head_after=2)
    outcome = _land(tmp_path, gh)
    assert outcome.status == "refused", outcome.as_dict()
    assert outcome.attempts[0].had_effect is False
    assert [call[0] for call in gh.calls] == ["view", "view"], "no merge was attempted"


def test_success_reported_without_moving_the_pull_request_is_refused(tmp_path):
    gh = _fake([(0, "merged")], [])
    outcome = _land(tmp_path, gh)
    assert outcome.status == "refused", outcome.as_dict()
    assert "never merged" in outcome.detail


def test_a_sha_that_is_not_the_pull_request_head_is_refused_before_any_merge(tmp_path):
    gh = _fake([(0, "merged")], [1])
    outcome = _land(tmp_path, gh, sha="b" * 40)
    assert outcome.status == "refused", outcome.as_dict()
    assert outcome.attempts == []
    assert "not this PR's head" in outcome.detail


class _ForeignHeadGh:
    def __init__(self):
        self.state = {"state": "OPEN", "headRefOid": SHA, "mergeCommit": None}
        self.reads = 0
        self.calls: list[list[str]] = []

    def pr_view(self, pr: str, repo: str):
        self.reads += 1
        self.calls.append(["view", repo])
        if self.reads == 3:
            self.state = {
                "state": "MERGED",
                "headRefOid": "b" * 40,
                "mergeCommit": {"oid": "f" * 40},
            }
        return subprocess.CompletedProcess(
            ["gh", "pr", "view", pr], 0, json.dumps(self.state), ""
        )

    def pr_checks(self, pr: str, repo: str):
        return subprocess.CompletedProcess(["gh", "pr", "checks", pr], 1, "", "")

    def merge(self, pr: str, repo: str, sha: str):
        self.calls.append(["merge", pr, repo, sha])
        return subprocess.CompletedProcess(
            ["gh", "pr", "merge", pr], 1, "", "the head does not match --match-head-commit"
        )


def test_a_merged_head_that_is_not_the_pin_is_refused_with_exit_four(tmp_path):
    outcome = _land(tmp_path, _ForeignHeadGh())
    assert outcome.status == "refused", outcome.as_dict()
    assert outcome.sha_mismatch is True
    assert outcome.attempts[0].had_effect is False
    assert outcome.attempts[0].state_after.get("headRefOid") == "b" * 40
    assert "not the reviewed SHA" in outcome.detail
    assert mm.main(
        ["--pr", "240", "--sha", SHA, "--json", "--repository", str(tmp_path),
         "--gate", str(_gate(tmp_path)), "--review", str(_review(tmp_path))],
        api=_ForeignHeadGh(),
        git_run=_clean_git(),
    ) == 4


def test_the_merge_call_is_a_true_merge_with_no_squash_or_rebase(tmp_path):
    recorded: list[list[str]] = []
    api = mm.GhApi(
        repository=tmp_path,
        runner=lambda command: (
            recorded.append(list(command)) or subprocess.CompletedProcess(command, 0, "", "")
        ),
    )
    api.pr_view("240", REPO)
    api.merge("240", REPO, SHA)
    assert recorded[1] == [
        "gh", "pr", "merge", "240", "--repo", REPO, "--merge", "--match-head-commit", SHA
    ], recorded
    assert "--squash" not in recorded[1] and "--rebase" not in recorded[1], recorded
    assert recorded[0][:4] == ["gh", "pr", "view", "240"], recorded


def test_a_dirty_tree_is_refused_before_the_pull_request_is_read(tmp_path):
    gh = _fake([(0, "merged")], [1])
    def dirty(command):
        return subprocess.CompletedProcess(["git", *command], 0, " M tools/dev/merge_mr.py\n", "")
    outcome = _land(tmp_path, gh, git_run=dirty)
    assert outcome.status == "refused", outcome.as_dict()
    assert "not clean" in outcome.detail
    assert gh.calls == [], "the pull request must not even be read"


def test_a_missing_local_gate_record_is_refused(tmp_path):
    gh = _fake([(0, "merged")], [1])
    outcome = mm.merge(
        "240", SHA, gh, REPO, tmp_path, _review(tmp_path), tmp_path / "absent.txt",
        git_run=_clean_git(),
    )
    assert outcome.status == "refused", outcome.as_dict()
    assert "gate record" in outcome.detail and "missing" in outcome.detail
    assert gh.calls == []


def test_a_local_gate_record_for_another_sha_is_refused(tmp_path):
    gh = _fake([(0, "merged")], [1])
    outcome = _land(tmp_path, gh, gate=_gate(tmp_path, sha="b" * 40))
    assert outcome.status == "refused", outcome.as_dict()
    assert "not the pinned" in outcome.detail
    assert gh.calls == []


def test_a_failed_local_gate_is_refused(tmp_path):
    gh = _fake([(0, "merged")], [1])
    outcome = _land(tmp_path, gh, gate=_gate(tmp_path, verdict="FAIL"))
    assert outcome.status == "refused", outcome.as_dict()
    assert "not green" in outcome.detail
    assert gh.calls == []


def test_a_missing_record_digest_is_refused(tmp_path):
    gh = _fake([(0, "merged")], [1])
    outcome = _land(tmp_path, gh, gate=_gate(tmp_path, digest="absent"))
    assert outcome.status == "refused", outcome.as_dict()
    assert "record.sha256" in outcome.detail and "altered" in outcome.detail
    assert gh.calls == []


def test_a_malformed_record_digest_is_refused(tmp_path):
    gh = _fake([(0, "merged")], [1])
    outcome = _land(tmp_path, gh, gate=_gate(tmp_path, digest="not-a-digest"))
    assert outcome.status == "refused", outcome.as_dict()
    assert "does not hold a sha256 digest" in outcome.detail
    assert gh.calls == []


def test_a_record_whose_digest_does_not_match_is_refused(tmp_path):
    gh = _fake([(0, "merged")], [1])
    outcome = _land(tmp_path, gh, gate=_gate(tmp_path, digest="0" * 64))
    assert outcome.status == "refused", outcome.as_dict()
    assert "was altered after the gate wrote it" in outcome.detail
    assert gh.calls == []


def test_a_record_whose_digest_matches_is_accepted(tmp_path):
    gh = _fake([(0, "merged")], [1])
    outcome = _land(tmp_path, gh)
    assert outcome.status == "merged", outcome.as_dict()


def test_a_missing_review_record_is_refused(tmp_path):
    gh = _fake([(0, "merged")], [1])
    outcome = mm.merge(
        "240", SHA, gh, REPO, tmp_path, tmp_path / "absent.md", _gate(tmp_path),
        git_run=_clean_git(),
    )
    assert outcome.status == "refused", outcome.as_dict()
    assert "review record" in outcome.detail and "missing" in outcome.detail
    assert gh.calls == []


def test_a_blocked_review_is_refused(tmp_path):
    gh = _fake([(0, "merged")], [1])
    outcome = _land(tmp_path, gh, review=_review(tmp_path, verdict="BLOCKED"))
    assert outcome.status == "refused", outcome.as_dict()
    assert "does not end in PASS" in outcome.detail
    assert gh.calls == []


def test_a_review_that_does_not_name_the_pinned_sha_is_refused(tmp_path):
    gh = _fake([(0, "merged")], [1])
    outcome = _land(tmp_path, gh, review=_review(tmp_path, sha="c" * 40))
    assert outcome.status == "refused", outcome.as_dict()
    assert "does not name the pinned" in outcome.detail
    assert gh.calls == []


def test_a_dry_run_reads_the_pin_and_merges_nothing(tmp_path):
    gh = _fake([(0, "merged")], [1])
    outcome = _land(tmp_path, gh, dry_run=True)
    assert outcome.status == "dry-run", outcome.as_dict()
    assert [call[0] for call in gh.calls] == ["view"], gh.calls


def test_a_red_actions_run_is_printed_and_does_not_block_the_merge(tmp_path, capsys):
    gh = _fake(
        [(0, "merged")], [1], checks=(1, "test-sdk	fail	1m2s	https://example.invalid/1\n")
    )
    code = mm.main(
        ["--pr", "240", "--sha", SHA, "--repository", str(tmp_path),
         "--gate", str(_gate(tmp_path)), "--review", str(_review(tmp_path))],
        api=gh,
        git_run=_clean_git(),
    )
    printed = capsys.readouterr().out
    assert code == 0, printed
    assert "actions: fail" in printed, printed
    assert "never a merge gate" in printed, printed
    assert "test-sdk" in printed, printed


def test_a_pending_actions_run_is_reported_as_pending(tmp_path):
    gh = _fake(
        [(0, "merged")], [1], checks=(8, "test-sdk\tpending\t0\thttps://example.invalid/1\n")
    )
    outcome = _land(tmp_path, gh)
    assert outcome.status == "merged", outcome.as_dict()
    assert outcome.actions["state"] == "pending", outcome.actions


def test_an_absent_actions_run_is_reported_as_none(tmp_path):
    gh = _fake([(0, "merged")], [1], checks=(1, ""))
    outcome = _land(tmp_path, gh)
    assert outcome.status == "merged", outcome.as_dict()
    assert outcome.actions["state"] == "none", outcome.actions


def test_the_merge_call_carries_the_pinned_sha(tmp_path):
    recorded: list[list[str]] = []
    api = mm.GhApi(
        repository=tmp_path,
        runner=lambda command: (
            recorded.append(list(command)) or subprocess.CompletedProcess(command, 0, "", "")
        ),
    )
    api.merge("240", REPO, SHA)
    assert recorded == [
        ["gh", "pr", "merge", "240", "--repo", REPO, "--merge", "--match-head-commit", SHA]
    ], recorded


class _ConcurrentPushGh:
    def __init__(self):
        self.state = {"state": "OPEN", "headRefOid": SHA, "mergeCommit": None}
        self.argv: list[list[str]] = []

    def pr_view(self, pr: str, repo: str):
        return subprocess.CompletedProcess(
            ["gh", "pr", "view", pr], 0, json.dumps(self.state), ""
        )

    def pr_checks(self, pr: str, repo: str):
        return subprocess.CompletedProcess(["gh", "pr", "checks", pr], 1, "", "")

    def merge(self, pr: str, repo: str, sha: str):
        self.argv.append(
            ["gh", "pr", "merge", pr, "--repo", repo, "--merge", "--match-head-commit", sha]
        )
        self.state = {**self.state, "headRefOid": "b" * 40}
        return subprocess.CompletedProcess(
            ["gh", "pr", "merge", pr], 1, "", "the head does not match --match-head-commit"
        )


def test_a_push_between_the_recheck_and_the_merge_cannot_land_an_unreviewed_head(tmp_path):
    gh = _ConcurrentPushGh()
    outcome = _land(tmp_path, gh)
    assert outcome.status == "refused", outcome.as_dict()
    assert outcome.attempts[0].had_effect is False
    assert outcome.attempts[0].state_after.get("mergeCommit") is None
    assert gh.argv and gh.argv[0][-1] == SHA, gh.argv


def test_a_git_error_fails_the_clean_tree_gate_closed(tmp_path):
    gh = _fake([(0, "merged")], [1])

    def broken(command):
        return subprocess.CompletedProcess(
            ["git", *command],
            128,
            "",
            "fatal: not a git repository (or any of the parent directories): .git",
        )

    outcome = _land(tmp_path, gh, git_run=broken)
    assert outcome.status == "refused", outcome.as_dict()
    assert "git status failed (128)" in outcome.detail
    assert str(tmp_path) in outcome.detail
    assert gh.calls == [], "the pull request must not be read when the tree cannot be read"


def test_a_transient_failure_that_recurs_is_refused_after_two_attempts(tmp_path):
    gh = _fake([(1, "HTTP 503 Service Unavailable")] * 3, [])
    outcome = _land(tmp_path, gh)
    assert outcome.status == "refused", outcome.as_dict()
    assert len(outcome.attempts) == 2, "at most one retry on a transient failure"
    assert outcome.attempts[1].error == "transient failure recurred"
    assert "recurred" in outcome.detail


def test_main_returns_four_when_the_head_moves_between_attempts(tmp_path):
    gh = _fake([(1, "HTTP 503 Service Unavailable")] * 2, [], moves_head_after=3)
    code = mm.main(
        ["--pr", "240", "--sha", SHA, "--repository", str(tmp_path),
         "--gate", str(_gate(tmp_path)), "--review", str(_review(tmp_path))],
        api=gh,
        git_run=_clean_git(),
    )
    assert code == 4, gh.calls


def test_the_docstring_names_the_exit_codes_the_code_returns():
    source = (
        REPOSITORY_ROOT / "tools" / "dev" / "merge_mr.py"
    ).read_text(encoding="utf-8")
    doc = " ".join(source[: source.index('"""', 3)].split())
    assert "Exit codes: 0 merged" in doc
    assert "3 refused" in doc
    assert "4 the pinned SHA is not the PR's head" in doc
    assert "--ticket" not in doc


# --- B8: probe_worktree.ps1 --------------------------------------------------


def _probe(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    shell = _require_powershell()
    return subprocess.run(
        [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(PROBE_WORKTREE), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=600,
    )


@pytest.fixture
def probe_repo(tmp_path: Path) -> dict:
    """A repository whose working tree holds a modified file to probe with."""
    _require_powershell()
    if shutil.which("git") is None:
        pytest.skip("git is required to build a probe worktree")
    root = tmp_path / "repo"
    root.mkdir()

    def git(*args: str) -> None:
        result = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, timeout=300
        )
        assert result.returncode == 0, f"git {args}: {result.stdout}{result.stderr}"

    git("init", "-q", "--initial-branch=master")
    disconnect_disposable_hooks(root)
    git("config", "user.email", "guard@example.invalid")
    git("config", "user.name", "guard")
    (root / "probe.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "helper.py").write_text("OTHER = 2\n", encoding="utf-8")
    (root / "tools" / "webfoot").mkdir(parents=True)
    (root / "tools" / "webfoot" / "journal.py").write_text("JOURNAL = 1\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-q", "-m", "base")
    (root / "probe.py").write_text("VALUE = 2\n", encoding="utf-8")
    return {"root": root}


#: The two refusals the probe must perform before it copies a byte. Each is pinned as
#: the STATEMENT it is, never as a word that appears somewhere: a substring guard
#: passes on a condition neutralised with `$false -and ...` and on a branch whose own
#: `exit` was dropped.
PARENT_STEP_CONDITION = r"if (($relative -split '[\\/]') -contains '..') {"
CONTAINMENT_CONDITION = "if (-not $insideTarget) {"
#: The test inside each `if`'s own parentheses, which is the text the locator compares:
#: the statement constants above are what a mutation replaces, these are what must match.
PARENT_STEP_TEST = r"($relative -split '[\\/]') -contains '..'"
CONTAINMENT_TEST = "-not $insideTarget"
COPY_CALL = "[System.IO.File]::Copy("


def _compact(text: str) -> str:
    return "".join(text.split())


def _mask(text: str, *, strings: bool) -> str:
    """Blank `#` comments, and optionally quoted strings, in place.

    Lengths and line breaks survive, so the two masks align index for index: the
    condition is compared on the mask that KEEPS strings, because its own test is
    quoted, and brace depth and statements are read on the mask that removes them.
    A refusal that was commented out or wrapped in a string stops being a refusal.
    """
    out = list(text)
    index = 0
    quote = ""
    while index < len(out):
        char = out[index]
        if quote:
            if strings:
                out[index] = " "
            if char == quote:
                if quote == "'" and index + 1 < len(out) and out[index + 1] == "'":
                    if strings:
                        out[index + 1] = " "
                    index += 2
                    continue
                quote = ""
            elif char == "`" and quote == '"':
                if strings and index + 1 < len(out):
                    out[index + 1] = " "
                index += 2
                continue
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            if strings:
                out[index] = " "
        elif char == "#":
            while index < len(out) and out[index] not in "\r\n":
                out[index] = " "
                index += 1
            continue
        index += 1
    return "".join(out)


def _matching(masked: str, open_at: int, opener: str, closer: str) -> int | None:
    depth = 0
    for index in range(open_at, len(masked)):
        if masked[index] == opener:
            depth += 1
        elif masked[index] == closer:
            depth -= 1
            if depth == 0:
                return index
    return None


def _condition_block(code: str, conditions: str, condition: str) -> tuple[int, str] | None:
    """The first `if` whose condition compacts to `condition`, with its own block.

    `code` has comments and strings blanked, so an `if` that only appears in either is
    not a candidate; `conditions` keeps strings, because a condition may quote one.
    """
    at = 0
    while True:
        at = code.find("if", at)
        if at < 0:
            return None
        if at > 0 and (code[at - 1].isalnum() or code[at - 1] in "_-$"):
            at += 2
            continue
        open_at = code.find("(", at)
        close_at = None if open_at < 0 else _matching(code, open_at, "(", ")")
        if close_at is not None and _compact(conditions[open_at + 1 : close_at]) == condition:
            brace_at = code.find("{", close_at)
            brace_end = None if brace_at < 0 else _matching(code, brace_at, "{", "}")
            if brace_end is not None:
                return at, code[brace_at : brace_end + 1]
        at += 2


def _statements(block: str) -> list[str]:
    """The block's statements, one per line or semicolon, braces and blanks dropped."""
    statements: list[str] = []
    for line in block.replace(";", "\n").splitlines():
        statement = line.strip().strip("{}").strip()
        if statement:
            statements.append(statement)
    return statements


def _is_nonzero_exit(statement: str) -> bool:
    """A whole `exit <non-zero>` statement; `exit 0` is not a refusal."""
    text = statement.strip()
    if text[:4].lower() != "exit":
        return False
    code = text[4:].strip()
    return code.isdigit() and int(code) != 0


def escape_refusal_problems(text: str) -> list[str]:
    """What the probe's escape refusals are missing, statement by statement.

    Everything is scanned on the masked script, so a refusal that was commented out or
    wrapped in a string is not a refusal. The parent-step branch must be that condition
    and must carry a whole `exit <non-zero>` statement in its own block; the containment
    branch must be `-not $insideTarget` and must carry a whole `continue` statement or a
    non-zero exit; and both must sit ahead of the byte copy.
    """
    code = _mask(text, strings=True)
    conditions = _mask(text, strings=False)
    copy_at = code.find(COPY_CALL)
    if copy_at < 0:
        return ["the probe has no byte copy to guard"]
    problems: list[str] = []
    for label, condition, needs_continue in (
        ("parent-step", _compact(PARENT_STEP_TEST), False),
        ("containment", _compact(CONTAINMENT_TEST), True),
    ):
        located = _condition_block(code, conditions, condition)
        if located is None:
            problems.append(f"the {label} refusal is not the condition it claims to be")
            continue
        at, block = located
        statements = _statements(block)
        has_exit = any(_is_nonzero_exit(statement) for statement in statements)
        has_continue = any(statement.lower() == "continue" for statement in statements)
        if needs_continue:
            if not (has_continue or has_exit):
                problems.append("the containment refusal carries no continue")
        elif not has_exit:
            problems.append("the parent-step refusal carries no non-zero exit")
        if at > copy_at:
            problems.append(f"the {label} refusal comes after the byte copy")
    return problems


def test_the_probe_pins_its_escape_refusal_as_text():
    """The two escape refusals, pinned as statements where no PowerShell host exists.

    The behavioural escape guards skip on a Linux runner, so the refusals they drive
    are pinned here over the script itself: the parent-step branch with its non-zero
    exit, the containment branch with its own refusal, and both ahead of the byte copy.
    """
    problems = escape_refusal_problems(PROBE_WORKTREE.read_text(encoding="utf-8"))
    assert problems == [], problems


def _drop_block(text: str, header: str) -> str:
    """Delete the block header through its own closing line, and nothing else.

    Line-wise on purpose: the closing brace is indented, so a `\\n}` search would run
    past the block and take the byte copy with it, which is a different mutation.
    """
    lines = text.splitlines(keepends=True)
    start = next(index for index, line in enumerate(lines) if header in line)
    end = next(
        index for index in range(start + 1, len(lines)) if lines[index].strip() == "}"
    )
    return "".join(lines[:start] + lines[end + 1 :])


def _drop_first_after(text: str, header: str, needle: str) -> str:
    at = text.index(needle, text.index(header))
    start = text.rindex("\n", 0, at) + 1
    end = text.index("\n", at) + 1
    return text[:start] + text[end:]


def _comment_first_after(text: str, header: str, needle: str) -> str:
    at = text.index(needle, text.index(header))
    start = text.rindex("\n", 0, at) + 1
    return text[:start] + "# " + text[start:]


def _replace_statement(text: str, header: str, needle: str, replacement: str) -> str:
    at = text.index(needle, text.index(header))
    start = text.rindex("\n", 0, at) + 1
    end = text.index("\n", at) + 1
    return text[:start] + text[start:at] + replacement + "\n" + text[end:]


#: Every neutralisation this guard must report. Each is applied to an in-memory copy of
#: the script, so the tracked file is never written.
ESCAPE_MUTATIONS = {
    "the containment block deleted": lambda text: _drop_block(text, CONTAINMENT_CONDITION),
    "the parent-step exit dropped": lambda text: _drop_first_after(
        text, PARENT_STEP_CONDITION, "exit 2"
    ),
    "the parent-step condition neutralised": lambda text: text.replace(
        PARENT_STEP_CONDITION,
        r"if ($false -and (($relative -split '[\\/]') -contains '..')) {",
        1,
    ),
    "the containment condition neutralised": lambda text: text.replace(
        CONTAINMENT_CONDITION, "if ($false -and -not $insideTarget) {", 1
    ),
    "the parent-step exit commented out": lambda text: _comment_first_after(
        text, PARENT_STEP_CONDITION, "exit 2"
    ),
    "the containment continue commented out": lambda text: _comment_first_after(
        text, CONTAINMENT_CONDITION, "continue"
    ),
    "the containment continue quoted": lambda text: _replace_statement(
        text, CONTAINMENT_CONDITION, "continue", "Write-Host 'continue'"
    ),
}


def test_the_escape_guard_reports_every_neutralisation():
    """Every neutralisation must be reported by name, including the masked ones.

    A refusal that was commented out or moved into a string is not a refusal, so the
    drive covers those beside the deleted and neutralised branches. The mutations run
    against in-memory copies, so the only restore this drive needs is the assertion that
    the tracked file's own text is byte-identical afterwards.
    """
    original = PROBE_WORKTREE.read_text(encoding="utf-8")
    assert escape_refusal_problems(original) == [], escape_refusal_problems(original)
    for name, mutate in ESCAPE_MUTATIONS.items():
        mutated = mutate(original)
        assert mutated != original, f"the mutation '{name}' no longer applies"
        assert "[System.IO.File]::Copy(" in mutated, (
            f"the mutation '{name}' must be surgical: the byte copy must survive it")
        assert escape_refusal_problems(mutated), (
            f"the mutation '{name}' was not reported by the escape guard")
    assert PROBE_WORKTREE.read_text(encoding="utf-8") == original, (
        "the tracked probe script changed under the drive")


def test_the_probe_worktree_refuses_a_file_whose_copy_differs(probe_repo):
    """The measured failure: a redirect converted the bytes the probe ran.

    Driven on the real comparison: the probed tree holds different bytes for a
    named file than the source does, which is what the redirect produced, and the
    tool must refuse rather than report a result.
    """
    root = probe_repo["root"]
    probed = root / "probed"
    subprocess.run(
        ["git", "worktree", "add", "--detach", "--quiet", str(probed), "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    # One byte differs from the source's own file, exactly as a CRLF conversion did.
    (probed / "probe.py").write_bytes(b"VALUE = 3\n")
    result = _probe(
        "-Path", "probe.py", "-VerifyOnly", str(probed), "-CheckOnly", cwd=root
    )
    assert result.returncode != 0, result.stdout + result.stderr
    assert "MISMATCH" in result.stdout.upper(), result.stdout + result.stderr
    assert "REFUSED" in result.stdout.upper(), result.stdout


def test_the_probe_worktree_copies_and_verifies_when_the_bytes_match(probe_repo):
    root = probe_repo["root"]
    result = _probe("-Path", "probe.py", "-CheckOnly", cwd=root)
    assert result.returncode == 0, result.stdout + result.stderr
    # The full SHAs are printed, which is what makes the probe's provenance usable.
    assert "sha256" in result.stdout.lower()
    assert "probe.py" in result.stdout


def test_the_probe_worktree_still_copies_a_nested_relative_name(probe_repo):
    """The correction must refuse escapes WITHOUT refusing the normal nested case."""
    root = probe_repo["root"]
    result = _probe("-Path", r"tools\webfoot\journal.py", "-CheckOnly", cwd=root)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout, result.stdout


def test_the_probe_worktree_refuses_a_parent_relative_name_that_would_escape(tmp_path: Path):
    """The review's counterexample: an escaped destination rewrote a tracked caller file.

    The name resolves OUTSIDE the repository to a real source and, under the detached
    target, resolves to a tracked file in the calling worktree; the byte copy then
    rewrote that file while the tool printed OK with equal digests. The refusal must
    come before any write, so the caller's file and the repository stay untouched.
    """
    _require_powershell()
    if shutil.which("git") is None:
        pytest.skip("git is required to build a probe worktree")
    outer = tmp_path / "outer"
    root = outer / "a" / "b" / "repo"
    root.mkdir(parents=True)
    (outer / "sentinel.txt").write_text("SOURCE FROM OUTSIDE REPOSITORY\n", encoding="utf-8")
    (root / "sentinel.txt").write_text("CALLER TRACKED SENTINEL\n", encoding="utf-8")

    def git(*args: str) -> None:
        result = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, timeout=300
        )
        assert result.returncode == 0, f"git {args}: {result.stdout}{result.stderr}"

    git("init", "-q", "--initial-branch=master")
    disconnect_disposable_hooks(root)
    git("config", "user.email", "guard@example.invalid")
    git("config", "user.name", "guard")
    git("add", "sentinel.txt")
    git("commit", "-q", "-m", "base")

    result = _probe("-Path", r"..\..\..\sentinel.txt", "-Keep", cwd=root)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "parent-directory" in result.stdout, result.stdout
    assert (root / "sentinel.txt").read_text(encoding="utf-8") == "CALLER TRACKED SENTINEL\n"
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True
    ).stdout
    assert status == "", status


def test_the_probe_worktree_is_tracked_in_its_own_launch_site_terms():
    """It starts no emulator, so it needs no identity gate; it must not look like one."""
    text = PROBE_WORKTREE.read_text(encoding="utf-8")
    assert "Start-Process" not in text
    assert "mGBA" not in text


def test_the_probe_worktree_leaves_the_caller_worktree_untouched(probe_repo):
    """A probe worktree is removed after the check, so nothing is left behind."""
    root = probe_repo["root"]
    before = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
    ).stdout
    result = _probe("-Path", "probe.py", "-CheckOnly", cwd=root)
    assert result.returncode == 0, result.stdout + result.stderr
    after = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
    ).stdout
    assert before == after, "the probe worktree must be removed when the check ends"
    assert os.sep in str(root)
