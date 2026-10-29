# Implementation readiness

Deliverable 7 of the DragonByte Z editor design package. Companion to
[`README.md`](README.md).

What in [`INTERACTION_SPEC_v0.2.md`](INTERACTION_SPEC_v0.2.md) is sufficiently
specified to build, what needs a named assumption, and what is blocked and by
what. **No GUI framework is chosen here, and nothing in this file chooses one.**

The distinction that decides most rows: an evidence gap blocks a **claim**, not a
build. A rectangle placement may be built while its rectangle-level runtime
observation is still missing (gap G1); it may not then be described as proven to
work in the game.

## 1. Ready to build

Each row names the rating it rests on in
[`COMPATIBILITY_MATRIX.md`](COMPATIBILITY_MATRIX.md).

| Spec item | Rests on | Notes |
| --- | --- | --- |
| Load a project and its verified base image, then open a map | OPS-01, OPS-02, OPS-03, all RUNTIME-PROVEN | the render path is proven for the maps it was measured on; the general case is a stated limit, not a blocker for map 40 |
| Show the four layer slots with an editable or read-only state and the reason | OPS-02 plus the SDK's own refusal reasons | the reason strings already exist (`tools/webfoot/map_paint.py:585-605`, `:626-635`) |
| List the pictures the map already uses, with thumbnails | OPS-06 limits, RUNTIME-PROVEN reads | the palette is exactly the map's vocabulary, so refused input is not offered |
| Capture one block from the palette as the feature | OPS-06, RUNTIME-PROVEN | this is the proven single-cell path |
| Draw the selection rectangle, the live size readout, and the dimming of the rest | editor state only; reads are OPS-01 and OPS-02 | writes nothing, so no authoring evidence is needed |
| Ghost preview at the pointer, snapped to blocks, suppressed over panels | preview only | a preview must route through the same validation as the write, as the shipped writer already does (`tools/webfoot/map_layout_write.py:6-10`) |
| Refusal states R1 to R5 and R7 to R9, each with its own sentence | OPS-04, OPS-05 limits, OPS-06 limits, OPS-09, OPS-10, OPS-11 | the SDK raises each of these today with a reason string |
| One placement as one validated batch, refusing all or nothing | OPS-05, OPS-06, ENCODING-CAPABLE | `tools/webfoot/map_paint.py:796-883` validates the whole batch before writing |
| No-op placement writes nothing and creates no undo entry | OPS-24, ENCODING-CAPABLE | `tools/webfoot/map_paint.py:658-665` |
| One placement is one undo entry, holding only the blocks it changed | OPS-24, ENCODING-CAPABLE | the inverse of a batch; `docs/research/MAP_TILE_PAINT.md:68-79` |
| A drag repeats, and the whole stroke is one merged undo entry | OPS-24 plus `../../desktop-ui.md` (a command id and `mergeWith`) | the merge is a command-layer rule; each position is still one validated batch write |
| The History panel: rows, current-position marker, saved-point marker, read-only | OPS-24 | a display, not a control; specified in the interaction spec section 8.1 |
| The refusal banner with wrap, its inset, and a status-line fallback for a long reason | none: wording and layout | one banner and, for an out-of-grid refusal, one inset naming the positions that do not fit; the longest string is R1 in the refusal table, sized against the banner |
| A placement whose write fails is refused, writes nothing and adds no entry | OPS-21, because a placement is a project write | same staged-write behaviour as save |
| Escape falls through to the next applicable level | none: interaction only | one press does the most immediate available thing |
| Zoom from the keyboard: `Ctrl+Plus`, `Ctrl+Minus`, `Ctrl+0` | none: interaction only | the Tiled convention, and the shell reserves neither |
| Visible history with the saved point marked, and Save not clearing it | OPS-24 plus `../DRAGONBYTE_Z_PRODUCT_SPEC.md` section 11 | |
| Save writes the project document atomically and reports the count written | OPS-21, ENCODING-CAPABLE | one staged document write; no image, no patch |
| The failure path of a save leaves every edit in memory and the file unchanged | OPS-21 | staged write, then move into place |
| The keyboard map, including the five-level Escape ladder | none: interaction only | every pointer step has a keyboard equivalent in spec section 11 |
| The claim table in spec section 9, as interface wording | ADR 0004 plus OPS-05, OPS-21, OPS-22, OPS-23 | this is a wording rule, so it is buildable immediately and testable in the window |
| W1, the collision warning, as static text attached to a placement | OPS-13, OPS-14 | states a fact about the format, needs no query |

## 2. Ready with a named assumption

| Spec item | Assumption it carries | What would falsify it |
| --- | --- | --- |
| Capture a rectangle of blocks from the map | that a rectangle of cells behaves like the single cell that is RUNTIME-PROVEN (OPS-05 is ENCODING-CAPABLE; gap G1) | the G1 probe: a 3 x 2 authored block, leave and re-enter, observe the live cell layout |
| Place a rectangle as one batch | same as above, plus that the batch write's all-or-nothing rule is what the product wants rather than per-cell commits | a measurement showing partial batches are needed for a workflow |
| Undo depth unlimited in a session | that entries stay small because they hold only changed blocks | a measured cost on a large multi-map project; the cap then becomes a measured number |
| Save writes `maps/layout.toml` for this map's placements | that the project's layout document is the only authored carrier for a placement, and that reopening is project-side rather than re-extraction (OPS-21's stated limit) | a workflow that needs a placement to travel in a different document |
| R6, the shared-root refusal | that the root-sharing query the resize path already has (`tools/webfoot/map_resize.py:276-297`) is reachable from the layout path unchanged | the query turning out to be resize-specific |
| A drag merges into one undo entry | that a command id plus `mergeWith`, as `../../desktop-ui.md` prescribes, keeps a long stroke legible, and that the document writes a stroke makes stay affordable | a measured cost on a long drag across a large layer; if it bites, the merge grain or a write batching rule is revisited, and the spec says so |
| The status line reports a count of placements, not of documents | that one save can carry placements made across several maps, so the count and the target must both be readable | a save path that can only carry one map at a time |

## 3. Blocked

| Spec item | Blocker | Blocker type |
| --- | --- | --- |
| W2, a warning about a layout record another map also references | withdrawn from v0.2: its trigger needs the record-sharing census (gap G7), so the product cannot tell "may" from "will" and must not guess. It returns when that census lands | a3 evidence gap, and it needs only a static census of 35 records by handler |
| W3, the "this may be hidden by the map's layering" warning | no proven query exists for "is this layer fully covered at this block", and the only measured case is one map's addends (`docs/research/MAP_RESIZE_AND_LAYERS.md:327-330`) | missing research |
| A performance budget for the canvas and the preview | no benchmark exists; the matrix gives limits (a batch is N cell writes, a render is a proven path) and no timings | missing research, and it needs a real project large enough to measure |
| Any statement that a stamped rectangle works in the game | gap G1: the rectangle is ENCODING-CAPABLE, never runtime-observed | a3 evidence gap |
| Tileset pixel authoring, at any level | gap G6: compressor output size and no free space; recorded POST-1.0 | missing capacity, not a design gap |
| Collision authoring under a stamped region | gap G5: no bounded static collision family was established, so there is no byte to write | a3 evidence gap at the format level |
| Per-block palette selection | OPS-11 is UNSUPPORTED: the bits are constant zero in the whole canonical corpus | unsupported by the format |

## 4. Excluded from v0.2 by decision, not blocked

These are not waiting on evidence; they are outside the one task. Each would need
its own ticket and, in three cases, an owner decision.

| Excluded | Why it is a decision and not a gap |
| --- | --- |
| the rest of the application (menus, navigation, other editors) | one task is the whole scope of this package |
| cross-map reuse | the SDK refuses it and equality of two maps' character blocks is unmeasured (OPS-09, OPS-10) |
| Build, Export and Play | separate actions with their own categories (OPS-22, OPS-23); folding them into Save would break the claim table |
| a user brush library | the project format has no place for one |
| an object or actor surface | a different data family (`docs/research/MAP_FORMAT.md:183-186`) |
| the GUI framework | an owner decision, explicitly outside this ticket |

## 5. Recommended first implementation milestone

**Name:** the placement model, driven with no window.

**Scope.** The whole one task at the model layer: open map 40 layer BG1, capture a
single block and a 2 x 2 rectangle, stamp one placement, undo it, save the
project, reopen the project. Nothing in this milestone draws a pixel: the spec's
behaviour is carried by plain objects and commands a test can drive, which is the
project's own rule for the model layer rather than a shortcut
(`../../workbench-architecture.md`).

**Why this milestone and not a window.** Every rated operation the task touches is
either RUNTIME-PROVEN or ENCODING-CAPABLE, so the model is buildable now. The
window is not: the framework is an owner decision this ticket cannot make, and a
window built before the model would encode the framework choice into the design.

**In scope (each rated):** OPS-05 batch write, OPS-06 single-cell write, OPS-07
region copy within a map, OPS-21 project save, OPS-24 undo/redo, and the read path
OPS-01 and OPS-02.

**Out of scope:** everything in sections 3 and 4, plus any window, any rendering,
and any runtime claim.

**Acceptance test**, one focused unit test file, run one file per process as the
project's testing rules require:

1. load the project and map 40, layer BG1, and assert the layer is editable and
   its grid matches the record;
2. capture blocks 5, 6, 9 and 10, assert the captured feature records four
   pointers and its source map and layer;
3. stage one placement at block 3, assert nothing on disk changed before commit;
4. commit, assert the project document holds exactly the four cells and that the
   cells that did not change are absent from it;
5. assert one undo entry exists, undo, and assert the project document no longer
   carries those cells and that the layer's other cells are untouched;
6. redo, save, assert the save reports one placement, reopen the project and
   assert the four cells are present with the same pointers;
7. attempt an out-of-grid placement and a placement of a pointer the map does not
   use, and assert each is refused with its own reason and that neither writes
   anything;
8. make a two-position drag as one stroke, and assert it produces exactly one undo
   entry covering both positions, and that one undo reverses both.

The test proves the model, not the product. The product proof is the walkthrough in
the real window that [`VISUAL_STUDY.md`](VISUAL_STUDY.md) specifies for each of the
eight states, and it cannot run until a framework decision exists.

**What the milestone may claim when it passes:** the project file on disk carries
the authored placements, undo restores the exact previous pointers, and the batch
is validated as one unit. **What it may not claim:** that the stamped rectangle was
observed in the game (G1), that collision changed (OPS-13), or that a built image
plays correctly (OPS-22 is a separate action with its own run).

## 6. What would change this assessment

- **The G1 probe landing.** It would promote the rectangle from ENCODING-CAPABLE to
  RUNTIME-PROVEN and remove the largest assumption in section 2.
- **G7's static census.** It would either unblock W2 or show that no dominant
  record is shared, in which case W2 disappears rather than being built.
- **A framework decision by the owner.** It would let the eight states become a
  walkthrough, and only then can the acceptance observations in
  [`VISUAL_STUDY.md`](VISUAL_STUDY.md) be tested at all.
- **A measured performance budget.** It would turn the unlimited undo depth and
  the preview cost from assumptions into numbers.

## 7. Outstanding owner decisions

Each needs the owner, not the evidence. The recommendation is what this package
would ship if nothing is said.

| # | Decision | Recommendation, and why |
| --- | --- | --- |
| 1 | the GUI framework | no recommendation. It stays owner-reserved and this ticket must not choose it; the model milestone does not depend on it |
| 2 | what "multi-tile environmental feature" means | the rectangle of 32 x 32 blocks, because a3 establishes there is no metatile object in this title (OPS-04, and section 8 of [`COMPATIBILITY_MATRIX.md`](COMPATIBILITY_MATRIX.md)). If the phrase meant metatile semantics, the one task needs re-scoping before milestone 1 |
| 3 | whether drag-repeat ships | **Recommendation: yes**, one merged undo entry per stroke. It is the gesture `../../desktop-ui.md` prescribes, the engine study records it working, and the reference analysis recommends it; the argument against it in round 1 was withdrawn as false |
| 4 | whether a visible History panel ships | **Recommendation: yes**, as specified in section 8.1 of the spec: one panel, rows, read-only, appearing with the first placement. The round 1 risk was unspecified chrome, not visibility; a1's undo recommendation asks for a visible history, and a read-only list cannot grow a second undo mechanism |
| 5 | whether any evidence category may appear in user-facing chrome | **Recommendation: no**, which is what v0.2 now says. Proof levels are the repository's vocabulary, and `../../desktop-ui.md` puts handles and offsets behind a disclosure, not proof categories |
| 6 | whether cross-map reuse is worth a G2 probe | **Recommendation: not for v0.2.** The refusal is correct until character-block equality between two maps is measured, and the probe is a separate research ticket; the refusal message now names that reason instead of implying impossibility |

## 8. What this package does not claim

- No user has tried any of it. Usability with real authors is **not measured**.
- No rendering has been produced in any GUI framework, so every visual claim is a
  specification, not an observation.
- No ROM-gated test was run for this package, and no image was built.
- Nothing here says a placed rectangle draws correctly in the game.
