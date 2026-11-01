# Legacy of Goku II: the authored-image route, supported operations and limits

LG2-068 lane D, on `ticket/log2-authored-route-001`. This document states what the
shared authored-image route already does for the Legacy of Goku II profile
`legacy_of_goku_ii_usa_rev0_204142e1` (game code ALFE, crc32 `204142e1`, sha256
`6e6c370c…ff75`), what it refuses, and what none of it establishes. It adds no
capability: every statement below is a measurement of code that already exists at
`da0842cf`.

## 0. The declared capacity region, and what declaring it does and does not do

Owner Cale approved a narrowly scoped capacity declaration on 2026-10-31, after the
independent adversarial review returned CONFIRM. The LOG2 profile now declares
exactly one free region:

```
file_offset 0x007fea01   size 384   end 0x007feb81   status CONFIRMED
```

The nearest candidate targets are `0x007fe601` and `0x007fef81`, 2,432 bytes apart,
and the required 1,024-byte clearance at each end leaves these 384 bytes. The licence
is therefore `distance - 2 * margin`, and it is **zero at a 1,216-byte margin**: this
declaration depends on a policy constant, not on a property of the ROM. The
candidate-free interior between those two targets is 2,431 bytes, one fewer, because
neither target byte is itself free. The tail's other 6,472 `FF` bytes are not declared, and the
897-byte window at `0x007ffc7f` is not declared either, because its clearance is
one-sided, bounded above only by the end of the image.

Of the seven checks in the single-window proof, only three are capable of failing for
this window - `fill`, `candidate_target`, `candidate_source`. `margin` passes by
construction wherever the gap is wide enough, `bounds` is a guard, and
`known_inbound` and `known_overlap` are structurally inert here because the highest
modelled owned byte is `0x006fd4d8` and the highest reference target is `0x006fd424`,
both over a megabyte below the tail. Citing "seven checks pass" for a tail window
overstates the evidence; cite the three that can fail.

**Declaring a free region does not grant a relocation capability.** `free_regions` is
not a member of the `Capability` enum, so `capability.require` never gates on it; it
is consumed directly by `allocation.allocate` and by `text._writable_regions`. The two
gates are independent, and measured after the declaration:

| Gate | LOG2 | Buu's Fury |
| --- | --- | --- |
| `free_regions` | 1 region, 384 B | 1 region, 256 B |
| `text_strings.relocatable` | **False** | **True** |
| declared capabilities | `text_strings`, `scripts` | all eight |

So `text._writable_regions` now returns `(0x7fea01, 384)` for LOG2, while LOG2 text
relocation stays refused by the separate stored `relocatable: False` field. A caller
wanting LOG2 text relocation needs its own evidence and its own ticket; this
declaration supplies neither, by construction rather than by convention.

## 1. The route works for LOG2 even without a declaration

The first thing measured was the route itself, before any change. A single
one-byte declared change at file offset `0x007FEA01` (the first byte of the
384-byte window lane C verified) was saved through
`tools.webfoot.authored_image.save_authored_image` against the canonical image:

```text
profile            = legacy_of_goku_ii_usa_rev0_204142e1
profile.free_regions = ()
profile.generated_expansion = None
canonical sha256   = 6e6c370c339ec9171cb1956adf837a0d342a197f78964882ef46c3086656ff75
canonical matches profile = True
change             = 0x007FEA01 ff -> 00
RESULT: SAVED
output_sha256      = 0675d1d15370d2e006d657e26dd7753f5fc0a845d81c25b29dc6c86afdff0464
output_size        = 8388608
changed_offsets    = ['0x7fea01']
staging left behind= False / False
reopen profile_id  = legacy_of_goku_ii_usa_rev0_204142e1
reconstructed sha256 = 6e6c370c339ec9171cb1956adf837a0d342a197f78964882ef46c3086656ff75
reconstructed equals canonical = True
canonical sha256 after = 6e6c370c339ec9171cb1956adf837a0d342a197f78964882ef46c3086656ff75
```

**VERIFIED:** the shared transaction saves, publishes its provenance document,
reopens through `verify_authored_image`, and reconstructs the canonical image from
the derivative alone - for LOG2, with no declared free region and no
`generated_expansion`. `tools/webfoot/authored_image.py`,
`tools/webfoot/write.py`, `tools/webfoot/allocation.py` and
`tools/webfoot/capability.py` name no game at all in executable code: measured
occurrences of `buu|legacy_of_goku|log2|logii|alfe|alge|bg3e|buue` are 0, 0, 0 and
0 respectively, and `capability.py`'s single hit is the docstring sentence that
records the game constant's removal.

**VERIFIED:** the route's licence to write is the caller's declared change plus the
canonical digest, not a `free_regions` entry. `allocation.allocate` is not on the
route's path; nothing in `save_authored_image` consults it.

## 2. What is supported

| Operation | Status | Evidence |
| --- | --- | --- |
| Save a fixed-width, in-bounds overwrite into the canonical LOG2 image, with provenance | SUPPORTED, VERIFIED | §1 and `tests/integration/test_authored_image_lg2_rom.py` |
| Reopen an emitted derivative and reconstruct the canonical image from it plus its manifest | SUPPORTED, VERIFIED | `authored_image.verify_authored_image`, `_reconstruct_canonical`; same test module |
| Deterministic output: the same inputs produce one image and one digest | SUPPORTED, VERIFIED | `tests/unit/test_authored_image_lg2_route.py::test_two_independent_runs_produce_one_image_and_one_digest` |
| Refusal of a non-canonical source, a canonical destination, and every alias of the source | SUPPORTED, VERIFIED | `tests/unit/test_authored_image.py` and `test_rom_destination_safety.py`, cited in §4 |
| Read LOG2 `text_strings` (260 pointers at `0x080E2840`, pool `0x080E2C50`) and `scripts` (`0x086D68DC`) | SUPPORTED (declared capability) | `tools/webfoot/data/roms.yaml`, LOG2 profile `tables:`; `capability.require` |

The two declared capabilities are exactly `text_strings` and `scripts`; that set is
asserted by `tests/unit/test_capability.py` and re-asserted in the new route test.

## 3. What is refused, and by which mechanism

| Refused operation | Mechanism | Message |
| --- | --- | --- |
| A structure LOG2 does not declare (map entries, enemy stats, character base stats, placement types, actor sprites, appearances) | `capability.require`, declaration branch (`capability.py`) | `profile 'legacy_of_goku_ii_usa_rev0_204142e1' does not declare map_entries; map access is unavailable for this ROM` |
| A profile file that moves a declared extent while keeping the hashes | `capability.require`, packaged-contract branch | `supplied profile … metadata conflicts with the packaged contract; refusing … against unverified extents` |
| Any allocation for LOG2 outside the 384-byte declared window, or larger than it | `allocation.allocate` → `_place` returns None → `InsufficientSpaceError` | `insufficient declared free space for <anchor> (<n> bytes, alignment <a>, <kind>, <addressability>)` |
| A write whose `old` bytes are not what the image holds, a write past EOF, an overlapping pair | `write.plan_changes` → `ChangeValidationError` / `OverlappingChangeError`, re-wrapped by the transaction | `… this plan was computed against a different image` / `… would write the same bytes` |
| A source that is not the canonical image, or a base that is not | `save_authored_image` digest re-proof | `the source ROM is not the canonical image this editor builds from` |
| A destination that already holds the canonical image | `refuse_canonical_destination` | `refusing to save: the destination <path> is a copy of the canonical ROM, so it is not replaced; choose another name` |
| The source named as the output, the manifest, or either staging path | `refuse_source_alias` | `refusing to save: the <label> path is the source ROM (<path>); choose another name` |
| A destination inside a protected ROM input directory, or a hardlink/junction to a protected ROM | `destination.refuse_rom_destination` | `refusing to write <target>: … protected ROM is read-only on every write path` |

`allocation.withhold` is not a refusal mechanism: subtraction only, it never raises.
For LOG2 it subtracts whatever is taken from the one declared 384-byte window.

**VERIFIED:** none of these refusals is LOG2-specific code. Each is a shared rule
that LOG2 reaches by not declaring something.

## 4. Failure safety

The transaction emits at temporary siblings, verifies there, and only then publishes
by `os.replace`, cleaning the staging names on every path. The five failures -
failed emit, failed verification, failed image publish, failed manifest publish, and
a plan that is not applicable - are each pinned by a test in
`tests/unit/test_authored_image.py`; the image-publish case against an existing
regular file is the one the long-standing suite did not cover and is added here
(`test_a_failed_image_publish_leaves_the_existing_destination_unchanged`).

## 5. Limitations - what this route does NOT establish

1. **A declared region is a licence to allocate inside the canonical image. It is
   not evidence that the engine tolerates a larger image.** The window below is
   384 bytes of the retail image; nothing here shows the engine reading a byte above
   canonical EOF, following a moved table or a repointed pointer, or accepting a
   16 MiB image. No runtime evidence was produced for this ticket, by contract.
2. **One `free_regions` entry is declared for LOG2, and only one.** The owner
   approved the 384-byte window in §0 on 2026-10-31 after independent review; nothing
   else in the tail is declared, and the capacity question itself belongs to the lanes
   that measured it. Section 1 below is a dated transcript of the route working
   *before* that declaration existed, kept as history.
3. **The 384 bytes are lane C's verdict, not this lane's measurement.** This lane
   re-measured only that the window is uniform `0xFF` fill in the canonical image
   (`tests/integration/test_authored_image_lg2_rom.py::test_the_window_is_uniform_fill_in_the_canonical_image`).
   The region is stated once as `WINDOW_FILE_OFFSET`/`WINDOW_SIZE` in each test
   module so a revised verdict changes one pair of constants.
4. **The route does not make a semantic edit legal.** It carries whatever the domain
   hands it. LOG2 has no domain caller: the one in-tree caller of
   `save_authored_image`, `tools/webfoot/map_layout_edit.py`, is pinned to the
   packaged Buu's Fury profile at three points, so a LOG2 image is refused there.
   LOG2's own `text_strings` writes go through `write.plan_changes` directly and are
   not relocatable (`relocatable: false` in the profile).
5. **A derivative is only as trustworthy as its manifest.** Verification accepts an
   image only when undoing its declared changes reproduces the canonical digest, so
   an undeclared byte change inside the canonical span is always refused; but the
   manifest itself is not signed, and a derivative whose manifest is lost refuses to
   reopen.
6. **Nothing here says an authored byte is read by the game.** Static evidence only.

## 6. Where the evidence lives

| Claim | Test |
| --- | --- |
| Route saves, reopens, reconstructs (LOG2 profile, synthetic image) | `tests/unit/test_authored_image_lg2_route.py` |
| Same, on the canonical image | `tests/integration/test_authored_image_lg2_rom.py` (set `LOG2_CANONICAL_ROM`) |
| Reproducible output | both modules, the two-run tests |
| Failure safety | `test_authored_image.py`, plus the image-publish test above |
| Unsupported write refused | `test_authored_image_lg2_route.py::test_a_capability_the_log2_profile_does_not_declare_is_refused_by_name` |
| Unverified allocation region refused | `test_authored_image_lg2_route.py::test_an_allocation_outside_any_declared_log2_region_is_refused` |
| Canonical identity protections | `test_authored_image.py::test_the_source_may_not_be_any_path_the_save_touches`, `::test_an_existing_destination_that_is_the_canonical_image_is_refused`, `::test_a_missing_source_or_an_unknown_profile_is_refused`, `test_rom_destination_safety.py` |
