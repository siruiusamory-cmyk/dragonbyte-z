# The first authored scene project, as a project definition

DBZ-051, branch `ticket/dbz-z002-first-scene-2`. This note is the tracked form of
the scene's project definition: three documents, one extraction command, one
build command, and the artifact facts a reviewer can re-measure. It is the whole
of the scene that can be authored today; the flag-setting event is missing and
`STAGE2A.md` section 7 states why in measured terms.

Canonical image `940ad5f01db4465b8877dfe739510cbf34f4ea3d390f3df13519808bc36f059e`,
read-only, hash re-checked before and after every build.

## The three documents

A project is the retail image extracted, plus these three files.

```toml
# maps/authored.toml - the office as a new map row, donor 35, own key
[map.yemma-office]
donor = 35
key_high = 0x99
key_low = 0x02
```

```toml
# maps/transitions.toml - the retail door into the office now leads to the clone
[transition."map:0036"."0000"]
prior_destination = "map:0035"
destination = "map:0452"
```

```toml
# dialogue/replacements.toml - Yemma's assistant relays the verdict
[dialogue."record:0:0x91B4"]
text = "King Yemma says, a Saiyan got you. Follow Snake Way to King Kai. Go."
```

`record:0:0x91B4` is the office assistant's own record, the one the engine's
A-press talk opens (`0x7809B4`, portrait operand `161`). The line is 68 units,
inside the record's 72-byte engine-proven budget, and it is spoken by the
assistant because the assistant is who the conversation belongs to - the
portrait byte is carried, never authored, so the speaker on screen is the
speaker of the record. It is a placeholder for the owner's own wording, not a
translation of LOG1 text.

## The two commands

```text
python -m tools.webfoot extract <retail image> <project directory> --no-graphics
python -m tools.webfoot build <project directory> --rom <retail image> --output <new image>
```

`extract --no-graphics` takes 3.0 s on the canonical image; the extraction is
`project.toml`, `enemies/`, `characters/`, `text/`, `maps/maps.toml`,
`placement_types/`, `events/`. Only the three documents above are edited.

Measured on two directories extracted independently from the same image, with
the same three documents copied in:

| item | value |
| --- | --- |
| `webfoot validate` | `PASS`, 141 enemy records, 9 character records, 1,534 strings, 452 maps, 0 problems |
| generated image | 16,777,216 bytes |
| build A sha256 | `535EF0772BA8A1C4E292DF70A40310A506069E249F22631FECB0194BDAF3C7B6` |
| build B sha256 | `535EF0772BA8A1C4E292DF70A40310A506069E249F22631FECB0194BDAF3C7B6` |
| changed bytes | 44,739 across five owners |

The five owners, from the build's own manifest:
`map_authoring:table`, `map_authoring:root:yemma-office`,
`map_authoring:layer:yemma-office`, `map:0036/transition:0000`,
`compressed-dialogue:record:0:0x91B4`.

## What the artifact says when it is read back

| property | value |
| --- | --- |
| relocated map table | base word at file `0x8A58` reads `0x08804A6C` |
| count helper immediate | `0x30C6` at file `0x125E2`, bound 453 |
| authored row | index 452, key bytes `0x99 0x02`, root `0x08804A18` |
| the conversation's record | `0x087809B4`, kind `5`, portrait operand `161`, handle repacked |
| its text units | 68, decoding to exactly the authored line |
| the door into the clone | `map:0036/transition:0000`, destination changed, arrival, region and facing untouched |

The base differs from the map-only build's `0x0880007C` because the dialogue
repack allocates before the map domain does, which is the allocator working as
designed and not a constant to pin.

**The door out** is inherited: the authored row carries donor 35's own connection
root, so the office's own exits are the retail office's exits. That was observed
working on the map-only clone - the engine took the player from row 452 back to
`map:0036` at frame 991 (`STAGE0B.md` section 3, another lane's run) - and it is
**NOT MEASURED** on this artifact.

## What is missing

1. **The authored flag event.** Blocked, with evidence, in `STAGE2A.md` sections
   5 to 7: the record kind that carries executable code exists (kind 2) and the
   flag primitive exists (native slot 29), but the conversation's record array
   has no repoint site in the image, so an authored record cannot yet be made
   reachable by a talk.
2. **Any runtime measurement of this artifact.** No emulator ran in this lane.
   The predecessor lane's screenshots are of a different, map-only image and are
   not evidence for this one.

## Reproducing the check

```text
python -m tools.webfoot extract <retail> <a> --no-graphics
python -m tools.webfoot extract <retail> <b> --no-graphics
copy the three documents into <a> and <b>
python -m tools.webfoot build <a> --rom <retail> --output a.gba
python -m tools.webfoot build <b> --rom <retail> --output b.gba
sha256sum a.gba b.gba
```
