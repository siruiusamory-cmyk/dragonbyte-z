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
application. This repository also contains an earlier desktop implementation in
`tools/dragonbyte/`; its name and launcher do not make it the new independent app.
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

## What you can edit

The **existing SDK** already provides project extraction, validation, new-image
builds, provenance manifests and BPS patch export. Its broadest implemented
authoring support is currently **Buu's Fury**. That implementation history does
not change the new application's LOG1-first priority.

For supported Buu's Fury structures, existing tools can render and edit map
layouts, author bounded map identities, add or move supported objects and warps,
edit mapped dialogue and relocate longer text, attach supported scripted behavior,
and import sprite graphics or author donor-based sprite definitions.

These operations have different bounds and evidence levels. Some are demonstrated
in the retail engine; others have application or headless build evidence only.
The [capability registry](docs/capability-registry.md) records those distinctions;
[Workbench usage](docs/workbench.md) explains the older editor workflow.

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

## Older Workbench screenshots

![Older Webfoot Workbench Maps browser displaying Grand Kai's Planet from a verified Buu's Fury ROM](public/dbz-map-browser.png)

*Older Webfoot Workbench: map browsing from the author's verified Buu's Fury copy.*

![Older Webfoot Workbench Layout editor showing staged chunk-cell painting and map structure controls](public/dbz-layout-editor.png)

*Older Webfoot Workbench: staging layout changes before building a new image.*
These verified captures show existing tooling, **not the new DragonByte Z application**.

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

## Limits and ROM ownership

The canonical source image stays **read-only**. Exact profile identity is checked
before profile-specific access; builds write new outputs, and reopening a modified
image requires valid provenance. These requirements remain mandatory. Planned
modified-ROM workflows do not waive today's input or write protections.

Do not publish ROMs, extracted game assets, saves, states or memory dumps. Share
patches rather than commercial images; the verified editor captures above are the
[documented screenshot exception](docs/ROM_SAFETY.md), not permission to distribute
assets. Keep backups of projects and outputs; formats may change before 1.0.

## License

Original code here is [MPL-2.0](LICENSE). Third-party material keeps its own terms;
see [third-party notices](THIRD-PARTY-NOTICES.md) and each disassembly repository's
license and notices. No commercial game content is supplied or relicensed.
