# LOG1 character runtime candidate

The runtime builder integrates the approved Goku, Super Saiyan Goku, Roshi and
LOG2 Krillin appearances into a new LOG1 image. Armoured Krillin uses the same
approved replacement appearance. The 22 approved fallback rows retain their
original LOG1 cells and colours. No artwork is trimmed or authored.

## Build

Use the canonical US images identified by these SHA-256 values:

| Image | SHA-256 |
| --- | --- |
| LOG1 | `3ba9919e26704b0f5fdc2bfabc7f7a0404c71413761d38abcd94224c3bd4b1b9` |
| Buu's Fury | `940ad5f01db4465b8877dfe739510cbf34f4ea3d390f3df13519808bc36f059e` |
| LOG2 | `6e6c370c339ec9171cb1956adf837a0d342a197f78964882ef46c3086656ff75` |

The tested compiler is devkitARM GCC 16.1.0. Assemble the existing authored
payloads before building from a clean checkout. These existing PowerShell
scripts require devkitARM at `C:/devkitPro/devkitARM`; `--toolchain-dir` controls
the subsequent runtime compilation. Wheel installations include the assembly
scripts under the installed `tools/webfoot/patchsource` directory and require
the approved manifests from the source checkout:


```powershell
& tools/webfoot/patchsource/log1-sprite-limits/assemble.ps1
& tools/webfoot/patchsource/log1-bf-presentation/assemble.ps1
& tools/webfoot/patchsource/log1-bf-presentation/assemble-box.ps1
python -m tools.webfoot.sprite_runtime --rom <log1.gba> --buu <buu.gba> --log2 <log2.gba> --output build/characters.gba --project build/characters-project --manifests config/sprite-imports --toolchain-dir <devkitARM/bin>
```

The output and project directory must be new. Inputs remain read-only. All
commercial asset data is generated inside the build project from the verified
inputs; none is supplied with the source. Keep generated projects and images
outside tracked source directories.

The builder copies its four runtime sources into the project, compiles twice
around the SDK allocator, and refuses a size or allocation change between
passes. It composes the existing dialogue presentation unchanged. The SDK's
validated, staged writer emits the image and its `.manifest.json`; the project
also receives `runtime-build.json` with compiler identity, source hashes and
linked symbols. The manifest records payload allocation, every changed span,
donor identities and expansion padding. The original eight MiB are retained
except for the declared runtime and presentation edits; new graphics storage
is appended in a sixteen MiB image.

## Runtime behavior

- Each donor piece keeps its exact pixels, anchor and flip. Palette planning
  first tries complete palettes; when they do not fit, it packs exact colours
  and draws transparent colour layers. Earlier objects' colours never move.
- Native objects, dialogue surfaces and damage tint retain their palette
  requirements. Imported objects also retain the native red flash and its
  expiry. Native fallback cells use their actual appearance palette.
- The bounded draw routine checks the tile window and OAM capacity before
  appending an object. A capacity refusal is counted; it cannot overwrite the
  next resource. Visibility and sorting use the full donor-piece union.
- Goku state 9 displays all eleven approved power-up frames within the original
  eighty-update window. Its second draw object uses a separate object clone;
  it consumes no additional slot in the native 96-actor pool. An exhausted
  palette registry can retain the actor's registered palette association while
  the renderer supplies the actual Super Saiyan palette. The original form and
  state transition still run.
- Player melee uses the donor's actual submitted attack rectangles and strict
  collision test. The original LOG1 hit reaction and damage calculation remain.
  The unrelated donor NPC proximity condition is not used as a melee hitbox.
- Ki flight uses the measured donor body-based muzzle, three-pixel movement,
  frame sequence, directional viewport exit and collision box. Early release
  waits for sixteen startup updates; native charging and resource spending
  continue only while held. Interruption checks reuse the native validation
  routine with zero added charge. The three native charge selections and LOG1
  damage calculation remain.

## Verification limits

Two clean builds with the tested compiler produce the same image and manifest.
The candidate SHA-256 is
`5cf700feb35c0ba1e5cf135bba1521d06c8bf84757b61ceed77708cfaaccd80d`.

Selected mGBA runs verify combat damage, projectile impact and cleanup, dialogue
presentation, and the complete controlled transformation. A transformation test
with all 96 actor slots occupied and all sixteen palette entries held still
finishes on update 80 without resource refusals. Hardware OAM, VRAM and palette
reconstruction verifies selected projectile frames, one donor damage flash and
restored native fallback pixels. These are selected scenarios, not full-game
coverage.

A key-only flight/landing run matches all 450 sampled player states, positions,
frames and ticks against retail, including 95 flying samples. A normal movement
and talk sequence opens Krillin dialogue; Roshi dialogue and all three imported
characters are visible together in the selected island scene. A separate combat
run peaks at nine OAM entries and 77 OBJ tiles within the guarded limits.

Natural story-trigger coverage and scene transitions, the complete
attack-effect inventory and final integrated review remain outstanding. Roshi
uses the approved structural slot fallback and explicitly assumed timing where
measurement is inconclusive. This candidate is not merge authorization.

## Integration review

An independent reviewer inspected the frozen builder, generated-asset path,
shared writer integration, runtime sources, packaging and address census.
Verdict: APPROVE WITH NON-BLOCKING NOTES. The missing prerequisite assembly
scripts were added to wheel package data and independently verified. The
reviewer independently passed 28 runtime/census unit tests and the canonical
two-build integration test, checked unchanged historical census anchors and
confirmed the four runtime sources match the reviewed runtime candidate.

Required readability, architecture, public-surface, public-release and built-site
gates pass. The architecture rule admits authored C only beneath the existing
patch-source directory; a positive and negative control protect that boundary.
The prerequisite Windows compiler path and external manifests remain documented
limitations. This review covers SDK integration; the gameplay gaps above remain.

The subsequent small-rectangle correction received independent APPROVE: native
cell size/shape bytes select hardware dimensions directly. The reviewer checked
all supported pairs against the explicit hardware table, passed 70 importer and
census tests, and reproduced 126 exact matches from retained hardware captures.
The canonical importer and two-build runtime integration group passed 22 tests.
Upward tail frames remain unobserved in that wall-limited scenario.
