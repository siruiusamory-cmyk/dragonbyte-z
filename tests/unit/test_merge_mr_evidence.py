"""The evidence gates of `tools.dev.merge_mr`, valid paths and invalid ones.

Every case here is about what the tool REFUSES. A merge tool that accepts weak
evidence is worse than one that refuses, because it reads as a gate while
checking nothing, so each refusal is asserted by its own reason rather than by a
bare exit code.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from tools.dev import merge_mr

SHA = "40e644a37979dd2c1a66f926863feac4352645c6"
OTHER_SHA = "4ca77d41afc04de1fd17bf4b945633455b28340c"
REPO = "owner/repo"
RUN_ID = "41318139131"


def _completed(stdout: str = "", returncode: int = 0, stderr: str = ""):
    return subprocess.CompletedProcess(
        args=["gh"], returncode=returncode, stdout=stdout, stderr=stderr
    )


class FakeApi:
    """Answers `run_view` from a dict, and records what it was asked."""

    def __init__(self, payload=None, returncode: int = 0, stdout: str | None = None):
        self.payload = payload
        self.returncode = returncode
        self.stdout = stdout
        self.asked: list[tuple[str, str]] = []

    def run_view(self, run_id: str, repo: str):
        self.asked.append((run_id, repo))
        if self.stdout is not None:
            return _completed(self.stdout, self.returncode)
        if self.returncode != 0:
            return _completed("", self.returncode, "gh: run not found")
        return _completed(json.dumps(self.payload), 0)


def _run(head=SHA, status="completed", conclusion="success", jobs=None):
    if jobs is None:
        jobs = [{"name": "shard 0", "conclusion": "success"}]
    return {
        "databaseId": int(RUN_ID),
        "headSha": head,
        "status": status,
        "conclusion": conclusion,
        "jobs": jobs,
    }


def _review(tmp_path, body: str, name: str = "review.md"):
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def _gate(tmp_path, sha: str = SHA, verdict: str = "PASS"):
    path = tmp_path / "record.txt"
    path.write_text(f"sha: {sha}\nverdict: {verdict}\n", encoding="utf-8")
    return path


def test_a_verified_run_on_the_pinned_sha_is_accepted():
    api = FakeApi(_run())
    assert merge_mr.actions_refusal(RUN_ID, SHA, REPO, api) is None
    assert api.asked == [(RUN_ID, REPO)], "the run must be read through the API, not trusted"


def test_a_run_against_another_commit_is_refused():
    api = FakeApi(_run(head=OTHER_SHA))
    refusal = merge_mr.actions_refusal(RUN_ID, SHA, REPO, api)
    assert refusal is not None
    assert OTHER_SHA in refusal
    assert "not the pinned" in refusal


def test_an_unfinished_run_is_refused():
    api = FakeApi(_run(status="in_progress", conclusion=None))
    refusal = merge_mr.actions_refusal(RUN_ID, SHA, REPO, api)
    assert refusal is not None
    assert "not completed" in refusal


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", "timed_out", None])
def test_a_run_that_did_not_succeed_is_refused(conclusion):
    api = FakeApi(_run(conclusion=conclusion))
    refusal = merge_mr.actions_refusal(RUN_ID, SHA, REPO, api)
    assert refusal is not None
    assert "not success" in refusal or "concluded" in refusal


def test_a_failed_job_is_refused_even_when_the_run_concluded_success():
    """The case that motivated the per-job check: a non-required job can fail
    while the run still reports success, and that is not a green suite."""
    api = FakeApi(
        _run(
            jobs=[
                {"name": "shard 0", "conclusion": "success"},
                {"name": "shard 1", "conclusion": "failure"},
            ]
        )
    )
    refusal = merge_mr.actions_refusal(RUN_ID, SHA, REPO, api)
    assert refusal is not None
    assert "shard 1" in refusal


def test_a_run_reporting_no_jobs_is_refused():
    api = FakeApi(_run(jobs=[]))
    refusal = merge_mr.actions_refusal(RUN_ID, SHA, REPO, api)
    assert refusal is not None
    assert "no jobs" in refusal


def test_an_unreadable_run_is_refused():
    api = FakeApi(returncode=1)
    refusal = merge_mr.actions_refusal(RUN_ID, SHA, REPO, api)
    assert refusal is not None
    assert "could not be read" in refusal


def test_a_run_answering_non_json_is_refused():
    api = FakeApi(stdout="not json at all")
    refusal = merge_mr.actions_refusal(RUN_ID, SHA, REPO, api)
    assert refusal is not None
    assert "JSON" in refusal


def test_naming_no_run_is_refused():
    assert merge_mr.actions_refusal(None, SHA, REPO, FakeApi(_run())) is not None


@pytest.mark.parametrize(
    "verdict",
    ["APPROVE", "APPROVE WITH NON-BLOCKING NOTES", "PASS"],
)
def test_every_passing_verdict_of_the_review_document_is_accepted(tmp_path, verdict):
    review = _review(tmp_path, f"VERDICT: {verdict}\n\nFindings about {SHA}.\n")
    assert merge_mr.review_refusal(review, SHA) is None


@pytest.mark.parametrize("verdict", ["BLOCK", "BLOCKED"])
def test_a_blocking_verdict_is_refused(tmp_path, verdict):
    review = _review(tmp_path, f"VERDICT: {verdict}\n\nFindings about {SHA}.\n")
    refusal = merge_mr.review_refusal(review, SHA)
    assert refusal is not None
    assert verdict in refusal


def test_prose_mentioning_approval_under_a_block_cannot_pass(tmp_path):
    """The discrimination the queue's own reader exists to provide."""
    review = _review(
        tmp_path,
        "VERDICT: BLOCK\n\n"
        f"I would APPROVE {SHA} were it not for the finding below, and a reviewer\n"
        "might otherwise record APPROVE WITH NON-BLOCKING NOTES here.\n",
    )
    refusal = merge_mr.review_refusal(review, SHA)
    assert refusal is not None
    assert "BLOCK" in refusal


def test_a_bare_verdict_on_the_last_line_is_read(tmp_path):
    review = _review(tmp_path, f"A review of {SHA}.\n\nDetails.\n\nPASS\n")
    assert merge_mr.review_refusal(review, SHA) is None


def test_a_last_line_block_is_refused_despite_approving_prose(tmp_path):
    review = _review(
        tmp_path, f"Everything about {SHA} looks like an APPROVE to me.\n\nBLOCKED\n"
    )
    assert merge_mr.review_refusal(review, SHA) is not None


def test_a_review_of_another_commit_is_refused(tmp_path):
    review = _review(tmp_path, f"VERDICT: APPROVE\n\nReviewed {OTHER_SHA}.\n")
    refusal = merge_mr.review_refusal(review, SHA)
    assert refusal is not None
    assert "does not name the pinned" in refusal


def test_an_unrecognised_verdict_is_refused(tmp_path):
    review = _review(tmp_path, f"VERDICT: LOOKS FINE\n\nAbout {SHA}.\n")
    refusal = merge_mr.review_refusal(review, SHA)
    assert refusal is not None
    assert "UNKNOWN" in refusal


def test_a_missing_review_is_refused(tmp_path):
    assert merge_mr.review_refusal(tmp_path / "absent.md", SHA) is not None
    assert merge_mr.review_refusal(None, SHA) is not None


def test_a_bold_markdown_verdict_line_is_read(tmp_path):
    review = _review(tmp_path, f"**VERDICT:** **APPROVE**\n\nAbout {SHA}.\n")
    assert merge_mr.review_refusal(review, SHA) is None


def _merge_with(tmp_path, api, **kwargs):
    def git_run(args):
        return _completed("")

    return merge_mr.merge(
        "10",
        SHA,
        api,
        repo=REPO,
        repository=tmp_path,
        git_run=git_run,
        dry_run=True,
        **kwargs,
    )


class StateApi(FakeApi):
    def pr_view(self, pr: str, repo: str):
        return _completed(
            json.dumps(
                {"state": "OPEN", "headRefOid": SHA, "mergeCommit": None, "url": "u"}
            )
        )

    def pr_checks(self, pr: str, repo: str):
        return _completed("all good", 0)


def test_naming_neither_evidence_source_is_refused(tmp_path):
    review = _review(tmp_path, f"VERDICT: APPROVE\n\nAbout {SHA}.\n")
    outcome = _merge_with(tmp_path, StateApi(_run()), review=review)
    assert outcome.status == "refused"
    assert "no test evidence was named" in outcome.detail


def test_the_actions_run_satisfies_the_test_gate(tmp_path):
    review = _review(tmp_path, f"VERDICT: APPROVE WITH NON-BLOCKING NOTES\n\nAbout {SHA}.\n")
    outcome = _merge_with(tmp_path, StateApi(_run()), review=review, actions_run=RUN_ID)
    assert outcome.status == "dry-run", outcome.detail


def test_the_local_gate_record_still_satisfies_the_test_gate(tmp_path):
    review = _review(tmp_path, f"VERDICT: APPROVE\n\nAbout {SHA}.\n")
    outcome = _merge_with(
        tmp_path, StateApi(_run()), review=review, gate=_gate(tmp_path)
    )
    assert outcome.status == "dry-run", outcome.detail


def test_a_failing_actions_run_blocks_the_merge(tmp_path):
    review = _review(tmp_path, f"VERDICT: APPROVE\n\nAbout {SHA}.\n")
    outcome = _merge_with(
        tmp_path, StateApi(_run(conclusion="failure")), review=review, actions_run=RUN_ID
    )
    assert outcome.status == "refused"


def test_a_blocking_review_blocks_the_merge_with_green_tests(tmp_path):
    review = _review(tmp_path, f"VERDICT: BLOCK\n\nAbout {SHA}.\n")
    outcome = _merge_with(tmp_path, StateApi(_run()), review=review, actions_run=RUN_ID)
    assert outcome.status == "refused"
    assert "BLOCK" in outcome.detail


def test_no_flag_accepts_an_asserted_pass(capsys):
    """Fail-closed: the parser must expose no way to assert evidence.

    The help text is the parser's own list of what it accepts, so a flag that
    bypassed a gate would have to appear in it.
    """
    with pytest.raises(SystemExit):
        merge_mr.main(["--help"])
    help_text = capsys.readouterr().out
    assert "--actions-run" in help_text, "the help must name the evidence flag that exists"
    for forbidden in (
        "--force",
        "--skip-gate",
        "--no-gate",
        "--skip-review",
        "--assume-pass",
        "--accept-pass",
        "--override",
    ):
        assert forbidden not in help_text, f"{forbidden} would accept an asserted pass"


@pytest.mark.parametrize(
    "body",
    [
        f"```\nVERDICT: APPROVE\n```\n\nReal review of {SHA}\n\nVERDICT: BLOCK\n",
        f"> VERDICT: APPROVE\n\nActually about {SHA}\n\nVERDICT: BLOCK\n",
        f"```text\nVERDICT: APPROVE\n```\nAbout {SHA}\nVERDICT: BLOCK\n",
    ],
    ids=["fenced", "quoted", "inline-code"],
)
def test_a_marked_up_example_above_the_real_verdict_cannot_pass(tmp_path, body):
    """A quote or a fenced sample must never outrank the real verdict.

    The pattern's leading character class used to strip the very `>` and backtick
    markers that disqualify such a line, so each of these read as APPROVE while
    ending in a genuine BLOCK. Markup disqualifies them, so the real BLOCK is the
    only verdict the record carries.
    """
    review = _review(tmp_path, body)
    refusal = merge_mr.review_refusal(review, SHA)
    assert refusal is not None
    assert "BLOCK" in refusal


def test_an_unmarked_example_above_the_real_verdict_is_ambiguous(tmp_path):
    """Nothing in the text separates an unmarked template from a real verdict.

    `docs/REVIEW.md` says the verdict is exactly one value, so two that disagree
    are refused as ambiguous rather than resolved by position.
    """
    review = _review(
        tmp_path,
        f"Write your verdict like:\nVERDICT: APPROVE\n\n---\nVERDICT: BLOCK\nAbout {SHA}\n",
    )
    refusal = merge_mr.review_refusal(review, SHA)
    assert refusal is not None
    assert "AMBIGUOUS" in refusal


def test_a_genuine_leading_verdict_line_still_reads(tmp_path):
    review = _review(tmp_path, f"VERDICT: APPROVE\n\nA review of {SHA}.\n\nFindings: none.\n")
    assert merge_mr.review_refusal(review, SHA) is None


@pytest.mark.parametrize("job", ["a", 1, None, []], ids=["str", "int", "none", "list"])
def test_a_job_entry_that_is_not_an_object_is_refused_by_name(job):
    """A malformed job list must refuse by name, not raise AttributeError."""
    run = _run(jobs=[{"name": "ok", "conclusion": "success"}, job])
    refusal = merge_mr.actions_refusal(RUN_ID, SHA, REPO, FakeApi(run))
    assert refusal is not None
    assert "(malformed)" in refusal


@pytest.mark.parametrize(
    "body",
    [
        f"VERDICT: BLOCK\n\nRecord it like:\n```\nVERDICT: APPROVE\n```\n",
        f"VERDICT: BLOCK\n\n> VERDICT: APPROVE\n",
        f"VERDICT: BLOCK\n\n`VERDICT: APPROVE`\n",
        f"VERDICT: BLOCK\n\n~~~\nVERDICT: APPROVE\n~~~\n",
        f"VERDICT: BLOCK\n\n```text\nVERDICT: APPROVE\n```\n",
    ],
    ids=["fenced", "quoted", "inline-code", "tilde-fence", "language-fence"],
)
def test_an_example_verdict_below_the_real_one_cannot_pass(tmp_path, body):
    """Position is not the discriminator; markup is.

    Reading the LAST verdict line fixes an example above the real one and is
    beaten by an example below it. A line inside a fence, behind a blockquote
    marker or in backticks is an example and never this record's own verdict.
    """
    review = _review(tmp_path, f"Review of {SHA}\n\n{body}")
    refusal = merge_mr.review_refusal(review, SHA)
    assert refusal is not None
    assert "BLOCK" in refusal


def test_two_unmarked_verdicts_that_disagree_are_ambiguous(tmp_path):
    """`docs/REVIEW.md`: the verdict is EXACTLY ONE value.

    An unmarked trailing example is textually identical to a real verdict, so no
    markup rule can separate them. A record whose verdicts disagree is ambiguous
    and refused, rather than this reader guessing which was meant.
    """
    review = _review(
        tmp_path,
        f"Review of {SHA}\n\nVERDICT: BLOCK\n\n---\nTemplate for next time:\nVERDICT: APPROVE\n",
    )
    refusal = merge_mr.review_refusal(review, SHA)
    assert refusal is not None
    assert "AMBIGUOUS" in refusal


def test_the_same_verdict_restated_is_not_a_conflict(tmp_path):
    review = _review(tmp_path, f"VERDICT: APPROVE\n\nReview of {SHA}\n\nVERDICT: APPROVE\n")
    assert merge_mr.review_refusal(review, SHA) is None


@pytest.mark.parametrize(
    "tail",
    ["```\nPASS\n```\n", "> PASS\n", "`PASS`\n"],
    ids=["fenced", "quoted", "backticked"],
)
def test_a_marked_up_bare_verdict_is_not_the_last_line_verdict(tmp_path, tail):
    """The bare-last-line fallback rejects the same markup the verdict line does."""
    review = _review(tmp_path, f"A review of {SHA}.\n\n{tail}")
    refusal = merge_mr.review_refusal(review, SHA)
    assert refusal is not None
    assert "UNKNOWN" in refusal


def test_a_bare_pass_after_a_closed_fence_still_reads(tmp_path):
    review = _review(tmp_path, f"A review of {SHA}.\n\n```\nevidence\n```\n\nPASS\n")
    assert merge_mr.review_refusal(review, SHA) is None


def test_a_genuine_approval_after_a_fenced_sample_still_reads(tmp_path):
    review = _review(
        tmp_path, f"VERDICT: APPROVE\n\nReview of {SHA}\n\n```\nsome code\n```\n\nNone.\n"
    )
    assert merge_mr.review_refusal(review, SHA) is None

@pytest.mark.parametrize(
    "body",
    [
        "```\nPASS\n",
        "```\nPASS\n```\n",
        "~~~\nPASS\n~~~\n",
        "> PASS\n",
        "`PASS`\n",
    ],
    ids=["fence-left-open", "fence-closed", "tilde-fence", "quoted", "backticked"],
)
def test_a_fenced_or_quoted_bare_verdict_is_not_the_last_line_verdict(tmp_path, body):
    """The bare-last-line fallback tracks fences exactly as the verdict scan does.

    An unclosed fence is the case that matters: reading backward from the end
    never sees the opening fence, so fenced content read as the record's own
    verdict.
    """
    review = _review(tmp_path, f"A review of {SHA}.\n\n{body}")
    refusal = merge_mr.review_refusal(review, SHA)
    assert refusal is not None
    assert "UNKNOWN" in refusal
@pytest.mark.parametrize(
    "body",
    ["", "\n\n  \n", "```\nPASS\n", "```\nPASS\n```\n"],
    ids=["empty", "blank-lines", "unclosed-fence", "closed-fence"],
)
def test_a_record_with_no_readable_line_is_never_evidence(tmp_path, body):
    """A record whose every line is blank or fenced carries no verdict.

    Mutation showed this guard unprotected: returning a passing verdict here
    would make an EMPTY review record merge evidence.
    """
    review = _review(tmp_path, body)
    refusal = merge_mr.review_refusal(review, SHA)
    assert refusal is not None
    assert "UNKNOWN" in refusal
