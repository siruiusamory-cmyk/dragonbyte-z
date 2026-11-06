# Naming conventions

This page records the naming this repository already uses, with the evidence for
each convention counted from the tree at `ca128adc`. It is descriptive before it
is prescriptive: a rule here exists because the code follows it, not because a
style guide prefers it. Where a convention is not enforced by a gate, this page
says so instead of implying a check that does not exist.

Human-facing **display names** are a different subject and are governed by
[ADR 0005](decisions/0005-naming-precedence.md); this page governs identifier
spelling in code, tests, data files and record identities.

## The conventions

| # | what | rule | evidence in this tree |
| --- | --- | --- | --- |
| 1 | module files | `snake_case.py` | 340 of 378 modules under `tools/` match `[a-z][a-z0-9_]*`; the 38 others are the special forms `__init__`, `__main__`, `_pyinstaller_entry`, `_version`, `_local_state_paths`, `_public_surface_tables`, `_io`. Example: `tools/webfoot/scripts.py` |
| 2 | classes | `PascalCase`; a module-private class keeps the underscore (`_Name`) | 936 `PascalCase` and 43 `_PascalCase` top-level classes under `tools/`. Examples: `class RomProfileCatalog` (`tools/webfoot/profile.py:1110`), `class ScriptError` (`tools/webfoot/formats/script_vm.py:6`) |
| 3 | functions and methods | `snake_case`; module-private takes a leading underscore | 1,866 public and 914 private top-level functions under `tools/`. Examples: `def build_project` (`tools/webfoot/build.py:1484`), `def _print_identification` (`tools/webfoot/cli.py:719`) |
| 4 | constants | `UPPER_SNAKE`; a value that is not proven carries the `_RAW` suffix | 2,278 module-level `UPPER_SNAKE` constants under `tools/`; 7 names end `_RAW`. Examples: `GBA_ROM_BASE` (`tools/webfoot/binary.py:8`), `TRANSITION_CLASS_A_RAW` (`tools/webfoot/formats/map_transitions.py:37`), `FACTORY_RAW` (`tools/webfoot/formats/map_placements.py:14`) |
| 5 | test functions | `test_` followed by a sentence in `snake_case`, stating the behaviour | 6,681 of 6,695 test functions match; mean 9.13 underscore-separated words. Examples: `test_a_screen_that_draws_nothing_is_missing_and_one_that_draws_elsewhere_is_extra` |
| 6 | test files | `test_<subject>.py`, one subject per file | 387 `test_*.py` modules: 289 under `tests/unit/`, 98 under `tests/integration/` |
| 7 | command subcommands | `kebab-case` | `relocation-proof`, `validate-map-entries`, `refs-to`, `refs-from` (`python -m tools.webfoot --help`, exit 0) |
| 8 | record identities | `<kind>:<id>`, with a map's id zero-padded to four digits | `map:0040` (`docs/PROJECT_STATE.md:609`), `enemy:434` (`docs/rom-profiles.md:137`), `text:0010`, `character:0` (`webfoot text set --help`, `webfoot stats set --help`) |
| 9 | ROM profile ids | `<game>_<region>_rev<revision>_<crc32>` | `buus_fury_usa_rev0_01c1707f` (`config/roms.yaml:4`), `legacy_of_goku_ii_usa_rev0_204142e1` |
| 10 | capability ids | `kebab-case`, stable, used as the site's row key and a test join key | `map-browser`, `shell`, `atlas`, `inspector` (`src/data/capabilities.json`) |
| 11 | documentation files | `lower-case-with-hyphens.md` under `docs/`; research records use upper-case names | `docs/README.md:64-65` states the rule; `docs/rom-profiles.md` and `docs/research/ROM_EDITOR_COVERAGE_LEDGER.md` are the two shapes |
| 12 | frozen-build entry shims | `<package>/_pyinstaller_entry.py` | 5 shims: `tools/webfoot/{enemyrand,warprand,workbench}/_pyinstaller_entry.py`, `tools/dragonbyte/_pyinstaller_entry.py`, `tools/buufury_text/_pyinstaller_entry.py` |

## Evidence for a name, not a style preference

Two of the conventions carry a correctness claim rather than a taste claim:

- **`_RAW` is a proof marker.** `CONTRIBUTING.md` says "Where a name is a guess,
  say so in a comment or leave the `_raw` suffix in place." `TRANSITION_CLASS_A_RAW`
  and `TRANSITION_CLASS_B_RAW` therefore read as unproven constants, and a later
  measurement that proves one is expected to rename it rather than leave a proof
  marker on a fact.
- **Record identities are join keys, not labels.** `map:0040`, `enemy:434` and
  `text:0010` are parsed by commands, tests and the atlas. Renaming the kind or
  changing the padding is a data change, not cosmetics; `docs/rom-profiles.md`
  explains why an enemy's key is a table index for Legacy of Goku II and a type id
  for Buu's Fury.

## What is enforced, and what is not

| convention | enforced by |
| --- | --- |
| record identities and profile ids | parsing code and the catalogue loader: an unparseable id or profile is a refusal, and the profile catalogue is a schema |
| command subcommands | `argparse` definitions; a documented command that names no parser fails |
| documentation file names | `docs/README.md` states it; **no gate checks it** |
| module, class, function, constant and test names | **no gate checks them.** The conventions are visible in review and in the counts above; a rename that breaks one does not fail a quality gate |
| capability ids | `tests/unit/test_capability_registry.py` checks the registry against the site and its references |

Being explicit about the third and fourth rows is deliberate: a convention that
claims an enforcement it does not have is worse than an unenforced convention.

## Relationship to ADR 0005

[`docs/decisions/0005-naming-precedence.md`](decisions/0005-naming-precedence.md)
is the naming authority and **nothing here contradicts it**. The lines it was
checked against:

- `:20` - "A human-facing display name comes from a fixed precedence, and nothing
  else" - the three rungs that follow are about display names, and this page does
  not add a fourth source.
- `:34-41` - the two rules: never infer a semantic name from appearance, and keep
  canonical ids and addresses as technical metadata. The `<kind>:<id>` identity in
  convention 8 is exactly that technical metadata, not a display name.
- `:43-45` - "There is **one naming authority.** A new editor surface resolves a
  display name through the existing source for its domain, or starts at the
  neutral fallback. It does not build its own name list." No convention on this
  page builds a name list.
- `:67-71` - the stat layer's display `alias` is named as a display convenience
  outside the three rungs. This page does not promote it to an identity, and
  convention 4's `_RAW` marker keeps an unproven constant visibly unproven.

Put plainly: ADR 0005 says *where a name comes from*; this page says *how an
identifier is spelled*. A change that obeys one cannot break the other.
