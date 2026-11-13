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

## Character steps (runtime)

The interpreter never waits: a native that takes several frames blocks inside its
own handler until it finishes, so steps compiled one after another already play in
order. No bracket is needed for ordering.

| Native | Operands, pushed in this order | Effect | Step |
| --- | --- | --- | --- |
| 96 | character, x, y | walk to a whole-pixel point at speed 100 | Walk to |
| 97 | character, x, y, speed | the same walk at the speed given | Walk to, with a speed |
| 83 | character, direction | face `0` down, `1` up, `2` left, `3` right | Face, Face toward |
| 60 | character, byte | the player lies down with byte `16`, and byte `0` stands up again | Lie down, Stand up |
| 136 | frames | wait that many frames | Wait |
| 56 ... 58 | none | 56 lets the actor commands after it queue instead of waiting; 58 blocks until the last of them finishes | Do together |

Native 83 with a direction outside 0 to 3 stops the game, so a direction is stored
as one of the four words and nothing else can reach the compiler.

Only one gesture byte is safe, and only on the player. `60(0, 16)` plays a lie-down
pose that stays until `60(0, 0)`, which returns the normal stance within 31 frames.
Byte 24 on the player leaves a permanent sprite corruption that nothing removes, and
byte 24 on any other character stops the game; byte 16 on another character does
nothing. Lie down and Stand up therefore carry no byte and no character: they are the
player's, always, and an event that lies the player down has to stand him up again on
every path to its end, or the build refuses it.

A 56 without its 58 leaves the queue latch set and later actor commands never start,
so one Do together block compiles to one record holding both, and they cannot be
separated. Frames measured at speed 100: 56 pixels took 60 frames; the same 56 pixels
took 120 frames at speed 50 and 30 at speed 200.

The character operand is the slot's position in the built object array, as
`-(index + 1)`; `0` is the player. A positive number names a definition rather than the
character standing there, so it is never emitted. An added character is appended and
does not move the slots before it, and a character whose "appears when" rule is false
is absent at runtime while keeping its slot. An unresolvable reference is a silent
no-op, which is why the build refuses a character it cannot find.

Seen on screen: a walk is drawn frame by frame on the way; the player cannot move
while a character step runs and can move again as the event ends, which is the
engine's own behaviour and not a step; a walk ignores map collision and always
arrives, so a walk cannot freeze the scene and choosing a sensible target is the
creator's part.

Character steps run in a conversation: a talk event, or a region event that speaks.
An enter or leave event, and a region that says nothing, is refused.

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
- Poses, gestures and animations. One gesture is proven safe and is offered as Lie
  down and Stand up, on the player only; every other gesture byte is not established,
  and one of them stops the game on a character other than the player.
- Creating or removing a character as an event step. Native 53 creates one, and no
  native removes one.
- Native 71, which faces one character toward another. It turns both of them and did
  not turn a product-placed character, so it stays out; the step is built from 83 and
  two known positions instead, and a character whose position the event cannot know is
  refused.
- Face toward after a step whose position is only known inside an If. The build says
  so and offers a fixed direction.
