# Provenance: lane B payloads (`bf-presentation`, `bf-portrait`)

Canonical LOG1 sha256 `3ba9919e26704b0f5fdc2bfabc7f7a0404c71413761d38abcd94224c3bd4b1b9`,
re-hashed by `check_presentation.py` on every run. No donor (Buu's Fury) byte is present
in either payload and no donor address is executed.

Classes here: **RUNTIME** = E's measured runs (`lg1-portrait-06/-07`, `lg1-gfx-04`,
`lg1-seam-05`); **BYTES** = read from the canonical image by this lane; **DERIVED** =
arithmetic over the two; **REF** = primary documentation.

## Per-routine classification

| Routine / region | Class | Evidence |
|---|---|---|
| `bf_presentation` (24 B) | new compatibility code | assembled; boundary and epilogue asserted |
| `bf_portrait` (464 B) | adapted mechanism, newly written | transform is the donor kernel's at BF `0x087B7D2C` (BYTES: `push {r4-r8,sb,sl,fp}`, descriptor `[r0+0x24/0x28/0x2C]`, 8 source rows of 8 bytes per 64-byte tile, left to right), re-implemented in Thumb; no BF address called |
| `0x08005118` retail compositor | retained LOG1 routine | the payload's fall-through target `0x08005119` |
| `0x08005380` per-frame box draw | retained LOG1 routine | called by `bf_presentation`, never patched |
| identity blobs `0x08541748` / `0x0853E4E8` | LOG1 facts, recomputed by the checker | BYTES: `0x080052D8` `rec = ((u32*)0x0815A4E8)[kind]`; kind 89 maps to `0x085415DC`, kinds 52 and 53 to the same `0x0853E340`; `rec[+0]` is the palette blob |
| rasters / palette | lane C output, SDK fixups | `portrait-{roshi97,goku57}-8bpp-linear.bin`, `shared-low128-obj-palette.bin` |

## Seam 1 - per-frame box draw (behaviour preserving)

Site file `0x0000EF30`, canonical `5964ffff` = signed -39847 from base `0x0800EF28` to
retail `0x08005381`. Consumer `0x08009828..0x08009830` inside `FUN_080097F8`, entry LR
`0x08009835`, 3240 entries per run (RUNTIME). `bf_presentation` calls the retail draw
with its return address in `r2` (`adr` + `adds r2, #1`), so `r0`/`r1` reach the callee
untouched, then returns. Workstream A replaces this entry with the box hook.

## Seam 2 - the portrait method (candidate)

Site file `0x0011490` = word `+0x10` of the dialogue method table `0x08011480`,
canonical `19510008` = `0x08005119`, code `0x08005118`, unique in the image. RUNTIME:
dispatched from `0x08002658`, entry LR `0x0800265D`, **8 entries per 3600 frames (once
per page)**, `r0 = 0x02003A80` (object), `r1 = 0x03000794` (context).

The engine stages pixels in **EWRAM** and flushes them to VRAM afterwards:

```
ctx+0x00 u16  OAM entry cursor              entry 0  -> exit 1
ctx+0x02 u16  tile cursor, 32-byte units    entry 1  -> exit 17  (retail: one 32x32 4bpp)
ctx+0x04 u32  EWRAM pixel cursor            entry 0x0200B024
ctx+0x0A u16  VRAM base tile of the block   entry 1, unchanged
0x08002896    copies (ctx+4 - 0x0200B024) bytes from 0x0200B024 to
              0x06010000 + (ctx+0x0A)*32 with DMA3, once per frame
0x0202BE24    shadow OAM base; entry = 8 bytes {attr0 | attr1<<16, attr2}, appended
```

### Order of operations - every guard before every write

1. **Fixup words** non-zero (an unbound build is inert, not fatal).
2. **Object sanity:** `[obj+0x34] == 0x08011480`; else retail.
3. **Identity:** the live palette bank `0x05000200 + 32*[obj+0x0D]`, entries 1..15, with
   `& 0x7FFF` on both sides (bit 15 is not a colour bit), against the ROM blob - Roshi
   `0x08541748`, Goku `0x0853E4E8` (kinds 52 and 53 share one record and one art, so a
   shared identity is correct, not ambiguous). This is a **read** and happens before any
   upload. Anything else tails into retail `0x08005119` with `r0`/`r1` restored.
4. **OAM bound:** `ctx+0` < 128; else retail.
5. **Tile bound:** `image_tile = ctx+2 + (ctx+2 & 1)` stays even and
   `image_tile + 128 <= 1024` (the 10-bit OBJ tile field); else retail.
6. **Staging capacity:** `(ctx+4 - 0x0200B024) + pad + 4096 <= 0x8000 - (ctx+0x0A)*32`.
   That right-hand side is the engine's own flush bound - the block copy must end at or
   below `0x06018000` - not an invented RAM edge. At the measured base tile 1 it is
   `0x7FE0`. Else retail.
7. Only then: the palette upload, the staging write, the cursors, the OAM entry.

A refusal is therefore side-effect free: no palette entry, no cursor, no pixel changes.

### Palette: 78 entries, not a bank config

The supported input is **78 entries** - donor index 0 as the transparent slot plus 77
opaque colours (the union of the three converted pieces, lane C). The payload copies 39
words (156 B) to `0x05000200`, so it writes banks 0..4 only. Banks 5, 6 and 7 are left
alone: bank 7 is the bank retail chose for this sprite, and an unknown speaker's portrait
keeps it. Entries 80..127 are never touched. There is no configurable bank count; 78 is
the documented number the conversion produces.

### Parity

The measured tile cursor is odd (1) and an 8bpp OAM tile index must be even, so one
32-byte unit of zeros is staged first and the image starts at tile 2. The cursor is read
at runtime, not assumed. Cursors are handed on consistently:
`ctx+4 = base + pad + 4096`, `ctx+2 = image tile + 128`, `ctx+0x0A` untouched, so the
flush length and base stay consistent by construction.

### OAM entry

attr0 = `y | 0x2000`, attr1 = `x | 0xC000` (size 3 = 64x64), attr2 = image tile, palette
bank 0, priority 0; `y` from `obj+2` exactly as retail reads it.

`0x2000` is attr0 **bit 13 = 256 colours** per GBATEK
(<https://mgba-emu.github.io/gbatek/>, OBJ attribute 0: bit 12 mosaic, bit 13
colours/palette, bits 14-15 shape), and E's donor 8bpp entries carry the same bit. The
checker asserts bit 13 set and bit 12 clear, so a regression to `0x1000` fails loudly.

**x is provisional.** 160 (right-hand portrait) / 16 (left-hand) is an integration value;
160 currently overlaps the old text area, and workstream A owns the final UI geometry.
This candidate is an integration test, not visual acceptance.

### Build inputs

`portrait.bin` ends with three zeroed words; the SDK fills them by fixup offset, so the
assembled bytes are final and carry no placeholder:

| Offset | Symbol | Bytes |
|---|---|---|
| `0x1C4` | `raster_roshi` | 4096, converted row-major 8bpp |
| `0x1C8` | `raster_goku` | 4096 |
| `0x1CC` | `palette_low128` | first 78 entries (156 B) are read |

## Commands

```
powershell -NoProfile -ExecutionPolicy Bypass -File assemble.ps1
python ..\tools\check_presentation.py
python ..\tools\verify_alpha.py
```

## Corrections to earlier claims of this lane

| Earlier claim | Now | Why |
|---|---|---|
| `ctx+4` is a VRAM destination; tile = `(ctx+4 - 0x06010000)/32` | `ctx+4` is EWRAM staging; tile = `ctx+2` | RUNTIME |
| round a VRAM address up to 64 bytes | pad one 32-byte staging unit | DERIVED |
| the method runs every frame | once per page | RUNTIME |
| identity is the `0x03000994` cache word | identity is the palette **bank content**, bit 15 masked | RUNTIME: cache all zero |
| attr0 256 colours is bit 12 (`0x1000`) | bit 13 (`0x2000`) | REF: GBATEK; E's donor 8bpp entries |
| 128 palette entries written | 78 written, banks 5..7 preserved | lane C's real count is 77 opaque |

## Not measured by this lane

* live bank content equal to the ROM blob's entries 1..15 (the identity path rests on
  it; a mismatch is silent - retail fallback, no crash);
* the candidate's OAM entry words and the 64x64 result on screen;
* the flush budget in a real page once other sprites stage after 4128 bytes;
* the visual placement (x is provisional) and box overlap;
* the BF box: workstream A's (`box.s`, `box.bin`, `box-sites.toml`, `BOX_SOURCE.md`).
