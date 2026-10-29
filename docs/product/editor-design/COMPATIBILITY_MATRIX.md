# Technical compatibility matrix

Deliverable 2 of the DragonByte Z editor design package. Companion to
[`README.md`](README.md).

One question: **which operations in the proposed interaction can the retail Buu's
Fury engine actually support?** Every row carries one of three categories and at
least one citation into this repository. Nothing here was re-derived for this
package; it is the technical audit's matrix, reproduced with its categories and
citations and with citations rewritten as repository-relative paths.

## Categories, and how they were applied

Defined by [`../../decisions/0004-proof-levels.md`](../../decisions/0004-proof-levels.md):

- **RUNTIME-PROVEN**: a governed emulator run observed the effect itself. ADR
  0004 requires "an engine observation of the specific authored result".
- **ENCODING-CAPABLE**: the bytes are written and re-read correctly, with no
  engine observation of that effect.
- **UNSUPPORTED**: the evidence shows the operation cannot work, or no evidence
  exists at all.

Two conventions from the audit are kept because they change how a row must be
read:

1. **Selection is editor state, not a write.** Rows about selecting a region are
   classified by the reads they compose, and the row says so.
2. **Every row is Buu's Fury** (sha256 `940ad5f0...059e`) unless the row says
   otherwise. No Legacy of Goku I or II document is used as Buu's Fury evidence.

## 1. The reads the whole editor rests on

| # | Operation | Category | Evidence | Limits |
| --- | --- | --- | --- | --- |
| OPS-01 | Read and render a map with all its layers | **RUNTIME-PROVEN** | `docs/research/MAP_RENDER_FORMAT.md:206` ("ROM-only vs VRAM oracle: EXACT"); `docs/research/BUU_MAP_GRAPHICS_DIAG.md:162-176`; capability `map-browser` `proof: runtime` | The proven render path is maps 39 and 40; `docs/research/ROM_EDITOR_COVERAGE_LEDGER.md:195` says "the general case is not proven"; layer forms other than dominant have no established consumer (`docs/PROJECT_STATE.md:393-397`) |
| OPS-02 | Enumerate the four layer slots, their grids and cells | **RUNTIME-PROVEN** (read) | `docs/PROJECT_STATE.md:380-406`; live dump agreement `docs/research/BUU_MAP_GRAPHICS_DIAG.md:79-105` | Exactly four slots per map root (`docs/research/MAP_RESIZE_AND_LAYERS.md:108-117`); an unused slot is a shared zero-dimension record |
| OPS-03 | Identify which graphics bank a map uses | **RUNTIME-PROVEN** per map selector | `docs/research/MAP_RENDER_FORMAT.md:73-92`; `docs/PROJECT_STATE.md:364-376` | The selector is per map; the bank table and bank bodies are engine-global |

## 2. Selection and copy

| # | Operation | Category | Evidence | Limits |
| --- | --- | --- | --- | --- |
| OPS-04 | Select a rectangle at **8x8 tile** granularity | **UNSUPPORTED** | `docs/ROADMAP_TO_1_0.md:442-446` (tile-level selection and copy were not delivered, because "the format's editable unit is the cell reference, not an individual 8x8 tile"); `docs/research/MAP_TILE_PAINT.md:14-34` | Tiles exist only as 10-bit ordinals inside a screen entry; writes are per 4-byte cell. A tile selection can be displayed, never authored. **This is why v0.2 offers no marquee at tile level.** |
| OPS-05 | Select a rectangle of **chunk cells** on one layer | **ENCODING-CAPABLE** | `docs/research/MAP_TILE_PAINT.md:47-51` (`set_layout_cells` validates a whole batch before writing); `tools/webfoot/map_paint.py:796-826`; `tests/unit/test_map_paint_any_chunk.py` | A batch is a set of single-cell writes. No runtime observation of a multi-cell rectangle exists (gap G1). **This is the row the task's "multi-tile feature" stands on.** |
| OPS-06 | Reassign one chunk cell (paint) | **RUNTIME-PROVEN** | `docs/research/MAP_TILE_PAINT.md:96-138` (matched A/B, 7,013 of 38,400 px differ, all inside the predicted cell box); capability `tiles` `proof: runtime` | Only a non-null chunk some dominant layer of **the same map** already uses (`tools/webfoot/map_layout_write.py:67-101`); 440 of 452 maps editable, 12 refused with a reason |
| OPS-07 | Copy a region within the same map | **ENCODING-CAPABLE** | Composed of OPS-06 cells, one merged write plan (`docs/research/MAP_TILE_PAINT.md:83-90`); region copy recorded as not delivered (`docs/ROADMAP_TO_1_0.md:443-444`) | No shipped region operation exists; the composition is a batch of proven cell writes, not a runtime-observed rectangle (G1) |
| OPS-08 | Select across layers | **RUNTIME-PROVEN** (read only) | `docs/research/MAP_RENDER_FORMAT.md:134-166`; `docs/research/BUU_MAP_GRAPHICS_DIAG.md:96-105` | There is no cross-layer write: every write addresses one layer's cell window. **This is why v0.2's selection captures one layer.** |

## 3. Paste across maps

| # | Operation | Category | Evidence | Limits |
| --- | --- | --- | --- | --- |
| OPS-09 | Paste into another map with the same bank | **ENCODING-CAPABLE** (corpus evidence only) | 165 shared chunk bodies, 160 across different maps (`docs/PROJECT_STATE.md:464-468`); a new map already inherits its donor's bodies (`docs/ROADMAP_TO_1_0.md:581-584`) | The SDK refuses it: `tools/webfoot/map_layout_write.py:80-84` ("not a chunk from another map"), `tools/webfoot/map_chunk.py:36-44`. Character-block equality between two maps is not measured anywhere |
| OPS-10 | Paste into a map with a different bank | **UNSUPPORTED** | Ordinals are map-scoped (`docs/PROJECT_STATE.md:466-468`); `docs/research/MAP_CHUNK_AUTHORING.md:36-39`; capability `chunks` limits | A foreign ordinal indexes the target's character block, so the paste draws different pixels. A semantic limit, not a capacity one. **This is why v0.2's stamp never crosses a map.** |

## 4. Palette

| # | Operation | Category | Evidence | Limits |
| --- | --- | --- | --- | --- |
| OPS-11 | Change a tile's palette | **UNSUPPORTED** | Entry bits 12-15 are zero in all 3,834,880 canonical entries (`docs/PROJECT_STATE.md:454-456`); all four layers are 8bpp at runtime (`docs/research/BUU_MAP_GRAPHICS_DIAG.md:193-194`, `:246-250`) | At 8bpp there is no palette bank to select. **This is why v0.2 has no palette control at all, rather than a disabled one.** |
| OPS-12 | Change a palette entry (global) | **ENCODING-CAPABLE** | `docs/research/GRAPHICS_FORMAT.md:377-398`, `:484-495`; capability `palette` `proof: application` | Global blast radius; which table feeds a map scene's background palette is not settled (contradiction C1 below). Outside the one task. |

## 5. Collision

| # | Operation | Category | Evidence | Limits |
| --- | --- | --- | --- | --- |
| OPS-13 | Read collision under a region | **UNSUPPORTED** | `docs/research/COLLISION_FORMAT.md:8-10` ("BLOCKED at the evidence gate"), `:186-202`; `docs/research/ROM_EDITOR_COVERAGE_LEDGER.md:52` | This title keeps no separate per-map collision table; movement is decided by a virtual dispatch whose data is built at load |
| OPS-14 | Edit collision under a pasted region | **UNSUPPORTED** | `docs/research/COLLISION_FORMAT.md:233-244` ("Collision WRITE: NOT SUPPORTED"); every authoring record repeats "no collision editing" | There is no byte to edit. **A stamped feature therefore inherits the target's walkability, and v0.2 says so once per placement rather than offering a collision control.** |

## 6. Authoring

| # | Operation | Category | Evidence | Limits |
| --- | --- | --- | --- | --- |
| OPS-15 | Place a reusable authored chunk | **RUNTIME-PROVEN** (inside the composing map) | `docs/research/MAP_CHUNK_AUTHORING.md:105-153` (593 of 1,024 BG1 entries changed, other layers byte-identical); capability `chunks` `proof: runtime` | Reusable across that map's layers only, limited to entries the template layer already displays; a chunk must be allocated above end of file |
| OPS-16 | Edit a tileset (tiles, pixels, bank order) | **UNSUPPORTED** | `docs/research/GRAPHICS_FORMAT.md:449-495` (no slack in 7,355 containers; median re-encode 1.06x); `docs/research/ROM_EDITOR_COVERAGE_LEDGER.md:196-197`; `docs/research/ROM_EDITOR_COVERAGE_SUMMARY.md:99` | No writer and no capacity. **This is why the Tileset Workshop has no pixel authoring in v0.2.** |
| OPS-17 | Edit a tileset arrangement (the chunk plane) | **RUNTIME-PROVEN** | Same run as OPS-15 (`docs/research/MAP_CHUNK_AUTHORING.md:127-150`) | Only the entry vocabulary the template layer displays; ordinals are map-scoped |
| OPS-18 | Resize a layer, or activate an unused slot | **RUNTIME-PROVEN** | `docs/research/MAP_RESIZE_AND_LAYERS.md:204-222`, `:271-330`; capability `resize` `proof: runtime` | Growth only, shrink refused, shared root refused (`:409-419`) |
| OPS-19 | Create and register a new map | **RUNTIME-PROVEN** | `docs/research/MAP_NEW_AUTHORING.md:207-240`; capability `map-new` `proof: runtime` | Ceiling of 510 rows, so 58 authored maps; a new map inherits the donor's collision behaviour |
| OPS-20 | Create a door or transition into a new map | **RUNTIME-PROVEN** | `docs/research/MAP_NEW_AUTHORING.md:236-240`; `docs/ROADMAP_TO_1_0.md:589-591` | A region overlapping a retail record loses to it |

## 7. Save, build, patch

| # | Operation | Category | Evidence | Limits |
| --- | --- | --- | --- | --- |
| OPS-21 | Save as a project change | **ENCODING-CAPABLE** | Four address-free project documents, reopen proven: `maps/layout.toml` (`docs/research/MAP_TILE_PAINT.md:52-57`), `maps/chunks.toml`, `maps/structure.toml`, `maps/authored.toml`; capability `save-as` `proof: application` | Project files are not ROM bytes, so no engine observation applies. **This is what v0.2's Save writes.** |
| OPS-22 | Rebuild a playable image | **RUNTIME-PROVEN** | Four independent derivatives were run in the retail engine: paint `50579a66...` (`docs/research/MAP_TILE_PAINT.md:105`), chunk `5c51ece7...` (`docs/research/MAP_CHUNK_AUTHORING.md:102`), resize `b2315cce...` (`docs/research/MAP_RESIZE_AND_LAYERS.md:283`, `:318`), new map `A70C9D26...` (`docs/research/MAP_NEW_AUTHORING.md:207-210`) | Build is a separate action from Save, and a build above end of file is 16 MiB. v0.2 does not fold Build into Save. |
| OPS-23 | Export a patch | **ENCODING-CAPABLE** | `tools/webfoot/patch.py:303` `export_patch`, `:390` `verify_patch`; ROM-gated test `tests/integration/test_patch_export_rom.py` | No recorded engine observation of a patched retail image. Outside the one task. |
| OPS-24 | Undo/redo of an authored operation | **ENCODING-CAPABLE** | One `QUndoStack` per surface: `docs/research/MAP_TILE_PAINT.md:68-79` (a drag is one gesture, a no-op stages nothing); `docs/research/MAP_RESIZE_AND_LAYERS.md:461-466` | Project-level history. **This is the row v0.2's undo model stands on.** |

## 8. What a "multi-tile environmental feature" is in this data

Four things, and only the first two are what the task can paint:

1. **Chunk cell**: one 4-byte, 4-aligned pointer at `layer + 0x18 + 4*cell`,
   row-major. The unit the engine draws and the shipped brush paints
   (`docs/PROJECT_STATE.md:461-463`).
2. **Chunk body**: 1,024 little-endian screen entries, one 32x32 plane, 256x256
   pixels (`docs/research/MAP_CHUNK_AUTHORING.md:19-34`). Each entry carries a
   10-bit tile ordinal, horizontal and vertical flip bits, and four palette bits
   that are always zero.
3. **Tile**: an 8x8, 8bpp, 64-byte block inside a map-scoped character block,
   addressed by ordinal, not independently selectable or writable (OPS-04).
4. **Object or actor**: not environment, and a separate surface.

**There is no metatile layer.** A bank has "no metatile and no composition rule"
(`docs/research/BUU_MAP_GRAPHICS_DIAG.md:232-239`). So a multi-tile feature is
either one chunk body seen through a single cell, or a set of adjacent cells. It
is never an intermediate arrangement object, and v0.2 does not invent one.

**No arrangement can be identified automatically.** There is no chunk catalogue
("a chunk is discovered only from a layer window",
`docs/research/MAP_CHUNK_AUTHORING.md:30`), and nothing carries a semantic label:
"No semantic labels. Nothing here says house, tree or cliff"
(`docs/research/TILESET_COMPOSITOR.md:286-292`). The author selects a rectangle;
the tool offers the distinct chunks inside it. Any "feature detection" would be an
invention.

## 9. What travels with a stamped rectangle

| Component | Travels | Evidence |
| --- | --- | --- |
| The 4-byte cell pointer and the chunk body | Yes, the body is shared, not copied | `docs/PROJECT_STATE.md:464-468`; 165 shared bodies |
| Tile ordinals and flips | Yes, inside the 1,024 entries | `docs/PROJECT_STATE.md:446-456` |
| The pixels those ordinals resolve to | Only if the target map's character block covers the same ordinals | `docs/PROJECT_STATE.md:466-468` |
| Palette | No | bits 12-15 unused at 8bpp |
| Priority and stacking | No: it is the map root's four addend bytes, not the cell | `docs/research/MAP_RENDER_FORMAT.md:231-233` |
| Collision | No, and it cannot | `docs/research/COLLISION_FORMAT.md:186-244` |
| The layer record's header fields | No | `docs/PROJECT_STATE.md:418-426` |

## 10. The refusal set v0.2 must show

Refuse, with the reason stated (the SDK already enforces most of these):

- a stamp whose source is a different map, or whose character block is not proven
  equal (`tools/webfoot/map_layout_write.py:80-84`, `tools/webfoot/map_chunk.py:36-44`);
- a chunk no dominant layer of the target map already uses
  (`tools/webfoot/map_layout_write.py:67-101`);
- a cell outside the layer's grid (a resize is growth-only and cannot shrink,
  `docs/research/MAP_RESIZE_AND_LAYERS.md:209-213`);
- an unsupported layer form: screen-entry plane, map 19's terrain field, absent
  slot, zero-dimension record, unclassified handler
  (`docs/research/MAP_TILE_PAINT.md:38-45`), and the 12 read-only maps;
- a map root shared with another map (11 roots serve more than one map,
  `docs/research/MAP_RESIZE_AND_LAYERS.md:24-25`, `:417-419`);
- any palette-bit intent (`docs/research/ROM_EDITOR_COVERAGE_LEDGER.md:202`).

Warn, because there is real risk and no evidence either way:

- **collision is unchanged and unauthored**: a stamped "wall" is walk-through
  unless the target already blocked there (`docs/research/COLLISION_FORMAT.md:220-231`);
- **shared layer records**: 1,464 unique records serve 1,808 references and 35
  records are shared between maps (`docs/PROJECT_STATE.md:382-391`). No guard was
  found for a record another map also references. Whether any of the 35 is a
  dominant record is not stated (gap G7), so the warning may say "may" and never
  "will";
- **the result can be partly hidden by priority**: on map 39 only 1,145 of about
  21,600 cell pixels of a low-priority layer showed
  (`docs/research/MAP_RESIZE_AND_LAYERS.md:327-330`).

## 11. Evidentiary gaps, and what each blocks

No probe was run for this package; every probe named is the audit's proposal.

| Gap | What it leaves unproven | Smallest probe (audit's proposal) |
| --- | --- | --- |
| G1 | A multi-cell rectangle is written but never observed | paint a 3x2 block on map 40 BG1 through `tools/runtime/capture_tilepaint001_afterrebuild.ps1` unchanged |
| G2 | An authored cross-map cell is never observed | place one pointer from map 39 into map 40 by a one-off patch and observe the live cell |
| G3 | Palette bits 12-15 have no measured semantics | one entry with a non-zero high nibble, leave and re-enter |
| G4 | Which table feeds a map scene's palette | breakpoint after the palette copy, dump both palette pages |
| G5 | Collision under a pasted region | trace which IWRAM vtable the movement predicate resolves to |
| G6 | Tileset pixel authoring | not a probe: compressor output size is the blocker, recorded POST-1.0 |
| G7 | A shared dominant layer record can be painted through another map | static census of the 35 cross-map records by handler |

Rows the one task depends on that are **not** RUNTIME-PROVEN: OPS-05 and OPS-07
(the rectangle), OPS-09 (cross-map, which v0.2 refuses anyway), OPS-21 (save) and
OPS-24 (undo).

## 12. Contradictions carried forward

Not resolved here, and not resolved by any decision in this package:

- **C1, which table is the background palette.** Four sources disagree; the
  runtime reading wins for the one scene it measured, and which of two tables is
  "the background palette" is not established. Consequence: nothing in v0.2
  depends on a per-map palette.
- **C2, whether a map entry field at `+0x04` is a count byte or a pointer.**
  The audit sides with the bytes and the consuming instruction (count byte). No
  v0.2 row depends on it.
- **C3, "layout write is runtime-proven".** A user gesture is runtime-proven; the
  narrow fixed-size writer's own single operation is application-level. This
  matrix keeps OPS-06 and OPS-21 apart for that reason.
- **C4, "1,516 dominant records" versus "1,420 records behind 1,516 references".**
  A reference count is not a record count. This is the risk G7 measures.

## 13. What this matrix is not

It is not a claim that the product can do these things today. It is the evidence
ceiling for a design: an operation rated ENCODING-CAPABLE may be specified and
built, and may not be described to a user as proven to work in the game. The
wording rules that follow from this are in
[`INTERACTION_SPEC_v0.2.md`](INTERACTION_SPEC_v0.2.md) section 9, and the build
sequencing that follows from it is in
[`IMPLEMENTATION_READINESS.md`](IMPLEMENTATION_READINESS.md).
