# Interaction specification v0.2

Deliverable 3 of the DragonByte Z editor design package. Companion to
[`README.md`](README.md). Status: **specified, not implemented.**

This document is the contract an implementation and a review are judged against.
It covers exactly one task and says nothing about the rest of the application.

## 0. The interaction contract, in five lines

```text
Task     select an existing multi-block environmental feature on a map, stamp it
         somewhere else, undo one stamp, and save the change to the project
Entry    a project is open from its verified base image, a map is open, and its
         target layer is editable; Maps > Map 33 > Background 0
States   S1 idle; S2 selecting; S3 feature captured; S4 stamp preview valid;
         S5 stamp preview refused; S6 placed, undo available; S7 undone;
         S8 saved
Failure  every refusal is decided before the click by the same rule the apply
         uses, appears attached to the placement with the reason in the user's
         words, and the feature stays in the hand so the user can move it
Accept   a placement changes the in-memory project by the measured number of
         blocks whose value differs, undo returns the exact previous values,
         save writes the project document and reports the count it wrote, and
         reopening the project shows the placed feature in place
```

The acceptance line is the one that decides whether the work is done. It is
observable in the real window and in the project file, and it is what
[`IMPLEMENTATION_READINESS.md`](IMPLEMENTATION_READINESS.md) schedules first.

## 1. Scope

The one task is the whole of v0.2. In particular v0.2 specifies **no** pixel
authoring, no palette control, no collision control, no object placement, no map
creation, no resize, no patch export, and no cross-map reuse. Those are not
missing features here; each is excluded for an evidence reason stated in
[`COMPATIBILITY_MATRIX.md`](COMPATIBILITY_MATRIX.md), and an implementation must
not invent an affordance for one.

**What v0.2 does, in the product's own terms.** v0.2 demonstrates chunk-arrangement
stamping: capturing and placing existing chunk references within one map. It is not
unrestricted environmental-feature selection; features that do not align to the
256 x 256 chunk grid cannot be captured in v0.2. Whether an arbitrary existing 8 x
8-tile arrangement can be placed is the open question the DRAGONBYTE-PLACEMENT-001
feasibility study exists to answer, and no v0.2 claim depends on its outcome.

## 2. Vocabulary: what the user reads, and what stays technical

The interface never asks the author to know ROM structure. Data terms are still
recorded, because a reviewer has to be able to check the mapping.

| User word | What it is in the data | Never on the main path |
| --- | --- | --- |
| block | one chunk placement: a 4-byte cell that points to a 32 x 32 plane of 8 x 8 tiles, 256 x 256 pixels; not an 8 x 8 graphics tile | chunk, cell pointer, ordinal, file offset |
| picture | one of the chunk images the map already uses | chunk body, container, bank, 8bpp |
| feature | the rectangle of blocks captured from the map | arrangement, stamp array, matrix |
| layer | one of the map's four background layers | layer record, handler, `+0x18` |
| project | the authored document set the editor writes | TOML, journal, document revision |
| saved | the project on disk matches the editor | clean state, stack index |
| this map's layout | the arrangement of pictures the map shows, block by block | layout record, pointer table, chunk list |
| blocking | whether the player can walk over a block | collision, predicate, vtable |

One word per thing: the tool is called **Stamp**, and what one gesture applies is a
**placement**. No sentence in the interface calls a placement a stamp.

**One block is one chunk placement**: a 4-byte cell that points to a 32 x 32 plane
of 8 x 8 tiles, 256 x 256 pixels. It is not an 8 x 8 graphics tile. Blocks are
numbered from 1 in reading order; the project document stores cell indices from 0.
The rectangle a user captures is a rectangle of these chunk cells, so a "2 x 2
blocks" feature is 512 x 512 pixels of map and never four hardware tiles.

Wording the main path uses: "Map 33", "Background 0 (BG0)", "Editable", "2 x 2
blocks (512 x 512 px)", "Saved". Background layer names are the engine's own and
are no more technical than a layer list in any tile editor; offsets, ordinals,
banks and addresses are not.

Everything technical lives in one place, per
[`../../desktop-ui.md`](../../desktop-ui.md): a `Technical details` disclosure at
the end of the inspector, collapsed by default and keyboard reachable, holding the
map index, the layer slot, the captured origin, the block coordinates and the file
offsets of the pending changes. It holds no evidence category: proof levels are
the repository's vocabulary and appear in its documents, never in the window, which
is the rule the anti-reference analysis holds
([`ANTI_REFERENCES.md`](ANTI_REFERENCES.md), section 2, device 3).

## 3. Entry and preconditions

- A project is open, and the image it was opened from passed identity
  verification (the SDK's own check; the window never asks the user for a hash).
- A map is open. The window shows its name and number in the canvas header, and
  the same line carries the target layer.
- The target layer is one of the map's four slots. A slot that is not editable is
  shown read-only with the reason (section 10, R4 to R6), and the rest of the task
  still works on an editable slot.
- The editor opens in **Select** with nothing captured, no selection and an empty
  undo history. The canvas is focused.

If the image fails identity verification the map does not open, and the window says
why in the same vocabulary: "This image does not match the base image the project
was made with, so Map 33 cannot be opened. Open the project's own base image." The
map list keeps the entry visible and read-only with that sentence, because a map
that silently disappears reads as a lost map.

**Where the project actions live.** The document line at the top of the editor
carries Undo, Redo and Save at its right end, in every state, each drawn disabled
when it is unavailable: Undo and Redo until the first placement, Save while the
project matches the saved point. They are the only place those three actions exist;
no second copy appears in the tool strip or anywhere else.

## 4. Mode model

Three tools, one active at a time. One authoring mode; there is no separate
"tileset workshop mode" for this task (section 5 explains why the tileset side has
no mode of its own here).

| Tool | Key | What the left button does | Shown as |
| --- | --- | --- | --- |
| Select | `S` | drag a rectangle of blocks on the map | strip button recessed, bullet glyph, status line "Select" |
| Stamp | `B` | place the captured feature | strip button recessed, bullet glyph, status line "Stamp: 2 x 2 blocks" |
| Pan | `H` | pan the canvas | strip button recessed, bullet glyph, status line "Pan" |

- **Shown:** a three-button strip on the left of the canvas header. The active
  button is recessed with a brightness step and carries a filled bullet glyph
  before its label, so it reads without colour. The status line repeats the active
  tool in words, because the strip can be collapsed with the panel.
- **Switched:** clicking a button, or `S` / `B` / `H` when the canvas has focus.
- **Stamp is disabled with the reason when nothing is captured**: the button is
  legible but disabled, and its tooltip says "Capture a feature on the map first"
  ([`../../desktop-ui.md`](../../desktop-ui.md): a disabled action says why where
  that is useful).
- **Middle-button drag pans in any tool**, and the wheel zooms about the cursor,
  matching the existing Maps canvases (`docs/desktop-ui.md`, direct manipulation).

**Escape, one level per press, in this order.** A press whose level has nothing to
act on falls through to the next applicable level, so one press always does the most
immediate thing that is available and is never spent on an empty level.

| Level | Acts on | Effect |
| --- | --- | --- |
| 1 | a drag in progress (selection or pan) | cancels it; the feature in the well is untouched |
| 2 | a placement position set by the keyboard | clears it; the feature stays captured |
| 3 | a selection rectangle with no capture yet | clears it; the tool stays Select |
| 4 | a captured feature | drops it and returns to Select; committed placements are untouched |
| 5 | nothing left | moves focus to the canvas |

Because of the fall-through, a user holding a captured feature and not dragging
drops it on the first press, at level 4, rather than on four presses. Escape never
removes a committed placement; `Ctrl+Z` is the only thing that does, and the status
line says so when a press reaches level 5 with edits pending ("Escape does not undo.
Ctrl+Z undoes the last placement."). Escape never closes the map and never discards
the project.

## 5. Selection model

Two selections exist in the package; only one of them is an authoring gesture.

### 5.1 Rectangle on the map (the capture)

- **Input:** press the left button on a block, drag, release. A click is a
  zero-distance drag and captures one block.
- **Keyboard equivalent:** move the focus block with the arrow keys, then hold
  `Shift` and press an arrow to extend the rectangle from its anchor, then
  `Enter` to capture. The anchor is the focused block; `Shift+arrows` grows or
  shrinks the same rectangle, and the header readout updates on each press.
- **What it captures:** the target layer only. A selection never spans layers,
  because every write in this title addresses one layer's cell window and a
  cross-layer write has no representation
  ([`COMPATIBILITY_MATRIX.md`](COMPATIBILITY_MATRIX.md), OPS-08). A block selected
  on another layer is not possible; other layers are drawn dimmed by one
  brightness step and are not hit-testable.
- **What it stores:** source map, source layer, origin block, columns, rows, and
  the ordered pointers of the captured blocks.
- **How it is shown:** an inner 1 px outline plus an outer 2 px outline in the
  interaction role, with four corner ticks drawn outside the rectangle, so the
  rectangle is legible on light and dark art and without colour. Blocks inside the
  rectangle step one brightness level up; the rest of the layer steps one level
  down while the drag is live. The canvas header shows the live size:
  "2 x 2 blocks (512 x 512 px)".
- **Capture itself is not an edit.** It changes nothing, stages nothing, and
  creates no undo entry.

### 5.2 Single block from the picture palette

- **Input:** click a picture thumbnail in "Pictures this map uses"; or
  `Tab` to the palette, arrows to a thumbnail, `Enter`. A single-block feature is
  captured and the tool switches to Stamp.
- **What it captures:** one block, using the same feature shape as 5.1, so the
  stamp path has one implementation.
- **Why there is no rectangle drag here:** the tile is not the authorable unit in
  this title. A tile-granular selection can be displayed and not authored
  ([`COMPATIBILITY_MATRIX.md`](COMPATIBILITY_MATRIX.md), OPS-04), and a drag in the
  palette would promise a sub-block feature the format cannot store. Instead the
  palette carries one hint line: "Drag on the map to capture several blocks at
  once."
- **Why the palette is the map's own pictures:** a cell may only take a chunk a
  dominant layer of the same map already uses (OPS-06 limits), so offering
  anything else would offer refused input.

### 5.3 What the selection does not do

- It does not select across layers (OPS-08).
- It does not select in tile units (OPS-04).
- It does not select across maps: the capture records its source map, and a
  captured feature is dropped with a reason if the user switches map while holding
  it (section 10, R1).
- It survives a target layer switch, and is re-validated against the new layer when
  it is placed. The legal pictures are the map's dominant-layer set, not one layer's,
  so a feature captured on Background 1 may be placed on Background 2; when the new
  layer cannot take it (read-only, or out of its grid) the banner names the reason and
  the capture stays in the well (section 10, R3 to R5).
- It does not survive a window close; v0.2 stores no user brush library, because
  the format has no place for one and the one task does not need one.

## 6. Brush preview

The preview exists so the author sees the result before committing it, and so a
refusal is visible before the click rather than after it.

- **The well.** A panel beside the canvas labelled "Captured feature" shows the
  captured blocks as one image, its size in blocks and pixels, and its source
  ("Map 33, Background 0, from block 1"). It is the persistent answer to "what am
  I holding", and it is the pattern taken from Porymap's selection well
  ([`REFERENCE_BOARD.md`](REFERENCE_BOARD.md) section 2).
- **The ghost.** With Stamp active and the pointer over the canvas, the captured
  blocks are drawn at the pointer at 60% opacity, with the same four corner ticks
  as the selection, a 2 px outer outline in the interaction role and a 1 px inner
  outline in the canvas role so it reads over any art. The outline weight and the
  ticks, not the tint, are what mark it as a preview.
- **Snapping.** The block under the pointer is the ghost's top-left block. There is
  no sub-block positioning, because the format has no sub-block unit.
- **The one refusal rule.** Exactly one signal, in three parts: the blocks that are
  the problem take the refusal hatch wherever the canvas has a cell for them; the
  ghost's cells that the canvas can show take the heavier dark outline and the
  triangle glyph at the top-left; and one banner in the inspector column carries the
  refusal in the user's words from the table in section 10. The banner sits in the
  column and never over map content, because the user has to judge the placement
  against the blocks it would cover; the glyph and the header count are what tie the
  banner to the ghost.
- **Out of bounds.** A block outside the layer's grid has no cell on the canvas, so
  the canvas shows only the cells of the ghost that fit, in ghost art, and the header
  reads "2 of 4 blocks do not fit". The commit is refused; the placement is not
  silently clipped. The inspector column then carries one inset under the banner,
  headed "Blocks that do not fit", and that inset is the only place the offending
  positions appear: it hatches them and names them as the feature's own positions and
  the blocks they sit beside ("positions 2 and 4 of the feature, one column right of
  blocks 4 and 8"). The inset is the refusal's checkable detail, and a refusal draws no
  other panel. Nothing is numbered that the user cannot see, and no block index off the
  grid ever appears.
- **Banner size.** The banner fills the inspector column, so it is 250 px wide, and
  it wraps to at most three lines at 12 px. A reason longer than that, and R1 in
  section 10 is the longest, shows its first clause in the banner and the whole
  sentence in the status line, so a refusal is never truncated.
- **Validity is decided by the apply rule.** The preview asks the same validation
  the commit path asks, so "may be previewed" and "may be applied" cannot
  disagree. This is not a new promise: the shipped writer already routes its
  preview through the same function as its commit
  (`tools/webfoot/map_layout_write.py:6-10`).
- **Never applies.** The preview stage holds no pointer in the project and opens no
  image file.
- **Suppressed** when the toolbox has no captured feature, when the active tool is
  not Stamp, when the pointer is over a panel, and while a drag is panning.
- **Keyboard equivalent.** In keyboard capture mode the ghost sits at the focused
  block; arrows move it one block, and the banner and the header readout update
  with it.

## 7. Placement

Every step in this section changes the **in-memory** project only. The one persistence
model is stated in section 9.1; the disk changes on Save and nowhere else.

- **One left click places the whole feature**, as one validated batch. The batch
  API validates every cell before it applies anything, so a batch containing one
  illegal block applies nothing at all rather than half of itself
  (`tools/webfoot/map_paint.py:802-822`).
- **Drag repeats, and one drag is one undo step.** Holding the button and moving
  places a copy at each block the pointer enters, snapped, and the whole drag is one
  merged undo entry holding every block the stroke changed. This is the gesture the
  repository's own UI authority prescribes (`../../desktop-ui.md`: a command carries
  an `id()` and a `mergeWith()` so that "a drag or a paint stroke collapses into one
  undo step"), the gesture the engine study records as working (one drag stroke, one
  entry, derived by diffing the before and after state), and the gesture the
  reference analysis recommends for this step ("paint by click and drag with grid
  snapping"). Each position in the drag is still one validated batch applied to the
  in-memory project; the merge is in the undo entry, not in the batch. A position
  that is refused is skipped with the banner and does not join the stroke;
  positions already placed stay.
- **A placement the project cannot hold is refused.** If the batch cannot be applied
  to the in-memory project (a cell outside the grid, a read-only layer, a value the
  SDK refuses), that position is refused with the SDK's reason, in-memory state is
  unchanged for it and no undo entry is added; positions already placed in the same
  stroke remain and stay undoable together. No disk write is involved: the disk
  changes on Save (section 9.1).
- **Overlap is allowed.** A placement may cover blocks it already covers. A placement
  whose result equals the current state is a no-op: nothing changes in memory, no undo
  entry appears, and the status line reads "Nothing changed"
  (`tools/webfoot/map_paint.py:658-665`).
- **After a placement:** the feature stays captured, the tool stays Stamp, the
  document line gains the modified marker, undo becomes available, and the status
  line reads "Placed 4 blocks. Ctrl+Z undoes this.", or "Placed 1 block. Ctrl+Z
  undoes this." in the singular. The count is the blocks whose value changed, not the
  blocks the placement covered: a block that already holds the target picture does
  not change, so a placement over four blocks of which two differ reads "Placed 2
  blocks".
- **A refused placement cannot be clicked into existence.** The click does nothing
  and the banner stays; the commit path refuses independently, so a preview bug
  cannot change the in-memory project.
- **Placing on a read-only layer** is impossible: the Stamp tool is disabled with
  the layer's own reason while a read-only layer is targeted.

## 8. Undo and redo

Undo and redo reverse or re-apply an entry against the in-memory project; they never
touch the disk (section 9.1).

| Question | v0.2 answer | Why |
| --- | --- | --- |
| Granularity | one placement is one step; a selection or a capture is not a step; a pan, a zoom or a layer switch is not a step | each position in a stroke is one validated batch applied to the in-memory project, and one stroke is one journal entry and one merged redo (OPS-24) |
| A drag | one merged step covering every block the stroke changed | section 7; a command id plus `mergeWith`, per `../../desktop-ui.md` |
| What an entry holds | the blocks the placement changed and their previous values | the inverse of a batch, nothing wider |
| What undo restores | only the blocks that placement changed; never the rest of the layer | narrower than a snapshot, so undo cannot clobber an unrelated edit |
| No-op | no entry | `tools/webfoot/map_paint.py:658-665` |
| Depth | no fixed cap in v0.2: one linear project timeline, entries proportional to blocks touched | a 2 x 2 placement costs four cells, and a cap would be a guessed number; a cap becomes a measured decision if cost shows up |
| Scope | project-wide, one stack, one timeline | `../DRAGONBYTE_Z_PRODUCT_SPEC.md` section 11 |
| Undoing an edit made on another map | the view moves to the map the entry changed | "undo reveals what it changes" (`../DRAGONBYTE_Z_PRODUCT_SPEC.md` section 11 rule 5) |
| Redo | re-applies the changes the entry recorded, revalidated; if the layer is no longer editable or a recorded pointer is no longer legal, redo refuses with the reason and changes nothing | a redo applies the entry to the in-memory project |
| History on save | **kept.** Save marks a point on the stack; it does not clear it | the dirty state is the stack position, not a flag (`../DRAGONBYTE_Z_PRODUCT_SPEC.md` section 11 rule 6) |
| After undo past a save | the document line returns to Modified, because the project no longer matches the saved point | same rule |
| After an image build | undo leaves the built image alone and the build report says the image is now older than the project | "undo affects the project, not images already built" |
| Not undoable | capture, selection, layer switch, zoom, pan, the save itself, any build | none of them is an edit |

Undo and redo are `Ctrl+Z` and `Ctrl+Shift+Z`, with `Ctrl+Y` accepted as an alias.
Both are shell-standard and already reserved (`docs/desktop-ui.md`: the shell owns
Undo, Redo and Quit).

### 8.1 The History surface

One panel, in the inspector column, appearing with the first placement and leaving
when the project is closed. It is a read-only display, not a control:

- one row per undo entry, oldest at the top, with the current position marked by a
  filled bullet, each row reading "3. Placed 4 blocks on BG0";
- an entry that has been undone stays in the list and is marked "(undone)", so the
  list is the timeline and the bullet is where the user stands on it;
- the saved point is marked on the list, so a user can see how far an undo has to
  go before the project reads Saved again;
- **rows cannot be clicked, activated or reached by Tab in v0.2.** The two ways to
  move are `Ctrl+Z` and `Ctrl+Shift+Z`, plus the document line's own buttons. A
  click-to-jump would be a second undo mechanism with its own rules and confirmation
  questions, and the one task does not need a second one;
- because it is a display it is out of the Tab order, and its contents reach a
  screen reader as a list carrying the same text.

## 9. Saving, and what the product may claim

**Save writes the project, and nothing else.** `Ctrl+S` writes the authored
project document that carries this map's layout (`maps/layout.toml`), as one
atomic document write. It does not write the canonical image, a new image, or a
patch. The category is the matrix's OPS-21, **ENCODING-CAPABLE**: the bytes are
written and re-read correctly, and no engine run observed this edit.

### 9.1 The one persistence model

Four statements, in this order, and every other sentence in this document follows
them:

- **A preview changes nothing.** Moving the ghost validates and draws; it holds no
  project state and writes no file (section 6).
- **A placement applies to in-memory project state.** One click, or one drag stroke,
  applies the validated batch to the project the editor is holding and adds one
  history entry (section 7). Nothing is on disk yet.
- **Undo and redo change in-memory state only.** They reverse or re-apply the entry
  against that same in-memory project; the disk is untouched (section 8).
- **Save is the only write to disk.** It writes the project document atomically: a
  temporary file is written, then moved into place, so a failed save leaves the
  previous file intact (below). Until that succeeds the document line reads Modified.

Consequences this document depends on: the Modified marker means "the in-memory
project differs from the last saved document", not "a file is open for writing"; a
placement whose blocks already hold the target values changes nothing in memory and
adds no entry; and the close prompt names the in-memory edits Save would write.

- **On success:** the status line reads "Saved 3 placements to the project", or
  "Saved 1 placement to the project" in the singular. The count is the placements
  whose blocks differ from the saved document at the moment of saving, so a
  placement made and then undone before the save is not counted, and undoing back
  past a save leaves nothing to count and disables the save action. The document
  line marker switches to Saved with a filled square glyph and the word; save stays
  disabled until the next edit; the technical disclosure records the document
  written.
- **On failure:** the status line reads "Refused" plus the SDK's reason in the
  user's words ("The project could not be written: the folder is read-only"), the
  document line stays Modified, every edit stays in memory and on the stack, and the
  file on disk is unchanged, because the write is staged and then moved into place.  There is never a partially written project.
- **A failed save does not discard work**, and the window never offers to close
  over unsaved edits without naming them: the close prompt names the count and the
  maps (`../DRAGONBYTE_Z_PRODUCT_SPEC.md` section 11).

**What the product may say about the result.** Three claims, three different
levels, and the interface must not merge them:

| Claim | Allowed wording | Level |
| --- | --- | --- |
| the project was written | "Saved to the project." | OPS-21, ENCODING-CAPABLE |
| an image was rebuilt | "New image written and re-read at <name>." | OPS-22, RUNTIME-PROVEN for the class of change that was run |
| this placement was seen in the game | only for a change class a3 rates RUNTIME-PROVEN; **a rectangle placement is OPS-05 ENCODING-CAPABLE, so v0.2 never says it** | OPS-05, gap G1 |
| a patch was exported | "Patch written and verified." never "tested in game" | OPS-23, ENCODING-CAPABLE |

v0.2 therefore ends at "Saved to the project." Build and Export are separate
actions outside this task, and when they are built they inherit this table
unchanged.

## 10. Refusals and warnings, one case at a time

Every refusal below is the audit's case, with the matrix row that rates it. A
refusal is never a modal: it is a state attached to the thing it is about, and it
leaves everything else usable. "Banner" means the banner anchored to the ghost in
section 6.

| # | Case | What the user reads | Where it appears | Rating |
| --- | --- | --- | --- | --- |
| R1 | the captured feature came from another map, or the user switched map while holding it | "This feature was captured on Map 39. This project refuses a feature from another map, because the two maps' tile numbers are not proved to mean the same pictures." | banner while the feature is held; the capture is dropped with this reason when the map changes | OPS-09, OPS-10 |
| R2 | a picture is not one this map already uses | "That picture is not one this map already uses." | palette entry marked unusable with the reason; a project cell holding a stale ordinal is read-only with the reason | OPS-06 limits |
| R3 | the placement runs past the layer's edge | "2 of 4 blocks do not fit inside Background 1." | the header count and the inset of blocks that do not fit; commit refused | OPS-05; a resize is growth only |
| R4 | the layer is a form the editor cannot write (screen-entry plane, terrain field, unclassified handler) | "Background 2 is stored in a form the editor cannot write, so it is read-only here." | layer chip, read-only reason in the header, Stamp disabled | OPS-04, OPS-05 limits; `docs/workbench.md:85-88` |
| R5 | the layer's grid holds only one picture, so there is nothing to paint with | "Background 3 has only one picture the editable layers use, so there is nothing to paint here." | layer chip and read-only reason | OPS-06 limits; `tools/webfoot/map_paint.py:589-605` |
| R6 | the map's layout is shared with another map | "This map's layout is shared with Map 62, so a change here would change both." | map-level banner at entry; layout is read-only | shared root, `docs/research/MAP_RESIZE_AND_LAYERS.md:24-25`, `:417-419` |
| R7 | the map is one of the 12 refused maps | "Map 12 can be opened and not changed." | canvas header chip with the reason | capability `layout` limits |
| R8 | a palette control is wanted | nothing: **no palette control exists in the task path** | absence, not a disabled control | OPS-11, UNSUPPORTED |
| R9 | a tile-granular rectangle is wanted | nothing to drag; the palette carries the redirect "Drag on the map to capture several blocks at once." | palette hint | OPS-04, UNSUPPORTED |
| W1 | whether stamped blocks block is unknown | "Warning: blocking for stamped blocks is unknown. No collision format has been identified for this title, so the editor cannot set or preserve blocking." | one post-placement warning in the status area, with a warning glyph and the word Warning | OPS-13, OPS-14, UNSUPPORTED; `docs/research/COLLISION_FORMAT.md:7-10`, `:186-202` |
| W2 | withdrawn from v0.2: a warning about a layout record another map also references | not shown. Its trigger is the record-sharing census (gap G7), so the product cannot tell "may" from "will" today and must not guess | none | gap G7; see [`IMPLEMENTATION_READINESS.md`](IMPLEMENTATION_READINESS.md) |
| W3 | the stamped result may be hidden by the map's own layering | **not shown in v0.2.** The product has no proven query for "is this layer fully covered here", so it must not guess | none | blocked; see [`IMPLEMENTATION_READINESS.md`](IMPLEMENTATION_READINESS.md) |

Rules the table enforces:

1. A refusal names the object, the number and where the change lands, in the
   form the interaction-contract reference calls correct: not "This will modify
   the map. Continue?".
2. The SDK's reason is translated, never replaced by a generic word: the word
   "Refused" always appears with a specific sentence after it.
3. A warning is attached to the placement it is about, and no warning is ever
   stated as a batch summary at the end of a session.
4. No refusal or warning claims a ROM fact the matrix does not rate.

The message texts name example maps and counts so a reviewer can judge the shape
of a sentence; the running product substitutes the real map name and the real
number, and no example number is a claim about the project.

## 11. Keyboard map

Every pointer step has a keyboard path, and no shortcut here collides with one
the shell already owns (`Ctrl+O`, `Ctrl+Shift+O`, `Ctrl+Shift+V`, `Ctrl+B`,
`Ctrl+R`, `Ctrl+1` to `Ctrl+4`; `docs/desktop-ui.md`).

| Input | Effect | Available in |
| --- | --- | --- |
| `S` / `B` / `H` | Select / Stamp / Pan | canvas focus |
| left drag on the map | capture a rectangle | Select |
| left click on the map | capture one block; or place the feature | Select; Stamp |
| `Shift` + `Left/Right/Up/Down` | extend or shrink the selection from its anchor | Select, no capture yet |
| arrows | move the focus block, or the pending stamp | Select; Stamp |
| `Enter` | capture the keyboard rectangle; or place at the pending position | Select; Stamp |
| `Escape` | the five-level ladder in section 4 | always |
| `Ctrl+Z` | undo one placement | always |
| `Ctrl+Shift+Z`, `Ctrl+Y` | redo | always |
| `Ctrl+S` | save the project | always |
| middle-drag | pan | any tool |
| wheel | zoom about the cursor | canvas |
| `Ctrl+Plus`, `Ctrl+Minus` | zoom in and out one step, about the centre of the view | canvas |
| `Ctrl+0` | zoom to fit the whole layer | canvas |
| `Tab` / `Shift+Tab` | focus the canvas, tool strip, layer strip, palette, well, inspector, status | window |
| space | **not bound** | place with `Enter` or a click, and Space must not fight the platform's paging convention |
| `Delete` | **not bound** | removing a block is not in this task; a bound Delete that did nothing visible would be worse than none |
| layer switch | the layer strip by keyboard; **no shortcut** | `Alt+1..4` was considered and rejected: one convention for layers and another for editors is two things to learn |

Focus is always visible as an outer ring that can coexist with selection, and no
state in this document relies on hover.

Zoom has a keyboard path (`Ctrl+Plus`, `Ctrl+Minus`, `Ctrl+0`, the Tiled
convention). Pan deliberately has no key of its own: moving the focus block with the
arrow keys scrolls the canvas so the focused block stays in view, which is the
keyboard equivalent of panning to where the work is, and a second bound key would be
a second mental model for the same movement
([`../../desktop-ui.md`](../../desktop-ui.md): a pointer workflow gets a keyboard
alternative "where one is reasonable").

## 12. The eight states, and what each one accepts

The diagrams are in [`VISUAL_STUDY.md`](VISUAL_STUDY.md) and
[`diagrams/`](diagrams/). Each state below names the observation that proves it
works, which is what a walkthrough in the real window must show.

| State | On screen | Acceptance observation |
| --- | --- | --- |
| S1 idle | map canvas, layer strip, empty well, Select active, no history | the canvas shows the map's own art, the well reads "No feature captured", undo and redo are disabled |
| S2 selecting | live rectangle, brightened blocks, live size in the header | the size readout matches the rectangle, dragging past the edge stops at the grid |
| S3 captured | selection committed, the well shows the feature, Stamp active | the well image is the captured blocks, the strip shows Stamp active, the palette hint is gone |
| S4 preview valid | ghost at the pointer with ticks and outlines, header shows "2 x 2 blocks" | the ghost tracks the pointer, arrow keys move it one block, no file changes on disk |
| S5 preview refused | ghost art on the cells that fit, the hatched positions in the inset, triangle glyph, banner with the reason | the banner names the specific reason, the inset names the positions that do not fit, and a click changes nothing |
| S6 placed | the feature at the new place, original still there, undo enabled, the History panel appears with one row | the status reads "Placed 4 blocks", undo is enabled, the document line reads Modified, and History shows one row naming the placement |
| S7 undone | the feature gone from the new place, redo enabled, the History row marked undone | `Ctrl+Z` restores the previous blocks exactly, the document line reads Saved when the placement was the only unsaved edit and Modified when other edits remain, and the History row stays with its undone marker |
| S8 saved | Saved marker, save disabled, status counts the placements, History keeps its rows and marks the saved point | the project file on disk carries the new values, and reopening the project shows the stamped feature |

## 13. What v0.2 deliberately does not decide

- **The GUI framework.** Not chosen here, per the ticket. Nothing in this
  document names a toolkit; the contracts are behaviour, not classes.
- **Exact pixel measurements** beyond type sizes and outline weights. The theme
  module owns spacing and control heights
  (`docs/desktop-ui.md`), and this package does not invent a second scale.
- **The performance budget.** The matrix's limits imply it (a batch is a set of
  cell changes; a render is a proven path), but no number is claimed and no
  benchmark exists. That is a readiness item, not a design assumption.
- **Whether the drag-repeat gesture and the History panel ship as specified.** Both
  are specified with their evidence, and both are product-feel calls rather than
  evidence calls, so [`REVIEW_REPORT.md`](REVIEW_REPORT.md) lists them as
  outstanding owner decisions with a recommended default.
- **A user-visible brush library.** The format has no place for one, and the one
  task does not need one.
- **Anything about the Tileset Workshop's pixel authoring**, which the matrix
  rates UNSUPPORTED (OPS-16). A workshop surface for this title can only work at
  the arrangement level (OPS-17), which is a different ticket.
