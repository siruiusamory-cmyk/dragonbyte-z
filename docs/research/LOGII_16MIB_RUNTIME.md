# Legacy of Goku II at 16 MiB: runtime evidence

LG2-068 / O1. This document records what was measured when a 16 MiB generated
expansion of the Legacy of Goku II canonical image was run on hardware emulation,
and - as importantly - what was not.

The claim under test was narrow and is stated here in the form it was proven:

> A 16 MiB derivative of the canonical LOG2 image boots to interactive gameplay,
> and the guest CPU performs a data read from an address above the canonical
> 8 MiB boundary.

Both halves were measured. Neither was inferred from static analysis.

## The images

| Image | Size | SHA-256 | Role |
|---|---|---|---|
| canonical | 8,388,608 | `6e6c370c…6ff75` | untouched source, never written |
| `build/o1-log2-16mib.gba` | 16,777,216 | `5F0B4526…CF7E` | clean expansion, 0xFF pad |
| `build/o1-log2-16mib-reloc.gba` | 16,777,216 | `B425F3CD…C602` | relocation derivative |

The clean image is the canonical bytes followed by 0xFF padding to 16 MiB. Its
canonical prefix is byte-identical to the source and its tail is uniformly 0xFF.
Generation is deterministic: two materialisations of the same declaration
produce the same digest. `tests/unit/test_log2_16mib_expansion.py` holds this
through the SDK's own route, `GeneratedImage.materialize`, so the assertion
fails if that route changes behaviour rather than merely re-proving that
concatenation is deterministic.

The canonical image was copied, never modified. Its digest was recorded before
and after every session and did not change.

## Evidence 1: the image boots to interactive gameplay

Driven through mGBA 0.10.5 (`5A3C98C2…F247`, Qt build, Lua scripting) by
`tools/runtime/o1_run_gameplay_route.ps1`, which loads
`tools/runtime/o1_clean_gameplay_route.lua` through the Scripting window.

Input uses the emulator's own API - `emu:setKeys`, `emu:addKey`,
`emu:clearKey` - and was confirmed reaching the console by reading `KEYINPUT`
(`0x04000130`): `0x037F` LEFT, `0x03DF` UP, `0x03EF` RIGHT, `0x03BF` DOWN.
Writes to `KEYINPUT` are **not** used and are not evidence: the register is
read-only hardware, reloaded from the pad every frame, so a debugger poke
proves nothing about input.

Frames are counted from the emulator's own `frame` callback, one increment per
frame boundary. `VCOUNT` is sampled alongside as a scanline counter (0-227) and
is **not** used as a frame count.

Measured over 5,520 frames on the clean image. The figures below are from one
named run, `build/o1-evidence/route-34408899352f400db6db511bd0cb292b`, produced
by the committed script; they are not a best-of across runs:

- boot -> title -> in-game overworld with the HUD drawn
- dialogue advancing character by character across sampled frames, so the engine
  is running rather than holding one composed frame
- dialogue cleared under driven A presses, then free movement
- 12 distinct player sprite positions during the walk phase, and 39 of the run's
  47 screenshots distinct by digest
- terrain, rock formations and NPC placement wholly different between frames
  4800 and 5400 - the player traversed the map

The sampled sprite is the first OAM entry outside the HUD corner, which is not a
stable identity across frames: it supports "the player moved", not a trajectory.
The qualitative result - an interactive in-game map under driven input - held in
every run; the exact position count is run-dependent, so it is attributed above
rather than stated as a property of the route.

Screenshots at `build/o1-evidence/route-*/shot-*.png`. The ROM digest was
unchanged after the run.

## Evidence 2: the guest CPU reads the expanded region

The proof channel is the GDB stub's read watchpoint (`Z3`) on the instrumented
probe build. It was validated before being trusted, and the validation found a
property that would otherwise have produced a false claim:

| Control | Target | Result |
|---|---|---|
| `Z0` code breakpoint | ROM entry `0x080000C0` | fires, `S05k` |
| `Z3` on an instruction **fetch** | `0x080000C0` | **does not fire** |
| `Z3` on a genuine **data** load | `0x08000134` | fires, `T05rwatch:08000134;` |
| `Z3` at the expanded region, clean image | `0x08800000` | silent for the whole run |

`Z3` observes data reads specifically, not instruction fetches. Had the sentinel
been armed without this check, a silent channel and a real negative would have
been indistinguishable.

### The relocated object

Rather than insert an artificial load, an existing read-only data object was
moved and its existing pointer repointed - the object's contents and the code
that reads it are unchanged.

The object at `0x081D4EE0` is 12 bytes of static data that the boot path
dereferences at `+0x0`, `+0x4` and `+0x8`. Its address is held in exactly one
literal word, at `0x08000204`, and that value occurs exactly once in the whole
8 MiB image - one literal, one raw word - so repointing it affects nothing else.

Before relocation, on the clean image:

| Address | stop PC | instruction | value retrieved |
|---|---|---|---|
| `0x081D4EE0` | `0x080001D2` | `LDR r0,[r4,#0]` | `0x030026C8` |
| `0x081D4EE4` | `0x080001C6` | `LDR r0,[r4,#4]` | `0x03000E88` |
| `0x081D4EE8` | `0x080001CC` | `LDR r0,[r4,#8]` | `0x03001120` |

with `r4 = 0x081D4EE0` at every stop.

`tools/runtime/o1_build_relocation.py` copies those 12 bytes to `0x08800000`
and rewrites the literal. It refuses unless the destination is 0xFF padding, the
literal holds the expected value, and the only prefix bytes that change lie
inside that one literal word. The resulting diff is **3 bytes** in the prefix
(the literal's fourth byte is `0x08` in both addresses) and **12 bytes** in the
tail.

After relocation:

| Address | stop PC | value retrieved | `r4` |
|---|---|---|---|
| `0x08800000` | `0x080001D2` | `0x030026C8` | `0x08800000` |
| `0x08800004` | `0x080001C6` | `0x03000E88` | `0x08800000` |
| `0x08800008` | `0x080001CC` | `0x03001120` | `0x08800000` |

The same instructions, at the same PCs, retrieve the same values from the
expanded region. `0x081D4EE0` no longer fires: the read genuinely moved.

`tools/runtime/o1_expanded_read_probe.py` records this result. It runs its
positive control in its own emulator session before the watch run and returns
exit 3 without reporting a result if that control does not fire, so a hit can
never be reported from an unvalidated channel. Two artifacts are committed:

| Artifact | Image | Watch | Result |
|---|---|---|---|
| `docs/research/o1-evidence/clean-no-hit.json` | clean | `0x08800000` | control fired, watch silent |
| `docs/research/o1-evidence/reloc-expanded-hit.json` | relocated | `0x08800000` | control fired, `T05rwatch:08800000;` at PC `0x080001D2`, `r4 = 0x08800000` |

Both are committed, so the result is auditable without re-running the emulator.
The route CSV for the named gameplay run is committed alongside them as
`docs/research/o1-evidence/route-34408899.csv`. They carry digests, addresses
and register state only - no ROM bytes.

The negative is as load-bearing as the positive: the same probe, the same
address, the only difference being the 15 relocated bytes.

The relocated image was then run through the same gameplay route and reached the
same in-game state, so the relocation does not break the engine.

## Limits of this evidence

- **One emulator.** All runtime evidence is from mGBA 0.10.5, in two builds: the
  instrumented SDL probe for GDB and the pinned Qt build for Lua. No second
  emulator and no hardware were used, so this is emulator behaviour, not a
  statement about every GBA implementation.
- **One address.** A single expanded address was proven addressable, as scoped.
  This is not an address-range sweep and says nothing about the rest of the
  8-16 MiB window.
- **No mapper claim.** The GBA cart bus addresses 32 MiB; nothing here
  establishes behaviour above 16 MiB or with any banking scheme.
- **The route is area-specific.** The gameplay route's inputs are tuned to the
  starting area and are not a general-purpose driver.
- **`IMAGE_SIZE` stays canonical-only.** It is the atlas scan window and asserts
  against the canonical length; a larger derivative does not change it.
- **The controls distinguish a data read from an instruction fetch, not a CPU
  read from every other bus master.** A `Z3` stop whose PC lands one instruction
  past a decoded `LDR` is what was measured; no control here rules out a DMA or
  prefetch as the agent of some other read.
- **The regeneration test runs on a synthetic canonical image.** It exercises the
  real `materialize` route, but reproducing the committed 16 MiB digest requires
  the private fixture and so is not a committed test.
