# DragonByte Z / Webfoot SDK

An evolving reverse-engineering and ROM-hacking initiative for Webfoot's
**Dragon Ball Z GBA trilogy**: *The Legacy of Goku*, *The Legacy of Goku II*
and *Buu's Fury*. We are building the foundations to understand these games,
modify them and create new content for their original engines.

**The next-generation DragonByte Z application targets the original Legacy of
Goku first.** It is planned as a new application and independent codebase, not
a reskin, rename or wrapper around the older Webfoot Workbench. Visual and
source-level authoring are both part of that direction; they are not complete.

No ROM or game data is included. Supply your own legally obtained supported ROM.

[Use the existing SDK](INSTALL.md) | [Documentation](docs/README.md) |
[Contribute](CONTRIBUTING.md)

## Four repositories, distinct roles

| Repository | Role |
| --- | --- |
| **[DragonByte Z / Webfoot SDK](https://github.com/siruiusamory-cmyk/dragonbyte-z)** | This repository: the independent SDK foundation, existing editors and verified format evidence. It is not the finished next-generation application. |
| **[Legacy of Goku disassembly](https://github.com/siruiusamory-cmyk/legacyofgoku-disasm)** | LOG1 assembly reconstruction, original formats and byte-exact rebuilding. |
| **[Legacy of Goku II disassembly](https://github.com/siruiusamory-cmyk/legacyofgoku2-disasm)** | LOG2 assembly reconstruction, format research and rebuild tooling. |
| **[Buu's Fury disassembly](https://github.com/siruiusamory-cmyk/buusfury-disasm)** | Buu's Fury assembly reconstruction, recovered data structures and rebuild tooling. |

Webfoot SDK remains an independent technical foundation. The **older Webfoot
Workbench** is an existing SDK interface, not the design or codebase for the new
application. The supported application is the creator application in
`tools/creator/`, which `DragonByte Z.cmd` and the packaged `DragonByte Z.exe` start.
The earlier desktop implementation in `tools/dragonbyte/` is deprecated reference
code; the creator application reuses its Qt-free session and journal.
The disassemblies provide complementary game-specific evidence, not interchangeable
formats or a promise that one game's edits work in another.

## Project status

**Active development, pre-1.0.** Native LOG1 authoring comes first for the new
application. The broader **LOG1-REMAKE** objective remains a separate, later
milestone: authored LOG1 content running inside the retail LOG2/Buu's Fury engine.
That objective is **not a standalone remake**, and it is not already delivered.
The game scope is these three GBA titles only.

The approved application goals include:

- Visual and source-level editing of maps, scripts, graphics and audio.
- C/assembly hooks alongside structured content authoring.
- Donor-ROM imports, modified-ROM projects and patch composition.
- Multiple build variants, with integrated testing and debugging.

These are **development goals, not a shipped feature list**. Arbitrary modified
ROMs, patch stacks and cross-game imports are not currently promised as supported
SDK inputs. Compatibility, provenance and validation must be established for each
workflow. Existing SDK capability counts do not measure completion of this program.

## DragonByte Z creator application

The first creator-facing release does one complete loop without a terminal:
**Open, Edit, Save, Build, Play, Revise.** Start a project from your own retail
Buu's Fury ROM, edit the game's text, build a playable ROM into the project's
`build` folder and play it in mGBA. Every edit is one undo step, text the game
cannot store is refused as you type, unsaved edits survive a crash and are checked
before they are restored, a failed build
keeps the last good ROM, and the source ROM is only ever read.
Play starts the emulator you choose; no particular mGBA version is required.
A Library tab shows every map, character sprite and portrait with a picture and
search, takes your own names for them, and lists where each is known to be used.
A link the tools have not established is shown as "not known" rather than guessed.
A Maps tab makes a new map from one of the game's maps and edits it by pointing:
place pieces, draw tiles, resize layers, paint where the player can walk, and add or
remove doors between maps. Walls compile into the game's own collision format.
Adding or renaming a map never moves another map, so doors keep leading where they did.
A door is finished by clicking the arrival point on its destination map.
A Characters tool shows who stands on a map and moves, copies, restyles and removes
characters by pointing; what it cannot change yet is stated on the character itself.
A Dialogue tab rewords what the game's characters say and writes new conversations:
pages, portraits, line and page breaks, a preview that wraps and pages the words as the
game does, and a remembered flag that changes what a character says the next time.
Any character on a map can be given any conversation, or a copy of its own.
A line the game speaks in several conversations is reworded in the one being edited.
Choosing a conversation or a character does not reread the whole game each time.
Dialogue the game cannot show, or a flag that would clash with one the project
already uses, is refused before a ROM is made.
An Events tab builds what happens from steps, with no scripting: talking to a
character, entering or leaving a map, or walking into a region drawn on the map can
say lines, ask a two-way question, branch on a flag, an answer or gear held, set and
clear flags, give and take gear, and open or close a passage. A character can be
set to appear only while a flag is set. Flags are named and keep their place in the
save file for good. A Story view shows what sets and reads each flag, and Play with
trace lists the steps the running game really executed. Give item gives gear, which
the game lists under Equip; supplies, shops, battles and music are not authored yet.
[How to use it](docs/creator.md). [What was measured](docs/research/EVENTS.md).

## What you can edit

The **existing SDK** already provides project extraction, validation, new-image
builds, provenance manifests and BPS patch export. Its broadest implemented
authoring support is currently **Buu's Fury**. That implementation history does
not change the new application's LOG1-first priority.

For supported Buu's Fury structures, existing tools can render and edit map
layouts, author bounded map identities, add or move supported objects and warps,
edit mapped dialogue and relocate longer text, attach supported scripted behavior,
and import sprite graphics or author donor-based sprite definitions.

`webfoot map transitions <rom> [map:NNNN]` prints the transition records a map's
own array holds, with each record's destination map, trigger region and file
offset; the typed-slot answer `webfoot map connections` is a separate, narrower
corpus and is not a per-map door list.

These operations have different bounds and evidence levels. Some are demonstrated
in the retail engine; others have application or headless build evidence only.
The [capability registry](docs/capability-registry.md) records those distinctions;
[Workbench usage](docs/workbench.md) explains the older editor workflow.

A project can also declare one Legacy of Goku dialogue scene and rewrite that
scene's lines from the command line: `webfoot scene show` prints the declared
scene and its authored text, `webfoot scene set-text` writes one node's text, and
`validate` then `build` accept each line at its own slot's measured capacity or
refuse it rather than relocate it. [Project format](docs/project-format.md)
records that route and its bounds. The route resolves against the packaged ROM
profile catalogue, so it is available from an installed package as well as from
a checkout.

The [LOG1 character runtime build](docs/sprite-runtime.md) combines the approved
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

## Supported games and maturity

| Game | Current SDK support, not future application priority |
| --- | --- |
| **The Legacy of Goku** | Exact ROM identification and 18 script families that load and round-trip losslessly. Opcode effects and player-visible authored behavior are not established. Full native authoring is a goal. |
| **The Legacy of Goku II** | Partial support: enemy HP editing, limited non-relocatable text and static script inspection, plus an authored-image route. A 16 MiB expansion has runtime evidence; this does not establish full content-authoring support. |
| **Buu's Fury** | Broadest implemented authoring path, bounded by the verified profile, content form and individual capability evidence. Other recognized images do not inherit that support. |

See [ROM profiles](docs/rom-profiles.md) and [verified SDK state](docs/PROJECT_STATE.md).
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

## Windows quick start

For the **existing SDK**, install Git and [uv](https://docs.astral.sh/uv/), then run
in PowerShell. Setup obtains Python 3.12 and installs the locked dependencies:

```powershell
git clone https://github.com/siruiusamory-cmyk/dragonbyte-z.git
cd dragonbyte-z
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1 -SkipUpstreams
.\.venv\Scripts\webfoot.exe --help
```

[Installation and existing tool launch instructions](INSTALL.md) are maintained
separately. They install the current tools, not the planned independent application.
The [newcomer walkthrough](docs/newcomer.md) distinguishes executed checks from
workflows that require a private ROM. Disassembly builds have their own prerequisites
and installation guides in each linked repository.

## Developer documentation

- [Documentation index](docs/README.md): SDK usage, architecture, formats and history.
- [Development policy](docs/DEVELOPMENT.md), [review gate](docs/REVIEW.md) and [ROM safety](docs/ROM_SAFETY.md).
- [Project format](docs/project-format.md), [architecture](docs/architecture.md) and [testing](docs/testing.md).
- [SDK roadmap](docs/ROADMAP_TO_1_0.md) and [research evidence](docs/research/README.md): existing toolkit milestones and technical bounds, not a completion claim for the new application.
- [The first authored scene project](docs/research/FIRST_SCENE_PROJECT.md): the tracked project at `examples/first-scene`, copied to a folder of your own before editing, the commands run from the repository root with the quick start's `webfoot`, the artifact they build, a step-by-step walkthrough for playing it by hand and changing its line, the conversation's own script setting a save flag, the flag's writer scan, the re-layout its span forced, and the runtime rows that show the flag change, the box ending and the player leaving; [created maps](docs/research/MAP_NEW_AUTHORING.md) now record a second donor measured end to end.
- [Conversation scripts](docs/project-format.md): a dialogue record's own code block, authored in place within the room its conversation leaves.
- [The reference authoring fixture](docs/research/FIRST_SCENE_PROJECT.md): the tracked project at `examples/first-scene` and `tests/integration/test_conversation_script_rom.py` are the SDK's regression fixture for dialogue, script and flag authoring, the scene is a tooling reference, not remake content, and the address census, the project model's frozen-container rule and its copy/pickle support now hold it.

## Limits and ROM ownership

The canonical source image stays **read-only**. Exact profile identity is checked
before profile-specific access; builds write new outputs, and reopening a modified
image requires valid provenance. These requirements remain mandatory. Planned
modified-ROM workflows do not waive today's input or write protections.

Do not publish ROMs, extracted game assets, saves, states or memory dumps. Share
patches rather than commercial images; the verified editor captures above are the
[documented screenshot exception](docs/ROM_SAFETY.md), not permission to distribute
assets. Keep backups of projects and outputs; formats may change before 1.0.

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

## License

Original code here is [MPL-2.0](LICENSE). Third-party material keeps its own terms;
see [third-party notices](THIRD-PARTY-NOTICES.md) and each disassembly repository's
license and notices. No commercial game content is supplied or relicensed.
