"""Classify a change into the gate tier it must run, and select that tier's tests.

A deleted or renamed documentation path widens to premerge, because tracked tests
read documentation content; an added or modified one stays docs.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from fnmatch import fnmatch
import os
from pathlib import Path
import subprocess

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RECORD_DIRECTORY = Path("build") / "ci-fast"
INTEGRATION_MEMBER = "tests/integration/test_container_decode_synthetic.py"

TIER_ORDER = ("docs", "code", "shared", "rom", "premerge")

TIER_RULES: tuple[tuple[str, str], ...] = (
    ("docs/*", "docs"),
    ("*.md", "docs"),
    ("public/*", "docs"),
    ("LICENSE", "docs"),
    ("THIRD-PARTY-NOTICES.md", "docs"),
    ("tools/runtime/*", "rom"),
    ("tools/research/*", "rom"),
    ("tools/ghidra/*", "rom"),
    ("tools/mgba_probe/*", "rom"),
    ("tools/save_catalogue/*", "rom"),
    ("tools/webfoot/formats/*", "rom"),
    ("config/roms.yaml", "rom"),
    ("tests/integration/*", "rom"),
    ("pyproject.toml", "premerge"),
    ("uv.lock", "premerge"),
    (".github/*", "premerge"),
    ("ci/*", "premerge"),
    ("scripts/*", "premerge"),
    ("tools/quality/*", "premerge"),
    ("tools/dev/*", "premerge"),
    ("tests/conftest.py", "premerge"),
    ("tests/gates.py", "premerge"),
    ("tests/shards.py", "premerge"),
    ("tests/rom_support.py", "premerge"),
    ("config/*", "premerge"),
    ("package.json", "premerge"),
    ("package-lock.json", "premerge"),
    ("astro.config.mjs", "premerge"),
    ("tsconfig.json", "premerge"),
    ("wrangler.jsonc", "premerge"),
    ("upstreams.lock", "premerge"),
    ("*.spec.in", "premerge"),
    ("*.version.txt", "premerge"),
    ("tools/webfoot/*", "shared"),
    ("src/*", "shared"),
    ("tools/dragonbyte/*", "code"),
    ("tools/export/*", "code"),
    ("tools/qa/*", "code"),
    ("tools/buufury_text/*", "code"),
    ("tests/unit/*", "code"),
)


@dataclass(frozen=True)
class Classification:
    tier: str
    rom_verification_required: bool
    complete_gate_required: bool
    unrecognized: tuple[str, ...]


def tier_of(path: str) -> str | None:
    normalized = path.replace("\\", "/")
    for pattern, tier in TIER_RULES:
        if fnmatch(normalized, pattern):
            return tier
    return None


def classify(changes) -> Classification:
    tiers = []
    unrecognized = []
    for change in changes:
        status, path = change if isinstance(change, tuple) else ("", change)
        tier = tier_of(path)
        if tier is None:
            unrecognized.append(path.replace("\\", "/"))
            tier = "premerge"
        elif tier == "docs" and status in ("D", "R"):
            tier = "premerge"
        tiers.append(tier)
    if not tiers:
        return Classification("premerge", False, True, ())
    widest = max(tiers, key=TIER_ORDER.index)
    return Classification(
        widest,
        "rom" in tiers,
        widest == "premerge",
        tuple(sorted(unrecognized)),
    )


def test_files() -> tuple[str, ...]:
    found = []
    for path in sorted((REPOSITORY_ROOT / "tests" / "unit").rglob("test_*.py")):
        found.append(path.relative_to(REPOSITORY_ROOT).as_posix())
    return tuple(found)


def selection(classification: Classification, paths) -> tuple[str, ...]:
    if classification.tier == "docs":
        return ()
    if classification.tier == "premerge":
        return ("tests/unit", INTEGRATION_MEMBER)
    if classification.tier in ("shared", "rom"):
        return ("tests/unit",)
    index = test_files()
    chosen: list[str] = []
    for path in paths:
        if isinstance(path, tuple):
            path = path[1]
        normalized = path.replace("\\", "/")
        if tier_of(normalized) != "code":
            continue
        if not (REPOSITORY_ROOT / normalized).is_file():
            return ("tests/unit",)
        stem = Path(normalized).stem
        matches = [name for name in index if stem in Path(name).stem]
        if not matches:
            return ("tests/unit",)
        chosen.extend(matches)
    return tuple(sorted(dict.fromkeys(chosen))) or ("tests/unit",)


def paths_from_name_status(text: str) -> tuple[str, ...]:
    return tuple(sorted({path for _status, path in changes_from_name_status(text)}))


def changes_from_name_status(text: str) -> tuple[tuple[str, str], ...]:
    found = []
    for line in text.splitlines():
        fields = line.split("\t")
        if len(fields) < 2:
            continue
        status = fields[0][:1].upper()
        found.extend(
            (status, field.replace("\\", "/")) for field in fields[1:] if field
        )
    return tuple(sorted(found))


def changed_paths(base: str, head: str) -> tuple[tuple[str, str], ...]:
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(REPOSITORY_ROOT),
            "diff",
            "--name-status",
            "--find-renames",
            f"{base}...{head}",
        ],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise SystemExit(
            f"cannot read the change {base}...{head}: {completed.stderr.strip()}"
        )
    return changes_from_name_status(completed.stdout)


def resolve(sha: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(REPOSITORY_ROOT), "rev-parse", "--verify", f"{sha}^{{commit}}"],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise SystemExit(f"cannot resolve {sha} to a commit: {completed.stderr.strip()}")
    return completed.stdout.strip()


def write_record(sha: str, base: str, classification: Classification, chosen) -> Path:
    directory = REPOSITORY_ROOT / RECORD_DIRECTORY / sha
    directory.mkdir(parents=True, exist_ok=True)
    lines = [
        "fast gate record",
        "================",
        f"sha            : {sha}",
        f"base           : {base}",
        f"tier           : {classification.tier}",
        f"rom_verification_required : {str(classification.rom_verification_required).lower()}",
        f"complete_gate_required    : {str(classification.complete_gate_required).lower()}",
    ]
    lines.extend(f"unrecognized   : {path}" for path in classification.unrecognized)
    lines.extend(["selection", "---------"])
    lines.extend(f"  {item}" for item in chosen)
    record = directory / "record.txt"
    record.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (directory / "selection.txt").write_text(
        "".join(f"{item}\n" for item in chosen), encoding="utf-8"
    )
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args(argv)

    sha = resolve(args.head)
    changes = changed_paths(args.base, args.head)
    classification = classify(changes)
    chosen = selection(classification, changes)
    record = write_record(sha, args.base, classification, chosen)

    print(f"tier: {classification.tier}")
    print(f"rom_verification_required: {str(classification.rom_verification_required).lower()}")
    print(f"complete_gate_required: {str(classification.complete_gate_required).lower()}")
    print(f"changed paths: {len(changes)}")
    print(f"selection: {' '.join(chosen) or '(none)'}")
    print(f"record: {record.relative_to(REPOSITORY_ROOT).as_posix()}")

    environment = os.environ.get("GITHUB_ENV")
    if environment:
        with open(environment, "a", encoding="utf-8") as handle:
            handle.write(f"TIER={classification.tier}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
