# Anti-reference analysis

Deliverable 5 of the DragonByte Z editor design package. Companion to
[`README.md`](README.md).

Two generated HTML prototypes were rejected by the owner. They are anti-references:
studied so their patterns are not repeated, never used as a starting point. Both
were read whole, as text and as layout, for this analysis. They live in the local
research archive, outside this repository, and neither is modified or reused.

| File | Size | SHA-256 |
| --- | --- | --- |
| `dragonbyte_map_tileset_grayscale_v01.html` | 30,646 bytes | `9883B0D46F0D14636C20DC19B303707FC9B1BA9083B42BA6E0BD1C8FEB0E13B7` |
| `map_tileset_prototype.html` | 27,316 bytes | `7A3448496D43B60F44FA57126F90F99428827AF26A9473588AD192C2F95BC731` |

Both hashes match the identities recorded for this ticket. Line references below
are into those files as read for this analysis.

## 1. `dragonbyte_map_tileset_grayscale_v01.html`

Its document title reads "Map & Tileset Workflows (Grayscale Study)".

### What it did

**Regions**, in page order:

| Region | Contents |
| --- | --- |
| Title strip | a square "DZ" mark, the application name, the document "Sample Project [Interaction study]", and a right-aligned tag "GRAYSCALE PROTOTYPE, NO ROM CONNECTION" (line 19) |
| Menu strip | File, Edit, View, Map, Tileset, Help as buttons whose tooltips admit they do nothing, plus a hint "Designed for Windows desktop, not a web dashboard" (line 20) |
| Tool bar | Undo, Redo; Select (active), Paint, Pick; a Zoom select and a Grid checkbox; a spacer; Export Demo JSON; Build ROM and Play in mGBA, both disabled (lines 21 to 27) |
| Document tabs | "Map Editor, Sample map" and "Tileset Workshop, Bank 000" (line 28) |
| Three-column work area, 230 px / fluid / 254 px (lines 29 to 82) | left: Project Navigator, Chunk Palette with a "MAP-SCOPED" tag, Layer Slots, Editing Scope; centre: canvas header, canvas, and a bottom dock; right: Inspector, Resource Dependencies, Collision |
| Bottom dock | two tabs, Messages and Interaction Notes, over a monospace log pane (line 59) |
| Status strip | three segments: readiness, target game, and "Design study v0.1" (line 83) |

The Tileset Workshop tab replaces the whole left, centre and right regions with a
second three-column set of its own: a bank list, a tile browser, a Selection
panel, a Tile Inspector, a 4 x 4 "Brush Composition" surface, and a Source
Modification panel (lines 37 to 48 and 74 to 80).

**Controls.** Gradient buttons with a 1 px border and an inset shadow when active;
a native-feeling zoom select; checkboxes; radio pills; a dark "action" button for
Save Brush; per-panel uppercase section titles with letter spacing; monospace note
lines.

**Interaction model, from its own script.** The document tab swap replaces all
three regions (`tabSelect`, line 105). A chunk-or-tile view toggle changes what the
canvas paints (`mapViewMode`, line 106). Tools are select, paint and pick
(`setTool`, line 107), with the right button acting as a temporary pick (line 119).
Painting is a press-drag-release stroke which snapshots the whole document before
the stroke and again after it, and pushes one entry into an 80-deep history
(lines 101, 119 to 121). There is no save and no save-as: the only output is
"Export Demo JSON" (line 127). Build ROM and Play in mGBA are permanently disabled
(line 26).

### Why it reads as generic, and why it is wrong for this task

1. **Two peer workspaces with their own toolbars.** The tab does not change a
   panel; it swaps the entire layout, so the user has two applications in one
   window. None of the five real editors works this way, and the reference
   analysis records it as a pattern the anti-references used and the real editors
   did not (reference analysis A1-5, "patterns the anti-references used", item 1).
2. **Composing the brush on a blank grid as the primary path.** A 4 x 4
   composition canvas is the only way to make a multi-tile brush (lines 78, 118).
   For the owner's task, "select an existing feature", this converts one gesture
   into roughly sixteen clicks, and no captured screenshot of the five real
   editors shows a blank brush-composition grid (A1-5 item 2).
3. **Research status as product chrome.** "GRAYSCALE PROTOTYPE, NO ROM
   CONNECTION", "MAP-SCOPED", "INSPECT / COMPOSE ONLY", "Research required"
   (lines 19, 33, 56, 72). These are notes about the prototype, printed where a
   user would look for what the product knows.
4. **Disabled future actions in the primary toolbar.** "Build ROM" and "Play in
   mGBA" occupy permanent toolbar width while being permanently useless (line 26);
   the five real editors keep a primary toolbar actionable (A1-5 item 4).
5. **A permanent message log as product chrome** (line 59), which none of the five
   editors puts in the workspace permanently (A1-5 item 5).
6. **A menu bar that is decoration.** Six menu buttons with tooltips explaining
   that they do nothing (line 20). A menu that cannot open is a promise the
   surface cannot keep.
7. **Undo is a snapshot of the whole document.** Two edits in two different places
   undo in an order that restores unrelated state, and nothing on screen shows
   which gesture an undo will reverse (lines 101 to 104). The reference analysis
   records the missing history surface as this file's specific weakness
   (A1-5 item 4).
8. **Its task is not the task.** It can place whole 256 x 256 chunks into a 2 x 2
   chunk grid and compose an editor-only 4 x 4 brush, and it can pick one chunk
   from the map. It cannot capture an existing multi-tile feature as one unit, and
   its "Save Brush to Project" saves into an in-memory array for the session.

### What v0.2 does instead, device by device

| Device it used | The v0.2 decision that avoids it |
| --- | --- |
| two peer workspaces with their own three-column layouts | one surface, one canvas, and the palette is a single-block picker inside it; the tileset side has no workspace because there is no authorable tile unit (spec section 5.2; matrix OPS-04, OPS-16) |
| compose the brush on a blank grid | the feature is captured from the map by dragging, and the source arrangement is never rebuilt by hand (spec section 5.1; reference analysis A1-4, "Pick the feature") |
| prototype and evidence tags in chrome | state words are about the author's data ("Editable", "Saved", "Refused"), and evidence categories live in a collapsed technical disclosure (spec section 2) |
| permanently disabled Build and Play | neither exists in the task path; a control that cannot work is absent, not greyed (spec section 1) |
| permanent message log dock | no log dock; a refusal is attached to the thing it is about (spec section 6) |
| decorative menu bar | no menu is specified in this package at all; nothing here promises a command that does not exist |
| whole-document snapshot undo, 80 deep | one placement is one entry, holding only the blocks it changed, with a specified History panel (spec section 8 and section 8.1; a2 idea 4) |
| a brush saved only for the session | no brush library: the format has no place for one and the one task does not need one (spec section 5.3) |

## 2. `map_tileset_prototype.html`

Its document title reads "Map & Tileset Interaction Study".

### What it did

**Regions:**

| Region | Contents |
| --- | --- |
| Fake window strip | product name, a "WORKSPACE STUDY 01, GRAYSCALE, INTERACTION PROTOTYPE" sub-tag, and drawn minimise, maximise and close glyphs (line 9) |
| Menu strip | seven plain text labels, File through Help, with no behaviour (line 10) |
| Tool bar | Undo, Redo; Pencil (active), Eyedropper, Pan; Grid, Chunk bounds, and a disabled "Collision (research)"; a spacer; a zoom out, a percentage, a zoom in; a disabled "Build ROM" (line 11) |
| Workspace tabs | Map Editor, Tileset Workshop (line 12) |
| Map workspace, three columns (lines 13 to 26) | left: a Project tree marked "fixture only", a Brush Library with an asset grid and "Saved arrangements", and a Commands block; centre: a document bar, a 720 x 480 canvas, and a lower strip with Problems, Activity, Build output tabs over a log; right: Map Layers as four radios, an Inspector with evidence flags, and a Properties table |
| Workshop workspace, three columns (lines 27 to 38) | left: Graphics Sources tree, a Browse panel with Raw and Inferred presentation, and a Source operations list; centre: two work panes, a 448 x 448 source grid and a 364 x 280 composition grid with a name field and Save Brush; right: Source Inspector, Brush Properties, and an Evidence Notes panel with PROVEN, VIEW ONLY, UNVERIFIED and UNRESOLVED rows |
| Status strip | a highlighted "PROTOTYPE" wordmark and "Local UI interactions only, ROM access disabled" (line 39) |

**Visual devices.** A counterfeit title bar with window buttons; tabs whose active
state is a top border plus a lighter fill; panel headers with small grey tags;
italic "notice" boxes; coloured evidence flags; a stack of label and value rows in
serif-free 12 px text everywhere; a monospace status line.

**Interaction model, from its own script.** The workspace tab swaps both side
columns and the centre (`tab`, line 55). Tools are paint, pick and pan (line 52).
A paint stroke records one snapshot before it starts and never while it continues,
into a 50-deep stack (lines 49 to 51). The composition surface is a 13 x 10 grid
that copies one source tile per cell (line 59), and "Save Brush" pushes a name into
a session array. Map cells hold an assembled tile ordinal, and the pick tool copies
one ordinal (line 50). Zoom runs from 0.5 to 2.0 in quarter steps.

### Why it reads as generic, and why it is wrong for this task

1. **A counterfeit desktop window.** Drawn minimise, maximise and close glyphs at
   the top right of a page that has no window (line 9). It is the single clearest
   example of chrome drawn to look like a product instead of being one.
2. **The dashboard shell.** Three columns of stacked, titled panels around a canvas
   that occupies the middle third, and a second set of the same for the workshop
   tab. Every concept gets a card, so nothing is allowed to be the subject.
3. **Evidence vocabulary as interface text.** "RUNTIME-PROVEN: authored chunk
   arrangements" in the Inspector (line 23), READ, PROJECT and RESEARCH flags
   (line 30), and an Evidence Notes panel with PROVEN, VIEW ONLY, UNVERIFIED and
   UNRESOLVED rows (line 37). This is the failure the product's own wording rules
   forbid in working chrome (`../../desktop-ui.md`, and
   `../DRAGONBYTE_Z_PRODUCT_SPEC.md` section 12: the support state appears in three
   named places, never as decoration).
4. **Two parallel workspaces again**, and this time with different column widths in
   each, so switching tabs moves every control.
5. **Brush composition as the primary path**, a 13 x 10 grid of single-tile
   stamps, with the arrangement instruction printed in a notice plate.
6. **Disabled future actions in the primary toolbar**: "Build ROM" and "Collision
   (research)" (line 11).
7. **A permanent Problems, Activity and Build output log** (line 19).
8. **A pick tool that copies one tile ordinal**, presented as if it were the way to
   reuse a feature (line 50), which cannot express a multi-block feature at all.
9. **Fixture identity everywhere.** "Example Map 0040", "Assembled tile ordinal
   004", "Bank 000 (sample)" (lines 15, 23, 28), so the workflow it demonstrates
   cannot be checked against a real project.
10. **Snapshot undo again**, 50 deep, with the whole map copied twice per stroke,
    and nothing showing what the next undo would reverse.

### What v0.2 does instead, device by device

| Device it used | The v0.2 decision that avoids it |
| --- | --- |
| counterfeit window buttons | the diagrams carry no window chrome at all; the application's own frame is the operating system's (visual study, framing note) |
| dashboard of titled panels | the canvas is the subject, and the right column holds only what the current state needs (visual study, "How to read a diagram") |
| evidence vocabulary as interface text | no evidence word appears anywhere in the window: technical facts and block coordinates sit in one collapsed disclosure and stop short of proof categories (spec section 2; review finding F14) |
| two parallel workspaces | one surface for the task, with a single-block palette inside it (spec section 5) |
| a composition grid as the primary path | capture from the map, one drag, with the well holding the result (spec sections 5 and 6) |
| disabled Build and Collision controls | both absent: no Build in the task path, and no collision control because the format has none (spec sections 1 and 10, R8 and W1) |
| a permanent log dock | refusals and warnings attach to the placement, and there is no log (spec section 6) |
| a one-ordinal pick tool | the capture records a rectangle of blocks, so a feature is one thing (spec section 5.1) |
| fixture identities | the diagram's grid is explicitly illustrative and the vocabulary names a real map, layer and block (visual study, framing note) |
| whole-map snapshot undo | per-placement entries holding only the changed blocks, plus the specified History panel (spec section 8.1) |

## 3. What both share, and the single decision that answers it

Both files present a **whole application at once**: a window frame, menus, a
toolbar, two workspaces, three columns of panels, a log dock and a status bar, for
a product whose real first task is one gesture on a canvas. The volume of chrome is
what makes them read as generated: a surface that shows everything cannot show what
matters, and the two of them independently arrived at the same arrangement because
that arrangement is the default shape of a generated desktop mockup (research basis
S1 and S2 in [`README.md`](README.md)).

The decision that answers it is at the top of
[`INTERACTION_SPEC_v0.2.md`](INTERACTION_SPEC_v0.2.md) and not at the end: this
package designs **one task**, and every state diagram contains only the controls
that task needs in that state. There is no other surface to compare against,
because there is no other surface yet.

Two smaller shared faults are worth naming because they are cheap to repeat:

- **Both claim capability in chrome.** Neither leaves a claim out; both put the
  claim on the frame. v0.2's rule is that a claim is stated once, in words, where
  the thing it describes is (spec section 9's claim table).
- **Both narrow the canvas with fixed side columns.** The first file reserves 230 px
  and 254 px either side (`dragonbyte_map_tileset_grayscale_v01.html:11`,
  `grid-template-columns:230px minmax(0,1fr) 254px`), the second 235 px and 266 px
  (`map_tileset_prototype.html:6`), so at their stated minimum widths the canvas is
  about half the window and the panels take the rest in fixed slices. In v0.2 the
  canvas is the largest single region in every one of the eight states: 576 x 394
  against 252 x 394 for the whole right column, and the panels shrink to the inspector
  content the state actually has.

Three devices survive from the rejected files into v0.2, and they are named here so
no reader has to guess whether they were inherited or chosen. Each is taken from a
real editor, and each file is the place the similarity would be visible:

- **The document line that names the map, the state and a measurement.** The first
  file draws "Sample map / BG1, SELECT CHUNK, 2 x 2 chunk grid, 512 x 512 px"
  (`dragonbyte_map_tileset_grayscale_v01.html:52`); v0.2 draws "Map 40, Background 1
  (BG1), Editable, 2 x 2 blocks (512 x 512 px)". It survives because it is MAGE's
  pattern and Lunar Magic's, not the prototype's invention: a status line that carries
  the target layer and the cursor position is what the reference analysis records as
  MAGE's "clearest layer target control" (A1-2, MAGE (a) and (c)) and as Lunar
  Magic's status-bar layer words (A1-3, Lunar Magic strength 3), and
  `../../desktop-ui.md` reserves exactly those facts for a status bar.
- **A thumbnail grid of the map's pictures, clicked to pick and then placed.** The
  first file's Chunk Palette (`:33`, `:118`) and the second file's "Tiles from current
  map" grid (`:16`, `:48`). It survives because both real editors that make reusing an
  existing feature cheap do it from a visual palette of the map's own content: Tiled's
  Tilesets view, where selecting tiles *is* the stamp brush, and Porymap's metatile
  pane with its Selection well (A1-2, Tiled (a) and (b); Porymap (a) and (b)). What
  the prototypes lacked and v0.2 adds is the rectangle capture from the map, so the
  palette is a shortcut and not the only path.
- **Four background layer slots as one selector.** The second file draws them as four
  radios (`map_tileset_prototype.html:22`). v0.2 draws a four-slot strip. It survives
  because it is MAGE's Edit radio group, the pattern the reference analysis recommends
  for this step by name: "Take MAGE's always-visible edit target because it is the
  clearest of the five" (A1-4, "Place it"). The difference is what the slots mean: in
  the prototype three of the four were labelled illustrative or "editable demo"; in
  v0.2 each slot carries its own real editable or read-only state with a reason.
