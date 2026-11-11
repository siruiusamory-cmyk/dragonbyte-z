# The first authored scene project, as a project definition

DBZ-051, branch `ticket/dbz-z002-first-scene-2`. This note is the tracked form of
the scene's project definition: four documents, one extraction command, one build
command, and the artifact facts a reviewer can re-measure. The scene's authored
event is here too: the office conversation runs a script, and that script now sets
a save flag.

Canonical image `940ad5f01db4465b8877dfe739510cbf34f4ea3d390f3df13519808bc36f059e`,
read-only, hash re-checked before and after every build.

## The four documents

A project is the retail image extracted, plus these files.

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

```toml
# dialogue/scripts.toml - the script the talk already runs now sets flag 228
[script."conversation:0x087809EC"."0000"]
prior_instructions = ["push_byte 2", "native_stack 27", "push_byte 3", "native_stack 28", "logical_and", "branch_if_zero 6", "push_byte 3", "terminate"]
instructions = ["set_save_flag 228", "push_byte 2", "native_stack 27", "push_byte 3", "native_stack 28", "logical_and", "branch_if_zero 5", "push_byte 3", "terminate", "push_byte 125", "native_stack 27", "branch_if_zero 4", "push_byte 9", "terminate"]
```

`record:0:0x91B4` is the office assistant's own record, the one the engine's
A-press talk opens (`0x7809B4`, portrait operand `161`). The line is 68 units,
inside the record's 72-byte engine-proven budget, and it is spoken by the
assistant because the assistant is who the conversation belongs to - the portrait
byte is carried, never authored, so the speaker on screen is the speaker of the
record. It is a placeholder for the owner's own wording, not a translation of LOG1
text.

`conversation:0x087809EC/entry:0` is the word array the dialogue runner holds as
its first word, and entry 0 is the type-0 record whose code block the engine runs
on the same frame as the A press. `set_save_flag 228` is the declared effect: one
byte push and native slot 29, the engine's own flag SET.

## The two commands

```text
python -m tools.webfoot extract <retail image> <project directory> --no-graphics
python -m tools.webfoot build <project directory> --rom <retail image> --output <new image>
```

`extract --no-graphics` takes 3.0 s on the canonical image; the extraction is
`project.toml`, `enemies/`, `characters/`, `text/`, `maps/maps.toml`,
`placement_types/`, `events/`. Only the four documents above are edited, and the
two `dialogue/` documents need the directory created.

Measured on two directories extracted independently from the same image, with the
same four documents copied in:

| item | value |
| --- | --- |
| `webfoot validate` | `PASS`, 141 enemy records, 9 character records, 1,534 strings, 452 maps, 0 problems |
| generated image | 16,777,216 bytes |
| build A sha256 | `F5E196187F08AC9AEDC3256385962B1A1690E31CF5B38F96E1352DACF324898D` |
| build B sha256 | `F5E196187F08AC9AEDC3256385962B1A1690E31CF5B38F96E1352DACF324898D` |
| bytes differing from the base | 406 |
| owners in the build plan | `map_authoring:table`, `map_authoring:root:yemma-office`, `map_authoring:layer:yemma-office`, `map:0036/transition:0000`, `compressed-dialogue:record:0:0x91B4`, `conversation:0x087809EC/entry:0` |

## Playing it yourself

Everything below is meant to be followed by someone who has not read the rest of
this page. It needs no instrument until the last step.

**1. What you need.** A legally obtained Buu's Fury (USA) retail ROM, whose SHA-256
must be `940ad5f01db4465b8877dfe739510cbf34f4ea3d390f3df13519808bc36f059e`; this
repository checked out; Python 3.11 or newer with the repository's own setup done
so `python -m tools.webfoot --help` answers from the repository root; and mGBA to
play the result, 0.11 or newer for the instrument step. Nothing is downloaded.

**2. Make the project.** From the repository root, with `<retail>` standing for
your ROM path and `<project>` for a directory that does not exist yet:

```text
python -m tools.webfoot extract <retail> <project> --no-graphics
```

That takes about three seconds and writes `project.toml` and the extracted tables.
Create `<project>/dialogue/` (the extraction writes no dialogue directory), then
copy the four documents from the sections above into it: `maps/authored.toml`,
`maps/transitions.toml`, `dialogue/replacements.toml` and `dialogue/scripts.toml`.

**3. Build the image.**

```text
python -m tools.webfoot build <project> --rom <retail> --output <scene.gba>
```

`<scene.gba>` must not exist yet. The command prints the base hash, the output
hash, one line per edit with a changed-byte count, and `RESULT: COMPLETE`. A
correct build reports this output hash:
`f5e196187f08ac9aedc3256385962b1a1690e31cf5b38f96e1352dacf324898d`. Add
`--verbose` if you want every changed byte offset listed.

**4. Play it.** Open `<scene.gba>` in mGBA (File, Open, or the image on the command
line). Do not open the retail ROM: the authored room, the line and the flag live in
the derivative.

**5. Reach the office by hand.** The scene sits in the game's opening, at the
Other World check-in station. If you have a save or a savestate from that point,
load it: you start on the cloud platform, with Goku (a halo over his head) between
two fences and a few souls drifting about. Walk south, down through the fence
opening and along the corridor, and step into the doorway at the end. That doorway
is `map:0036`'s own door and it now leads into the authored office instead of the
retail one. Inside, the room is tiled, with a desk to the east; walk south until
you stand next to the small blue clerk with glasses and press A. From a new game,
play the opening until you reach that station first.

**6. What you should see.** The dialogue box opens at the bottom of the screen with
the clerk's portrait on the left and the line you authored typing out, beginning
`King Yemma says, a Saiyan got you.` Press A to reveal the rest of the line and
again to advance; the retail pages that follow the authored one (`Wait a second!`,
then `Please, go ahead!`) still play under the same portrait. After the last page
the box closes and you can walk again. Walk back north through the door to leave
the office and return to the station.

**7. Change one word.** Open `<project>/dialogue/replacements.toml`. The key is
`[dialogue."record:0:0x91B4"]` and the value is the line. Change any word, for
example `King Yemma` to `Lord Yemma`, run step 3 again to a new output path, and
play step 5 again: the box shows your new word. Nothing else needs editing, and
nothing in the ROM or the extraction is modified in place.

**8. See the flag change.** The flag is save state, not something the game draws:
nothing on screen changes when it is set, and no menu shows it. To watch it, use
the tracked launcher, which runs the same route with a read-only observer and
writes the evidence into a run directory:

```text
powershell -NoProfile -ExecutionPolicy Bypass -File tools/runtime/start_dbz002b_session.ps1 `
  -RomPath <scene.gba> -RomSha256 <its sha256> -Label my-first-run `
  -StatePath <your check-in station savestate> -Route talkend -MaxFrames 4200 -DriveFrames 3900
```

It starts mGBA and returns; the run ends itself at the frame budget. Then read
`build/dbz002b/my-first-run/dbz002b-observation.csv` and look for
`FLAG_SET,flag=228` and the `FLAG_AFTER` row two frames later: the byte it prints
goes from `0x00` to `0x10`. `-StatePath` is optional; without it the launcher
starts the image from the beginning and `-Route talkend` has nothing to drive, so
reach the station yourself in that case. The launcher requires mGBA 0.11 with the
scripting breakpoint API, defaults `-MGBPath` to the standard Windows install, and
forces both the save and the savestate directories into the run directory.

## What the artifact says when it is read back

| property | value |
| --- | --- |
| relocated map table | base word at file `0x8A58` reads `0x08804A6C` |
| count helper immediate | `0x30C6` at file `0x125E2`, bound 453 |
| authored row | index 452, key bytes `0x99 0x02`, root `0x08804A18` |
| the conversation's record | `0x087809B4`, kind `5`, portrait operand `161`, handle repacked |
| its text units | 68, decoding to exactly the authored line |
| the door into the clone | `map:0036/transition:0000`, destination changed, arrival, region and facing untouched |
| the talk script | `0x78098F`, 29 bytes: `00 e4 02 1d 00 02 02 1b 00 03 02 1c 04 13 00 05 00 03 11 00 7d 02 1b 13 00 04 00 09 11` |

The base differs from the map-only build's `0x0880007C` because the dialogue
repack allocates before the map domain does, which is the allocator working as
designed and not a constant to pin.

**The door out** is inherited: the authored row carries donor 35's own connection
root, so the office's own exits are the retail office's exits. Measured on this
artifact: the player left row 452 for `map:0036` (key `0x0104`) at frame 2,666 and
played on for another 1,134 frames.

## Why the talk script is rewritten rather than appended to

The steer's shape was "append four bytes before the terminating instruction": the
measured body is fifteen bytes and the next conversation record starts fourteen
bytes after it. That room is **not free**. The fifteen-byte body's forward branch
(`branch_if_zero 6` at `0x780998`) lands on `0x78099F`, where a second body
begins:

```text
0x78098F  00 02 02 1B 00 03 02 1C 04 13 00 06 00 03 11     entry 0's body
0x78099E  11                                              unreachable terminator
0x78099F  00 7D 02 1B 13 00 04 00 09 11                   the branch target
0x7809A9  00 00 00                                        padding
0x7809AC                                                  the next record, kind 5
```

The branch base is the pre-operand cursor (handler `0x08003E57`), so the target is
`0x780999 + 6 = 0x78099F`, and the second body decodes cleanly from there and is
reached at runtime: the interpreter entered it with cursor `0x087809C7` for the
conversation's later entry 5, on the same run that entered `0x0878098F`. Overwriting
those bytes would corrupt a live path.

The whole span is therefore re-laid out inside its own 29 bytes: the flag set
goes first, the canonical body follows verbatim with its displacement changed from
6 to 5 because it now sits four bytes later, and the second body follows
byte-identically at its new address (its own internal displacement of 4 still
lands on its own terminator). Nothing outside the span changes, and the VM stack is
left exactly as found: `push_byte 228` adds one value and slot 29 consumes it.

## The flag: 228, and why it is free

Retail's own script bodies name flags 1 to 387 in the dialogue pool, and the event
corpus names 266 and 267. A scan of every candidate record body in the dialogue
pool (`0x77C5A4..0x79B704`, kind 0 code at `+3`, kind 2 code at `+8`, decoded with
the production decoder) collects the operands feeding slots 29, 186 and 187:
`set` sites cover 1 to 387 with gaps, range writes sit at 388 and 393, and no site
names 228. The flag is one byte, so no retail body can even spell a flag above 255
with `push_byte`; 228 sits inside the widest gap under that ceiling and inside the
region retail itself writes. `tests/integration/test_conversation_script_rom.py`
asserts the corpus names save flags at all and does not name this one.

The flag's byte is not the pool base plus the bit index. The handler forms it as
`save object + 0x55 + (flag >> 3)` and sets bit `flag & 7`, so flag 228 is
`0x03001068 + 0x55 + 28 = 0x030010D9` with bit 4, five bytes above the pool base
word `0x030010B8` (`object + 0x50`). Reading the pool base as the array base lands
five bytes low and silently reads a different flag. Re-derive it with:

```text
python -c "print(hex(0x03001068 + 0x55 + (228 >> 3)), 228 & 7)"
```

## Runtime evidence on this artifact

Image `F5E19618...4898D`, savestate `25009C63...424A6`, four bounded runs under
mGBA 0.11.0.0 (`build\dbz002b\scene-talk-01` to `-04`).

| frame | channel | what it says |
| --- | --- | --- |
| 305 | `MAP_ROW` | row 452, key `0x9902`, lookup args `(0x99, 0x02)` |
| 857 | `VM_POOL` | interpreter entered `0x0878098F` with the authored bytes `00 E4 02 1D ...` |
| 857 | `FLAG_SET` | flag 228, byte `0x030010D9`, bit 4, `before=0x00` |
| 859 | `FLAG_AFTER` | the same byte reads `0x10` |
| 857 | `DIALOGUE` | `0x087809B4` kind 5 portrait 161, the authored line in the native box |
| 961 | `DIALOGUE` | `0x087809BC`, the retail chain continues after the authored page |
| 1345 | `VM_POOL` | entry 5's body at `0x087809C7`, so the later code still runs |
| 2666 | `MAP_ROW` | row 36, key `0x0104`, the player left the office |

Screenshots, by full path:

- `build\dbz002b\scene-talk-01\page_00887.png` the authored line, assistant portrait
- `build\dbz002b\scene-talk-01\page_01047.png` the retail page that follows it
- `build\dbz002b\scene-talk-03\tick_02640.png` the box closed, play resumed
- `build\dbz002b\scene-talk-04\tick_02880.png` back on `map:0036` after the exit

## What is missing

1. **Portrait authoring.** The assistant speaks the line with its own portrait,
   which is correct for that speaker. Authoring a different portrait operand is not
   built and this scene does not need it.
2. **Music selection.** The authored row inherits `music_id 15` from donor 35.

## Reproducing the check

```text
python -m tools.webfoot extract <retail> <a> --no-graphics
python -m tools.webfoot extract <retail> <b> --no-graphics
copy the four documents into <a> and <b>
python -m tools.webfoot build <a> --rom <retail> --output a.gba
python -m tools.webfoot build <b> --rom <retail> --output b.gba
sha256sum a.gba b.gba
```
