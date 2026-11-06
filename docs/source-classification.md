# Source classification

Every tracked file belongs to exactly one class, decided by its path. The classes
say what a file *is* in this repository - shipped code, a test, a record, a
tool - so that a reader can tell a product change from a measurement, and so that
a reviewer knows which rules apply before opening the file. The rule is path-based
and checkable; nothing here classifies a file by its content or by how good it is.

Apply the rules in this order and stop at the first match:

| # | class | rule | files |
| --- | --- | --- | --- |
| 1 | evidence record | path starts with `docs/research/` | 213 |
| 2 | test, ROM-gated | path starts with `tests/integration/` | 100 |
| 3 | test, portable | path starts with `tests/` | 301 |
| 4 | documentation | path starts with `docs/`, or the file name ends `.md` | 72 |
| 5 | configuration | path starts with `config/`, or the file is `pyproject.toml`, `uv.lock`, `upstreams.lock`, `.gitignore` or `.gitattributes` | 9 |
| 6 | public site | path starts with `src/` or `public/`, or the file is `astro.config.mjs`, `package.json`, `package-lock.json`, `tsconfig.json` or `wrangler.jsonc` | 29 |
| 7 | CI and developer tooling | path starts with `.github/`, `ci/`, `scripts/`, `tools/quality/` or `tools/dev/`, or the file is `.gitlab-ci.yml` | 47 |
| 8 | entry shim | path starts with `tools/webfoot/`, `tools/dragonbyte/` or `tools/buufury_text/`, and the file is `__main__.py` or `*_pyinstaller_entry.py` | 11 |
| 9 | shipping SDK | path starts with `tools/webfoot/`, `tools/dragonbyte/` or `tools/buufury_text/` | 223 |
| 10 | supporting toolkit | path starts with `tools/` | 314 |
| 11 | release packaging | the file name ends `.spec.in`, `.version.txt` or `.cmd` | 10 |
| 12 | licence | the file is `LICENSE` | 1 |

Total: **1,330 tracked files**, every one classified, no file in two classes.
Counted with `git ls-files` against `ca128adc`.

## What each class means in practice

- **evidence record** - a measurement of the game or a proof of a format, with
  its evidence and its limits (`docs/research/ROM_EDITOR_COVERAGE_LEDGER.md`).
  It is not product documentation and it is not code: a claim in it is promoted
  by the record's own evidence, never by where it sits.
- **test, ROM-gated** - reads a canonical image and skips cleanly without one
  (`tests/integration/test_project_build_rom.py`). A skip is the designed
  outcome on a machine with no image.
- **test, portable** - synthetic fixtures only, no image and no network
  (`tests/unit/test_write_invariants_property.py`).
- **documentation** - what a user or a contributor reads
  (`docs/testing.md`, `CONTRIBUTING.md`).
- **configuration** - identity data and pinned inputs: the profile catalogue is
  `config/roms.yaml`, and `uv.lock` pins the environment
  (`config/roms.yaml`).
- **public site** - the progress site's source and its published assets
  (`src/data/capabilities.json`, `public/dbz-map-browser.png`).
- **CI and developer tooling** - what gates a change
  (`tools/quality/public_surface.py`, `.github/workflows/ci.yml`).
- **entry shim** - a module whose only job is to reach another module's `main`
  (`tools/webfoot/__main__.py`, `tools/dragonbyte/_pyinstaller_entry.py`).
  A frozen build starts here, so it is not shipping logic and not a test.
- **shipping SDK** - the product: identification, formats, project, build,
  relocation, the desktop editor and the text editor
  (`tools/webfoot/build.py`, `tools/webfoot/workbench/map_browser_tab.py`).
- **supporting toolkit** - code in `tools/` that is not the shipping product: the
  runtime instruments (`tools/runtime/`), the read-only research adapters
  (`tools/research/`), the emulator probe harness (`tools/mgba_probe/`), the
  static-analysis scripts (`tools/ghidra/`), the exporter (`tools/export/`), the
  catalogue tool (`tools/save_catalogue/`), the capture tooling (`tools/qa/`) and
  the shipped presets (`tools/presets/`). These produce evidence or operate on an
  image; a reader should not expect the product's safety guarantees from them.
- **release packaging** - the launchers and frozen-build inputs
  (`DragonByte Z.cmd`, `DragonByte Z.spec.in`).
- **licence** - `LICENSE`, referenced by `pyproject.toml`.

## What this rule does not classify

- **Generated or ignored files.** The rule covers the index. A built image, an
  extracted asset, a save or a `.venv` is not tracked and is never classified;
  the ignore rules and `docs/ROM_SAFETY.md` govern those, not this page.
- **Ownership.** Two files in one class can have different owners and different
  review requirements; the class does not decide who may change a file.
- **Per-game support.** Whether a class of code supports a given image is the ROM
  profile's declaration, not a path rule; see
  [`rom-profiles.md`](rom-profiles.md).
- **Content correctness.** A shipping module and a broken shipping module are the
  same class. Tests, gates and review say whether the content is right.
- **Third-party provenance.** What came from outside is recorded in
  [`THIRD-PARTY-NOTICES.md`](../THIRD-PARTY-NOTICES.md) and `upstreams.lock`, not
  derived from a path.
- **A new top-level directory.** A path the rules do not name falls to no class
  by construction. Adding one is a classification change, so it comes with an
  edit to this table.
