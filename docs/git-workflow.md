# GitHub integration workflow

How to push a branch, open a pull request, read its Actions results and finalize
after the merge in this repository without tripping on environment or tooling
traps. Operational only: the permanent rules stay in
[`DEVELOPMENT.md`](DEVELOPMENT.md) and [`REVIEW.md`](REVIEW.md).

GitHub is the authoritative remote since the 2026-10-28 cutover. GitLab is
read-only history: the push mirror is disabled, and the `gitlab` remote carries
the disabled push URL `DISABLED-gitlab-is-read-only`, so a push there fails
loudly instead of landing anywhere.

Read this before pushing, and before reporting any authentication failure. The
most expensive mistake in this area is misreading an environment problem as a
permissions problem: a non-interactive session does not run an interactive login
profile, so a credential helper that depends on one can hand git an empty token
and produce an "Access denied" that says nothing about authorization. Diagnose
the resolved helper before concluding anything, and never retry a push in a
loop, weaken a credential check, or work around one.

This document is operational detail and is deliberately not summarized in the
policy documents, which stay readable by being concise.

## Remotes

```text
origin   https://github.com/siruiusamory-cmyk/dragonbyte-z.git   (fetch and push)
gitlab   https://gitlab.com/siruiusamory/log1-remake.git         (fetch only; push disabled)
```

`origin` is where new development goes. `gitlab` stays configured so GitLab
history and the rollback information recorded from it remain readable from this
checkout. Do not re-enable the GitLab push mirror and do not push to `gitlab`
for any reason; both are owner rules from the cutover.

## Credential helper: the canonical setup

Authentication goes through the `gh` CLI, which already holds a working token
for `github.com`:

```bash
gh auth status                   # confirms host, protocol and token presence
gh auth setup-git                # points git at gh's credential helper for github.com
```

Both the global config and the repository config must resolve to a helper that
can produce a github.com credential:

```text
credential.https://github.com.helper = !gh auth git-credential
```

Check what git actually resolves, including where each value came from:

```bash
git config --list --show-origin | grep credential
```

### Diagnose before concluding anything about permissions

Never report a permissions or token-scope problem from the error text alone.
Confirm which helper produced the credential and whether its password was empty:

```bash
GIT_TRACE=1 GIT_TERMINAL_PROMPT=0 git push --dry-run origin <branch> 2>&1 \
  | grep -E "credential|helper"
```

An empty `password=` in the helper output, or a `run_command` line naming a
helper that is not `gh auth git-credential`, is the cause. Token scope, SSH keys
and account state are separate questions; a working read path does not prove the
write path is authorized, and a broken helper does not prove it is not.

Do not work around this by exporting a token for one command; the next session
loses it. Fix the resolved helper instead, and mention any change outside the
repository in the final report. If authentication is genuinely required and
cannot be resolved, stop and report it. Never retry a push in a loop, and never
weaken or bypass a credential check.

## Pushing and opening the pull request

```bash
git push -u origin <branch>
git ls-remote origin refs/heads/<branch>   # confirm the remote tip equals HEAD
gh pr create --base master --head <branch> \
  --title "<title>" --body-file <body file>
```

`--body-file` is the reliable form: a long multi-line description passed through
a Windows shell can be split into several arguments and silently truncated.
`gh pr create` prints the pull request URL; trust the read, not the creation
output:

```bash
gh pr view <number> --repo siruiusamory-cmyk/dragonbyte-z \
  --json number,state,headRefOid,baseRefName,url,isDraft
```

Confirm `state` is `OPEN`, `headRefOid` is the SHA you pushed, `baseRefName` is
`master`, and `url` names `siruiusamory-cmyk/dragonbyte-z`.

## Reading Actions results

Actions results are read and reported. They do not gate a merge while the
owner's Actions limit stands: the green local gate record and the independent
review are the merge evidence, and a red or pending run is reported in the merge
tool's output rather than hidden.

```bash
gh pr checks <number> --repo siruiusamory-cmyk/dragonbyte-z
gh run view <run id> --repo siruiusamory-cmyk/dragonbyte-z --json status,conclusion,jobs
```

To wait on a run, use the shared watcher, which bounds itself and reports a
terminal state:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$DSH_HOME\tools\watch-pipeline.ps1" -RunId <id>
```

Its exits are 0 terminal, 3 after three poll errors, 4 at the timeout. A run you
report as green is quoted from its `RUN success` line, never from "queued".

## Before merging

`.github/workflows/` describes what Actions runs; the tracked job bodies live in
`ci/*.ps1` and can be run by hand, which is how a local gate record is produced.
Merging to `master` is a deploy surface: treat a merge to `master` as a deploy
even when the change looks internal.

### Is the reviewed candidate still valid against live master?

A pull request's run tests the branch's own commit. It does not test master as
master is at the moment the merge lands, and master can move while a branch is
open.

```powershell
# in a ticket worktree, never in the primary checkout
.\scripts\pre-merge-check.ps1 -Ref <branch or SHA>
```

It fetches the target, prints the predicted merged tree
(`git merge-tree --write-tree <target> <candidate>`), and exits 1 when the target
changed a path the candidate changed, or when the merge conflicts. It pushes and
merges nothing, and it refuses the primary checkout structurally rather than by
name: the primary is the checkout that answers `.git` for its own
`git rev-parse --git-dir`, and a bare `.` is refused too. A path with no `.git`
at its root - a subdirectory of the primary included - is refused before that
compare, and its message names the checkout root git reports for it. A linked
worktree of the primary is allowed; every ticket worktree is one. It does write,
and the wording matters: `git fetch` creates remote-tracking refs, and
`merge-tree --write-tree` writes tree and blob objects into the shared `.git` -
in a linked worktree, into the primary's `--git-common-dir`. No branch, index,
working tree or remote is touched. `-ReportOnly` reports without failing;
`-ExpectMergedTree <sha>` additionally fails when the predicted merged tree is
not that digest, and no such digest is recorded anywhere today, so nothing
checks the printed tree by default.

The gate is not a re-test. It costs seconds where a full re-test costs minutes to
tens of minutes, so it is not replaced by re-running the suite on every merge. An
exit 1 asks for a rebase onto live master and a re-run of the change's own
focused tests; it does not ask for a full suite. The recorded measurement behind
it predates the cutover and still reads as its justification: on the GitLab
sample of three merges (MR 230, 234, 235), one had drifted at merge time by ten
commits, and that one changed a file master had also changed, while composing
cleanly. That shape - two lanes editing one file with no textual conflict, so the
composition is never tested on either side - is what this gate stops.

## Merging

Merge with a merge commit so recorded commit SHAs stay reachable, and never
squash a branch whose individual commits are cited as evidence:

```powershell
.venv\Scripts\python.exe -m tools.dev.merge_mr --pr <number> --sha <reviewed sha> `
    --gate build\local-ci\<sha>\record.txt `
    --review ~\.dsh\review-queue\results\<review id>.md
```

The tool refuses a dirty tree, a missing or failing local gate record, a review
record that does not end in PASS or does not name the pinned SHA, and a pull
request whose head is not that SHA. It merges with `gh pr merge --merge`, reads
the pull request again, and reports merged only when the state is `MERGED` with a
merge commit at the pinned head. It prints the Actions result it read and never
gates on it.

## Finalizing after the merge

Fetch and record the exact post-merge `origin/master` SHA, then check that the
closeout records are still true. Each of these has caught a real defect:

1. **Reachability.** Cherry-picking reproduces a change under a *new* SHA. If
   the closeout cites the authoring branch's hashes, they may not be ancestors
   of `master` and may never have been pushed. Verify every cited hash:

   ```bash
   git merge-base --is-ancestor <sha> origin/master && echo reachable
   git log --oneline origin/master..<authoring-branch>   # should be empty
   ```

2. **Baseline drift.** A documentation-only follow-up moves `origin/master`
   past the SHA the previous record named as the next ticket's baseline. Name
   the tip and allow later documentation-only commits, or the record is stale
   the moment it lands.

3. **Superseded wording.** Search the merged documents for statements that the
   integration invalidated, such as a review still asserting the branch is not
   merged or not archived.

4. **Equivalence.** Prove the accepted content survived integration by comparing
   blobs, not by re-reading prose:

   ```bash
   git diff --stat <authoring-tip> origin/master -- <paths>
   ```

5. **Cleanup only after reachability is proven.** Delete a worktree or branch
   only when it holds no unique commits or tree objects.

   ```bash
   git rev-list --objects <branch> --not origin/master | wc -l
   git worktree remove <path>
   git branch -D <branch>
   ```

   Keep a branch if it holds a unique revision of any file, even when the
   difference looks cosmetic. Implying safety from "the merged version is
   better" is not proof that nothing is lost.

Scratch files written under `build/` are ignored, so removing a worktree leaves
them behind; clean them up deliberately.

## Validating a merged result

Prefer a detached worktree of the merge commit over reusing a branch that has
already been deleted or moved:

```bash
git worktree add --detach <temporary directory>\<verify> origin/master
```

Portable tests should pass with no ROM present; ROM-gated tests skip and report
the reason. Run the ROM-gated subset against the canonical ROM when the change
touches decode or extraction paths, then re-hash the ROM to prove it was only
read.
