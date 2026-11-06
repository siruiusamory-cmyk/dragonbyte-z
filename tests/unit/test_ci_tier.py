"""The change classifier: every tier, the fail-closed fallbacks and the record."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.dev import ci_tier

REPRESENTATIVE = (
    ("docs/*.md", ("docs/testing.md",), "docs"),
    ("a documentation image", ("public/dbz-map-browser.png",), "docs"),
    ("a portable test", ("tests/unit/test_hashing.py",), "code"),
    ("an ordinary tool", ("tools/dragonbyte/rows_model.py",), "code"),
    ("the shipping SDK", ("tools/webfoot/workbench/theme.py",), "shared"),
    ("the progress site", ("src/data/project.ts",), "shared"),
    ("the image codec", ("tools/webfoot/formats/webfoot_lz.py",), "rom"),
    ("runtime tooling", ("tools/runtime/mgba_identity.py",), "rom"),
    ("the ROM-gated suite", ("tests/integration/test_container_decode_synthetic.py",), "rom"),
    ("the test harness", ("tests/gates.py",), "premerge"),
    ("a workflow", (".github/workflows/ci.yml",), "premerge"),
    ("the dependency manifest", ("pyproject.toml",), "premerge"),
)


@pytest.mark.parametrize(("label", "paths", "tier"), REPRESENTATIVE, ids=[row[0] for row in REPRESENTATIVE])
def test_every_tier_is_reachable_by_its_own_paths(label, paths, tier):
    assert ci_tier.classify(paths).tier == tier


def test_an_unknown_path_selects_the_broadest_tier_and_names_itself():
    classification = ci_tier.classify(["mystery/new-surface.xyz"])

    assert classification.tier == "premerge"
    assert classification.complete_gate_required is True
    assert classification.unrecognized == ("mystery/new-surface.xyz",)


def test_a_mixed_change_takes_the_widest_tier_it_names():
    assert ci_tier.classify(["docs/testing.md", "tests/unit/test_hashing.py"]).tier == "code"
    assert ci_tier.classify(["docs/testing.md", "tools/webfoot/workbench/theme.py"]).tier == "shared"
    assert ci_tier.classify(["tests/unit/test_hashing.py", "mystery.txt"]).tier == "premerge"


def test_an_empty_change_is_not_a_silent_pass():
    classification = ci_tier.classify([])

    assert classification.tier == "premerge"
    assert ci_tier.selection(classification, []) == (
        "tests/unit",
        ci_tier.INTEGRATION_MEMBER,
    )


def test_a_rename_is_judged_by_both_of_its_paths():
    renamed = ci_tier.paths_from_name_status(
        "R100\ttools/webfoot/workbench/old_tab.py\ttools/webfoot/workbench/new_tab.py\n"
    )

    assert renamed == (
        "tools/webfoot/workbench/new_tab.py",
        "tools/webfoot/workbench/old_tab.py",
    )
    assert ci_tier.classify(renamed).tier == "shared"
    assert ci_tier.classify(["R100"]).tier == "premerge"


def test_a_deleted_documentation_file_widens_to_premerge():
    changes = ci_tier.changes_from_name_status("D\tdocs/decisions/0001-adr.md\n")
    classification = ci_tier.classify(changes)

    assert classification.tier == "premerge"
    assert ci_tier.selection(classification, changes) == (
        "tests/unit",
        ci_tier.INTEGRATION_MEMBER,
    )


def test_a_renamed_documentation_file_widens_to_premerge():
    line = "R100\tdocs/old-guide.md\tdocs/new-guide.md\n"
    changes = ci_tier.changes_from_name_status(line)

    assert ci_tier.classify(changes).tier == "premerge"
    assert ci_tier.paths_from_name_status(line) == (
        "docs/new-guide.md",
        "docs/old-guide.md",
    )


def test_a_modified_or_added_documentation_file_stays_docs():
    for line in ("M\tdocs/testing.md", "A\tdocs/new-guide.md"):
        changes = ci_tier.changes_from_name_status(line + "\n")
        classification = ci_tier.classify(changes)

        assert classification.tier == "docs", line
        assert ci_tier.selection(classification, changes) == (), line


def test_a_mixed_change_with_a_deleted_documentation_file_widens_to_premerge():
    changes = ci_tier.changes_from_name_status(
        "M\ttests/unit/test_hashing.py\nD\tdocs/testing.md\n"
    )
    classification = ci_tier.classify(changes)

    assert classification.tier == "premerge"
    assert ci_tier.selection(classification, changes) == (
        "tests/unit",
        ci_tier.INTEGRATION_MEMBER,
    )


def test_a_deleted_code_file_keeps_its_own_tier():
    changes = ci_tier.changes_from_name_status("D\ttools/dragonbyte/rows_model.py\n")

    assert ci_tier.classify(changes).tier == "code"


def test_a_rom_change_carries_the_rom_flag_even_when_a_wider_tier_wins():
    classification = ci_tier.classify(["tests/gates.py", "tools/runtime/mgba_identity.py"])

    assert classification.tier == "premerge"
    assert classification.rom_verification_required is True


def test_a_documentation_change_selects_no_test():
    classification = ci_tier.classify(["docs/testing.md", "CHANGELOG.md"])

    assert ci_tier.selection(classification, ["docs/testing.md", "CHANGELOG.md"]) == ()


def test_a_changed_portable_test_selects_itself():
    classification = ci_tier.classify(["tests/unit/test_hashing.py"])

    assert ci_tier.selection(classification, ["tests/unit/test_hashing.py"]) == (
        "tests/unit/test_hashing.py",
    )


def test_a_changed_module_selects_the_test_files_that_name_it():
    classification = ci_tier.classify(["tools/dragonbyte/datapage.py"])
    chosen = ci_tier.selection(classification, ["tools/dragonbyte/datapage.py"])

    assert chosen and all("datapage" in Path(name).stem for name in chosen), chosen


def test_a_module_no_test_file_names_selects_the_portable_suite():
    classification = ci_tier.classify(["tools/dragonbyte/diagnostics.py"])

    assert ci_tier.selection(classification, ["tools/dragonbyte/diagnostics.py"]) == (
        "tests/unit",
    )


def test_a_code_change_never_selects_a_rom_backed_integration_test():
    integration = ci_tier.REPOSITORY_ROOT / "tests" / "integration"
    matching = sorted(path.name for path in integration.glob("test_*app*_rom.py"))
    assert matching, "no integration test carries the stem, so this guard proves nothing"
    module = "tools/dragonbyte/app.py"
    chosen = ci_tier.selection(ci_tier.classify([module]), [module])

    assert chosen, "the code tier selected nothing"
    assert all(name.startswith("tests/unit/") for name in chosen), chosen


def test_a_shared_or_rom_change_selects_the_portable_suite():
    for path in ("tools/webfoot/workbench/theme.py", "tools/runtime/mgba_identity.py"):
        classification = ci_tier.classify([path])
        assert ci_tier.selection(classification, [path]) == ("tests/unit",), path


def test_a_premerge_change_selects_the_portable_suite_and_the_rom_free_member():
    classification = ci_tier.classify(["pyproject.toml"])

    assert ci_tier.selection(classification, ["pyproject.toml"]) == (
        "tests/unit",
        ci_tier.INTEGRATION_MEMBER,
    )


def test_the_record_names_the_commit_and_the_tier(tmp_path, monkeypatch):
    monkeypatch.setattr(ci_tier, "REPOSITORY_ROOT", tmp_path)
    classification = ci_tier.classify(["docs/testing.md"])

    record = ci_tier.write_record("a" * 40, "b" * 40, classification, ())

    text = record.read_text(encoding="utf-8")
    assert f"sha            : {'a' * 40}" in text
    assert "tier           : docs" in text
    assert "verdict" not in text
    assert record.parent.name == "a" * 40
    assert (record.parent / "selection.txt").read_text(encoding="utf-8") == ""


def test_the_rules_only_name_declared_tiers_and_keep_the_rom_free_member_rom_gated():
    declared = set(ci_tier.TIER_ORDER)

    assert {tier for _, tier in ci_tier.TIER_RULES} <= declared
    assert ci_tier.tier_of(ci_tier.INTEGRATION_MEMBER) == "rom"


def test_a_measured_path_reports_every_pin_not_only_the_one_it_was_asked_about():
    """The DBZ-008 shape: a brief names one pin and its sibling moves too.

    The profile catalogue is inside the census set, so a change to it moves the
    whole-tree pair and the enforcement pair together. The report therefore names
    every pin, which is what a specification has to declare.
    """
    from tests.unit import address_literal_census as census

    lines = ci_tier.measurement_lines(
        [("M", "tools/webfoot/data/roms.yaml")]
    )

    named = " ".join(lines)
    assert "pin CENSUS_HEX5" in named
    assert "pin ENFORCEMENT_ROM_HEX" in named, named
    assert set(census.PIN_NAMES) == set(census.pinned())


def test_the_row_that_moves_with_a_measured_path_is_named_with_its_counts():
    from tests.unit import address_literal_census as census

    row = [
        entry for entry in census.EXEMPTIONS
        if entry.path == "tools/webfoot/data/roms.yaml"
    ][0]

    named = [
        line for line in ci_tier.measurement_lines([("M", row.path)])
        if f"row {row.path}" in line
    ]

    assert named, "the changed path has an exemption row and it was not reported"
    assert str((row.hex5, row.rom_hex, row.decimal)) in named[0]


def test_an_unmeasured_change_reports_nothing():
    assert ci_tier.measurement_lines([("M", "docs/testing.md")]) == []
