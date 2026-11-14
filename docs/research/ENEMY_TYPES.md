# Project enemy types

A **project enemy type** is a record the project owns, written onto one of the
sixteen rows of Buu's Fury's enemy type table that the base game never names. It
is the SDK half of "new enemy": the type exists, its statistics can be set, and a
build writes it into an image. Placing an enemy that uses it is a separate
capability and is not part of this format.

## The table

| fact | value | class |
| --- | --- | --- |
| table | 150 records of 28 bytes at ROM `0x08711274`, rows 0..149 | STATICALLY VERIFIED: `config/roms.yaml` and `tools/webfoot/data/roms.yaml`, `enemy_stats.count: 150` |
| record fields this format edits | `exp` u24 `+0x00`, `hp` u24 `+0x04`, `strength` u8 `+0x0D`, `endurance` u8 `+0x0F` | STATICALLY VERIFIED: `tools/webfoot/formats/stat_tables.py` |
| behaviour row | `+0x08`, u16 | STATICALLY VERIFIED (Phase 1): it selects the enemy's behaviour |
| descriptor | `+0x14`, a pointer whose third word is the defeat callback | STATICALLY VERIFIED |

The extent was **141** in the profile before this format existed. The bytes say
150: rows 0..149 are populated and their `+0x08` values are distinct, and row 150
is all zero. Rows 141..149 are named by retail map placements, so a "free row"
predicate written against 141 would have treated nine live rows as spare.

Two consumers deliberately keep an explicit bound of their own, because widening
them is a measurement rather than a consequence of the extent:

- `tools/webfoot/data/enemy_families.py::UNLINKED_PLACEMENT_SELECTORS` names
  placement selectors 141, 142 and 145..149. The census that proved a placement
  selector indexes the stat table covered rows 0..140, so the placement-type layer
  still reports those selectors as reference-only and the enemy randomizer's
  eligibility is unchanged.
- `tools/webfoot/formats/stat_tables.py` keeps `ENEMY_TABLE_LAST` and
  `ENEMY_RECORD_COUNT` as the evidence the 141-row readers were verified against;
  no production reader uses them, and the profile is the authority.

## The sixteen spare rows

```text
30 31 34 42 73 81 83 87 92 95 114 126 134 135 139 144
```

Measured, not inferred. Every map's object array was walked, every table loader
and every constructor call that can produce a type number was decoded, and the
union of what they select covers 134 of the 150 rows. The complement is 16 rows
after removing the rows that are used another way: 52, 53 and 55 are a scripted
three-enemy encounter built by code at `0x08039C4E`; 61 and 84 are constants in
code; 143 is a record copied by code; 11, 74 and 113 appear in the appearance
table.

"No map placement, loader or constructor names it" is a measured negative with a
known expiry: a script that computes a row at run time would not appear in any of
those three walks. No decoded script native can name a row (two independent
scans), which is what makes the negative usable.

Runtime: a donor record copied onto rows 139, 61 and 52 built, fought and died
with the donor's statistics. That is one of the sixteen rows run to a kill; the
other fifteen are measured but not run.

## The donor family

A type copies a **donor**: a retail row whose record is copied verbatim and then
edited. Only one family is offered:

| family | rows | offered |
| --- | --- | --- |
| defeat callback `0x08018951` | 89, all with non-zero HP | yes |
| defeat callback `0x0800A9B9` | 55 | no |
| `0x08018937`, `0x080333C5`, `0x08032D45` | 6 (rows 24, 58, 60, 61, 127, 140) | no |

The family is computed from the image at read time: each type record's `+0x14`
word points at its descriptor, and the descriptor's third word is the callback. A
record with no HP is refused as a donor as well. The 55-row family's defeat leaves
the body in place and still hitting the player, and the six rows on the three
undecoded callbacks were never run, so neither is a donor until a run says
otherwise.

## The project file

`enemies/types.toml`, one table per type:

```toml
[type."enemy:cave-wolf"]
row = 30
donor = 86
raw = "<the record's 28 bytes as claimed, hex>"
hp = 900
experience = 120
```

| field | meaning |
| --- | --- |
| table key `enemy:<name>` | the type's permanent identity: `[a-z][a-z0-9_-]{0,63}` after the prefix |
| `row` | the table row. Assigned once, by `claim`, from the spare pool; never recomputed |
| `donor` | the retail row the bytes were copied from. Provenance, never resolved to a row at build time |
| `raw` | the 28 bytes as claimed, hex. A build requires them to equal the base image's bytes at `donor` |
| `hp`, `experience`, `strength`, `endurance` | written only when they differ from the donor's own value |

There is no address, no offset and no other row in the file. No other project file
stores a row: another document names the type (`enemy:cave-wolf`) when one is
needed.

## Identity rules

- **Claim** takes the lowest spare row not already taken and stores it. Claiming a
  name that exists returns the registry unchanged.
- **Rename** rewrites the key, and every project document that names the old key,
  in one edit. The row, the donor and the bytes never move.
- **Duplicate** takes a new row from the pool and copies the donor and the bytes.
- **Delete** is refused while any project document names the type, and the row
  returns to the pool once nothing does. No row is retired: nothing measured shows
  a save file holds a type row, so the flag registry's retirement rule does not
  apply.
- **Reorder** does nothing. The document is written in key order, and a
  hand-reordered file loads to the same registry.
- **Statistics** are refused outside the field's width, and a value equal to the
  donor's removes the field rather than storing it.

### The behaviour row is the donor's

`+0x08` selects the enemy's behaviour, so a type keeps its donor's value. That
means a built image carries two records with one `+0x08`, which the stat layer
would have refused as a duplicate identity. The exemption is narrow: only a record
on a **spare** row may share a `+0x08`, and that record is then named by its row
(offset above every type id the image carries so a position cannot collide with
one). Two retail rows sharing a `+0x08` are still refused, because there the value
names neither record.

## Load refusals

Each is a plain message and a named test:

| input | refusal |
| --- | --- |
| two types on one row | names both identities and the row |
| a row outside the spare pool | names the row and how many rows the base game leaves unnamed |
| a donor outside the computed family, or a donor with no HP | names the donor and the family size |
| `raw` that differs from the base image's bytes at `donor` | names the row and the differing byte offsets |
| a field outside the 28-byte record | names the field and its width bound |
| a claim when every spare row is taken | states the pool size |
| a delete while a project document names the type | names the documents |

A project pinned to a different base image is refused before any of these by
`project.toml`'s `base.sha256` and `base.profile_id`, so a type is never re-seeded
with whatever sits on its row in another image.

## Build

A build writes each type's 28 bytes on its claimed row and nothing else in the
table:

- the stat domain already emits a change for every type-table record, so the type
  is written **inside** that change (the same fold the map domain needs) and a
  project that also edits the same row in `enemies/enemies.toml` is refused rather
  than silently ordered;
- retail rows are never written;
- a project without `enemies/types.toml` builds byte-identical to a build without
  this format;
- two builds of one project are byte-identical.

Measured on the canonical image: one claimed row differs, at the bytes where the
donor's record differs from the row's own record, and every other byte of the
8 MiB output equals the base.

## Not established

- A type built **by this SDK** has not been run in the engine; the runtime evidence
  is a research fixture that wrote the same 28 bytes by hand.
- The type does not appear in the game's appearance panel: the 232-row appearance
  table has no entry for a spare row, and what the panel draws for such an enemy
  was not seen.
- Placing an enemy that uses a project type, defeat descriptors and every creator
  surface are later slices. This format on its own cannot put an enemy on a map.
- The negative "no map placement names this row" is measured, not proved: a run
  that logs the row at the constructor for a full playthrough would close it.
