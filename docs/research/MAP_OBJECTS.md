# Map objects: what a map places, and what authoring them is proven to do

Buu's Fury (USA). Addresses are ROM addresses in the canonical image. Each claim is
marked `STATIC` (read from the image), `RUNTIME` (observed in mGBA on a privately
built image) or `NOT ESTABLISHED`.

## The array

Every map table row holds a one-byte object count at `+0x04` and a pointer at `+0x14`
to that many record pointers. The engine walks the array once when the map loads.
`STATIC`: 316 of the 452 maps have objects, 1,898 slots in all, at most 51 on one
map; no array is named by two rows.

Each record begins with a pointer to its factory. Three factories account for every
slot:

| Family | Count | Position | Sprite id | Status in DragonByte Z |
|---|---|---|---|---|
| placement (`0800FD55`) | 1,559 | `+0x0C` | `+0x10` | shown, not edited |
| NPC (`08017DA3`) | 191 | `+0x08` | `+0x10` | moved, copied, restyled, removed |
| scene (`080111A9`) | 148 | `+0x08` (inferred) | `+0x0C` | shown, not edited |

43 maps mix families. The sprite id is the argument the engine passes to its sprite
resolver; ids of 10 and above index the sprite table and are Library sprite
`id - 10`. `RUNTIME`: on a built image, each constructed record's sprite field
equalled the resolver's argument.

## NPC records

A 28-byte header: `+0x04` a word that is zero or story data, `+0x08` the position as
two halfwords, `+0x10` the sprite id, `+0x14` an entry count and `+0x18` a pointer to
the behaviour entry. The wander class (`0800A7A1`) has a 16-byte entry whose `+0x08`
holds a box of four halfwords: left, top, right, bottom.

## What was run

All runs used a private copy of the image, a door added from map 33 into the map
under test, and scripted input. The source image's SHA-256 was the same before and
after every build.

| Question | Result |
|---|---|
| A base-game NPC moved on its own map | `RUNTIME`: stands at the new position. Four bytes of the base image change. |
| A copy of a standing NPC | `RUNTIME`: stands where placed. |
| A copy of a wanderer with its own box | `RUNTIME`: wanders inside the authored box. |
| A copy of a wanderer that shares its donor's entry | `RUNTIME`: stands still when it is outside the donor's box. |
| A copy taken from another map | `RUNTIME`: appears and wanders (map 116 to map 102). |
| Talking to a copy | `RUNTIME`: pressing A beside a copy of a talking NPC opened the same dialogue record as the donor (`087855A8`), with its portrait. |
| A copy drawn with another sprite | `RUNTIME`: a copy whose sprite id was replaced (204 to 279) was drawn with the new sprite and still opened the donor's dialogue. One pair was run; the application offers the sprites that base-game NPC records use. |
| Removing a base-game NPC | `RUNTIME`: the removed slot was not constructed; every later slot was, and talking still worked. |
| NPCs and the player | `RUNTIME`: the player stopped 16 pixels short of an NPC placed in the path, and walked through the same spot on a control image without it. |
| Which slots are constructed at load | `RUNTIME`: NPC records whose `+0x04` word is zero were constructed when the map loaded. Records whose `+0x04` word is set were not; distance from the player was not the condition. What sets them off is `NOT ESTABLISHED`. |
| Copies of placement records | `NOT ESTABLISHED`. On a map of only NPCs a placement copy was never constructed. On its own map, the common enemy placements are not constructed at load at all, base-game ones included, so a copy could not be told from a failure. |
| Initial facing | `NOT ESTABLISHED`. |
| The scene family's layout beyond sprite and position | `NOT ESTABLISHED`. |
| Entry sizes of the other NPC behaviour classes | `NOT ESTABLISHED`. A copy keeps naming its donor's entry, so none is needed. |

## How an edit is written

`tools/webfoot/map_objects.py` holds the project document (`maps/objects.toml`) and
the build domain. A base-game object is named by its slot; an added one by an id that
never changes when it is renamed. Only NPC records are written; an edit to a
placement or scene record is refused. A move on a base-game map rewrites the four
position bytes in place, unless the project made a map from that map: then the
move is a copy, because the made map still names the original record. Anything else re-emits the map's array in the generated
expansion: kept base-game slots in their original order, then the added records,
each a copy of a base-game record. An edit to a base-game object records the
family, sprite and position it was made for, and the build refuses it when the image
no longer matches. A map the project made carries its own array and copied records,
so its donor map is never changed. The count stays one byte: 255 objects a map.
