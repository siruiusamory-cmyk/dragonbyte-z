# From a clone to a verified modification

Five stages, in the order the toolkit takes them: understand what it supports,
provide a verified ROM, modify a supported resource, build an output, validate
the result. Each stage states whether it was **executed** while this page was
written, with the command and its exit code, or **not executed**, with the
reason. Nothing on this page claims a step that was not run.

The short version of the honesty problem: this page was written without a game
image. Stage 1 was executed end to end, stage 2 was executed on its refusal path
only, stage 4's transaction was executed on a synthetic fixture, and stages 3 and
5 were not executed at all. The limits section at the end says what that costs.

## Stage 1 - understand what the toolkit supports

```powershell
webfoot --help
```

Executed in the module form from the clone root:

```text
python -m tools.webfoot --help          exit=0
usage: webfoot [-h] [--profiles PROFILES]
               {placement,entity,event,graphics,atlas,relocation-proof,identify,
                validate-map-entries,map-entries,variation-arrays,stats,text,map,
                extract,validate,build,randomize,patch,tileset} ...
```

What is *supported* is a property of the ROM profile, not of the title. Measured
from `config/roms.yaml` through `tools.webfoot.capability`:

| profile | capability domains declared |
| --- | --- |
| `buus_fury_usa_rev0_01c1707f` | actor_sprites, appearances, character_base_stats, enemy_stats, map_entries, placement_types, scripts, text_strings |
| `buus_fury_usa_rev0_dcf23468` | none - identity only |
| `legacy_of_goku_usa_a3c8c767` | scripts |
| `legacy_of_goku_ii_usa_rev0_204142e1` | enemy_stats, scripts, text_strings |

So Buu's Fury (the local profile) is the only image with a full authoring surface,
Legacy of Goku II adds enemy HP and text, and Legacy of Goku has its script
records read. The 24 shipped *product* capabilities in
[`src/data/capabilities.json`](../src/data/capabilities.json) are the editor
surface; this table is the per-image data underneath it. The registry and its
rules are in [`capability-registry.md`](capability-registry.md).

**EXECUTED.** `python -m tools.webfoot --help` exit 0; the capability table was
printed by a script that loads the catalogue.

## Stage 2 - provide a verified ROM

Keep your own image outside version control; the ignored `roms\` directory is the
conventional place. Then identify it:

```powershell
webfoot identify ".\roms\<your image>.gba"
```

Identification is cryptographic. `config/roms.yaml` is authoritative, and a
profile matches only when its SHA-256 and every other configured hash and
metadata constraint agree. On a match the command prints the profile id and the
status `VERIFIED`; anything else prints `UNKNOWN` or `CONFLICT` and a reason, and
exits non-zero (the `UNKNOWN` case was measured at 1).

Executed refusal path (a text file, not an image):

```text
python -m tools.webfoot identify README.md          exit=1
Profile:
NONE
Status:
UNKNOWN
Reason: no configured cryptographic identity matched
```

Executed missing-file path:

```text
python -m tools.webfoot identify <absent>.gba       exit=2
error: ROM does not exist: <absent>.gba
```

**PARTIALLY EXECUTED.** The refusal is proven; the success path (`Profile:
<profile-id>`, `Status: VERIFIED`) was **not executed**, because no game image is
available here. That wording is read from the identification code
(`tools/webfoot/cli.py`, `_print_identification`, and the status values in
`tools/webfoot/profile.py`), so it is what the code prints, not something a run
showed.

## Stage 3 - modify a supported resource

Two routes reach the same project and the same build.

**Editor route.** Open the ROM and a project in DragonByte Z
(`dragonbyte-z`, or `python -m tools.webfoot.workbench` for the beta surface) and
edit in the destination that owns the resource: Maps for map layout and warps,
Scripts & Text for a dialogue line, Graphics for a sprite or a palette. Four
walkthroughs, each with the capabilities it covers and the proof level it
reaches, are in [`journeys/`](journeys/README.md).

**Command route.** Two commands edit a resource and write a new image with a
manifest, without a project directory:

```text
webfoot text set <rom> <identity> <value> --output <new-rom> [--manifest <path>]
webfoot stats set <rom> <identity> <field> <value> --output <new-rom> [--manifest <path>]
```

Their identities are records, not addresses: `text:0010`, `enemy:434`,
`character:0`. `text set` takes control codes as `{08:XX}` and a literal brace as
`{{`. The usage text above was executed (`--help`, exit 0); **the edit itself was
NOT EXECUTED**, because it needs a verified image.

## Stage 4 - build an output

The project route is `extract` once, then `build` as often as you like:

```text
webfoot extract <rom> <project-dir> [--no-graphics]
webfoot build   <project-dir> --rom <base-rom> --output <new-rom> [--manifest <path>]
```

`extract` writes a text project (`project.toml`, one TOML file per table,
optionally the sprite PNGs) whose `project.toml` records the base image hash.
`build` writes a **new** image and refuses to overwrite one; it stages and
verifies before publishing, and its manifest records the base hash, the output
hash and every changed byte span. `docs/project-format.md` is the format and
[`journeys/safe-build-and-derivative-reopen.md`](journeys/safe-build-and-derivative-reopen.md)
is the delivery contract.

Executed refusal at the ROM boundary:

```text
python -m tools.webfoot extract README.md <dir> --no-graphics     exit=2
error: extraction requires an exactly verified ROM
```

**NOT EXECUTED for a game image.** What *was* executed is the same transaction
on a synthetic fixture with no ROM I/O, twice, to show that the emitted bytes are
deterministic from pinned inputs:

```text
python -m tools.webfoot relocation-proof   exit=0
run 1 sha256 26a7cc405372a27a9dfb0a7bbef064216d5cb389c982e73c671641da89db517c
run 2 sha256 26a7cc405372a27a9dfb0a7bbef064216d5cb389c982e73c671641da89db517c
manifest.base.sha256   5a352392b492d8debc04736564bc94fce792625743bdda09d8add52512ddaff6
manifest.output.sha256 6a7666fc3751d5d9b111dee280071dcc208264274c9abfd0ad78dc08baa9cf62
manifest.changed_byte_count 43
```

That is the build transaction's shape and its determinism, **not** a game edit:
the fixture is constructed and makes no claim about any retail image.

## Stage 5 - validate the result

```text
webfoot validate <project-dir> --rom <base-rom>
```

Validation reads the project against the base image and writes nothing. A build
also writes a provenance manifest beside the image, and the editor reopens its own
emitted image only when that manifest proves the image is the canonical base plus
exactly the declared edits. Today that reopen is accepted for one change class
only, the dominant-layer chunk replacement described in
[ADR 0002](decisions/0002-authored-derivative-trust.md); every other emitted
image is launched but refused as a derivative, and the journey says so.

Executed usage and missing-input refusals:

```text
python -m tools.webfoot validate                      exit=2
usage: webfoot validate [-h] --rom ROM project
webfoot validate: error: the following arguments are required: --rom

python -m tools.webfoot validate <absent-dir> --rom README.md   exit=2
error: project directory does not exist: <absent-dir>
```

**NOT EXECUTED** on a real project and image. The manifest fields that the
validation reads back were executed on the synthetic fixture in stage 4.

## Per-stage summary

| stage | status | evidence |
| --- | --- | --- |
| 1. understand support | EXECUTED | `--help` exit 0; capability table printed from `config/roms.yaml` |
| 2. verified ROM | PARTIALLY EXECUTED | refusal exit 1 and missing-file exit 2 executed; success path inferred from code |
| 3. modify | NOT EXECUTED | usage exit 0 only; needs a verified image |
| 4. build | NOT EXECUTED (game) / EXECUTED (synthetic) | extract refusal exit 2; deterministic synthetic emit, two runs byte-identical |
| 5. validate | NOT EXECUTED (game) | usage and missing-input refusals exit 2; manifest shape from the synthetic emit |

## What this path does not prove

- It does **not** demonstrate a complete workflow. No game image was present, so
  no extract, edit, build or validate ever ran against one, and no claim here
  rests on a run that did not happen.
- It does not claim runtime behaviour of any authored change. That evidence
  exists per capability in [`src/data/capabilities.json`](../src/data/capabilities.json)
  and in the journeys; it is not reproduced here.
- The per-profile table is the profile's declared capability set. Whether an
  operation is *proven* for an image is the registry's claim, not the catalogue's
  declaration.
