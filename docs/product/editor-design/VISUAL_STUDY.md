# Visual study

Deliverable 4 of the DragonByte Z editor design package. Companion to
[`README.md`](README.md) and [`INTERACTION_SPEC_v0.2.md`](INTERACTION_SPEC_v0.2.md).

Eight states of one task, each an original hand-written SVG in
[`diagrams/`](diagrams/). Each diagram is the canvas plus only the controls that
state needs; there is no full-window mockup, no dashboard, no decorative panel,
and no game artwork. Blocks are abstract numbered and hatched placeholders.

## What the study is, and what it deliberately is not

It is a set of adjudicable pictures: every element in every diagram exists because
a named state needs it, and every choice has the reference finding that justifies
it listed in the table under its diagram.

It is not a picture of the application. There is no title bar, no menu bar, no
tab strip, no dock, no status of the whole product and no activity log. Those are
exactly the devices the two rejected prototypes leaned on
([`ANTI_REFERENCES.md`](ANTI_REFERENCES.md)); drawing them here would repeat the
failure this package exists to avoid.

## How to read a diagram

- **Frame.** The top strip is the document line (map, target layer, editability, the
  Undo, Redo and Save actions at its right end, and the save state). The second strip
  holds the tool buttons and the live measurement. The large rectangle is the map
  canvas. The right column holds only the panels this state uses. The bottom strip is
  the status line, then a numbered legend.
- **Annotations.** Circled numbers point at the thing they justify; the legend
  under each diagram states each in one line, and the table in this file gives the
  reason and its source.
- **Text sizes.** All text is 12 px or larger at 100 per cent scaling. No text is
  smaller to make room.
- **States are never colour alone.** The palette is a neutral brightness ladder
  plus one interaction hue (a magenta, taken from the repository's own
  interaction family in the previous theme, not invented here). Every state adds a
  second mechanism: an outline weight, a corner tick, a hatch, a drawn glyph
  (filled square for saved, open ring for modified, triangle for refused, filled
  bullet for the active tool) and a word. Remove the hue and every state still
  reads. Colours named here are roles, not theme values, because the theme module
  has not been chosen and this package does not pick one.
- **The grid is illustrative.** A 4 x 3 grid of blocks is drawn because it fits
  the page, not because a map has twelve blocks. Real grids come from the map's
  own layer record ([`COMPATIBILITY_MATRIX.md`](COMPATIBILITY_MATRIX.md), OPS-02).

## S1. Idle with the map open

Diagram: [`diagrams/state-1-idle.svg`](diagrams/state-1-idle.svg)

The map is visible, the target layer is named, nothing is captured, and the two
things the user could try to do before capturing anything (undo, stamp) are
visibly unavailable.

| # | What the diagram shows | Why, and from where |
| --- | --- | --- |
| 1 | Select is active: recessed, bullet glyph before the label, and named again in the status line | a2 reusable idea 10 and the mode-label lesson in a1 (Aseprite's thin mode strip is recorded as that product's weakness 4): the active mode gets a second, non-colour cue |
| 2 | Stamp is present, legible and disabled | `../../desktop-ui.md` ("a disabled action should say why"); a2 records the transparent-tile skip as the reason a stamp needs to know it has nothing to hold |
| 3 | The captured-feature well is empty and says so | a2 reusable idea 2, the persistent well; the empty state is a word, not a blank box |
| 4 | The document line shows the save state as a filled square and the word Saved | `../../desktop-ui.md` state rule: brightness plus glyph plus word |

Acceptance: the canvas shows the map's own art, undo, redo and save are disabled,
and the well reads "No feature captured".

## S2. Selection in progress

Diagram: [`diagrams/state-2-selecting.svg`](diagrams/state-2-selecting.svg)

| # | What the diagram shows | Why, and from where |
| --- | --- | --- |
| 1 | Live size readout, in blocks and pixels | a1 A1-4 "Form the brush": the selection is the brush, so its extent must be readable while it is being made; a2 idea 1 (drag extends, clamped) |
| 2 | Blocks inside the rectangle step one brightness level up | a2 idea 10: the edited region is made to read by dimming the rest, rather than by tinting the selection |
| 3 | The rest of the layer steps one level down while the drag is live | same source; this is a view-only device and writes nothing |
| 4 | Corner ticks outside the rectangle, plus a 3 px outline and a 1 px inner outline | the state must survive a colour-blind reader (S5 of the research basis, R7); weight and ticks are the second mechanism |

Acceptance: the readout matches the rectangle, and the rectangle stops at the
grid edge rather than continuing past it.

## S3. Selection made, feature captured

Diagram: [`diagrams/state-3-captured.svg`](diagrams/state-3-captured.svg)

| # | What the diagram shows | Why, and from where |
| --- | --- | --- |
| 1 | Stamp becomes the active tool the moment a feature exists | a1 A1-4 "Form the brush": the selection becomes the brush immediately, so the next gesture is placement |
| 2 | The well shows the four captured blocks as one image, with size and source | a1 A1-4 "Preview before placing", which names Porymap's always-visible selection well as the pattern; a2 idea 2 |
| 3 | The source selection stays outlined, dashed, after the capture | the source is still useful information (where the feature came from); a1 records Porymap hiding unusable saved features as its weakness 1, and the fix is to keep things visible and marked |
| 4 | The palette carries one hint line, "Drag on the map to capture several blocks at once" | the palette is a single-block picker, and the reason there is no rectangle drag in it is a format fact (OPS-04). A hint redirects; a silently inert drag would not |

Acceptance: the well image is the captured blocks, the palette hint is the only
sentence in that panel, and no second tool appears.

## S4. Stamp preview, placement allowed

Diagram: [`diagrams/state-4-preview-valid.svg`](diagrams/state-4-preview-valid.svg)

| # | What the diagram shows | Why, and from where |
| --- | --- | --- |
| 1 | Ghost drawn at 60 per cent opacity over the destination blocks | a2 reusable idea 2 measures the same idea: alpha-128 copies of the real art at the snapped destination, nothing written until the click |
| 2 | Heavier outline plus corner ticks on the ghost | a2 idea 2 also draws a per-cell border; the ticks are added here because outline alone loses to a busy map |
| 3 | The ghost is snapped to a block corner | a2 idea 5: the grid governs where new content lands |
| 4 | The status line names the result of the click: "click to place 4 blocks" | `references/interaction-contract.md` shape: the state says what the user can do next, and names the number |

Acceptance: the ghost tracks the pointer, the arrow keys move it one block, and
nothing on disk changes while the pointer moves.

The one right-column panel beyond the well exists to carry a single decision: this
gesture is one undo step. Its two earlier lines ("4 blocks on Background 1" and
"Nothing written until the click") repeated the well and the status line, so they are
gone.

## S5. Stamp preview, refused

Diagram: [`diagrams/state-5-preview-refused.svg`](diagrams/state-5-preview-refused.svg)

| # | What the diagram shows | Why, and from where |
| --- | --- | --- |
| 1 | The two positions that do not fit are hatched in the inset, which names them as positions 2 and 4 of the feature, one column right of blocks 4 and 8 | a position outside the layer's grid has no cell on the canvas, so the inset is the only place it can be shown; `INTERACTION_SPEC_v0.2.md` section 6 names that inset as the refusal's checkable detail |
| 2 | The cells of the ghost that fit are drawn as ghost art, at 60 per cent opacity, under a 5 px outline with corner ticks and a filled triangle | one refusal rule, three parts: the outline and the glyph mark the ghost wherever it can be drawn, the hatch marks the blocks that are the problem, and the banner names the reason. Here the problem blocks have no canvas cell, so the canvas shows only what fits |
| 3 | A banner in the inspector column carries the refusal in words | the contextual-warning rule in `references/interaction-contract.md`: the warning names the object and the number. It sits in the column rather than over the map because the user has to judge the placement against the blocks it would cover |
| 4 | The header carries the count, "2 of 4 blocks do not fit" | `../../desktop-ui.md` requires a refusal to name what is wrong; a count is the smallest true statement |

The canvas ends at the layer edge, so the ghost's fourth column has no cell to stand
on: the canvas shows the two cells that fit and the inset alone carries the two that
do not, by position and by the block they follow. That is the geometry, not a
convention, and the drawing states it rather than hatching cells that are inside the
grid.

Refusal by clamping is deliberately **not** chosen here. a2 records that its
palette drag clamps to the tile range (`tileset_editor.py:1557-1558`), which is
right for a palette and wrong for a write: a clamped stamp would silently place
part of a feature. The engine writer refuses an out-of-grid cell, so the preview
refuses it too.

Acceptance: the banner names the specific reason, and a click changes nothing on
disk or in the project.

## S6. Placed, undo available

Diagram: [`diagrams/state-6-placed.svg`](diagrams/state-6-placed.svg)

| # | What the diagram shows | Why, and from where |
| --- | --- | --- |
| 1 | The same four block patterns now also appear at the destination, full opacity, while the source is untouched | a2 idea 3: a stamp carries the pattern it holds; a1 A1-4 "Place it" (paint by click with grid snapping) |
| 2 | The document line switches to the open ring glyph and the word Modified | `../DRAGONBYTE_Z_PRODUCT_SPEC.md` section 11: the dirty state is the stack position, shown as marker plus word |
| 3 | Undo becomes enabled and names the gesture it will reverse | `../../desktop-ui.md` requires an undiscoverable action to be discoverable; a1 records Tiled's undocumented undo as that product's weakness 1, so the affordance is labelled here |
| 4 | One History row for one gesture, and the blocking warning is stated once, in words | a2 idea 4 (one stroke, one entry); the History panel is specified in `INTERACTION_SPEC_v0.2.md` section 8.1; a3 OPS-13 and OPS-14 (blocking is not addressable), so the honest statement is that stamped blocks do not block |

Acceptance: the destination blocks changed, the source blocks did not, undo is
enabled, the document line reads Modified, and History holds one row.

## S7. After undo

Diagram: [`diagrams/state-7-undone.svg`](diagrams/state-7-undone.svg)

| # | What the diagram shows | Why, and from where |
| --- | --- | --- |
| 1 | The destination blocks hold their previous pictures again | state is restored by the placement's own inverse, not by a snapshot of the layer: the batch recorded the cells it touched |
| 2 | Redo becomes available and is labelled | `../../desktop-ui.md` interaction checklist (undo and redo both walked) |
| 3 | The document line reads Saved again, because the stack moved back to the saved point | `../DRAGONBYTE_Z_PRODUCT_SPEC.md` section 11 rule 6: the dirty state is the stack index, so undoing to the saved point restores Saved exactly. With the placement as the only unsaved edit, that is this case; with other unsaved edits the line reads Modified |
| 4 | The History row stays visible, marked undone, and the captured feature is still in the well | the History panel is the timeline and the marker is the position on it (`INTERACTION_SPEC_v0.2.md` section 8.1); the well is not history, so it survives |

Acceptance: `Ctrl+Z` restores exactly the previous block values, redo is enabled,
and the document line reads Saved, because the placement was the only unsaved edit.

## S8. After save

Diagram: [`diagrams/state-8-saved.svg`](diagrams/state-8-saved.svg)

| # | What the diagram shows | Why, and from where |
| --- | --- | --- |
| 1 | The panel reports what was written: one placement, to the project file | a1 A1-4 "Save it": name the target document so the user knows what was replaced; a3 OPS-21 is the rating (ENCODING-CAPABLE) |
| 2 | The document line returns to the filled square and the word Saved | the same marker vocabulary as S1, so saved and modified are one pair of glyphs |
| 3 | Save is disabled until the next edit, and undo stays available | `../DRAGONBYTE_Z_PRODUCT_SPEC.md` section 11: history is kept across a save, and the saved point is marked on it |
| 4 | The panel says "No image was built" and records that the game playing it is **not** stated | a3 OPS-05 is ENCODING-CAPABLE and OPS-22 is a separate action, so the interface must not merge project save with a runtime claim (ADR 0004, "RUNTIME PROOF requires an engine observation of the specific authored result") |

Acceptance: the project file carries the new block values, the save action is
disabled, and the status line reports the count it wrote.

## What every state omits, on purpose

- **No docked activity log.** Both rejected prototypes dedicated a bottom dock to
  messages, and no collected screenshot of the five real editors makes that
  permanent chrome (a1 A1-5, "patterns the anti-references used").
- **No evidence labels in working chrome.** "RUNTIME-PROVEN" and its siblings are
  annotation vocabulary for this package only, and appear in no part of the running
  window, not even its technical disclosure (a1 A1-5; spec section 2).
- **No disabled future actions in the primary toolbar.** Build and Play are absent
  from these states, not greyed (a1 A1-5).
- **No second workspace with its own toolbar.** The tileset side of this task is a
  single-block picker inside the same surface, because there is no tile-level unit
  to author (OPS-04) and no tileset pixel authoring (OPS-16).
- **No status bar of the whole application.** The bottom strip is the editor's own
  context line, which is what `../../desktop-ui.md` reserves the status bar for.

## What is not measured

These are diagrams, not captures. Nothing here shows how any of it renders in a
GUI framework, and no usability session has been run. The acceptance observations
in each section are the walkthrough a real window must pass, and they are
unverified until that window exists ([`IMPLEMENTATION_READINESS.md`](IMPLEMENTATION_READINESS.md)).
