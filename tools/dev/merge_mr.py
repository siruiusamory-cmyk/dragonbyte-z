"""Land a pull request pinned to the exact SHA that was reviewed.

`gh pr merge --match-head-commit <sha>` puts the pin on GitHub's side: the server
refuses a merge whose head is no longer the reviewed SHA, so a push between the
re-check and the merge cannot land unreviewed code. The reads before and after
every attempt are the evidence: the merge is only reported when the pull request
moved to MERGED, carries a merge commit, and its head is the SHA that was
reviewed. Read the state, never the exit code alone: a `gh` that exits nonzero
after a merge that landed the pinned head is a success, and a `gh` that exits 0
without moving the pull request is not.

The merge is always a merge commit (`gh pr merge --merge`, never `--squash` and
never `--rebase`), because a branch's individual commits are cited as evidence
and squash would rewrite them out of reach. GitHub Actions results are read from
`gh pr checks` and printed on every run; they never gate the merge while the
owner's Actions limit stands, and a red or pending run is reported, never hidden.

Three gates run before the pull request is read, and each one refuses by name:
a clean working tree, a passing local gate record for the pinned SHA, and a PASS
review record that names the pinned SHA. The pin itself is then enforced twice:
here against the head just read, and by GitHub against `--match-head-commit`.
Nothing is merged when any of them is missing; they are evidence the tool
requires, never defaults it invents.

    python -m tools.dev.merge_mr --pr 12 --sha <reviewed sha> \
        --gate build/local-ci/<sha>/record.txt --review ~/.dsh/review-queue/results/<id>.md

Exit codes: 0 merged (or already merged), 2 usage or an unreadable pull request,
3 refused, 4 the pinned SHA is not the PR's head.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from tools.dev.review_queue_index import verdict_of

DEFAULT_REPO = "siruiusamory-cmyk/dragonbyte-z"

TRANSIENT = re.compile(
    r"\bHTTP[ /:]*5\d\d\b|timed out|connection (?:reset|refused)", re.IGNORECASE
)


@dataclass
class Attempt:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    state_before: dict
    state_after: dict
    had_effect: bool
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "command": self.command,
            "returncode": self.returncode,
            "stdout": self.stdout.strip(),
            "stderr": self.stderr.strip(),
            "state_before": self.state_before.get("state"),
            "state_after": self.state_after.get("state"),
            "merge_commit_before": (self.state_before.get("mergeCommit") or {}).get("oid"),
            "merge_commit_after": (self.state_after.get("mergeCommit") or {}).get("oid"),
            "had_effect": self.had_effect,
            "error": self.error,
        }


@dataclass
class Outcome:
    status: str
    detail: str
    attempts: list[Attempt] = field(default_factory=list)
    sha_mismatch: bool = False
    actions: dict | None = None

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "detail": self.detail,
            "sha_mismatch": self.sha_mismatch,
            "actions": self.actions,
            "attempts": [attempt.as_dict() for attempt in self.attempts],
        }


def read_state(pr: str, repo: str, api) -> dict:
    result = api.pr_view(pr, repo)
    if result.returncode != 0:
        raise RuntimeError(
            f"cannot read pull request {pr}: {(result.stderr or result.stdout).strip()}"
        )
    return json.loads(result.stdout)


def had_effect(after: dict) -> bool:
    return after.get("state") == "MERGED" and bool((after.get("mergeCommit") or {}).get("oid"))


def read_actions(pr: str, repo: str, api) -> dict:
    result = api.pr_checks(pr, repo)
    output = (result.stdout or result.stderr or "").strip()
    if not output or "no checks reported" in output.lower():
        return {"state": "none", "exit": result.returncode, "output": output}
    state = {0: "pass", 8: "pending"}.get(result.returncode, "fail")
    return {"state": state, "exit": result.returncode, "output": output}


def record_field(text: str, key: str) -> str | None:
    for line in text.splitlines():
        name, separator, value = line.partition(":")
        if separator and name.strip() == key:
            return value.strip()
    return None


def gate_refusal(gate: Path | None, sha: str) -> str | None:
    if gate is None:
        return "no local gate record was named: pass --gate build/local-ci/<sha>/record.txt"
    if not gate.is_file():
        return f"the local gate record {gate} is missing, so there is no green local gate to merge on"
    text = gate.read_text(encoding="utf-8", errors="replace")
    recorded = record_field(text, "sha")
    if not recorded:
        return f"the local gate record {gate} names no sha, so it cannot be tied to the pinned {sha}"
    if recorded.lower() != sha.lower():
        return (
            f"the local gate record {gate} is for {recorded}, not the pinned {sha}: a green "
            "run of another commit is not evidence about this one"
        )
    verdict = record_field(text, "verdict")
    if verdict != "PASS":
        return f"the local gate is not green for {sha}: {gate} records verdict {verdict!r}"
    return None


def review_refusal(review: Path | None, sha: str) -> str | None:
    if review is None:
        return "no review record was named: pass --review <the independent review result file>"
    if not review.is_file():
        return f"the review record {review} is missing, so no independent review is on file"
    text = review.read_text(encoding="utf-8", errors="replace")
    verdict = verdict_of(review)
    if verdict != "PASS":
        return (
            f"the review record {review} does not end in PASS (it reads {verdict!r}): an "
            "independent review that did not pass is not merge evidence"
        )
    if sha.lower() not in text.lower():
        return (
            f"the review record {review} does not name the pinned {sha}: a review of another "
            "commit is not evidence about this one"
        )
    return None


def merge(
    pr: str,
    sha: str,
    api,
    repo: str = DEFAULT_REPO,
    repository: Path | None = None,
    review: Path | None = None,
    gate: Path | None = None,
    git_run=None,
    dry_run: bool = False,
) -> Outcome:
    if repository is None:
        return Outcome(status="refused", detail="no repository was named for the clean-tree check")
    run = git_run or _runner(repository)
    dirty = run(["status", "--porcelain"])
    if dirty.returncode != 0:
        return Outcome(
            status="refused",
            detail=(
                f"git status failed ({dirty.returncode}) in {repository}: "
                f"{(dirty.stderr or dirty.stdout).strip()[:200]}. A tree that cannot be read "
                "is not a clean tree."
            ),
        )
    if dirty.stdout.strip():
        return Outcome(
            status="refused",
            detail=(
                f"the working tree at {repository} is not clean: "
                f"{len(dirty.stdout.strip().splitlines())} path(s) differ. Commit or remove them "
                "before merging, or the merge cannot be tied to the reviewed tree."
            ),
        )
    for refusal in (gate_refusal(gate, sha), review_refusal(review, sha)):
        if refusal:
            return Outcome(status="refused", detail=refusal)

    before = read_state(pr, repo, api)
    actions = read_actions(pr, repo, api)

    def finish(result: Outcome) -> Outcome:
        result.actions = actions
        return result

    head = (before.get("headRefOid") or "").lower()
    if sha.lower() != head:
        return Outcome(
            status="refused",
            sha_mismatch=True,
            detail=(
                f"the pinned SHA is not this PR's head: asked for {sha}, the pull request is at "
                f"{head or '(no sha)'}. Re-freeze and re-review, or merge the reviewed SHA by "
                "hand after checking what moved."
            ),
        )
    if before.get("state") == "MERGED":
        return finish(Outcome(status="merged", detail="already merged"))
    if dry_run:
        return finish(
            Outcome(
                status="dry-run",
                detail=f"PR {pr} is open at {head}; a merge would be attempted",
            )
        )

    outcome = Outcome(status="refused", detail="no attempt was made")
    outcome.actions = actions
    for number in (1, 2):
        state_before = read_state(pr, repo, api)
        if (state_before.get("headRefOid") or "").lower() != sha.lower():
            attempt = Attempt(
                command=[],
                returncode=0,
                stdout="",
                stderr="",
                state_before=state_before,
                state_after=state_before,
                had_effect=False,
                error="the PR's head is no longer the pinned SHA",
            )
            outcome.attempts.append(attempt)
            outcome.sha_mismatch = True
            outcome.detail = (
                "the pull request is no longer at the reviewed SHA: asked for "
                f"{sha}, it is at {state_before.get('headRefOid')}. Nothing was merged; "
                "re-freeze and re-review."
            )
            return outcome
        result = api.merge(pr, repo, sha)
        state_after = read_state(pr, repo, api)
        effect = had_effect(state_after)
        attempt = Attempt(
            command=list(getattr(result, "args", []) or []),
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            state_before=state_before,
            state_after=state_after,
            had_effect=effect,
        )
        if effect and (state_after.get("headRefOid") or "").lower() != sha.lower():
            attempt.had_effect = False
            attempt.error = "the PR merged a head that is not the reviewed SHA"
            outcome.attempts.append(attempt)
            outcome.status = "refused"
            outcome.sha_mismatch = True
            outcome.detail = (
                "the pull request merged a head that is not the reviewed SHA: asked for "
                f"{sha}, the merged head is {state_after.get('headRefOid')} with merge commit "
                f"{(state_after.get('mergeCommit') or {}).get('oid')}. The pinned merge did not "
                "land this review; re-freeze and re-review the head that merged."
            )
            return outcome
        outcome.attempts.append(attempt)

        if effect:
            outcome.status = "merged"
            outcome.detail = (
                f"merged on attempt {number}; PR state {state_before.get('state')} -> "
                f"{state_after.get('state')}, merge commit "
                f"{(state_after.get('mergeCommit') or {}).get('oid')}"
            )
            return outcome

        failed = result.returncode != 0
        if not failed:
            attempt.error = "no server-side effect"
            outcome.status = "refused"
            outcome.detail = (
                "the merge command reported success and the pull request never merged: "
                "refusing to report a merge that did not happen"
            )
            return outcome

        text = f"{result.stdout}\n{result.stderr}"
        if TRANSIENT.search(text):
            if number == 1:
                attempt.error = "transient failure with no effect"
                continue
            attempt.error = "transient failure recurred"
            outcome.status = "refused"
            outcome.detail = (
                "a transient failure recurred on the one permitted retry, so it is not a flake "
                "this tool may keep retrying. Command said: "
                f"{(result.stderr or result.stdout).strip()[:400]}"
            )
            return outcome
        attempt.error = "merge failed with no effect"
        outcome.status = "refused"
        outcome.detail = (
            f"attempt {number} failed with no server-side effect; refusing to retry a "
            f"deterministic failure. Command said: {(result.stderr or result.stdout).strip()[:400]}"
        )
        return outcome

    outcome.detail = "exhausted the single permitted retry"
    return outcome


def _runner(repository: Path):
    api = GhApi(repository)
    return lambda command: api._subprocess_run(["git", "-C", str(repository), *command])


class GhApi:
    def __init__(self, repository: Path | None = None, runner=None):
        self.repository = repository
        self._run = runner or self._subprocess_run

    def _subprocess_run(self, command: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            command, capture_output=True, text=True, cwd=self.repository, timeout=300
        )

    def pr_view(self, pr: str, repo: str) -> subprocess.CompletedProcess:
        return self._run(
            [
                "gh",
                "pr",
                "view",
                pr,
                "--repo",
                repo,
                "--json",
                "state,headRefOid,mergeCommit,url",
            ]
        )

    def pr_checks(self, pr: str, repo: str) -> subprocess.CompletedProcess:
        return self._run(["gh", "pr", "checks", pr, "--repo", repo])

    def merge(self, pr: str, repo: str, sha: str) -> subprocess.CompletedProcess:
        return self._run(
            [
                "gh",
                "pr",
                "merge",
                pr,
                "--repo",
                repo,
                "--merge",
                "--match-head-commit",
                sha,
            ]
        )


def main(argv: list[str] | None = None, api=None, git_run=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pr", required=True, help="pull request number")
    parser.add_argument("--sha", required=True, help="the reviewed candidate SHA")
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--review", type=Path, help="the independent review result file")
    parser.add_argument("--gate", type=Path, help="the local gate record for the pinned SHA")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        outcome = merge(
            args.pr,
            args.sha,
            api or GhApi(args.repository),
            args.repo,
            args.repository,
            args.review,
            args.gate,
            git_run=git_run,
            dry_run=args.dry_run,
        )
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(outcome.as_dict(), indent=2))
    else:
        print(f"{outcome.status}: {outcome.detail}")
        for attempt in outcome.attempts:
            print(
                "  attempt: exit {0}, PR {1} -> {2}, merge commit {3}, effect {4}".format(
                    attempt.returncode,
                    attempt.state_before.get("state"),
                    attempt.state_after.get("state"),
                    (attempt.state_after.get("mergeCommit") or {}).get("oid"),
                    attempt.had_effect,
                )
            )
        if outcome.actions:
            print(
                "  actions: {0} (gh pr checks exit {1}); reported, never a merge gate".format(
                    outcome.actions["state"], outcome.actions["exit"]
                )
            )
            for line in (outcome.actions.get("output") or "").splitlines():
                print(f"    {line}")
    if outcome.sha_mismatch:
        return 4
    return {"merged": 0, "dry-run": 0}.get(outcome.status, 3)


if __name__ == "__main__":
    raise SystemExit(main())
