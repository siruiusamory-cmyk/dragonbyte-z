# Enemy placements: what a project writes, and what is proven

Buu's Fury (USA). Addresses are ROM addresses in the canonical image, measured
this slice unless marked otherwise. Classes: `STATIC` (read from the image),
`RUNTIME` (observed in mGBA on a privately built image, cited from
`docs/research/P010_ENEMY_DEATH_AND_REWARDS.md` and the S0/E3 reports) or
`NOT ESTABLISHED`.

## The project document

An enemy placement lives in the map's object document, `maps/objects.toml`,
beside the characters the project already adds. It is an entry of that map's
`made` table whose `type` key names the enemy:

```toml
[objects."map:0033".made."ghoul-1"]
type = "enemy:ghoul"
x = 176
y = 152
appears = "met_ghoul"
```

| Key | Meaning |
|---|---|
| `type` | `enemy:<name>` for a type this project holds in `enemies/types.toml`; `enemy:<row>` for a base-game type, named by its row because the base game gives those types no name |
| `x`, `y` | placement `+0x0C`, signed map pixels, checked against the map's own extent |
| `appears` | the placement condition word: `always` (absent), a story flag name, or `!` and a flag name for "while clear" |
| `sprite` | placement `+0x10`. Only the sprite the base game draws this enemy with is accepted; a placement without it takes that sprite |
| `name` | display text, never an identity |

The entry's key is its identity on that map. `place_enemy`, `move_enemy`,
`duplicate_enemy` and `remove_enemy` in `tools/webfoot/map_objects.py` are the
whole write surface, and none of them touches a placement the base game made.

## The record

An authored enemy placement is 32 bytes in the retail format
(`tools/webfoot/formats/map_placements.py`):

| Offset | Field | Authored value |
|---|---|---|
| +0x00 | factory | `0x0800FD55`, the placement family |
| +0x04 | condition word | the `appears` encoding below |
| +0x08 | type row | resolved from the type identity at build time |
| +0x0C | position | two halfwords, x then y |
| +0x10 | sprite id | the donor's sprite or the placement's own, if that is the donor's |
| +0x14 | descriptor | `0x080555A0`, the descriptor those records share, whose first word is `0x0800421D` (`bx lr`) |
| +0x18 | child count | 1 |
| +0x1C | child pointer | `0x080716EC`, the child pointer those same 1,391 records share |

That tail is `RECORD_TAIL` in the codec, already in the repository for a
different reason, and the authored record reproduces it byte for byte. `STATIC`:
1,391 placement records hold exactly those three words; the remaining 168 differ
in the descriptor, the count or the child pointer.

Retail enemy placements are not editable. Moving, duplicating or removing one is
refused with a plain message, and so is a `moved` or `removed` entry for one.

## The condition word

The map loader reads placement `+0x04` before it makes the object. `RUNTIME` for
operations 1 and 2, `STATIC` for the rest, from `docs/research/P010_ENEMY_DEATH_AND_REWARDS.md`:

| Word | The loader does |
|---|---|
| 0 | builds the object |
| `(1<<16) \| flag` | builds it when the flag is set |
| `(2<<16) \| flag` | builds it while the flag is clear |
| `(3<<16) \| flag` | clears the flag and builds it when the flag was set |
| high halfword zero, word not zero | builds nothing |
| any other word | treats it as a script pointer and builds when the script's result is non-zero |

A project writes the first three forms. The flag is a `story/flags.toml` name;
`events.appearance` is the one resolver, and a name the project does not hold is
a refusal. A condition word that names a script is never written, and neither is
the clear-and-build form.

## Built-object policy

Validate refuses a map whose **built-object census** is above
`BUILT_OBJECT_POLICY`, 23. The census is `map_objects.built_objects`: for every
slot the map would load, the condition word is applied the way the loader applies
it, with a script pointer counted as building because its result cannot be known
before the build, plus one per object the project adds.

Measured on the canonical image (`STATIC`, via `built_objects`):

| Map | Slots | Unconditional | Flag-gated | Script | Census |
|---|---:|---:|---:|---:|---:|
| 134 | 23 | 4 | 0 | 19 | 23 |
| 137 | 14 | 11 | 2 | 1 | 14 |
| 32 | 51 | 0 | 0 | 51 | 0 |

23 is the largest census any of the 316 base-game maps with objects reaches, and
map 134 is that map. The engine compares no object count of its own: the known
failure mode is a malformed chain in the object-list walker above a load of
nearly twice this number, and every run at 31 built objects or fewer returned
control. The number is therefore a conservative policy that keeps a project
inside the base game's own envelope, not a boundary the engine draws, and the
refusal says so.

## Expanded storage

The record and the map's re-emitted object array are requested from the one
allocator as `MAP_OBJECT_RECORD` and `PLACEMENT_REFERENCE_ARRAY`, both with
`Addressability.EXPANDED_ONLY` at the call site, so both land at or above file
offset `0x00800000` (`.gba` address `0x08800000`) in a 16 MiB image. A project
with no enemy placement allocates nothing and builds as it did before.

## What is not established

- The behaviour of an authored placement in the running game through this exact
  path. The record format and the condition word are `RUNTIME`-proven in research
  fixtures; this product path is measured by a built image only until the
  acceptance slice runs it.
- Sprite pairings other than the one the base game draws the enemy with. Two
  swaps ran in research and neither is named in the evidence, so the writer
  accepts only the donor's sprite.
- A defeat link. Placement `+0x14` is the do-nothing descriptor; the per-placement
  defeat node is a later slice.
- An appearance-panel entry for a project type. The panel's table has no row for
  one.
- Objects created after a map loads. The census cannot see them.
