# Reference board

Deliverable 1 of the DragonByte Z editor design package. Companion to
[`README.md`](README.md).

This board records what five real desktop tile editors do for the four steps of
the one task (pick a multi-tile feature, preview it, place it, undo and save),
and what DragonByte Z v0.2 takes from each. Every observation was made from an
authentic captured image and its product's own documentation by the reference
analysis agent; the observations are restated here in words, and each image is
named so the claim can be re-checked.

## What is stored here, and what is not

The images themselves are **not in this repository**. They are third-party
product screenshots whose terms are, for most of them, unstated, so no licence
permits redistribution; the repository may additionally hold no game graphics at
all (`../../decisions/0006-public-product-screenshots.md`, "What this does not
authorize"). The files live in the **local research archive**, which is outside
version control by role, not by path. This board carries the product, the source
URL, the captured file name and the sha256 the archive recorded, which is enough
to identify an image without republishing it.

A reader of this repository therefore sees: a written observation, the product it
concerns, the address it came from, and the identity of the file that shows it.

## The board

Legend: **Observed** is what the image and manual show. **Take** is what v0.2
adopts. **Reject** is what v0.2 does not adopt, with the reason. Citations of the
form "reference analysis A1-2, Tiled (a)" are to the reference analysis report's
own sections; the line ranges are its lines.

### 1. Tiled 1.12.2 documentation set and the 1.4.0 capture

| Field | Value |
| --- | --- |
| Source | <https://doc.mapeditor.org/en/stable/manual/editing-tile-layers/> and <https://doc.mapeditor.org/en/stable/manual/layers/> |
| Images | `tiled-05-screenshot-front.png` sha256 `2354e577b0be6ac36859233283aa59e76b4cb82eea3258acab8e829e7b7812c8`; `tiled-04-lock-visibility.png` sha256 `3219e006f8361bc8c5c97e319d99dee18a0dacacb6fed840639b79d6ce2d02d7`; `tiled-02-feature-tiles.png` sha256 `1acc1520f3b5d3170401af5f29579105a3db90f5801ae037b13a0218f0e5af40`; `tiled-09-new-tileset-created.png` sha256 `b686e5ed2a3f8a161ddfac28f0cd33cc6408d99e4e2445bee9026fb14708f5ca` |
| Terms recorded | not stated (documentation page footers carry a copyright line) |

**Observed.** One window: a Project dock on the left, document tabs, the map
canvas in the centre, a right-hand dock group, and a Tilesets dock holding one
tab per tileset plus a tile palette. A tool options strip sits above the canvas.
The Layers panel is the target selector and the state display at once: each row
carries an eye and a lock, and rows nest into groups. Selecting one or more tiles
in the Tilesets view *is* the stamp brush, and a right-drag on the map captures a
rectangle of tiles from the active layer as a new stamp. Named stamps persist in
a Tile Stamps view; Ctrl+1 to 9 stores and 1 to 9 recalls. Terrain painting
replaces hand-picking corner tiles with a terrain rule (reference analysis A1-2,
Tiled (a), (b), (c); A1-3, Tiled strengths 1 to 4).

**Take.** Capture-from-the-map as the cheap path for a feature that already
exists; a persistent place that holds the captured thing; a layer target that is
a visible control rather than an implicit mode.

**Reject.** The stamp library and the named-stamp slot keys are not in v0.2: the
engine has no store for an editor-side stamp, and a store is a second concept the
one task does not need. Terrain rules are out: they exist in Tiled because its
tiles carry terrain metadata, and Buu's Fury carries none (see
[`COMPATIBILITY_MATRIX.md`](COMPATIBILITY_MATRIX.md), OPS-16 and section 2.2).

### 2. Porymap

| Field | Value |
| --- | --- |
| Source | <https://huderlem.github.io/porymap/manual/introduction.html>, <https://huderlem.github.io/porymap/manual/editing-map-tiles.html> |
| Images | `porymap-06-tileset-dropdowns.png` sha256 `ac7fd5d4ec37afc3aa3e8eb852d8c021b4e4bb3dddf4e3c952ed2adcc36ae715`; `porymap-03-right-click-metatile-selection.gif` sha256 `898fbfbc74bdd81a5de71cc091cf7140570430ba4ff454657184c82b177e6516`; `porymap-05-prefab-list.png` sha256 `c36a1dcf59e04168fc82a26a5f2203b01949d27cdfb6df402d8864bc22098787` |
| Terms recorded | not stated (manual footer carries a copyright line) |

**Observed.** A drag in the metatile pane selects a rectangle, and the selection
becomes the paint brush. The current selection is always visible in a dedicated
Selection well beside the metatile grid, so the user never paints blind. Hovering
the map draws a white outline of the tiles that will be painted, and that outline
can be turned off from the View menu. Right-click, and right-click-drag, copies a
region from the map straight into the brush. A prefab is a named multi-metatile
feature saved once and reused, created from a map selection, and prefabs whose
tilesets do not belong to the open map are hidden from the list rather than shown
as unusable (reference analysis A1-2, Porymap (a), (b), (c); A1-3, Porymap
strengths 1, 2, 3).

**Take.** The pair the task needs most: a persistent well showing the captured
feature, plus a hover outline showing what will land under the cursor. v0.2 keeps
both, and it keeps the rule that the well and the outline agree.

**Reject.** Hiding an unusable saved feature. v0.2 shows a captured feature as
unusable with the reason, because a feature that silently disappears reads as
data loss (A1-3, Porymap weakness 1). The Prefab store itself is out for
the same reason as Tiled's stamp library, and the two-tilesets-per-map dropdown
pair has no counterpart here: Buu's Fury resolves tile graphics per map from a
selector, not from a user-chosen pair.

### 3. Aseprite 1.3 and later

| Field | Value |
| --- | --- |
| Source | <https://www.aseprite.org/docs/tilemap/>, <https://www.aseprite.org/docs/workspace/>, <https://www.aseprite.org/docs/layers/> |
| Images | `aseprite-01-tilemap-example.png` sha256 `512937148a2ee7ed4397ada9aafacd81fddbe8e450bffe7899adedfaa0142d48`; `aseprite-06-workspace.png` sha256 `409ac8b7aee182ad8456d136315efc7ee3c26de5467359baf663637dc05c5bc3`; `aseprite-07-layer-in-timeline.png` sha256 `5a2ad4cec4dff30ee873d3833d3aa7ef3b269c9bc7290776ddd8568672e8c723` |
| Terms recorded | not stated (site footer carries a copyright line) |

**Observed.** A tileset panel sits beside the canvas and the canvas holds tile
references into it. The manual's own diagram shows the panel feeding grid cells,
with tile index 0 as the empty tile. Drawing has two modes, Draw Tiles and Draw
Pixels, switched with Space+Tab, and the pixel modes have their own shortcuts
with their consequences stated. Layer rows in the timeline carry eye, lock and
continuous icons, so a tilemap layer behaves like any other layer (reference
analysis A1-2, Aseprite (a), (b), (c); A1-3, Aseprite strengths 1 and 4).

**Take.** Two levels of edit, map content versus source art, are separate modes
with an explicit switch, and neither can be reached by accident from the other.

**Reject.** v0.2 has one edit level, not two: source art authoring is
UNSUPPORTED in this title (OPS-16), so the design must not present a mode for it.
What v0.2 borrows is only the lesson that a mode which changes what gets destroyed
needs a visible label, which the reference analysis records as Aseprite's own
weakness 4.

Coverage gap, stated rather than filled: no public Aseprite screenshot shows
multi-tile selection in its tileset panel, so this board makes no claim about
that behaviour (reference analysis SC1).

### 4. Lunar Magic 3.71

| Field | Value |
| --- | --- |
| Source | <https://fusoya.eludevisibility.org/lm/>, <https://fusoya.eludevisibility.org/lm/program.html> |
| Images | `lunar-magic-05-objectsnew2.jpg` sha256 `24fe7c969c514bb5d029e39a44536a903212dd60108b112e178a60391c361781`; `lunar-magic-04-dragnew2.gif` sha256 `05a2ae5de5845dac8f6fd158a77fa091a32b4b8c7d339958434c5637f020d2a2`; `lunar-magic-06-overnew2.gif` sha256 `ca6363d6df90aa2ae497315ae2b347c6d038be0174c62cbb8e419bebdd78243e` |
| Terms recorded | not stated (freeware editor, site carries no reuse terms) |

**Observed.** The Add Objects window pairs a name list with a large preview pane
and states the insert gesture in words in its own status line ("CTRL + Right
Click to paste from here into level"). While a multi-object drag is in progress a
"Behind" indicator appears, which is depth feedback during a move. Layer state is
reported in words in the status bar ("Layer 2 8x8 Editor Mode Enabled") rather
than as a persistent control. The editor writes the ROM and must open it each run,
so the ROM is the document (reference analysis A1-2, Lunar Magic (b), (c), (f);
A1-3, Lunar Magic strengths 1, 2, 3).

**Take.** The preview pane and the in-place gesture reminder; and the idea that
the thing being placed is seen before it is used.

**Reject.** Layer state as a transient status string. v0.2 keeps the target layer
visible as a control whose state cannot scroll away (A1-3, Lunar Magic weakness
4), which is MAGE's pattern instead. The ROM-as-document is rejected outright:
DragonByte Z keeps the canonical image immutable and saves authored project data.

### 5. MAGE (Metroid Advance Game Editor 1.3.2)

| Field | Value |
| --- | --- |
| Source | <https://www.gamebrew.org/wiki/Metroid_Advance_Game_Editor_-_MAGE_GBA>; screenshot 1 is an archived romhacking.net gallery copy <http://web.archive.org/web/20250120065041im_/https://www.romhacking.net/utilities/screenshots/1212screenshot1.png> |
| Images | `mage-01-rhdn-screenshot1.png` sha256 `733c402a629b8fce6f508fc2eed65620dd937eee817bcd7e7ad33b1bd81e7da0`; `mage-03-mzmmage3.png` sha256 `2e4f15d89a629f2f6e53050b41b18fbafa9d12bbf1e60118a13a8cbc7e7478a7` |
| Terms recorded | not stated for the archived copy; the GameBrew page footer states CC BY-SA 4.0 unless otherwise noted |

**Observed.** An Edit radio group of BG0, BG1, BG2, BG3 and Clip sits immediately
left of the room canvas, separate from the View checkboxes for the same set, so
the edit target is always visible and always distinct from visibility. The room
canvas draws the room's scroll and screen boundaries. The tileset panel and the
room canvas share one window, and at 400x300 the canvas is barely usable
(reference analysis A1-2, MAGE (a), (c), (g); A1-3, MAGE strengths 1, 3 and
weakness 4).

**Take.** The always-visible edit target, and it is the clearest of the five.
v0.2 makes the target layer a labelled control beside the canvas with the same
separation between "which layer I edit" and "which layers I can see".

**Reject.** Competing for one window at a fixed small size. v0.2's canvas is the
dominant area and the target layer is a strip, not a panel (A1-3, MAGE weakness
4). MAGE has no multi-tile brush at all, which is exactly the gap this package
exists to close (A1-3, MAGE weakness 1).

## What the board does not claim

- **No product was installed or run.** Every observation is from a captured
  image plus that product's own documentation, as the reference analysis states.
  Nothing here is a claim about how any of the five behaves under load, on a
  second monitor, or with a large project.
- **No editor surface was measured firsthand.** The engine study reports COMPLETE
  after its round 2 run, and what that run established is narrower than it sounds: the
  clone boots, opens a 1920 by 1080 window and shows its title screen, captured three
  times with hashes. The room editor and tileset editor sit behind the in-game dev menu
  and need a keypress and a menu click, which the run rules forbid, so they remain
  unobserved. Every interactive statement this package draws from that study is read
  from its source, and is described as such.
- **Aseprite's multi-tile selection is unshown**, and that gap is recorded above
  rather than filled by inference.

## Counts, for checking

Ten images are cited by name, from five products, each with its source page
recorded above and its sha256 taken from the reference analysis attribution
table. The archive holds 24 images in total; this board cites the ten that carry
a decision, because a longer list would be a catalogue and not a board.

## How the board was used

Each row of the cross-product table in the reference analysis (A1-4) maps one
task step to the pattern v0.2 adopts. Those adoptions appear as decisions in
[`INTERACTION_SPEC_v0.2.md`](INTERACTION_SPEC_v0.2.md) section 5 to section 8, and
as numbered annotations in [`VISUAL_STUDY.md`](VISUAL_STUDY.md), where every
annotation names the finding above that justifies it.
