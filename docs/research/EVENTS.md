# Buu's Fury events: what was measured for event authoring

This records what DragonByte Z relies on to build events, and how each fact was
established. "Runtime" means it was seen in mGBA on an image built by the
application from a disposable project, never on a hand-patched ROM. The source ROM
was read only; its SHA-256 was the same before and after every run.

## What an event is built into

| Authored thing | What the game reads |
| --- | --- |
| Talk event | a conversation: an array of record pointers the character names at record `+0x0C`. Speech is a kind 5 record, every other step a kind 0 script record whose result picks the next record |
| Region event with speech | the same conversation, started by a region of class `0x0800742D` |
| Region event without speech | one script body, started by a region of class `0x08007387` |
| Enter and leave events | one script body named by the map row at `+0x30` (enter) and `+0x34` (leave) |
| "Appears when" | the object record's word at `+0x04`: `0` always, `0x0001NNNN` while flag N is set, `0x0002NNNN` while it is clear |

A map row is `0x38` bytes. `+0x03` is the region count and `+0x10` the region list,
whose entries are `{condition, record}`. A region record is class, activation
routine, rectangle in pixels, and the conversation or script it starts. Regions an
event adds are appended to a re-emitted copy of the list; the game's own entries
keep their order and their bytes.

## Region activation routines (runtime)

| Routine | Behaviour seen | Offered as |
| --- | --- | --- |
| `0x08007791` | fires each time the player walks in | each time the player walks in |
| `0x080077DF` | fires once per load of the map | the first time, each visit |
| `0x0800770D` | fires when A is pressed inside | when the player presses A inside |
| `0x0800776D` | fires every frame while inside | not offered |
| `0x0800774F` | fires on A while facing up | not offered |

`0x08007499` is the save circle's class. It is recognised and never authored.

## Script natives used (runtime)

| Native | Effect | Step |
| --- | --- | --- |
| 24 | result of the last two-choice page, 0 for the first choice | If the answer is |
| 27, 28 | test a save flag, and the inverted test | If flag is set, is not set |
| 29, 30 | set and clear a save flag | Set flag, Clear flag |
| 43, 44 | make a rectangle walkable, and block it | Open passage, Close passage |
| 146 | count entries of one item in the gear list | If the player has |
| 147, 148 | add one entry to the gear list, remove one | Give item, Take item |

Native 35 (music) was not seen working and is refused by name at build.

Natives 147 and 148 work on the list at save structure `+0xE4` (a count, then one
word per entry, at most 250). That list is gear: an item given by 147 is shown by
the game under Equip. Supplies are kept elsewhere, as one count byte per item, and
no script native for them was identified, so they cannot be given.

## The acceptance run

Project: two characters copied from a standing character of the game, a door from
map 33 to the save circle on map 102, and five events (a talk event with an Ask,
a spoken region, a leave event, an enter event on a map that already has an enter
script, and a region inside a passage rectangle). Flags 157 to 162.

| Step | Seen in the game |
| --- | --- |
| First talk | speech; item 1 given then taken (gear count 0, 1, 0); flag 160 set then cleared; flag 157 set |
| Walk into the region | flag 158 set, then its speech |
| Second talk | the Ask page; first choice; item 1 given; flag 159 set; speech |
| Leave map 33 | flag 161 set by the leave event |
| Enter map 102 | the second character is constructed only when flag 159 is set; the enter event opens the rectangle when it is set and blocks it when it is not; the region inside the rectangle sets flag 162 only when it is open |
| The game's own enter script on map 102 | the same four instructions run after the authored event as run on the control image |
| Save at the circle, reset, load | flag bytes `E0 06` and gear count 1 as before the reset; the second character constructed; the passage opened; the region inside fires; Equip lists the item ("Dirty Shirt") |
| Trace | the application's trace script listed every step above in order, by event and step number, and nothing from another event |
| Control (same project, no events) | no flag set, no item, the copied character says its original line, the game's enter script unchanged |

## What is not established

- More than 47 project flags. No safe room in the save file was established.
- Supplies, shops, battles, music, item definitions and map variations.
- The two region routines not offered above, beyond the behaviour listed.
- Leave events and chained enter events on maps other than the one each was run on.
  An enter or leave event is refused wherever the end of the game's own script
  cannot be found.
- Events on a map of the creator's own were not run in the game.
- Item names. An item is chosen by number.
