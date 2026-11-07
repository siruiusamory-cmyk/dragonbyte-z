# BOX_SOURCE : authentic BF dialogue box, LOG1 target

Lane A. One source (`box.s`), three payloads, three guarded sites. Every address
below is read from canonical LOG1 `3BA9919E…4B1B9` or cited to a runtime measurement;
nothing here is inherited from Buu's Fury.

Session 5 changes, in full: every independently split payload and every fixup word now
sits on a 4-byte boundary (`.balign 4` before `bf_box_strips`, `resource_words` and
`bf_box_window`), because the SDK places each payload at an alignment-4 address while
the assembler computed the Thumb `adr`/literal-pool arithmetic from the flat image
offsets: `bf_box_geometry` is 10 bytes, so `bf_box_strips` used to start at image
offset `0xA` and every PC-relative reference in it would have moved by 2 on placement.
The strip 2 entry was missing attr0 bit 13 (16 colours instead of 256). The three
entries are now affine, matrix 0, and the uniform opening ramp is implemented. Both
declarations name their own payload and use the closed fixup symbols. `assemble-box.ps1`
now builds `box.s` AND `text.s` from tracked source and asserts alignment, zero fixup
words and no unresolved ELF relocation.

Session 4 changes: the geometry hook now sets the donor default portrait position
instead of provisional page fields; the strips payload places the box at the donor's own
x positions and records the surface tile for the text controller; the separate
9,216-byte text surface and its four extra sprites are gone (the text is painted into
the box surface, which is the donor's own mechanism).

## Control invariant: the portrait object never positions the box

`bf-box-geometry` writes the original portrait object (`0x02003A80`, a UI object, not a
world actor) at x 8, y 88. That is the position the **untouched retail renderer
`0x08005119`** reads when lane B has no mapped face for a node: node 9 has kind `0x31`,
an original reaction icon, and it must stay visible at the left edge. The box strips take
their x from this file's own `BOX_X` constants (72/136/200) and never from the object,
so the icon is not drawn under the box, no temporary object copy is made and no RAM is
added. The retail entry writer preserves the matrix pad halfword (it masks only
`0xF000` of word 1 at `0x08005174..0x08005186`), so a native sprite update to an entry
does not disturb the coefficients.

`tools/check_box_sites.py` (lane A lab) pins the 12 bytes of `bf-box-geometry.bin`, so a
change of that object position to the box x fails loudly instead of silently moving the
fallback icon.

## Source classes

| payload | class | why |
|---|---|---|
| `bf-box-strips` | **adapted original mechanism** | the donor's own form: E measured BF drawing its dialogue box as three 8bpp OAM strips 64x64/64x64/32x64 at x 72/136/200, y 88, beside the 64x64 portrait at x 8, and painting glyph pixels into those same strip surfaces. Stage into the engine's EWRAM cursor, append packed shadow OAM, advance the cursors, the same path E measured for the portrait. Re-implemented in Thumb for this target's ABI; no donor bytes execute and no donor address is used. |
| `bf-box-geometry` | **new compatibility code** | the portrait object's pixel position is a retail structure (IWRAM object +0x00 x, +0x02 y); the value is the donor's measured default placement. |
| `bf-box-window` | **new compatibility code** | clears the retail 9-slice entries from the page map before retail publishes it. |
| box raster | **transferred original asset** | donor file `0x71758`, 160x64 8bpp, 10,240 B, 14 indices (index 0 the only transparent one). Converted by lane C/D into the shared low OBJ bank; this lane consumes it by fixup and writes no palette. The same resource is the dialogue text surface (see TEXT_SOURCE.md). |

## What the target engine provides (measured or read, relied on)

- the dialogue page object `0x02029D94`; its cell map is **inline at `+0x24`,
  2,048 B**, published by `0x08008D8A` from a per-frame method;
- `0x08008D14` fills the map with `bank<<12` by DMA (count `0x0400`, control
  `0x8100` = 16-bit, source fixed), a fill, not a template copy;
- the retail 9-slice window uses BG0 tiles `0x64..0x68` in palette bank 0, so
  `tile >= 0x64` identifies a window entry unambiguously;
- the render context `0x03000794`: `+0x00` OAM entry cursor, `+0x02` tile cursor in
  32-byte units, `+0x04` EWRAM staging cursor, `+0x0A` OBJ base tile; the flush
  `0x08002896` copies `ctx[+0x04] - 0x0200B024` bytes to `0x06010000 + ctx[+0x0A]*32`;
- the shadow OAM is one 1,024-byte region at `0x0202BE24`, copied whole to
  `0x07000000` by `0x080098C6` (256 words, control `0x8400`); `0x080098DE` clears the
  same 1,024 B with control `0x8500`;
- frame order: draw `+0x08`, flush `+0x18`, update `+0x1C`, so anything staged at
  `+0x10` shows the same frame and anything staged at `+0x1C` shows the next.

## Finding: the page geometry fields are not ours to set (session 4)

`bf-box-geometry` used to write `page+0x02/+0x06` (left/wrap columns). The page build
copies its own four-halfword rect from IWRAM into `page+0x02..+0x08` at
`0x08005338..0x0800534A`, which is **after** the `vtable[0]` call at `0x0800530E`, so
those writes were dead. The payload now writes only the portrait object. The box rect
itself is engine-determined; the OBJ box sits at the donor's default placement
regardless, which is what the owner asked for.

## Tile order (contiguous per strip) and its self-check

A 1D OBJ sprite reads its character data contiguously, so the tiles are packed per
strip, not in 20-column raster rows:

| strip | source column | tiles per row | 32-byte units |
|---|---|---|---|
| 1 (64x64) | 0 px | 8 | 128 |
| 2 (64x64) | 64 px | 8 | 128 |
| 3 (32x64) | 128 px | 4 | 64 |

`tools/check_box.py` walks the donor raster with exactly this order, rebuilds the
160x64 image from the staged tile block and the three strip rects, and compares it
byte for byte with the source raster: **10,240 B identical, 160 tiles, 3 strips**
(session 1; unchanged by this session's geometry move, which touches only the OAM
x/y halfwords).

The text controller addresses the same block as three strips with 8x8 8bpp tiles of
64 bytes (512 B per 8-row band in a 64-px strip, 256 B in the 32-px strip), which
`check_text.py` verifies against an independent framebuffer derivation for every ink
pixel of all seven approved lines.

## Runtime footprint

- pixels: `ctx+4` (`0x0200B024`): pad (0 or 32 B) + 10,240 B; `ctx+2` advanced to
  `box tile + 320` where the box tile is forced even for 8bpp; the flush must end at
  or below `0x06018000` (guard);
- OAM: three packed entries at `0x0202BE24 + 8*[ctx+0]`, cursor advanced by 3
  (guard: three free entries before the table end);
- `page+0x0E` (a provably unreferenced u16 hole in the page object) carries the
  box surface's first tile from this payload to `bf-text`;
- matrix 0's two pads `0x0202BE24 + {0x06, 0x1E}` (PA and PD; PB/PC stay zero), written
  by the build and advanced once per dialogue frame, no entry attribute of another
  sprite is touched;
- resource words are zero in the shipped block and filled by the SDK, so the bytes
  are position independent and an unbound word falls back rather than reading
  address 0.

## Interface for D

1. Place `bf-box-strips` (504 B); write `box_raster` (10,240 B adapted donor raster,
   offset `0x1EC`), `portrait_payload` (the placed address of `bf-portrait`, offset
   `0x1F0`) and `lifecycle_table` (the 112-byte node plan, offset `0x1F4`).
2. Place `bf-box-geometry` (12 B) and bind site `0x0011480`; place `bf-box-window`
   (412 B) and bind site `0x0000EF30` **taking that site from this document, dropping
   `bf-presentation`**.
3. Place `bf-text` (`text.bin`, 1064 B) and bind site `0x0000EF44`; its fixups at
   `0x41C`/`0x420`/`0x424` name `box_raster` (the same 10,240 B resource, second
   reference), `font_blob` (the raw 3,598 B font resource) and `lifecycle_table` (the
   same plan, second reference). One resource each, bound to one placed address.
4. The composition now reads `text-sites.toml` (D added it to
   `PRESENTATION_DECLARATIONS`) and binds `lifecycle_table` to `bf-dialogue-plan`
   through `emit_dialogue_plan`; this lane's independent derivation
   (`tools/derive_lifecycle.py` in the lane lab) and D's emitter produce the SAME 112
   bytes, `a9271663ee4b8cae17fa038175eb4902e238971b9f0e8735df172bcfbeb9d2d2`, from the
   canonical image.
5. `bf-box-strips` also declares `palette_low128` (offset `0x214`, 156 B) and copies
   the shared bank into OBJ entries 0..77 itself, after every guard. Lane B copies the
   same resource but only inside its mapped-speaker path, so without this an unmapped
   speaker's conversation would carry a box and glyphs with no bank. Native bank 7 and
   banks 8..15 are never touched; B still works standalone when the word is zero.
6. Site `0x0011480` is a **new** site: it needs profile admission and a runtime entry
   count before it is trusted (D's open blocker, unchanged).
6. `assemble-box.ps1` now assembles `box.s` **and** `text.s` from tracked source, so
   `text.s`, `text-sites.toml` and `TEXT_SOURCE.md` must be tracked or the clean-checkout
   assertion in `tests/unit/test_presentation_payloads.py` fails.

## Layout (donor default placement)

| item | position |
|---|---|
| box OBJ strips | x 72 / 136 / 200, y 88 (64x64, 64x64, 32x64) |
| portrait OBJ | x 8, y 88 (set by `bf-box-geometry`; staged by lane B) |
| text content origin | (80, 91), 144 px per line, four lines, pitch 14 |

224 px of 240 are used, and the box's own art bounds the text area.

## Animation: the donor's opening ramp, steady advance, and the collapse

Implemented from E's measurement (`handoff-E-animation.md`, run `bf-anim-01`): all four
donor box entries are affine with matrix 0, `PB = PC = 0`, the box opens over seven
frames with `PA = PD = trunc(2048/(2+k))`, `k = 0..6` = 1024/682/512/409/341/292/256,
resting at `0x100` (1:1), and it collapses on the reverse ramp with one final 2048 step
(E measured the close in frames 542..549 and the reopen at 559..565).

Session 7 makes the lifecycle the donor's own, driven by bounded ROM metadata instead of
by "every page build":

| where | what |
|---|---|
| `oam_table` in `bf_box_strips` | attr0 gains bit 8, attr1 leaves bits 9..13 = 0 (matrix 0) |
| `bf_box_strips`, after its guards | looks this stage's text pointer (`page+0x14`, written by the engine's installer `0x0800930A`) up in the `lifecycle_table` and writes `PA = PD = 2048` for the FIRST text stage of a conversation, `0x100` for every later one |
| `bf_box_window`, first thing it does | if `P_DONE`'s upper byte holds a collapse phase, writes that phase's reverse ramp row instead of touching the opening walk |
| `bf_box_window`, otherwise | reads PA and walks the `affine_ramp` table one step per dialogue frame |
| `bf_text_update`, when a stage's string ends | reads the plan's `final` flag and, on the last text stage only, arms the 8-frame collapse in `P_DONE`'s upper byte, then returns 1 after the 2048 step has been on screen for one frame |

Timing, from the measured frame order (draw `+0x08`, flush `+0x18`, update `+0x1C`) and
the rebuild's whole-shadow clear `0x080098DE`: the build happens in the update slot, so
at the first frame after it the `+0x08` payload advances 2048 → 1024 and the `+0x18`
flush draws `k = 0`; the seventh flush is `k = 6` = 1:1. The 2048 step is therefore never
drawn on the way in, exactly as in the donor, whose opening starts at 1024.

The collapse runs in the opposite direction and has to: the node's own teardown frees the
dialogue slot (`0x08005358`), rebuilds the shadow OAM (`0x0800535E`) and flushes
(`0x08005366`) as soon as the dialogue state exits, so no owned entry survives to
animate afterwards, and the native installer zeroes the whole `P_DONE` word at the next
stage install, so the phase cannot outlive its stage. Phase 1..7 publish 292/341/409/512/
682/1024/2048 through the same `affine_ramp` rows and the same entry-identity guard; phase
8 writes nothing, which is what guarantees the 2048 step reaches hardware OAM for one
whole frame before the pointer is cleared and the payload returns 1. Eight frames, by
construction; E owns the measurement.

Matrix layout (lanes B and E, GBATEK): matrix `m` is PA/PD at `0x0202BE24 + 0x20*m +
{0x06, 0x1E}` and PB/PC at `+{0x0E, 0x16}`, the fourth halfword of entries `4m..4m+3`,
never a contiguous 16-byte group, and a sprite selects `m` through attr1 bits 9..13, not
through its own entry index. Writing `+0x1E` therefore touches entry 3's *pad*, not its
attributes. The walk only advances from a value these two payloads wrote, so a native
affine user is never repointed; `PB`/`PC` stay zero because the rebuild zero-fills all
1,024 shadow bytes and nothing else writes a pad. The `check_box_sites.py` byte check
asserts the only halfword stores in `bf-box-window` are the page-map cell (`imm5 0`) and
the two pads (`imm5 3`/`15`), that the three staged entry rows equal the donor's own
attr words, and that the collapse phase is read out of `P_DONE` before anything else.

Not shipped, with the reason on the record:

- **The X spread at rest** is the steady triple 72/136/200 (+8 for lane B's portrait).
  The donor's per-frame −2/+6/+12/−10 motion appears only during the ramp rows, where
  this file writes the measured x per row; holding the steady triple between animation
  frames is the donor's own resting state.
- **The fourth sprite's x** is written during the ramp rows only (68 → 8). Lane B's
  entry owns the resting position. Nothing here assumes that sprite is 64x64: the shared
  matrix scales whatever size lane B leaves, and this lane writes no size, shape or attr
  word for it.
- **The lifecycle covers the conversation the plan is derived from.** `dialogue_plan`
  walks the profile's authored record (record 66 today), so another NPC's conversation
  finds no plan record: the box is then drawn instantly at 1:1 and closes exactly as
  retail does. That is the designed fallback, not a gap to paper over with a guessed
  open.
