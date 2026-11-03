"""The two GitHub workflows: the partitioned PR gate and the dispatched full regression.

The PR gate is the only automatic workflow. ``prepare`` classifies the change with
``tools.dev.ci_tier``, runs the digest check and the tree-wide quality gates once,
and publishes the selected tests as an artifact; four ``partition`` jobs run that
one selection under the existing shard variables, so the tests are the same in
every job and the selection is never recomputed; ``record`` turns the whole run
into one verdict and names every failure. The full regression keeps the sharded
ten-job structure and runs only when a human dispatches it;
``scripts/local-ci.ps1`` and the merge gate are what make it mandatory before
integration. These tests pin both halves, so a job, a trigger, a pin or a gate
cannot drift out of either file.
"""

from __future__ import annotations

import re

import yaml

from tests.gates import REPOSITORY_ROOT
from tools.quality import architecture

WORKFLOWS = REPOSITORY_ROOT / ".github" / "workflows"
FAST_PATH = WORKFLOWS / "ci.yml"
FULL_PATH = WORKFLOWS / "full-regression.yml"

PINNED_ACTION = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}\Z")
FLOATING_REF = re.compile(r"@(?:main|master|latest|v[0-9]+)\b")
USES_LINE = re.compile(r"^[ \t]*uses:[ \t]*(\S+)(.*)$", re.MULTILINE)
MODULE_INVOCATION = re.compile(r"-m\s+([A-Za-z_][A-Za-z0-9_.]*)")

FAST_PREPARE_JOB = "prepare"
FAST_PARTITION_JOB = "partition"
FAST_RECORD_JOB = "record"
FAST_JOB_NAMES = (FAST_PREPARE_JOB, FAST_PARTITION_JOB, FAST_RECORD_JOB)
PARTITION_COUNT = 4
FULL_JOB_NAMES = ("shard", "gates", "integration", "adjacency", "report")
TRACKED_GATE_BODIES = (
    r"ci\test_sdk.ps1",
    r"ci\adjacency.ps1",
    r"ci\test_integration.ps1",
)
ALL_TREE_GATES = ("public_surface", "architecture", "public_release", "readability")
INTEGRATION_MEMBER = "tests/integration/test_container_decode_synthetic.py"

ROM_NEEDLES = ("." + "gba", "." + "agb", "." + "sav", "save" + "state")
SECRET_NEEDLES = ("sec" + "rets", "gh" + "p_", "api" + "_key", "pass" + "word", "to" + "ken")

AUTOCRLF_OFF = "git config --global core.autocrlf false"
AUTOCRLF_READ_BACK = "git config --get core.autocrlf"
VOLUME_FROM_WORKSPACE = "Split-Path -Qualifier $env:GITHUB_WORKSPACE"
LEDGER_PATH = "docs/research/ROM_EDITOR_COVERAGE_LEDGER.md"
CHECKOUT_OWNER = "actions/checkout"
SETUP_PYTHON_OWNER = "actions/setup-python"
UPLOAD_OWNER = "actions/upload-artifact"
DOWNLOAD_OWNER = "actions/download-artifact"
SHARD_JOB = "shard"
SHARD_MATRIX_SIZE = 10


def _text(path) -> str:
    return path.read_text(encoding="utf-8")


def _document(path) -> dict:
    return yaml.safe_load(_text(path))


def _triggers(document: dict) -> dict:
    return document.get("on") or document.get(True)


def _jobs(path) -> dict:
    return _document(path)["jobs"]


def _steps(path, job: str) -> list[dict]:
    return _jobs(path)[job]["steps"]


def _step(path, job: str, owner: str) -> dict:
    matches = [
        step
        for step in _steps(path, job)
        if str(step.get("uses", "")).startswith(owner + "@")
    ]
    assert len(matches) == 1, (job, owner)
    return matches[0]


def _uses_index(path, job: str, owner: str) -> int:
    matches = [
        index
        for index, step in enumerate(_steps(path, job))
        if str(step.get("uses", "")).startswith(owner + "@")
    ]
    assert len(matches) == 1, (job, owner)
    return matches[0]


def _run_indices(path, job: str, fragment: str) -> list[int]:
    return [
        index
        for index, step in enumerate(_steps(path, job))
        if fragment in str(step.get("run", ""))
    ]


def _run_index(path, job: str, fragment: str) -> int:
    matches = _run_indices(path, job, fragment)
    assert len(matches) == 1, (job, fragment)
    return matches[0]


def _run_script(path, job: str, fragment: str) -> str:
    return str(_steps(path, job)[_run_index(path, job, fragment)]["run"])


def test_the_workflow_parses_with_the_two_triggers_and_the_five_windows_jobs():
    """Prevents: a trigger or the runner label being dropped from either workflow."""
    gate = _document(FAST_PATH)
    triggers = _triggers(gate)
    assert set(triggers) == {"pull_request", "push"}
    assert triggers["pull_request"] is None
    assert triggers["push"] == {"branches": ["master"]}
    assert gate["defaults"]["run"]["shell"] == "pwsh"

    full = _document(FULL_PATH)
    assert set(_triggers(full)) == {"workflow_dispatch"}
    assert set(full["jobs"]) == set(FULL_JOB_NAMES)
    for name, job in full["jobs"].items():
        assert job["runs-on"] == "windows-latest", name
        assert isinstance(job["timeout-minutes"], int), name


def test_the_prepare_job_owns_every_step_that_must_run_once():
    """Prevents: a once-only step being repeated per partition, and the one-job shape creeping back."""
    jobs = _jobs(FAST_PATH)

    assert set(jobs) == set(FAST_JOB_NAMES)
    for name in FAST_JOB_NAMES:
        assert jobs[name]["runs-on"] == "windows-latest", name
        assert isinstance(jobs[name]["timeout-minutes"], int), name
    once = (
        "-m tools.dev.ci_tier",
        INTEGRATION_MEMBER,
        "-m tools.quality.public_surface",
        "-m tools.quality.readability",
        "-m tools.quality.architecture",
        "-m tools.quality.public_release",
    )
    for fragment in once:
        assert len(_run_indices(FAST_PATH, FAST_PREPARE_JOB, fragment)) == 1, fragment
        for name in (FAST_PARTITION_JOB, FAST_RECORD_JOB):
            assert _run_indices(FAST_PATH, name, fragment) == [], (name, fragment)
    assert len(_run_indices(FAST_PATH, FAST_PREPARE_JOB, "-m pip install")) == 1
    assert _uses_index(FAST_PATH, FAST_PREPARE_JOB, CHECKOUT_OWNER) < _run_index(
        FAST_PATH, FAST_PREPARE_JOB, "-m pip install"
    )


def test_the_partition_job_runs_four_independent_shards_of_the_one_selection():
    """Prevents: a partition that recomputes or narrows the selection, or a raised restart allowance."""
    job = _jobs(FAST_PATH)[FAST_PARTITION_JOB]

    assert job["needs"] == FAST_PREPARE_JOB
    assert job["strategy"]["fail-fast"] is False
    assert job["strategy"]["matrix"]["partition"] == list(range(PARTITION_COUNT))
    assert str(job["env"]["WEBFOOT_SHARD_COUNT"]) == str(PARTITION_COUNT)
    assert job["env"]["WEBFOOT_SHARD_INDEX"] == "${{ matrix.partition }}"
    assert job["env"]["QT_QPA_PLATFORM"] == "offscreen"
    script = _run_script(FAST_PATH, FAST_PARTITION_JOB, "--dist loadfile")

    assert "selection.txt" in script
    assert "@selection" in script
    assert "-n 4" in script
    assert "--max-worker-restart=0" in script
    assert "--durations=25" in script
    assert "--durations-min=1.0" in script
    assert "throw" in script
    assert _uses_index(FAST_PATH, FAST_PARTITION_JOB, DOWNLOAD_OWNER) < _run_index(
        FAST_PATH, FAST_PARTITION_JOB, "--dist loadfile"
    )


def test_no_suite_invocation_grants_a_worker_restart_or_a_skip():
    """Prevents: a concentrated failure being papered over by a restart allowance or a filter."""
    text = _text(FAST_PATH)

    assert text.count("--max-worker-restart=0") == 1
    assert re.search(r"--max-worker-restart=(?!0\b)\d", text) is None
    assert re.search(r"(^|\s)(-k|--deselect|--ignore|--maxfail)\b", text) is None
    assert re.search(r"(^|\s)skip(\s|$)", text) is None


def test_an_empty_partition_is_tolerated_only_when_every_node_was_deselected():
    """Prevents: a green change going red because a small selection leaves one shard nothing,
    and the opposite, a real failure being excused as an empty shard."""
    script = _run_script(FAST_PATH, FAST_PARTITION_JOB, "--max-worker-restart=0")

    assert "deselected in " in script
    assert "-eq 5" in script
    assert re.search(r"\^\(FAILED\|ERROR\) ", script) is not None
    assert "no tests ran" in script
    assert "throw" in script


def test_the_record_verdict_calls_anything_but_success_or_skipped_a_failure():
    """Prevents: a cancelled or timed-out partition being recorded as a successful gate."""
    script = _run_script(FAST_PATH, FAST_RECORD_JOB, "GITHUB_STEP_SUMMARY")

    assert "needs.partition.result != 'success'" in script
    assert "needs.partition.result != 'skipped'" in script
    assert "needs.partition.result == 'failure'" not in script


def test_the_record_job_needs_both_halves_and_always_publishes_the_verdict():
    """Prevents: a record that claims success while a partition is red, or no record at all."""
    job = _jobs(FAST_PATH)[FAST_RECORD_JOB]

    assert set(job["needs"]) == {FAST_PREPARE_JOB, FAST_PARTITION_JOB}
    assert job["if"] == "always()"
    downloads = [
        step
        for step in _steps(FAST_PATH, FAST_RECORD_JOB)
        if str(step.get("uses", "")).startswith(DOWNLOAD_OWNER + "@")
    ]
    assert len(downloads) == 2
    script = _run_script(FAST_PATH, FAST_RECORD_JOB, "GITHUB_STEP_SUMMARY")

    assert "record.txt" in script
    assert "verdict" in script
    assert "needs.partition.result" in script
    assert "FAILED" in script and "ERROR" in script
    upload = _step(FAST_PATH, FAST_RECORD_JOB, UPLOAD_OWNER)
    assert upload["if"] == "always()"
    assert upload["with"]["name"] == "pr-gate-record"
    assert "build/ci-fast/" in upload["with"]["path"]


def test_the_pr_gate_cancels_a_superseded_run_on_the_same_ref():
    """Prevents: a superseded update paying for a hosted job it no longer needs."""
    concurrency = _document(FAST_PATH)["concurrency"]

    assert "github.ref" in concurrency["group"]
    assert concurrency["cancel-in-progress"] is True


def test_every_action_is_pinned_to_a_commit_with_its_version_in_the_step_name():
    """Prevents: a mutable major tag silently changing what CI runs."""
    for path in (FAST_PATH, FULL_PATH):
        text = _text(path)
        owners = []
        for reference, _rest in USES_LINE.findall(text):
            assert PINNED_ACTION.fullmatch(reference), (path.name, reference)
            owners.append(reference.split("@")[0])
        assert FLOATING_REF.search(text) is None, path.name
        for required in (CHECKOUT_OWNER, SETUP_PYTHON_OWNER, UPLOAD_OWNER):
            assert required in owners, (path.name, required)
        for job, job_body in _jobs(path).items():
            for step in job_body["steps"]:
                if "uses" not in step:
                    continue
                name = str(step["name"])
                owner = str(step["uses"]).split("@")[0]
                assert owner in name, (path.name, job, name)
                assert re.search(r"v\d", name), (path.name, job, name)
    assert DOWNLOAD_OWNER in _text(FULL_PATH)


def test_the_shard_job_runs_ten_parallel_slices_of_the_portable_suite():
    """Prevents: a shard count or an environment variable drifting apart."""
    job = _jobs(FULL_PATH)[SHARD_JOB]

    assert job["strategy"]["fail-fast"] is False
    assert len(job["strategy"]["matrix"]["shard"]) == SHARD_MATRIX_SIZE
    assert str(job["env"]["WEBFOOT_SHARD_COUNT"]) == str(SHARD_MATRIX_SIZE)
    assert job["env"]["WEBFOOT_SHARD_INDEX"] == "${{ matrix.shard }}"
    script = _run_script(FULL_PATH, SHARD_JOB, "tests/unit -q -n 4 --dist loadfile")
    assert "report-shard-${{ matrix.shard }}.xml" in script
    upload = _step(FULL_PATH, SHARD_JOB, UPLOAD_OWNER)
    assert upload["if"] == "always()"
    assert "report-shard-${{ matrix.shard }}.xml" in upload["with"]["path"]
    assert "artifacts/steps" in upload["with"]["path"]


def test_the_four_quality_gates_are_their_own_job_one_step_each():
    """Prevents: the gates being folded back into the suite's job."""
    for gate in ALL_TREE_GATES:
        assert len(_run_indices(FULL_PATH, "gates", f"-m tools.quality.{gate}")) == 1, gate


def test_the_gates_job_fills_the_pip_cache_it_asks_for_and_installs_first():
    """Prevents: a cached pip setup whose cache the job never creates."""
    install = _run_index(FULL_PATH, "gates", "-m pip install")
    script = _run_script(FULL_PATH, "gates", "-m pip install")

    assert script.strip().startswith("python -m pip install"), script
    assert "--quiet" in script, script
    assert re.search(r"-e\s+\.(\s|$)", script), script
    assert "[" not in script, "the gates job installs extras the gate set does not need"
    for gate in ALL_TREE_GATES:
        assert install < _run_index(FULL_PATH, "gates", f"-m tools.quality.{gate}"), gate


def test_the_integration_job_runs_the_rom_free_member_by_name():
    """Prevents: the integration member widening to the ROM-gated directory."""
    script = _run_script(FULL_PATH, "integration", INTEGRATION_MEMBER)

    assert "-q" in script
    install = _run_script(FULL_PATH, "integration", "-m pip install")
    assert '.[dev]' in install and 'workbench' not in install


def test_the_adjacency_job_runs_both_orders_in_one_step_and_carries_the_exit():
    """Prevents: an exit after the forward order skipping the reverse order."""
    forward = _run_indices(FULL_PATH, "adjacency", "-Order forward")

    assert forward, "the forward order is not run"
    assert forward == _run_indices(FULL_PATH, "adjacency", "-Order reverse")
    script = _steps(FULL_PATH, "adjacency")[forward[0]]["run"]
    assert "-m scripts.adjacency_run" in script
    assert "$forward = $LASTEXITCODE" in script
    assert "$forward -ne 0" in script


def test_the_report_job_needs_the_shards_and_always_publishes():
    """Prevents: the red run being the one with no merged report."""
    job = _jobs(FULL_PATH)["report"]

    assert SHARD_JOB in job["needs"]
    assert job["if"] == "always()"
    _step(FULL_PATH, "report", DOWNLOAD_OWNER)
    assert "ci/merge_junit.py" in _run_script(FULL_PATH, "report", "ci/merge_junit.py")
    assert "merged-suite.log" in _run_script(FULL_PATH, "report", "merged-suite.log")
    upload = _step(FULL_PATH, "report", UPLOAD_OWNER)
    assert upload["if"] == "always()"
    assert "report.xml" in upload["with"]["path"]


def test_every_job_keeps_the_committed_bytes_and_the_temporary_root():
    """Prevents: one job quietly losing a precondition the others carry."""
    for name in FULL_JOB_NAMES:
        checkout = _uses_index(FULL_PATH, name, CHECKOUT_OWNER)
        assert _run_index(FULL_PATH, name, AUTOCRLF_OFF) < checkout, name
        assert AUTOCRLF_READ_BACK in _run_script(FULL_PATH, name, AUTOCRLF_OFF)
        assert _run_index(FULL_PATH, name, LEDGER_PATH) > checkout, name
        assert "[char]13" in _run_script(FULL_PATH, name, LEDGER_PATH)
        root = _run_index(FULL_PATH, name, VOLUME_FROM_WORKSPACE)
        assert root > checkout, name
        script = _run_script(FULL_PATH, name, VOLUME_FROM_WORKSPACE)
        assert 'Add-Content -Path $env:GITHUB_ENV -Value "TMP=' in script
        assert 'Add-Content -Path $env:GITHUB_ENV -Value "TEMP=' in script

    text = _text(FULL_PATH)
    assert text.count(AUTOCRLF_OFF) == 1
    assert text.count(VOLUME_FROM_WORKSPACE) == 1
    assert text.count(LEDGER_PATH) == 1
    assert _run_index(FULL_PATH, SHARD_JOB, VOLUME_FROM_WORKSPACE) < _run_index(
        FULL_PATH, SHARD_JOB, "tests/unit -q -n 4 --dist loadfile"
    )

    for name in (FAST_PREPARE_JOB, FAST_PARTITION_JOB):
        checkout = _uses_index(FAST_PATH, name, CHECKOUT_OWNER)
        assert _run_index(FAST_PATH, name, AUTOCRLF_OFF) < checkout, name
        assert AUTOCRLF_READ_BACK in _run_script(FAST_PATH, name, AUTOCRLF_OFF)
        assert _run_index(FAST_PATH, name, LEDGER_PATH) > checkout, name
        assert "[char]13" in _run_script(FAST_PATH, name, LEDGER_PATH)
        root = _run_index(FAST_PATH, name, VOLUME_FROM_WORKSPACE)
        assert root > checkout, name
        script = _run_script(FAST_PATH, name, VOLUME_FROM_WORKSPACE)
        assert 'Add-Content -Path $env:GITHUB_ENV -Value "TMP=' in script
        assert 'Add-Content -Path $env:GITHUB_ENV -Value "TEMP=' in script


def test_the_runner_python_is_the_minor_version_the_project_declares():
    """Prevents: the gate running on an interpreter the project does not declare."""
    for name in (FAST_PREPARE_JOB, FAST_PARTITION_JOB):
        step = _step(FAST_PATH, name, SETUP_PYTHON_OWNER)
        assert step["with"]["python-version"] == "3.12", name
        assert step["with"]["cache"] == "pip", name
        assert step["with"]["cache-dependency-path"] == "pyproject.toml", name
    for name in FULL_JOB_NAMES:
        step = _step(FULL_PATH, name, SETUP_PYTHON_OWNER)
        assert step["with"]["python-version"] == "3.12", name
        assert step["with"]["cache"] == "pip", name
        assert step["with"]["cache-dependency-path"] == "pyproject.toml", name


def test_every_checkout_keeps_no_credential_and_fetches_the_history_the_gate_diffs():
    """Prevents: a shallow clone failing the classifier's own diff, or a stored credential."""
    for path, names in (
        (FAST_PATH, (FAST_PREPARE_JOB, FAST_PARTITION_JOB)),
        (FULL_PATH, FULL_JOB_NAMES),
    ):
        for name in names:
            step = _step(path, name, CHECKOUT_OWNER)
            assert step["with"]["persist-credentials"] is False, (path.name, name)
            assert step["with"]["fetch-depth"] == 0, (path.name, name)


def test_the_workflow_commands_are_the_gate_set_the_tracked_bodies_carry():
    """Prevents: the workflow and the reviewed gate bodies drifting apart."""
    workflow = _text(FULL_PATH)

    for body in TRACKED_GATE_BODIES:
        text = (REPOSITORY_ROOT / body).read_text(encoding="utf-8")
        for module in sorted(set(MODULE_INVOCATION.findall(text))):
            assert module in workflow, (body, module)
    for gate in ("public_surface", "readability"):
        assert f"-m tools.quality.{gate} --all" in workflow
    assert INTEGRATION_MEMBER in workflow


def test_the_workflow_directory_is_a_declared_top_level_root():
    """Prevents: a workflow tripping the repository purity rule it lives under."""
    for name in ("ci.yml", "full-regression.yml"):
        assert architecture._rule_top_level_roots([f".github/workflows/{name}"]) == [], name


def test_the_workflow_names_no_rom_file_and_no_secret():
    """Prevents: a commercial image or a credential entering a public workflow."""
    for path in (FAST_PATH, FULL_PATH):
        lowered = _text(path).lower()
        for needle in ROM_NEEDLES + SECRET_NEEDLES:
            assert needle not in lowered, (path.name, needle)


def test_the_pr_gate_installs_the_extras_the_portable_suite_imports():
    """Prevents: a GUI module collapsing to a whole-file skip over every change."""
    for name in (FAST_PREPARE_JOB, FAST_PARTITION_JOB):
        script = _run_script(FAST_PATH, name, "-m pip install")

        assert script.strip().startswith("python -m pip install"), script
        assert "--quiet" in script, script
        for extra in ("dev", "workbench", "research"):
            assert extra in script, (name, extra)


def test_the_pr_gate_classifies_the_change_with_the_one_classifier():
    """Prevents: a second copy of the path rules, or a gate that guesses the tier."""
    assert re.search(r"-m\s+tools\.dev\.ci_tier", _text(FAST_PATH))
    script = _run_script(FAST_PATH, FAST_PREPARE_JOB, "-m tools.dev.ci_tier")

    assert "--base" in script and "--head" in script
    assert "$env:GITHUB_SHA" in script
    assert "throw" in script, "a classification failure must fail the job"
    assert _jobs(FAST_PATH)[FAST_PREPARE_JOB]["outputs"]["tier"] == (
        "${{ steps.classify.outputs.tier }}"
    )


def test_the_pr_gate_checks_the_committed_digests_before_it_runs_the_selection():
    """Prevents: the pinned fixture drifting while a green focused run hides it."""
    identity = _run_index(FAST_PATH, FAST_PREPARE_JOB, INTEGRATION_MEMBER)

    assert _steps(FAST_PATH, FAST_PREPARE_JOB)[identity]["if"] == "env.TIER != 'docs'"
    assert "throw" in _run_script(FAST_PATH, FAST_PREPARE_JOB, INTEGRATION_MEMBER)
    assert _jobs(FAST_PATH)[FAST_PARTITION_JOB]["needs"] == FAST_PREPARE_JOB


def test_the_pr_gate_runs_the_tests_the_classifier_selected():
    """Prevents: the classification being written and then ignored."""
    script = _run_script(FAST_PATH, FAST_PARTITION_JOB, "--dist loadfile")

    assert "selection.txt" in script
    assert "@selection" in script
    assert "-n 4" in script
    assert "build\\ci-fast" in script
    assert "throw" in script


def test_a_documentation_change_skips_the_tests_and_runs_every_quality_gate():
    """Prevents: a documentation path escaping a gate that reads documentation."""
    for gate in ALL_TREE_GATES:
        index = _run_index(FAST_PATH, FAST_PREPARE_JOB, f"-m tools.quality.{gate}")
        assert "if" not in _steps(FAST_PATH, FAST_PREPARE_JOB)[index], gate
    index = _run_index(FAST_PATH, FAST_PREPARE_JOB, INTEGRATION_MEMBER)
    assert _steps(FAST_PATH, FAST_PREPARE_JOB)[index]["if"] == "env.TIER != 'docs'"
    assert _jobs(FAST_PATH)[FAST_PARTITION_JOB]["if"] == (
        "needs.prepare.outputs.tier != 'docs'"
    )


def test_the_pr_gate_keeps_every_quality_gate_the_local_record_runs():
    """Prevents: a tree-wide gate being dropped from the automatic path."""
    for gate in ALL_TREE_GATES:
        assert (
            len(_run_indices(FAST_PATH, FAST_PREPARE_JOB, f"-m tools.quality.{gate}")) == 1
        ), gate
    assert "-m tools.quality.public_surface --all" in _text(FAST_PATH)
    assert "-m tools.quality.readability --all" in _text(FAST_PATH)


def test_the_prepare_job_publishes_a_record_that_names_the_commit_and_the_tier():
    """Prevents: a green run nobody can tie to a commit or to a decision."""
    index = _run_index(FAST_PATH, FAST_PREPARE_JOB, "GITHUB_STEP_SUMMARY")
    assert _steps(FAST_PATH, FAST_PREPARE_JOB)[index]["if"] == "always()"
    script = _run_script(FAST_PATH, FAST_PREPARE_JOB, "GITHUB_STEP_SUMMARY")

    assert "record.txt" in script
    assert "sha" in script and "tier" in script
    upload = _step(FAST_PATH, FAST_PREPARE_JOB, UPLOAD_OWNER)
    assert upload["if"] == "always()"
    assert upload["with"]["name"] == "pr-gate-selection"
    assert "build/ci-fast/" in upload["with"]["path"]
