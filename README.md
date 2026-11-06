# DragonByte Z / Webfoot SDK

Tools for inspecting, editing and building mods for Webfoot's **Dragon Ball Z
Game Boy Advance games**: *The Legacy of Goku*, *The Legacy of Goku II* and
*Buu's Fury*. The Webfoot SDK supplies the formats, project model and safe build
pipeline; desktop editors make supported content accessible without ROM addresses.

No ROM or game data is included. Supply your own legally obtained supported ROM.

**Start here:** [Windows setup and launch](INSTALL.md) |
[Documentation](docs/README.md) | [Contributing](CONTRIBUTING.md)

![Webfoot Workbench Maps browser displaying Grand Kai's Planet from a verified Buu's Fury ROM](public/dbz-map-browser.png)

*The existing Workbench: browse maps rendered from ROM bytes.*

![Webfoot Workbench Layout editor showing a staged chunk-cell paint and map structure controls](public/dbz-layout-editor.png)

*The existing Workbench: stage layout changes before building a new image.*
These are real captures from the author's verified Buu's Fury copy. They show the
Workbench, not the separate DragonByte Z application under development.

## What you can edit

The most developed authoring path is **Buu's Fury**. Support is specific to the
verified ROM profile and content form; an unsupported operation is refused or
shown read-only with a reason.

| Area | Existing SDK and Workbench capabilities |
| --- | --- |
| Find and inspect | Atlas search, recovered fields, decoded text and rendered map layers. |
| Maps | Paint chunk layouts, create chunks, grow supported layer grids, activate layers and author new map identities. |
| Objects and warps | Add or move supported objects; retarget, move and create transitions. |
| Dialogue and scripts | Edit mapped text, relocate longer dialogue, clone entities and attach authored scripts to supported triggers. |
| Graphics | Import edited sprite PNGs, recolour shared object palettes, and author donor-based sprite and appearance definitions. |
| Build and share | Validate a project, build a new ROM, record provenance and export a BPS patch. |

The SDK also exposes operations headlessly. That does not mean every operation
has a desktop control or runtime proof: native 8x8 tile placement, for example,
is verified headlessly and has no claimed emulator rendering acceptance.
[Capability definitions and evidence](docs/capability-registry.md) describe the
individual bounds; [Workbench usage](docs/workbench.md) covers its editor flow.

## Supported games and maturity

| Game | Current maturity |
| --- | --- |
| **Buu's Fury** | Leading authoring and runtime-validation target. The verified local profile supports the broadest editing path; other recognized images do not inherit its format support. |
| **The Legacy of Goku II** | Partial SDK support, including enemy HP editing and an authored-image route. A 16 MiB expansion has runtime evidence; the HP edit and declared free region do not have runtime acceptance. Text relocation remains refused. |
| **The Legacy of Goku** | Earlier format work: 18 script families load and round-trip losslessly. Opcode effects and player-visible authored behavior are not established. |

See [ROM profiles](docs/rom-profiles.md) for exact identities and supported
structures. A matching title or header alone does not establish compatibility.

## Project status

**Active development, pre-1.0.** The shipping SDK is `tools/webfoot/`.
The existing optional Workbench is `tools/webfoot/workbench/`; the separate
DragonByte Z application is `tools/dragonbyte/`. The captures above document the
Workbench and do not establish completion of that separate application.

The acceptance objective is **playable Legacy of Goku content authored inside
the original Legacy of Goku II/Buu's Fury engine**. Existing editing and build
capabilities are useful now; they do not establish that the complete playable
LOG1-remake objective has been delivered. This is not a standalone game engine.

The capability registry tracks a fixed set of operations, not an overall
project-completion percentage. Follow the [roadmap](docs/ROADMAP_TO_1_0.md) and
[verified technical state](docs/PROJECT_STATE.md) for scope and remaining work.

## Windows quick start

Install Git and [uv](https://docs.astral.sh/uv/). Setup obtains Python 3.12 and
installs the locked SDK, PySide6 and developer dependencies. In PowerShell:

```powershell
git clone https://github.com/siruiusamory-cmyk/dragonbyte-z.git
cd dragonbyte-z
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1 -SkipUpstreams
.\.venv\Scripts\Activate.ps1
webfoot --help
```

Supply your own legally obtained supported ROM. Keep it local, outside version
control. For the **Workbench shown above**, identify the image and build its
required atlas first (substitute your own ROM path):

```powershell
webfoot identify "C:\Games\Buu's Fury.gba"
webfoot atlas regenerate "C:\Games\Buu's Fury.gba" --out .\build\atlas
python -m tools.webfoot.workbench
```

Use **Open ROM** to select that same verified image. For the separate DragonByte Z
application, run `python -m tools.dragonbyte` or double-click `DragonByte Z.cmd`.
An emulator such as mGBA is needed for Run, not for installation or inspection.
The [installation guide](INSTALL.md) includes troubleshooting;
the [newcomer guide](docs/newcomer.md) covers project extraction, validation,
build and patch commands, with the extent of their verification stated.

## Developer documentation

- [Documentation index](docs/README.md): usage, architecture, formats and history.
- [Project format](docs/project-format.md) and [architecture](docs/architecture.md): SDK data and dependency boundaries.
- [Development policy](docs/DEVELOPMENT.md), [review gate](docs/REVIEW.md) and [ROM safety](docs/ROM_SAFETY.md): required contribution rules.
- [Testing](docs/testing.md): focused tests, reproducibility and governed merge checks.
- [Reverse engineering](docs/reverse-engineering.md) and [research evidence](docs/research/): measured formats and their confidence levels.
- [Release artefacts](docs/release-artefacts.md): local ROM outputs, distributable patches and packaging.

## Limits and ROM ownership

You must supply your own legally obtained ROM; **no ROMs or game data are
included**. Exact profile identity is checked before profile-specific access.
The canonical input stays read-only, builds write new outputs, and reopening a
modified image requires valid provenance. Those protections are mandatory.

Authoring remains bounded: graphics replacements keep their dimensions, sprite
frames inherit donor geometry and timing, some structures stay read-only, and
new text-table IDs are not claimed. Keep backups of projects and outputs;
project formats can change before 1.0.

Do not commit or attach ROMs, extracted assets, saves, states or memory dumps.
Share patches rather than commercial game images. The two editor captures above
are the documented screenshot exception, not permission to publish game assets.
See the [full safety contract](docs/ROM_SAFETY.md).

## License

Original code is licensed under [MPL-2.0](LICENSE). Third-party material keeps its
own terms: see [third-party notices](THIRD-PARTY-NOTICES.md).
