# ROM Profiles

Profiles are cryptographic identities, not fuzzy classifiers. `config/roms.yaml` is authoritative for the CLI.

## Verified configured profiles

### `buus_fury_usa_rev0_01c1707f`

- Title: Dragon Ball Z: Buu's Fury
- Region: USA
- Game code: `BG3E`
- Revision: 0
- Size: 8,388,608 bytes
- CRC32: `01c1707f`
- MD5: `3a74fce97f1ea2b28c2a50ec3df0acee`
- SHA-1: `f1c4b07554d2a3b1ad2f325307051e775ce68087`
- SHA-256: `940ad5f01db4465b8877dfe739510cbf34f4ea3d390f3df13519808bc36f059e`
- Evidence: local reproducible observation; `2genkidev/buusfury@cc53d0cd2d1c167e749419187e2d92017ac07468`, `README.md:6`
- Confidence: `CONFIRMED`
- Compatibility: exact local/disassembly base. No compatibility claim with the recomp profile.
- MapEntry table: GBA address `0x0808E2E0`, file offset `0x0008E2E0`, 452 records of `0x38` bytes. This metadata is profile-scoped and independently corroborated by target-ROM code inspection.

### `buus_fury_usa_rev0_dcf23468`

- Title: Dragon Ball Z: Buu's Fury
- Region: USA
- Game code: `BG3E`
- Revision: 0
- Size: 8,388,608 bytes
- CRC32: `dcf23468`
- MD5: `808eda67b17c901e9052f47bdc419e2f`
- SHA-1: `e65738e9d67688309f09811a54f495523ec9aada`
- SHA-256: `15df2fbbe072cc5d28a699ae9af9c56657e290cdb47c92e57d6ce14a01be4b64`
- Evidence: `mstan/DragonBallZBuusFuryRecomp@453a913a9f67916b9b358776da1c1229b09a6c80`, `baserom.md`
- Confidence: `CONFIRMED` as the upstream requirement
- Compatibility: distinct from the local profile. Binary differences are unresolved.
- MapEntry table: intentionally unconfigured. No table metadata transfers from the local profile.

### `legacy_of_goku_usa_a3c8c767`

- Title: Dragon Ball Z: The Legacy of Goku
- Region: USA
- Game code: `ALGE`
- Revision: `UNKNOWN` and intentionally unconstrained
- Size: 8,388,608 bytes
- CRC32: `d47ccff4`
- SHA-1: `a3c8c76742f11fc6a3f6e3fcca20992458cac0b5`
- SHA-256: `3ba9919e26704b0f5fdc2bfabc7f7a0404c71413761d38abcd94224c3bd4b1b9`
- Evidence: `mstan/DragonBallZLegacyOfGokuRecomp@fbe502a3d44256402262cd3f5baeb072a7235932`, `baserom.md`
- Confidence: `CONFIRMED` as the upstream requirement; revision remains `UNKNOWN`

### `legacy_of_goku_ii_usa_rev0_204142e1`

- Title: Dragon Ball Z: The Legacy of Goku II
- Region: USA
- Game code: `ALFE`
- Revision: 0
- Size: 8,388,608 bytes
- CRC32: `204142e1`
- MD5: `4e1565aa1f0627c2bf5e51019440cb70`
- SHA-1: `18e0715dec419f3501c301511530d2edcd590f8b`
- SHA-256: `6e6c370c339ec9171cb1956adf837a0d342a197f78964882ef46c3086656ff75`
- Evidence: `mstan/DragonBallZLegacyofGokuIIRecomp@add98b5d76fb2b822be870f29fa27b22c9a95631`, `baserom.md`
- Confidence: `CONFIRMED` as the upstream requirement
- Enemy stat table: GBA address `0x086D56AC`, file offset `0x006D56AC`, 109 records of `0x18` bytes, ending at `0x086D60E4`. HP only; see below.

## Enemy stat records: two formats, selected by declared record size

Two games declare `enemy_stats`, and they are not the same record format.

| Profile | Record size | HP field | Editable fields |
| --- | --- | --- | --- |
| `buus_fury_usa_rev0_01c1707f` | `0x1C` | u24 at `+0x04` | exp, hp, level, strength, power, endurance |
| `legacy_of_goku_ii_usa_rev0_204142e1` | `0x18` | u32 at `+0x04` | hp |

The codec is chosen from the record size the profile declares, by
`formats.stat_tables.enemy_codec_for_record_size`. A declared size no codec
implements raises `UnknownEnemyCodecError`; there is no default and no nearest
match, because reading an unverified layout through the wrong codec produces
plausible nonsense rather than an error. Nothing on this path asks which game it
is looking at - that coupling was removed in TOOLKIT-005 and is not reintroduced
to add a second game.

**The selector is the safety boundary, and the recognisability tests are not.**
Measured against the canonical Legacy of Goku II image, Buu's
`looks_like_enemy_record` accepts 109 of 109 records of the LOGII table. A LOGII
record's unsigned 32-bit values at `+0x00` and `+0x04` are small enough to leave
`+0x03` and `+0x07` zero, which satisfies both of Buu's pad-byte gates by
accident; `+0x0C` lands in 1..200, which satisfies its level gate; and it reads a
`0x1C` window over `0x18`-stride data without ever checking stride, so it is
loose here rather than strict. A review measured 312 further 4-aligned offsets
near the table that also pass it. Pointing the Buu codec at this table would
therefore decode at stride `0x1C` with a 3-byte HP and scatter writes across
record boundaries. What prevents that is the declared record size, not a
predicate.

The LOGII predicate is a positive structural test in its own right and does not
call, wrap or fall through to Buu's. It checks what held across all 109 records:
HP at `+0x04` inside the observed range 1..10,200, the `+0x10` word within its
three measured values, and `+0x14` resolving inside the GBA ROM window. The HP
range is a **declared** bound taken from the observed corpus, not a proven engine
limit - nothing in the ROM was found to enforce it - so a value above it is
unrecognisable as a record while still being legal to write. The unsigned 32-bit
width bound the encoder checks is separate from it.

An earlier survey reported that no LOGII table matched this toolkit's stat record
shapes. That was a statement about the codec's record size, which is `0x1C`
against LOGII's `0x18`, and it was read as a statement about the ROM.

### Why Legacy of Goku II exposes HP and nothing else

HP is the only field in the record with a located reader. The enemy constructor
at `0x0800E280` loads it with `ldr r0,[r1,#4]` at `0x0800E2E6` and stores it to
`[entity+0x188]` with `str r0,[r5,#8]` at `0x0800E2EA`. The record's other five
words are preserved byte for byte by `encode_log2_enemy_record`, which copies the
original and overwrites only the four bytes of the HP span:

| Offset | Why it is not exposed |
| --- | --- |
| `+0x00` | u32, HP-shaped across the table, but no reader was found. Naming it a stat would be a guess. |
| `+0x08` | u32, 23 distinct values, no reader found. |
| `+0x0C`, `+0x0D`, `+0x0E` | Three separate unsigned bytes, not one packed word: the scouter reader loads each with its own `ldrb`, at `[r6,#0xC]`, `[r6,#0xD]` and `[r6,#0xE]`. |
| `+0x0F` | Takes three measured values (`0x26`, `0x40`, `0x80`); no reader found. |
| `+0x10` | Takes only three values across the table. A near-constant enum, not a stat. |
| `+0x14` | A pointer to a descriptor struct whose words are code addresses. Writing it would corrupt control flow. |

`character_base_stats` stays undeclared for Legacy of Goku II: no character
base-stat table has been located in that image. The semantic `StatTables` layer
serves a profile that declares only `enemy_stats`, so LOGII enemy HP is read,
edited and saved through the same API and the same `webfoot stats` commands as
Buu's Fury's: the enemy table loads, the character side is empty, and an edit
accepts only the fields the declared record format decodes - here, `hp`.

### Naming an enemy record

Buu's Fury's record decodes `type_id` at `+0x08` and the canonical table carries
each value once, so an identity key is that type id: `enemy:434`. LOGII's record
decodes no type id, and a census of its 109 records found no unique field at all
- the widest is 92 distinct values at `+0x0C`, and `+0x08` takes 23 - so its key
is the table index: `enemy:41` is record 42, at file offset `0x006D5A84`. Which
scheme applies follows the record format the profile declares, never the profile
id. The index is unique by construction and stable for a given image, but it is a
position rather than a property of the record: nothing may grow or reorder the
table today, and a table that could would need a new identity scheme rather than
a reinterpreted index.

## Header-only upstream support

DragonByteZ additionally recognizes `ALGP` LoG Europe revision 0, `ALFP` LoG II Europe revision 0, `ALFE` LoG II USA revision 0, and `BG3E` Buu's Fury USA revision 0. Its pinned implementation checks game code, 8 MiB size, and revision but supplies no cryptographic whitelist. These are not configured as verified profiles without hashes.

## Matching rules

1. Configured SHA-256 must match exactly.
2. Every other configured hash and metadata constraint must also match.
3. Exactly one profile must survive.
4. Header/size matches without a cryptographic match are `UNKNOWN`.
5. A cryptographic match plus contradictory metadata is `CONFLICT`.
6. Multiple exact matches are an error.

Distinct hashes normally remain distinct profiles even if title, game code, revision, and size agree.
