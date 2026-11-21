# Webfoot SDK overview

This page is for developers and ROM hackers. It describes the command-line SDK
under `tools/webfoot/`, the per-game support level and the research behind it.
To make a game with the DragonByte Z application, read the
[repository README](../README.md) and the [user guide](creator.md) instead.

Commands on this page run from a source checkout; [INSTALL.md](../INSTALL.md)
sets one up.

## What the SDK can edit

The **existing SDK** already provides project extraction, validation, new-image
builds, provenance manifests and BPS patch export. Its broadest implemented
authoring support is currently **Buu's Fury**. That implementation history does
not change the new application's LOG1-first priority.

For supported Buu's Fury structures, existing tools can render and edit map
layouts, author bounded map identities, add or move supported objects and warps,
edit mapped dialogue and relocate longer text, attach supported scripted behavior,
import sprite graphics or author donor-based sprite definitions, and claim one of
the sixteen enemy type rows the base game never names with a copy of a donor
record whose statistics can then be set.

A project enemy type lives in `enemies/types.toml`: the type's name, the row it
was claimed on, the retail row it was copied from, the bytes it was claimed with,
and only the statistics that differ from the donor's. A build writes the claimed
row and nothing else in the type table, and a project without the file builds
unchanged. Donors are limited to the 89 types of the family whose defeat the base
game runs normally;
[project enemy types](research/ENEMY_TYPES.md) records the format, the
identity rules, the sixteen-row pool and how it was measured.

An enemy can then be placed on a map from the same object document a project
already uses for characters: `maps/objects.toml` carries its `type` (a project
type by name or a base-game type by row), its position, the sprite the base game
draws it with, and the rule it appears by - always, when a story flag is set, or
while one is clear. The record is written in the retail format and, with the map's
object array, placed above 8 MiB by the allocator. Moving, duplicating and
removing an added enemy are project edits; a placement the base game made is not
editable. Validation refuses a map that would build more than 23 objects when it
loads, which is the largest load the base game itself uses, and states that the
number is the project's conservative policy rather than a count the engine
enforces. An added enemy may also name a story flag it sets when defeated: the
build points the record's descriptor at a node holding the engine's own script entry
and a one-step set-flag script, both above 8 MiB, for the 89-type family only;
[enemy placements](research/ENEMY_PLACEMENT.md) records the document, the
record layout, the condition word encoding, the defeat link and the census.

`webfoot map transitions <rom> [map:NNNN]` prints the transition records a map's
own array holds, with each record's destination map, trigger region and file
offset; the typed-slot answer `webfoot map connections` is a separate, narrower
corpus and is not a per-map door list.

These operations have different bounds and evidence levels. Some are demonstrated
in the retail engine; others have application or headless build evidence only.
The [capability registry](capability-registry.md) records those distinctions;
[Workbench usage](workbench.md) explains the older editor workflow.

A project can also declare one Legacy of Goku dialogue scene and rewrite that
scene's lines from the command line: `webfoot scene show` prints the declared
scene and its authored text, `webfoot scene set-text` writes one node's text, and
`validate` then `build` accept each line at its own slot's measured capacity or
refuse it rather than relocate it. [Project format](project-format.md)
records that route and its bounds. The route resolves against the packaged ROM
profile catalogue, so it is available from an installed package as well as from
a checkout.

The [LOG1 character runtime build](sprite-runtime.md) combines the approved
Goku, Super Saiyan Goku, Roshi and LOG2 Krillin replacements with the existing
Buu's Fury dialogue presentation. It uses exact per-piece palettes, retains all
22 approved native fallback rows, and emits a sixteen-MiB candidate through the
SDK's staged writer with allocation and change provenance. Selected mGBA tests
cover combat (ki blasts in all four directions), dialogue open, advance and close with the sprites on screen (both scripted dialogue that opens without a button press and dialogue opened with A), damage tint, walking palettes, flight/landing and the complete controlled transformation;
natural story playback and broader gameplay verification remain outstanding.
The candidate also replaces the player's ki use, passive ki regeneration and
melee/energy damage with Buu's Fury math (no held orb); Buu's Fury progression and
enemy statistical profiles are not integrated, and the player's Buu's Fury stats stay fixed.

The reusable import validator remains available as
`python -m tools.webfoot.sprite_import config/sprite-imports/goku-base.json
--donor-rom <path> --target-rom <path>`. It reads the donor in place, converts
frames into target cells and four-bit tiles, and reports FITS, DOES NOT FIT or
UNKNOWN for the resources its contract can establish. A whole donor library can
still fail that contract even when the approved runtime subset fits: four
unselected Super Saiyan rows share one frame that exceeds a bank within a tile.
The runtime preserves the approved native fallback for that state. No colour
trim is applied. Tile order, local palette indices, donor anchors and mirrored
offsets are retained by the piece adapter.

The runtime transformation enters through state nine's absolute dispatch words
and preserves the eighty-update window. A shared Thumb branch encoder rejects
unreachable calls outside the ARMv4T four-MiB range. The bank helper returns an
unshifted index because the retail continuation places it in the object attribute.

## Support by game

| Game | Current SDK support, not future application priority |
| --- | --- |
| **The Legacy of Goku** | Exact ROM identification and 18 script families that load and round-trip losslessly. Opcode effects and player-visible authored behavior are not established. Full native authoring is a goal. |
| **The Legacy of Goku II** | Partial support: enemy HP editing, limited non-relocatable text and static script inspection, plus an authored-image route. A 16 MiB expansion has runtime evidence; this does not establish full content-authoring support. |
| **Buu's Fury** | Broadest implemented authoring path, bounded by the verified profile, content form and individual capability evidence. Other recognized images do not inherit that support. |

See [ROM profiles](rom-profiles.md) and [verified SDK state](PROJECT_STATE.md).
A matching title or GBA header alone does not establish compatibility.

## Reverse engineering and recompilation

Byte-exact reconstruction checks whether an assembly-and-data build reproduces
the original image. It provides a baseline for understanding engine behavior and
original formats before changing them. The disassembly builds still depend on
your own ROM for generated content and remaining binary slices; byte identity
does not mean every byte has a semantic explanation.

**Assembly reconstruction is not matching C decompilation.** LOG1 and LOG2 build
without game C source; Buu's Fury remains predominantly assembly with a few small
C files. None of these repositories claims fully recovered original C source.

Static recompilation is an **additional research direction**. The disassembly
projects include recompiler-input tooling, but that is not a finished native
trilogy port. Reconstructing a ROM, authoring new GBA content and validating a
native runtime are different milestones.

## Runtime builds and bounded emulator runs

The Legacy of Goku pause page can be built as a four-tab ring (Status, Options,
Items, Quests) with the donor game's own panel art, composed on top of the merged
sprite, dialogue and combat build. Items lists the inventory by the game's own item
names and counts, Quests lists completed quests by name, and opening and closing
the page fades without a white frame. The Options tab ends in a Save Game row that
calls the game's own save routine. The build assembles its payload sources itself, so it
runs from a fresh clone given the private ROM inputs. See `tools/webfoot/pause_menu.py` and
`docs/runtime-capture.md` for the governed runtime evidence path.

A bounded emulator run keeps its savegames and its savestates in its own run
directory: `tools/runtime/start_dbz002b_session.ps1` forces both paths into the run
and records them in its `inputs.json`, so a quicksave cannot land outside it even on
a machine with a configured global savestate location.

## Developer documentation

- [Documentation index](README.md): SDK usage, architecture, formats and history.
- [Development policy](DEVELOPMENT.md), [review gate](REVIEW.md) and [ROM safety](ROM_SAFETY.md).
- [Project format](project-format.md), [architecture](architecture.md) and [testing](testing.md).
- Focused test runs: `scripts/rom-focused-check.ps1` runs the files in `config/rom-dependent-tests.txt`, the tests that need the game image, against a private copy of it, and `scripts/pre-merge-check.ps1` asks for that run when a change touches one of them.
- Before a push: `scripts/pre-push-gate.ps1` runs the four repository meta test files and `python -m tools.quality.architecture`, and records a pass for the commit under the git directory, so pushing the same commit again skips the run. Given the pushed commit ids, it refuses any commit that has no recorded pass and is not the clean checked-out commit. The ids are bare arguments; the interpreter is named with `-Python <path>`.
- [Runtime evidence](skills/mgba-runtime.md): acceptance and runtime evidence runs observe the game through the product's own unmodified trace script, loaded by a `dofile` wrapper.
- [SDK roadmap](ROADMAP_TO_1_0.md) and [research evidence](research/README.md): existing toolkit milestones and technical bounds, not a completion claim for the new application.
- [The first authored scene project](research/FIRST_SCENE_PROJECT.md): the tracked project at `examples/first-scene`, copied to a folder of your own before editing, the commands run from the repository root with the quick start's `webfoot`, the artifact they build, a step-by-step walkthrough for playing it by hand and changing its line, the conversation's own script setting a save flag, the flag's writer scan, the re-layout its span forced, and the runtime rows that show the flag change, the box ending and the player leaving; [created maps](research/MAP_NEW_AUTHORING.md) now record a second donor measured end to end.
- [Conversation scripts](project-format.md): a dialogue record's own code block, authored in place within the room its conversation leaves.
- [The reference authoring fixture](research/FIRST_SCENE_PROJECT.md): the tracked project at `examples/first-scene` and `tests/integration/test_conversation_script_rom.py` are the SDK's regression fixture for dialogue, script and flag authoring, the scene is a tooling reference, not remake content, and the address census, the project model's frozen-container rule and its copy/pickle support now hold it.
