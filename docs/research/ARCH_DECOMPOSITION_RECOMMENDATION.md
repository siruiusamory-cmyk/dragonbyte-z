# Architecture follow-up: the four oversized modules

**Status:** measurement and recommendation only. Nothing in this document was
refactored, split, moved or renamed; the owner's boundary for this phase is "Do
not refactor or relocate these modules in this implementation phase". Measured at
`ca128adc`; every count below is reproducible from the commands in
[`tools/README.md`](../../tools/README.md) conventions and the source tree.

**Method.** Structure from `ast` (classes, methods, self-attribute use, module
globals, import resolution), consumers from `git grep` and a resolved import
graph, coverage from the test files that import the module. Byte shares after a
hypothetical move are INFERRED from structure; nothing was actually moved, so no
post-move byte size is claimed.

## 0. A contract defect, measured

The ticket asks that every boundary be checked against "the SEVEN
import-direction rules in `architecture.py`". There is no seven-rule set.
Measured in `tools/quality/architecture.py`:

- `RULES` (line 409) holds **ten** rules; one of them, `_rule_import_direction`
  (line 326), is the import-direction rule.
- That rule enforces **two directed edges** (`:343-354`): the shipping package
  must not import the application, and the application must not import the beta
  desktop package.
- One rule is an **observation**, not a failure: `_observation_large_modules`
  (line 388), threshold 100,000 bytes, which is what names these four modules.

So the checkable object is 10 rules, 2 directed import edges and 1 observation.
Every boundary below is scored against that measured set, and the disagreement is
reported rather than papered over. If a seven-rule list exists elsewhere, it is
not in this file at this commit.

The roots the rules use: `SHIPPING_ROOT = "tools/webfoot"`,
`PRODUCT_ROOT = "tools/dragonbyte"`, `BETA_ROOT = "tools.webfoot.workbench"`.
`_rule_top_level_roots` compares only the **first path segment**, so every file
under `tools/` already passes it; a move inside `tools/webfoot` is invisible to
that rule and visible only to the import edges and the size observation.

## 1. `tools/webfoot/workbench/map_browser_tab.py` - 378,883 B

| fact | measured |
| --- | --- |
| lines / classes / methods / module functions | 8,328 / 16 / 369 / 4 |
| responsibilities | undo commands `288-907` (45 methods: `PaintCellsCommand` 288, `ChunkCellCommand` 406, `AuthoredPlaceCommand` 514, `StructuralPaintCommand` 614, `ResizeCommand` 790, `NewLayerCommand` 857); dialogs and new-map `910-1409` (22 methods); canvas and overlays `1243-1881` (41 methods: `ChunkGridOverlay` 1412, `ChunkPlaneOverlay` 1575, `MapBrowserCanvas` 1763); the tab itself `MapBrowserTab` 1884-8327, **228 methods in 6,444 lines = 77.4 % of the file** |
| consumers | 1 shipping: `tools/webfoot/workbench/editors.py:34`; 6 test files, 204 test functions, of which 51 name this module's symbols; the five unit files all guard on `PySide6` |
| imports | 11 shipping `tools.webfoot` modules plus 4 siblings (`theme`, `build_panel`, `session`, `widgets`); top of the stack, one inbound edge |
| coupling | `MapBrowserTab` touches 184 distinct self-attributes, makes 537 self-method calls over 160 methods, reads 652 module globals across 126 names; no `global` statement and no mutable module state; three methods over 100 lines (`__init__` 1020, `_refresh_editor_state` 233, `apply_to_project` 158) |
| verdict | **NO decomposition.** 77.4 % of the file and 228 of 369 methods are one class that no seam touches; the three movable groups are 19 % of the lines; the size observation survives them |

## 2. `tools/webfoot/project/model.py` - 181,830 B

| fact | measured |
| --- | --- |
| lines / classes / methods / module functions | 4,001 / 26 / 103 / 51 |
| responsibilities | errors and project metadata `200-353`; map documents `357-1162` (7 classes, 32 methods); transitions `1178-1970` (10 classes/functions, 23 methods); graphics overrides `1974-2106`; sprite, appearance and authored-map documents `2205-2979` (33 methods); validation and serialisation `2982-4001` (20 validators, 7 emitters, 8 writers, 11 readers, `read_project` 3876) |
| consumers | **14 shipping files import `project.model` directly and 40 import the `tools.webfoot.project` package**, 22 of them only through its re-export; 28 test files import `project.model` directly, 91 import the package; the widest-consumed module of the four |
| imports | 2 siblings (`atomic`, `format`), 3 `formats` modules, 5 function-local imports; mid-layer hub, no UI, no ROM |
| coupling | no dominant class: 103 methods over 26 classes, maximum 8 (`MapStructure`, `TransitionCreations`); the weight is module-level, with 20 shared validators and four functions over 100 lines (`_read_maps` 174, `read_project` 125); no mutable module state |
| coverage | 516 test functions in the importing files, 221 naming model symbols; no PySide6, 9 of the 28 test files are ROM-gated; `tests/unit/test_map_chunk_project.py` pins that the module never imports a ROM-opening module |
| verdict | **YES, decomposition would materially help.** The interface the tree depends on is the package (`tools.webfoot.project`), not `project.model`: four document domains already exist inside one file, the largest class has 8 methods, and a split by document costs one shared validator module and no test import change. The size observation clears only if all three domains move (INFERRED, ~122 KB of the 182 KB) |

## 3. `tools/webfoot/workbench/warp_tab.py` - 146,377 B

| fact | measured |
| --- | --- |
| lines / classes / methods / module functions | 3,272 / 5 / 150 / 11 |
| responsibilities | record classes and undo commands `214-462` (`CreationDraft` 254, `StageTransitionCommand` 347, `CreationState` 371, `StageCreationCommand` 401); `WarpTab` 465-3268, **142 methods in 2,804 lines = 85.7 %** |
| consumers | 1 shipping (`editors.py:36`); 3 test files, 130 test functions, 21 naming symbols |
| imports | 6 shipping `tools.webfoot` modules plus 3 siblings; consumer of the transition authority, one inbound edge |
| coupling | 59 self-attributes, 278 self-method calls over 97 methods, 277 module-global reads; concerns are interleaved by method name (`creation*` 895-2250, `on*` 919-2905), so no byte cut separates them; `__init__` 245 lines |
| coverage | 21 symbol-level tests; the small record classes are directly tested, the tab is exercised through a real tab object |
| verdict | **NO decomposition.** 85.7 % of the lines are one class; the one clean seam (`214-462`) frees 249 of 3,272 lines; the obvious second seam (`_build_creation_page` plus 17 `creation*` methods) needs a collaborator object over 45 test-visible methods, which is re-architecture, not decomposition |

## 4. `tools/webfoot/workbench/graphics_tab.py` - 110,305 B

| fact | measured |
| --- | --- |
| lines / classes / methods / module functions | 2,260 / 5 / 83 / 2 |
| responsibilities | undo commands `135-308` (`PaletteRecolourCommand`, `AuthoredSpriteCommand`, `AuthoredAppearanceCommand`); preview helpers `311-397` (`indexed_pixmap`, `PreviewLabel`); `GraphicsTab` 400-2259, **67 methods in 1,860 lines = 82.3 %** |
| consumers | 3 shipping: `workbench/app.py:62`, `workbench/map_tab.py:69` (imports `indexed_pixmap`) and `tools/qa/visual_pass_capture.py:51`, which imports the private `_IDENTITY_ROLE` and reads `graphics._grid` |
| imports | 10 shipping `tools.webfoot` modules plus 4 siblings; three inbound edges, the widest spread of the tabs |
| coupling | 70 self-attributes, 120 self-method calls over 47 methods, 254 module-global reads; `__init__` 485 lines; concerns interleaved (`on*` 902-2184, `palette*` 1587-1688) |
| coverage | 7 test files, 149 test functions, 20 naming symbols; all seven guard on `PySide6`; **24 monkeypatch paths spell `tools.webfoot.workbench.graphics_tab.<name>`**, so any symbol moved out of this module breaks them |
| verdict | **NO decomposition.** 82.3 % of the lines are one class; the movable slice is 263 lines (11.6 %); whether it would clear the 100 KB observation is **not established** because no move was made; the private `_IDENTITY_ROLE`/`_grid` coupling makes the module a de facto API |

## 5. Boundary check against the measured rule set (SC10)

Each candidate is scored against the ten rules, with the import rule shown as its
two edges. "unchanged" means the move neither shrinks nor extends a rule.

| candidate | move | roots | import edge 1 (shipping must not import application) | import edge 2 (application must not import beta) | other rules (language, tests, probes, generated, proprietary, local state, test imports, site/sdk) | shrinks an import rule? | available? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| model C1 | sprite/appearance/authored-map documents `2205-2979` + writers `3801-3873` to `project/sprites.py` | unchanged | unchanged (stays under `tools/webfoot`) | unchanged | all unchanged; no pytest, no probe prefix, no local-state name | no | **yes**, after validators move to `project/validate.py` |
| model C2 | transitions `1178-1966` + `3747-3798` to `project/transitions.py` | unchanged | unchanged | unchanged | unchanged | no | **yes** |
| model C3 | maps/layers/chunks `357-1162` + `3651-3744` to `project/maps.py` | unchanged | unchanged | unchanged | unchanged | no | **yes** |
| map browser C1 | commands `288-907` to `workbench/map_browser_commands.py` | unchanged | unchanged | unchanged (still inside `BETA_ROOT`, which edge 2 forbids importing from `tools/dragonbyte`; no dragonbyte import added) | unchanged | no | yes, but frees 19 % |
| map browser C2/C3 | dialogs, canvas | unchanged | unchanged | unchanged | unchanged | no | yes, same limit |
| warp C1 | records/commands `214-462` to `workbench/warp_records.py` | unchanged | unchanged | unchanged | unchanged | no | yes, 7.6 % of lines |
| warp C2 | creation page to `workbench/warp_creation.py` | unchanged | unchanged | unchanged | unchanged | no | **no** - needs a collaborator rewrite of 45 test-visible methods |
| graphics C1/C2 | commands `135-308`, preview `311-397` to two modules | unchanged | unchanged | unchanged | unchanged | no | yes, 11.6 % of lines, 24 patch paths and 2 importers to re-point |
| graphics C3 | palette editor to a collaborator | unchanged | unchanged | unchanged | unchanged | no | **no** - interleaved, not a byte cut |

No candidate violates a rule and no candidate shrinks or extends an import rule:
every proposed module stays inside `tools/webfoot`, which is `SHIPPING_ROOT`, and
none crosses into or out of `tools/dragonbyte` or the beta package. The only rule
any split moves is the size **observation**, and only a split that clears 100,000
bytes per file can retire it.

## 6. The remainder: is anything left unclassified (SC11)?

The earlier audit's 446-unit classification is **not in this worktree**: `git grep
"UNDETERMINED" -- docs` returns nothing and no tracked file carries the 613-file
list. Its counts therefore cannot be reconciled from here, and the 717-file
remainder was re-derived instead of trusted, by classifying **all 1,330 tracked
files** under the path rule in [`source-classification.md`](../source-classification.md).

| class | files | risk |
| --- | --- | --- |
| supporting toolkit (`tools/` outside the shipping packages) | 314 | low - 295 are runtime instruments and research adapters that produce evidence, not product |
| tests | 401 (301 unit, 100 integration) | none in themselves; see risk 1 |
| shipping SDK | 223 | low |
| evidence records (`docs/research/`) | 213 | none |
| documentation | 72 | none |
| CI and developer tooling | 47 | medium - see risk 2 |
| public site | 29 | none |
| entry shims | 11 | none |
| release packaging | 10 | medium - see risk 3 |
| configuration | 9 | low |
| licence | 1 | none |
| **total** | **1,330, zero unmatched** | |

A second, independent classification by static import closure (kindly prepared by
a read-only helper lane and checked here) gives shipping 232, instruments 295,
manual tools 78, and reproduces the 1,330 and 401 totals; the two rules differ in
what they call "shipping", not in the total or in the risk list.

### Named risks, each measured

1. **One of 100 integration files runs in CI.** `.github/workflows/ci.yml` runs
   `tests/integration/test_container_decode_synthetic.py` only; every ROM write
   path is guarded by tests no workflow invokes. `docs/testing.md` states this
   deliberately (a hosted runner has no image), so it is known and accepted, not
   undiscovered.
2. **Two CI definitions coexist.** `ci/*.ps1` are the GitLab-era job bodies and
   still cite `.gitlab-ci.yml` as their authority (`ci/common.ps1:3,10`,
   `ci/adjacency.ps1:12,22`, `ci/test_sdk.ps1:28`), while GitHub Actions runs the
   inline steps. `.gitlab-ci.yml` is tracked and three tests parse it, so it is
   BLOCKED rather than dead; the drift between the two definitions is real.
3. **Ten release scripts have no automatic check.** `scripts/build-*`,
   `scripts/package-*` and `scripts/smoke-*` (10 files) are named by no workflow
   and no test. A broken frozen build ships until a human runs a smoke script.
4. **`tools/quality/package_content.py` is a documented manual tool, not dead and
   not in CI.** It is imported by `tools/quality/public_release.py`, covered by
   `tests/unit/test_package_content.py`, and documented at
   `docs/DEVELOPMENT.md:61` and `docs/release-artefacts.md:138`. No workflow runs
   it, so release hygiene depends on the release step remembering it. Verdict:
   **live, tested, manual**, with a real gap in automation, not a hidden path.
5. **Name-loaded assets are invisible to an import scan.**
   `tools/buufury_text/theme.py:465` loads `_icon_directory()/f"{name}.svg"`, so
   the 18 SVGs under `tools/buufury_text/icons/` have no importer and are live;
   `tools/runtime/mgba_session.ps1:83` runs `-m tools.save_catalogue`, which has
   no shipping importer either. An `importer == 0` row is not evidence of death.
6. **One duplicate pair, intentional and guarded.** `config/roms.yaml` and
   `tools/webfoot/data/roms.yaml` are byte-identical (sha256 `bcbb50ef…`), pinned
   by `tests/unit/test_profile_authority_contract.py` and
   `tests/unit/test_project_safety.py`; the packaged copy exists for frozen
   builds.

**Verdict on the remainder: no significant undiscovered risk.** Every file with
no importer, no workflow hit and no test hit resolves to a documented hand-run
release tool, a name-loaded asset, or a documented manual input. The genuine gaps
(1-3) are known and written down, not hidden in the unclassified set.

## 7. Recommendation for the consolidation phase

Nothing here is authorised for this phase; this is the recommendation the owner
asked for.

1. **Split `tools/webfoot/project/model.py` first and only.** It is the one module
   whose size comes from several things living together: four document domains,
   26 small classes, 14 direct shipping importers, 28 direct test importers, and a
   package-level interface that already hides it. Order: extract the 20 shared
   validators to `project/validate.py`, then split sprites/appearances, maps,
   transitions, then update `project/__init__.py`. Do not split
   `read_project`/`write_project` orchestration; it belongs at the package edge.
2. **Leave the three workbench tabs alone.** Each is 77-86 % one class with 59-184
   self-attributes; the movable slices are 7.6-19 % of their lines, the size
   observation survives every available seam, and the tabs carry monkeypatch and
   private-attribute couplings that make them a de facto API. If readability is
   the goal, the higher-value change is the 1,020-line `__init__` in
   `MapBrowserTab`, which is a method-level refactor with its own tests, not a
   module split.
3. **Retire or annotate the second CI definition.** Not a module boundary and not
   this phase's work, but it is the largest measured maintainability risk in the
   remainder: `ci/*.ps1` describe a pipeline nobody runs, and one of them names
   `.gitlab-ci.yml` as the authority for a variable.
4. **Give the ten release scripts one check.** A single job that runs the smoke
   scripts against a fixture package would convert a memory-dependent step into a
   gate; it is outside this ticket's fence but it is the highest-value automation
   gap found.

## 8. What this evidence does not establish

- It does not establish any runtime behaviour: no module was exercised.
- It does not establish a post-move byte size, line count or test result; no file
  was moved, so every "would clear the threshold" statement is INFERRED.
- It does not establish that the earlier 446-unit classification was wrong; it
  establishes that the classification is not present in this worktree and that a
  1,330-file path classification reaches the same totals.
- It does not establish that the three "leave alone" verdicts would survive a
  different goal; they answer the ticket's question, "would decomposition
  materially improve development", measured by coupling, consumer spread and
  possible seam size.
