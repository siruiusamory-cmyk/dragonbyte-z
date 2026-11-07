# TEXT_SOURCE.md - the BF dialogue text controller in LOG1 (lane A)

Lane A, session 4, 2026-11-07. Status: **implemented source, assembled and statically
checked; not executed.** No emulator was launched by this lane (E owns that), so
nothing here is a gameplay or parity claim. Every statement is labelled: read from
bytes, inferred from structure, runtime-measured by E and quoted, or not established.

This supersedes the prototype in this file's earlier revision (the per-character BG0
map writer at 0x08008DBE). That writer is retired: its seam could not carry the
string, its BL retargets were out of Thumb-1 range, and its BG tile block was never
proven owned.

## 1. Pins

| Item | Value |
|---|---|
| Donor BF | the canonical Buu's Fury (U) image, sha256 `940AD5F01DB4465B8877DFE739510CBF34F4EA3D390F3DF13519808BC36F059E` |
| Target LOG1 | the canonical Legacy of Goku (USA) image, sha256 `3BA9919E26704B0F5FDC2BFABC7F7A0404C71413761D38ABCD94224C3BD4B1B9` |
| Payload | `text.bin`, 1,064 B, sha256 `455DF399D661603E424967805F479A9CA353535E54D94C02196ACCFCDB85E575` |
| Payload source | `text.s`, `arm-none-eabi-as -mcpu=arm7tdmi -mthumb`, exit 0 |
| Fixups | `0x41C` -> `box_raster` (10,240 B), `0x420` -> `font_blob` (3,598 B), `0x424` -> `lifecycle_table` (112 B, the node plan), all zero in the shipped bytes; each declaration names its own payload (`payload = "bf-text"`) |
| Seam | file `0x0000EF44`, expect `6b64ffff`, base `0x0800EF28`, -> `0x08005393` |
| Font resource | raw donor range `0x06E05C..0x06EE6A`, 3,598 B, sha256 `95E97071F6C0318D9EEE0160D63300B6D3FB780C73A4A02C10A0F1CC605FD085` |
| Check tool | the lane-A text-source check script, exit 0, 40 checks (section 7) |

Both canonicals were hashed before and after the session and never written.

## 2. The seam, and the contract it must keep

Read from bytes at `0x08005392..0x080053A8`, which is what the table slot
`0x0800EF28 + 0x1C` points at in the canonical image:

```
08005392  push {r4, lr}
08005394  r4 = [0x080053B8] = 0x02029D94     ; the dialogue page object
08005396  r1 = [0x080053EC] = 0x080051B5     ; the callback retail passes
0800539A  bl   0x08009328                    ; the retail reveal body
0800539E  r0 = ([page+0x14] == 0) ? 1 : 0
080053A8  pop  {r4, pc}
```

`FUN_080097F8` (the per-frame dispatcher, `0x08009828..0x08009850`) calls the
object's `+0x0C` method (`0x08005B38`), which calls the `+0x18` flush method and
then entry `+0x1C` once, and returns that entry's `r0` as the object's own return.
A non-zero return closes the dialogue object (`0x08009852..0x0800986C`). So the
seam's whole ABI is: one call per frame, `r0` in, `r0` out meaning "conversation
over"; the page is reached by literal, exactly as retail does.

The payload therefore replaces the wrapper and keeps both halves of the contract:
it returns 1 only after the node's string has been consumed and the player pressed,
and it leaves `page+0x14 = 0` in that state, which is what retail leaves behind.

The retail body `0x08009328` is a 10-frame-per-glyph typewriter on an 18-cell map
grid (countdown reload `0x32`, per-frame table `{5,15,25}` at `0x080116B4`, word fit
in map cells). Owner direction: do not inherit it. The payload never calls it except
as the refusal path.

## 3. Donor rules, and the two the bytes decided

From lane C's source proof (`0x0800AED0` composer, `0x0803DE50`, `0x0803F444`) plus
two points re-read from the donor this session:

1. **Font layout, table first.** The resource is a 256-entry `u16` table at offset 0
   (`map[code]` = record offset in `u16` units) followed by 224 contiguous records:
   `u16 width`, `width` `u16` ink column masks (bit `r` = row `r`, bit 0 = top row),
   then one trailing `u16` that is never ink. The walk ends exactly at 3,598 B.
   Because the table is at the base, **no descriptor is read**; the SDK emits only
   the raw 3,598 B, and an earlier draft that added 3,600 would have read past the
   allocation (coordinator catch, corrected here).
2. **Advance** = `width + 1`; `map[code] == 0` draws nothing and advances 1.
   Code `>= 0xFF` advances 12 and draws nothing: retail's wide base is 0 and no
   dialogue unit at or above `0xFF` exists, so the class is unexercised and the
   shipped resource holds no wide columns to read. DEVIATION from the donor's unused
   path, recorded in section 8.
3. **The break rule (settled from the donor's own bytes this session).** At
   `0x0803DEE0..0x0803DEF0` the composer computes `pen + advance`, compares it with
   the layout wrap (`r2`), and on overflow stores the *current* candidate
   (`stm r3!, {r6, r7}`) and leaves the line. `r6`/`r7` hold the last space's source
   pointer and the pen at that space, and at `0x0803DEAA` a space overwrites them
   with itself. Consequence, which the naive reading gets wrong: when the
   overflowing code is *itself* a space, the line breaks at that space, so the line
   keeps every glyph before it. That is why node 5's first line is 143 px
   ("A few went missing! If you") and not 121. The payload implements the donor
   branch; the check tool walks the same rule and reproduces all seven of lane C's
   published line tables exactly (section 7).
4. **Layout 0**: wrap 144 px of content measured in the pen's own coordinates
   (origin 0, limit 144, i.e. absolute 8..151 in the box), 4 lines per page, bitmap
   top `first_y - 12 = 3`, line pitch 14, one ink byte, no shadow, no outline.
   The earlier "144 absolute" reading loses 8 px and is falsified by the same table.
5. **Stream**: `0x0A` ends a line, `0x0B` ends a page, `0x00` ends the node string,
   `0x08 <u16>` sets the ink byte and consumes 4 bytes.
6. **Cadence**: one glyph per frame (donor: 500 of 508 measured gaps = 1 frame).
   Spaces are glyphs and take a frame; control codes do not.
7. **Held A**: a press that began before the reveal finished does not advance the
   finished page (donor measured: 260 frames held, 229 after completion, no page
   change). A fresh press after completion advances exactly one page. Retail's own
   done branch is already edge-keyed, `0x0800933C` tests `0x03003D14` bit 0/bit 1,
   and the input poll `FUN_0800A664` writes that halfword as
   `current & ~previous` every frame, so the payload tests the same halfword and
   inherits the donor's behaviour for both measured cases.

## 4. What the payload does, per frame

Read the guard set first (section 5). Then:

* `page+0x1C == 0` means a page start, the retail install `0x0800930A` zeroes it
  at every page, so the payload copies the box surface resource back over the
  staged box span (10,240 B). This is the donor's own reset: glyphs are painted
  into the box pixels, so a page turn must restore them from the box source.
* `page+0x1C` counts revealed glyphs of the page; it is incremented and the payload
  inks glyph number `count-1` at the position the layout gives it, by re-laying the
  page out from `page+0x14` every frame (stateless; no RAM beyond the stack).
* When the layout walk ends (4 lines used, a `0x0B`, or a `0x00`), and the counted
  glyph does not exist, the page is complete: `page+0x20 = 1` and `page+0x14` is set
  to the resume pointer (past a `0x0A`/`0x0B`, on the `0x00`).
* While complete, a new A/B press edge either advances one page
  (`+0x1C = 0`, `+0x20 = 0`) or, when the resume pointer is 0 or points at `0x00`,
  finishes the node exactly as retail does: `page+0x14 = 0`, clear the press edge
  and the input latch, return 1.
* Every helper call stays inside the payload. There is no BL to a far address: the
  only absolute transfers are `bx` through a literal, and one of them is the refusal
  path's call to the retail body `0x08009329` with retail's callback `0x080051B5`.

## 5. Ownership and guards

Owned page fields (none other is written): `+0x14` text pointer/resume pointer,
`+0x1C` revealed count, `+0x20` page-complete flag. `+0x18` is left entirely to the
retail install, which recomputes it per page. `+0x02..+0x08`, `+0x10` and `+0x0E`
are never written by this payload, `+0x0E` is written by the box payload and read
here.

Refusal is total: every guard runs before the first write, and a refusal tail-calls
the retail body `0x08009328` with retail's own callback and returns the wrapper's
`r0`, so a refused frame is byte-for-byte the retail frame. Guards:

1. both resource words non-zero (the lifecycle word is OPTIONAL: zero means no closing
   animation, which is retail's own end state);
2. `page+0x0E` (the box surface's first tile) `>= 2`, UNsigned below, so tile 2 IS
   valid (the first even tile after a staging base of 1) and tiles 0/1 are retail art.
   This comparison was `bls` (<=) and silently handed every frame to the retail body,
   i.e. to the retained native BG font; root caught it in a real mid-node capture;
3. `ctx[+0x0A]` (flush base tile) non-zero and below that tile, otherwise the
   staged address would be meaningless;
4. `page tile + 320 <= ctx[+0x02]`, the tile cursor must have been advanced past
   the whole box surface, which is what proves the span is real and inside the
   flushed range (this is the guard that replaces the withdrawn "tile 88 free slab"
   model);
5. `page+0x14` inside the ROM window `0x08000000..0x087FFFFF`.

Stack: `push {r4-r7,lr}` (20 B) plus a 76-byte frame, so `sp` stays 8-aligned at
every BL and at the retail call boundary. No helper pushes an odd number of words.

## 6. Surface, staging lifetime and geometry

The box payload stages the donor box surface once per page through the engine's own
EWRAM staging cursor: pad (32 B when the cursor is odd), then 10,240 B as three 1D
8bpp strips (64x64, 64x64, 32x64 = 320 32-byte units). It records the first tile in
`page+0x0E` and advances `ctx[+0x02]` to `tile + 320`. The engine's flush
`0x08002896` copies `ctx[+0x04] - 0x0200B024` bytes to `0x06010000 + ctx[+0x0A]*32`
every frame, and the per-frame order is draw `+0x08`, flush `+0x18`, update `+0x1C`
; so a glyph inked at `+0x1C` is on screen the next frame, which is also exactly the
donor's one-frame reveal lag. Staging persists until the next rebuild; the span ends
at the next page build, which is why the payload never accumulates anything.

Geometry (donor default placement, E's run-bf-present-01): box strips at x
72/136/200, y 88; portrait x 8, y 88; text content origin (box x + 8, box y + 3) =
(80, 91); lines at pitch 14, ink rows 3..60 of the 64-row surface, columns 8..151.

The whole staged extent for a dialogue page is pad (0/32) + 10,240 (box) + portrait
4,096 (lane B) = 14,336..14,368 B from `0x0200B024`, i.e. it ends at or below
`0x0200E844`. No second surface exists.

## 7. Checks performed, and what they do not prove

`tools/check_text.py` (exit 0), against the canonical images, the approved dialogue
and the assembled payload:

* the font resource is the donor range, its digest matches, and it is self-consistent
  **without** the descriptor: 224 contiguous records from the table end, walk ends
  exactly at 3,598 B, codes `0x00..0x1F` empty;
* the wrap model reproduces lane C's published widths for all seven nodes exactly
  (`105/128/21`, `130/43`, `45`, `139/33`, `120/137/141`, `143/128/138/25`, `53`),
  every node fits one 4-line page, and no line exceeds 144 px;
* every ink pixel of every approved line maps to the same byte in the 10,240-byte
  surface by two independent derivations (framebuffer-then-tiles versus the payload's
  strip formula), and stays inside x <= 151, y <= 60;
* the payload's three fixup words are the last 12 bytes and zero; every literal-pool load is
  in the documented set (`page`, `ctx`, staging base, the two input halfwords, the ROM
  window bounds, `0x08009329`, `0x080051B5`, and the constants 320 / 1,280 / 144 / 12);
  every BL target lies inside the payload;
* all four declared seams exist exactly once in the canonical image and their
  canonical words resolve to the retail routines this derivation used
  (`0xEF44 -> 0x08005393`, `0xEF30 -> 0x08005381`, `0x11490 -> 0x08005119`,
  `0x11480 -> 0x08005109`), and the retail bodies open with the expected pushes.

**Not proved by any of this:** that a glyph appears, that a page turns, that the game
runs. Execution is E's gate.

## 8. Deviations

Departure from the donor: `text.s` | the donor's wide-glyph class reads columns at
`wide_base + 2*wide_advance*(code-0x100)` | advances 12 and draws nothing | the
donor's `wide_base` is 0, no dialogue unit at or above `0xFF` is observed, and the
shipped 3,598-byte resource holds no wide columns, so the donor path itself would
read ordinary table bytes as ink; drawing nothing is the only bounded behaviour and
the class is unobservable in retail.

Departure from the donor: `text.s` | the retail page turn refills the BG map and redraws the
9-slice through `0x080051B5` | the payload restores the box surface and does not
touch the BG map | the glyphs are not in the BG map, and the map is not ours to
write (`+0x10` is the scene's destination pointer); `bf-box-window` clears the retail
window entries every frame anyway.

Departure from the donor: `text.s` | `page+0x18` holds retail's remaining-line budget | left to the
retail install, unused | the 4-line cap comes from the donor layout constant and the
layout is recomputed per frame, so a stored budget would duplicate state that can go
stale; the field keeps the value retail's own install computes.

## 8b. Conversation lifecycle: the closing animation (session 7)

When a stage's string ends, the payload looks the live pointer up in the ROM plan the
SDK derives from the image's own record graph (`stage_final`, closed range match,
unique or refuse). If the plan marks the stage as the conversation's FINAL text stage,
the payload arms an 8-frame collapse in the upper byte of `page+0x20` - bit 0 keeps
retail's page-done meaning - and returns 0. Each frame advances the phase by one with
no input read; `bf_box_window` writes that phase's reverse ramp row so the collapse is
identical to the donor's measured close. At phase 8 the 2048 step has been flushed for
one whole frame and only then is the pointer cleared and 1 returned. It has to happen
inside this payload: the node's teardown frees the dialogue slot, rebuilds the shadow
OAM and flushes as soon as the state exits, and the installer `0x0800930A` zeroes the
whole word at the next stage install, so the phase is node-local and cannot outlive
its stage. No new RAM, no new page byte, no graph write, no blocking frame barrier.

## 9. Not measured (explicit)

No emulator run in this lane. Not measured: any on-screen glyph or page, the reveal
cadence on hardware, whether the staged span survives every page build, whether the
flush covers the inked bytes in practice, the OBJ/BG priority result on screen, the
palette index 2 colour after B's bank load, the box art itself, page-turn latency,
the animation (E owns the affine matrix proof; nothing affine is shipped here), and
whether the retail driver's node advance fires exactly as it does today.

## 10. Harvest

Tools: `tools/check_text.py` (font/layout/raster/payload/seam checks),
`assemble-box.ps1` (assembles box.s + text.s, splits payloads, asserts a 4-byte boundary for every split entry and fixup, asserts zero fixup words and no unresolved ELF relocation).
Knowledge: the composer's space-overflow break rule; the page object's field
ownership and the wrapper's return contract; the box surface as the text surface.
Pitfalls: (P1) a font resource "descriptor pointer" that is the resource base plus a
constant invites reading past the allocation; consume the table directly;
(P2) a wrap model that breaks at the *previous* space on a space overflow gets
node 5 wrong by 22 px, and the donor's `stm r3!, {r6, r7}` at `0x0803DEE8` decides it;
(P3) an 8bpp OBJ strip is 64 bytes per 8x8 tile and 512 bytes per 8-row band, so
reusing the 4bpp (32 B) strides halves the address and lands every glyph in the wrong
tile row.
