# Webfoot Project Format

TOOLKIT-002. A mod is a directory of text under version control, not a sequence
of edits applied to a binary.

## Lifecycle

```
webfoot extract <rom> <project-dir>
webfoot validate <project-dir> --rom <base-rom>
webfoot build <project-dir> --rom <base-rom> --output <output-rom> [--manifest <path>]
```

The base ROM is an input on every path and an output on none. A build always
writes a new image and refuses to overwrite an existing one. Extraction writes
into a clean directory: `webfoot extract` refuses a destination that exists and
is not empty, so re-running it never overwrites authored files.

## Layout

```
project/
  project.toml            identity: format version, profile, base ROM hash
  enemies/enemies.toml    141 enemy stat records
  characters/characters.toml   9 playable-character base-stat records
  text/strings.toml       1,534 strings                      (TOOLKIT-004)
  graphics/graphics.toml  sprite asset manifest + object palette (TOOLKIT-010)
  graphics/assets/        7,390 indexed PNGs, one per distinct payload (TOOLKIT-010)
  sprites/sprites.toml    one new actor-sprite identity, and its actor
  sprites/**/*.png        the source sheets that identity is drawn from
  appearances/appearances.toml   new character-appearance definitions
  raw/bytes.toml          authored raw byte writes, by file offset
  patch/edits.toml        optional: allocated payloads and the seam that reaches them
```

One file per table rather than per record: 141 single-record files would be a
worse Git experience, not a better one. Only the supported content types get
directories - no empty directories are reserved for systems that do not exist.

`raw/bytes.toml` is the authored form of a raw byte write: a `[bytes]` table
whose keys are file offsets and whose values are hex, one entry per byte range,
written by the application's own document writer. Its shape is declared once, in
`tools/dragonbyte/rawbytes.py`, and the shipping package reads it with
`tools.webfoot.project.rawbytes`; the two cannot drift, because a test reads one
file through both readers and asserts they agree. A missing file means the
project authors no raw byte, matching every other optional document.

The document states what the bytes become, never what they were. `before` is not
stored, because the base image is the only authority for it, so `build` reads the
bytes it is about to replace out of the image and the plan refuses the change
unless the image really holds them.

A raw write is an ordinary `ByteChange` with the owner `raw:<image address>`. It
joins the same single plan as every semantic domain, so a raw write that meets
another domain's bytes is the plan's overlap error rather than a silent
last-writer-wins, and a write that reaches outside the image is a validation
problem rather than a truncated emit.

`text/strings.toml` is written only when the verified profile declares a string
table, and a project without it simply authors no text. All 1,534 strings share
one file rather than being split per scene, because nothing yet knows which
scene a string belongs to and inventing a grouping would mean inventing facts.

Graphics are the bulk of an extraction - 7,390 PNGs, one per distinct container
offset reachable by a piece, against a few dozen TOML files, measured at 44.0s
versus 1.8s on the canonical image - so
`extract_project(..., graphics=False)` (CLI: `extract --no-graphics`) omits them
for anyone editing stats or text. A build from such a project is **still
byte-identical**, because unchanged graphics are re-emitted from the base image
rather than from the project. The flag costs authoring reach, not correctness.

`graphics/` is the one content type written as **files plus a manifest** rather
than as a single table, because pixels are not text: an indexed PNG is what an
image editor can open, and one file per asset is what makes an edit reviewable.
The manifest carries what a PNG cannot - the dimensions the *piece* record
declares, the bit depth, the packed extent an edit is bounded by, and the list of
characters a change would affect - so none of that has to be inferred from the
image. A shared payload appears **once**: writing a private copy per consumer
would turn 7,390 real payloads into 11,005 fictional ones and would make a global
edit look local. The object palette travels as raw GBA 15-bit words, never as
RGB, because an 8-bit triple cannot round-trip to a unique word.

**Editing a PNG is how a project authors pixels, and the build consumes it.**
Each manifest asset also records the digest of the PNG extraction wrote
(`png_sha256`) and of the indices it encoded (`pixels_sha256`). An asset whose
file no longer matches its recorded digest is an authored override: the build
decodes it, refuses anything that is not the indexed form, refuses a changed
dimension or an index above the piece's bit depth, and plans the result through
the same `GraphicsOverrides` surface the palette overrides use. There is no
registration step and no separate command - `extract`, edit the PNG, `validate`,
`build` is the whole workflow, and one resolver runs in both `validate` and
`build` so the two cannot disagree about which graphics a project authors.
Palette and pixel edits merge into the one write plan, so neither can overwrite
the other.

A re-encoded payload that fits the extent its original container occupied is
written in place, and the bytes between the new payload and the end of that
extent are left untouched rather than rewritten. A payload that does not fit is
placed by the allocation authority and every confirmed reference to the old
payload is rewritten in the same batch; the original bytes are left intact, so a
reference this toolkit did not discover still reaches the art it always reached.
`docs/research/GRAPHICS_PIXEL_OVERRIDE.md` records what is proven about that
boundary, including the one property it leaves `UNKNOWN`.

Build outputs (`.gba`, manifests) are artefacts and belong outside the authored
tree; the repository `.gitignore` already excludes them. Extracted PNGs are
ROM-derived and are likewise never committed.

## `project.toml`

```toml
[project]
format_version = 1
name = "buus_fury_usa_rev0_01c1707f"

[base]
profile_id = "buus_fury_usa_rev0_01c1707f"
game = "buus_fury"
sha256 = "940ad5f01db4465b8877dfe739510cbf34f4ea3d390f3df13519808bc36f059e"
size = 8388608
```

`sha256` is the contract: a build against any other image fails closed.
`profile_id` is checked independently, because a matching hash with mismatched
table extents would still be wrong.

**No filesystem path is recorded.** A path is a fact about one machine, and a
project that pinned one would stop being portable the moment it was cloned.

## Records

The wolf, exactly as extracted from the canonical ROM:

```toml
[enemy.434]
type_id = 434
hp = 175
exp = 225
level = 60
strength = 10
power = 0
endurance = 20
raw = "e1000000af000000b20100003c0a0014808000002089700829117108"
```

A profile whose enemy record decodes one field extracts one field. Legacy of
Goku II's record is `0x18` bytes with HP at `+0x04` and no `type_id`, so its
entries carry `hp` and `raw` and are keyed by table index:

```toml
[enemy.41]
hp = 130
raw = "1400000082000000150000000302038080000000c4f36f08"
```

- **The table key is the durable identity**, not a table position. Enemy
  identity keys on `type_id`, which DATA-001 verified is unique across all 141
  Buu's Fury records. A record format that decodes no `type_id` and has no
  unique field - Legacy of Goku II's, measured across its 109 records - keys on
  the table index instead, which is unique by construction but is a position;
  `docs/rom-profiles.md` states which format uses which. Character identity keys
  on roster position and remains the weaker of the two, carried forward
  unchanged from TOOLKIT-001.
- **A record carries the fields its own format decodes.** `type_id` and the six
  Buu's Fury stat fields are not a universal shape, and a project that omitted a
  field its ROM decodes is reported during validation rather than at load.
- **Values are semantic.** No offsets, no addresses. A project that stored them
  would break whenever anything moved and would be meaningless to a future
  decomp backend.
- **`raw` carries the record's undecoded bytes**, verbatim, and is validated
  against the base image during validation and build. Both layouts have spans
  this project has not decoded - 12 bytes of enemy after-battle data, 6
  character technique ids, the pad bytes - and byte-identical reconstruction
  requires every one of them. It is not intended for hand editing; a missing or
  tampered `raw` is refused rather than defaulted.
- **Enemies carry no alias.** This project has verified names for the 9
  characters and for no enemy, so extraction emits none rather than inventing
  labels that would then read as extracted facts. The slot exists for when a
  source is verified.

## Strings

TOOLKIT-004. Text is variable-length, so it is authored differently from a
fixed-stride record:

```toml
[text."text:0010"]
text = "New Game"

[text."text:0041"]
text = "{08:05}HP:{08:02} {08:76}%d{08:05}/{08:76}%d{08:02}"
```

- **The key is the pointer-table index**, zero-padded to four digits so lexical
  order matches numeric order. It is identity because the game reaches a string
  *through* the table - see `docs/research/TEXT_FORMAT.md`.
- **`{08:XX}` is a control code**, `XX` being the operand byte in hex. The
  operand's meaning is `UNKNOWN` and is preserved rather than named. `{{` is a
  literal brace, so ROM text containing `{08:02}` cannot be mistaken for a
  control code on the way back in.
- **`%d` and `%s` are ordinary text.** The game's formatting is in-band ASCII,
  not control data.
- **Newlines are real newlines**, escaped as `\n` by the TOML emitter.
- **There is no `raw` blob and no address.** A stat record needs `raw` because
  only part of its stride is decoded; the text codec is lossless over the whole
  pool, so the authored string already *is* the complete description of its
  bytes. A second copy could only disagree with the first.

**Editing is in-place.** The pool is exhaustively tiled, so a string has no slack
to grow into: replacement text must fit the original allocation, and shorter text
is zero-padded to it deterministically rather than repacking the pool. Longer
text needs relocation, which needs profile-declared free space. Buu's Fury declares
one small verified region (`[0x007EA400, 0x007EA500)`, 256 bytes, TOOLKIT-028),
which is far too small to relocate a text pool, so canonical growth is still
refused with the exact byte deficit. The relocation machinery itself is proved on synthetic fixtures.

**Repeated text is not shared text.** 153 texts occur more than once, but each
occurrence has its own bytes, so editing one changes only that one.

## New actor sprites

SPRITE-NEW-PROJECT-SURFACE-001. A **new actor-sprite identity** is content the
canonical image does not contain: a sprite the engine answers to by an id it has
never had, plus the one map actor that draws it. `sprites/sprites.toml` describes
exactly one, and the sheets it draws from are PNGs beside it.

```toml
[sprite.cui]
sprite_id = 307
donor_sprite_id = 10
free_palette_entries = [8, 9, 103, 193, 236]

[sprite.cui.animation.stand]
sheet = "sprites/cui/stand.png"
frames = 2

[sprite.cui.animation.walk]
sheet = "sprites/cui/walk.png"
frames = 4

[sprite.cui.actor]
map = "map:0102"
family = "map-sibling-08017da3"
position = [209, 580]
retained_raw = 0
data_pointer_raw = 142104172
behaviour_template = "map:0102/object:0007"
wander_box = [192, 544, 272, 624]
```

- **Exactly one identity per build, and that is a property of the image.** An
  identity is added by growing the character registry and repointing the two
  literal words that name it, so a second identity in one build would grow the
  same registry again and point the same two words at a different table. A
  document declaring two is refused rather than half-applied.
- **`sprite_id` is stated, not derived.** The engine id an identity answers to is
  the id its appended registry entry yields, and the planner accepts exactly that
  number; stating it is what keeps a build from silently attaching an actor to an
  id this build did not author.
- **`donor_sprite_id` names an identity the image already contains, and it
  supplies both the geometry and the shape.** Its character-structure header is
  cloned and its first frame supplies the geometry every authored frame copies -
  placement offsets, pixel extents and packed OAM attributes. Before that, every
  frame of every animation slot the donor structure names is decoded (a slot whose
  animation word is null names no record and is skipped) to measure the one frame
  rect the donor proves: `width x height`, its anchor, its pixel count and its
  piece count (`sprite_identity.measure_donor_envelope`). A donor whose own frames
  occupy more than one rect, or one rect at more than one anchor, proves no single
  shape or placement and is refused, and every sheet cell must be exactly the
  measured rect. A larger cell is a composition shape this build cannot prove and
  a smaller one would need a placement nothing has measured, since the authored
  frame copies the donor's own anchor; both are refused. The docstring of
  `sprite_identity.plan_new_sprite_identity` and
  `docs/research/SPRITE_NEW_COMPOSITION_GUARD.md` carry the measurement.
- **Animation slots are ordered by name.** A TOML table has no order to inherit,
  and the engine reads an animation by its slot index, so the order is a stated
  rule: `stand` precedes `walk`, and a build emits them in that order.
- **A sheet is one row of square cells in four facing groups**, `frames` of them
  per facing. The file's own width states the same count, so a sheet whose
  dimensions and declaration disagree is refused instead of resolved by
  preferring one. Eight-bit RGB and RGBA are both accepted; a fully transparent
  pixel is a hole and becomes the transparent entry, and a partly transparent one
  is refused because a sprite pixel is one palette index. The hole a sheet draws
  in colour rather than in alpha is `(255, 0, 255)`: that is the chroma key the
  planner uses, a fully transparent pixel's colour is normalised to it, and a
  pixel that is that colour is a hole whether the sheet meant it or not.
- **`free_palette_entries` is the author's claim, and it is checked.** The SDK
  decodes the actor-sprite graphics but not every payload that shares the 256-entry
  object palette, so it cannot derive which entries are free; it verifies the
  claim against what it can prove - no decoded actor-sprite graphic draws a
  requested entry - and refuses an entry that fails rather than recolouring
  another asset.
- **The actor is authored, carried or resolved, and the three are kept apart.**
  `map`, `position` and `wander_box` are authored. `retained_raw` and
  `data_pointer_raw` are the new object header's `+0x04` and `+0x0C` words, whose
  meanings are UNRESOLVED: they are stored as the raw words they are, carried
  verbatim, and never dereferenced. `behaviour_template` names an existing slot of
  the **same** map's object array; the build copies that record's inline behaviour
  entry and writes the authored wander box into it, so the actor starts from a
  behaviour the engine already runs on that map. A ROM address is not an
  authoring API and is never accepted here.
- **Two combinations are refused because only one writer can win.** The actor's
  plan re-emits that map's `MapEntry` record and object array, so a project that
  also edits that record's fields, or gives that map an authored placement
  expansion, is refused rather than silently dropped or reported later as a
  byte-range overlap.

## New appearance definitions

APPEARANCE-AUTHORING-GATE-001. A **new appearance definition** is one more record
in the engine's character-appearance table: an identity the image does not have,
naming an on-screen name it already holds and the sprite identity that draws it.
`appearances/appearances.toml` describes one or more.

```toml
[appearance.new_face]
text_index = 1188
sprite_id = 10
```

- **The record's own identity is its position in the table, and the build assigns
  it.** The engine addresses record `i` as `table + 16 * i` with no bound check, so
  an appended definition is index 232, then 233, in the document's own name order.
  A raw offset is not an authoring API and is never accepted here.
- **The whole table moves, because it cannot grow where it is.** The canonical
  extent ends exactly where a literal-named descriptor block begins, and the count
  is three compiled `cmp rN,#0xE8` loop bounds rather than a stored number. The
  build therefore re-emits the table above the original end of the image with the
  authored records appended, rewrites the five literal-pool words that name it and
  patches the three bounds. The canonical records are copied verbatim, not
  re-encoded, so an untouched definition keeps its own bytes.
- **`text_index` names an existing string.** It is the record's `+0x00`, an index
  into the profile's declared text pointer table; the record's `+0x02` is written
  as its successor, which holds on 232 of 232 canonical records. Creating a new
  text-table id is not shipped, so an authored definition shares a name with the
  retail definition that already uses that index rather than inventing one. An
  index whose successor is outside the table is refused.
- **`sprite_id` binds a sprite identity no canonical record selects**, or the id
  an authored actor-sprite identity in the same project takes. The engine's search
  returns the earliest matching record, so an id a retail record already selects
  would make the appended record either unreachable or a replacement for that
  record's resolution; such a document is refused. Sprite id 149 is refused too,
  because the engine remaps it before it compares. A value below the accessor's floor of 10 and a value the registry
  does not reach are both refused.
- **The portrait slot and the stat index are not authorable here.** The record's
  `+0x08` and `+0x0C` are written to the two corpus-legal defaults the SDK states
  (no portrait, no stat record), which 98 and 88 of the 232 canonical records
  already carry. Offering either as a field would mean authoring a portrait or a
  stat record, and no shipped surface does.
- **The count bound is enforced, not discovered later.** The engine keeps one seen
  bit per record in a 232-bit array and the block initializer zeroes a word just
  past it, so at most 8 records may be appended to the 232 the image has. That bound
  is INFERRED, and it is below the 255 a Thumb `cmp rN,#imm8` could state: the
  encoding is not the binding limit.

## Dialogue scene text and patch payloads

DIALOGUE-BACKPORT-001. Two optional documents extend a project whose profile
declares the surface they need. Both are authored through commands, so a person
never types a file offset:

```
webfoot scene init <project> --rom <base-rom>
webfoot scene show <project> --rom <base-rom>
webfoot scene set-text <project> --rom <base-rom> --node 0 --text "..."
webfoot donor portrait <project> --donor <donor-rom> --name "Master Roshi" --slot 97
webfoot donor convert <project> --donor <donor-rom> --name "Master Roshi" --slot 97 \
    --name Goku --slot 57 --box
webfoot payloads plan <project> --rom <base-rom>
```

`scene set-text` writes `raw/bytes.toml`, because a dialogue line is a raw byte
write with one extra fact: how much room its slot has. The profile's `scene_text`
block declares that record, its node layout and the exact node indices of one
scene, so a replacement is bounded by the canonical slot and padded with spaces;
a replacement that does not fit is refused rather than relocated. A node outside
the declared scene is refused, and unsupported control codes are never invented.

`patch/edits.toml` states the three things a raw write cannot: bytes that have no
address yet, the seam that reaches them, and where those bytes came from.

```toml
[[payload]]
label = "bf-presentation"          # lower-case words joined by "-"
file = "assets/bf-presentation.bin"
source_class = "new"               # transferred | adapted | new
origin_note = "..."                # prose only; never provenance
sha256 = "..."                     # the build recomputes it and refuses a mismatch
transform = "identity"             # the named transform that produced the bytes
alignment = 4                      # power of two, 4..256
code = true                        # a method-table target must be executable

[[relative]]
site = 0x00ef30                    # the seam, as a FILE offset
expect = "5964ffff"                # the canonical bytes there, or the build refuses
base = 0x0800ef28                  # the ROM table base the stored value is relative to
target = "bf-presentation"
origin_note = "..."
```

Three seams, one encoder each: `[[hook]]` is an ARMv4T Thumb `bl` (±4 MiB from
`site + 4`); `[[pointer]]` writes an allocated address into a 4-byte word; and
`[[relative]]` stores `(payload_gba + 1) - base` as a signed 32-bit value for a
consumer that adds its own table base, which is what the LOG1 NPC dialogue method
table does. The absolute pointer encoder refuses a relative site, and a `relative`
entry refuses a target that is not declared `code`.

A `[[pointer]]` has two forms. `site` + `expect` overwrites a retail word, guarded
by the canonical bytes there. `in` + `at` fills a FIXUP word inside an allocated
payload (`in = "bf-portrait"`, `at = 0x1c4`): the payload is named explicitly, the
four bytes must be reserved zeros, `at + 4` must lie inside the payload, and two
fixups may not claim one slot. An offset alone never identifies a block - two
payloads can hold the same offset - so a document that fills a word has to say
which payload owns it.

Payload placement is the same allocator every other domain uses: the lowest
aligned first fit inside the profile's declared `free_regions`, guarded by the
document's `expect` bytes, the payload digest and donor fingerprint, and the
project's destination protections. A `transferred` or `adapted` payload without a
donor digest and span is refused; `new` code carries neither. A payload that does
not fit the declared windows fails closed - it never reaches above the end of the
image unless the profile declares an expansion.

`donor convert` builds ONE shared low 128-entry palette over every piece it is
given, because on the GBA only OBJ index 0 is transparent: donor index 0 takes
slot 0, every other donor index - including one that paints the same BGR555 black
- stays opaque in slots 1.., and entries 128..255 keep the target's own art. It
refuses rather than quantising when the opaque colours exceed 127.

`scene init --presentation` composes `sites.toml`, `box-sites.toml` and
`text-sites.toml` in that order. A later declaration that claims a retail seam an
earlier one already claims SUPERSEDES it, and a payload nothing reaches is not
composed, so the box hook and the text controller replace the behaviour-preserving
pass-throughs at their own seams without any lane editing another lane's source.

The presentation declarations compose compatibility CODE, not extracted data:
`presentation.bin`, `portrait.bin`, the three box blocks and the text controller are
assembled from the `.s` sources committed beside them, and the assembled bytes are
generated output (`*.bin` is ignored) rather than tracked. The shipping workflow
therefore assembles them before the first `scene init`, from a clean checkout and with
nothing else on the machine:

```
powershell -NoProfile -ExecutionPolicy Bypass -File assemble.ps1      # presentation, portrait
powershell -NoProfile -ExecutionPolicy Bypass -File assemble-box.ps1  # box blocks, text controller
```

Both scripts are deterministic and ROM-free: one `arm-none-eabi-as` pass over tracked
source, `objcopy` to flat bytes, and for the box a symbol-boundary split. Each
declaration pins the digest of the file it composes, so the initializer refuses a
missing payload or a payload the source does not produce, naming the script to run.
`tests/unit/test_presentation_payloads.py` copies exactly the tracked files of the
declaration directory into an empty directory, runs both assemblers there and checks
every declared digest, so the workflow is proved not to need a workstation's leftovers.
Donor art, palettes and the font stay out of Git: they are extracted from a verified
donor image at `scene init` time and never tracked.

## Dialogue replacements

`dialogue/replacements.toml` rewrites existing compressed-dialogue records in place
and repacks the container when the new text is longer:

```toml
[dialogue."record:0:0x91B4"]
text = "A Saiyan got you, Goku. King Kai waits. Go."
```

The key is the record's own **selector and decoded start**, the anchor the
authoring operation preserves: a replacement splices at the record's end, so the
start names the same record in the base image and in every derivative built from
it. A registry name such as `goku-greeting` is also accepted; an anchor is what a
record the registry does not carry uses. Resolution reads the image's own record
inventory, so an anchor that names no record is refused by name rather than
guessed at.

The record's portrait operand, its text token window and its capacity are not
authored here: a replacement that does not fit the container is refused with the
byte deficit, and the portrait byte is carried unchanged.

## Conversation scripts

`dialogue/scripts.toml` authors the code block a conversation record runs, in
place:

```toml
[script."conversation:0x087809EC"."0000"]
prior_instructions = ["push_byte 2", "native_stack 27", "terminate"]
instructions = ["set_save_flag 228", "push_byte 2", "native_stack 27", "terminate"]
```

The key is the address of the word array the dialogue runner holds as its first
word, and the entry is that array's own index. A dialogue record's kind selects a
handler, and kinds 0 and 2 run a script before the box is drawn, so this is where
a conversation can change save state: the engine's flag SET is native slot 29,
declared as `set_save_flag` with one flag number.

`prior_instructions` is what the canonical body decodes to, and an image whose
body decodes differently is refused. The room is **measured, never authored**: it
runs from the code block to the next record the conversation's own array can
select, and the authored body must fill it exactly, because a shorter body would
leave canonical instructions reachable after a terminate. The body is a mnemonic
list for the profile's verified opcode set, so it can only contain instructions
the toolkit decoded from canonical bytes; a forward branch takes its two-byte
displacement as written.

## Determinism

Given the same project files, the same verified base ROM and the same toolkit,
the output ROM is byte-identical across repeated builds. This is asserted, not
assumed:

- records are ordered by durable identity, never by table position or by
  filesystem traversal order;
- files are written LF and end with exactly one newline, so extraction does not
  depend on which machine ran it;
- authored files and build manifests contain no timestamp, path, hostname,
  username or random value.

Writing is a small in-repo TOML emitter rather than a dependency: Python's
stdlib `tomllib` parses TOML but does not serialize it, the authored schema is a
closed set of integers and short strings, and key order, integer formatting and
quoting all have to be ours for determinism to be a property we can test.

## Build manifest

```json
{
  "schema_version": 1,
  "base": { "profile_id": "...", "sha256": "940ad5f0..." },
  "output": { "sha256": "9e714ca4...", "size": 8388608 },
  "changed_byte_count": 1,
  "changes": [
    {
      "offset": 7412700, "offset_hex": "0x00711BDC", "size": 28,
      "owner": "enemy:434", "reason": "enemy edit: hp",
      "old": "...", "new": "..."
    }
  ],
  "project": { "name": "...", "format_version": 1 }
}
```

Every emitted byte change names the semantic owner responsible, so the manifest
answers *which edit changed these bytes*, not merely *these bytes differ*.

`changes` is the guarded WRITE set, not a diff. Each entry is the span one owner
wrote: `old` and `new` are that whole span, and a span may contain bytes that
already equal the canonical image - a code payload's 0xFF padding landing in a
0xFF free window, or an authored line's space padding. `changed_byte_count` counts
the bytes that actually differ, so it can be smaller than the summed `size`.
A verifier of diff confinement therefore checks that every differing byte lies
inside a declared span, never that every declared byte differs. The exact set of
differing offsets is recomputed from the base and the output image, and is not
required to equal the declared spans; a build's own manifest is the reproducible
provenance record, not a substitute for that recomputation.

## Validation

`validate` checks, and `build` re-checks before writing anything:

- project schema and format version;
- profile support and base ROM hash/size agreement;
- identity key and `type_id` agreement;
- semantic field ranges (enemy and character `level` cap at 200, from P-010's
  `cmp r6,#0xc8` at `0x08013A00` in the EXP award path);
- `raw` presence, length, and agreement with the base image;
- for a raw byte document: that it parses, that every key is a file offset and
  every value an even-length hex string, and that every write lies inside the
  canonical image. A document that cannot be read is refused, never read as "this
  project authors no raw byte", because that reading would emit the canonical
  bytes while reporting success. An entry that changes nothing is refused with its
  offset named, for the same reason: it cannot become a change, and dropping it
  silently would leave a person believing an authored write shipped;
- records the ROM lacks, and records the project omits;
- for text: identity key form and range, encodability (unsupported characters,
  malformed `{08:XX}` tokens, embedded NULs), whether the encoded text fits its
  allocation, duplicate identities, strings the ROM lacks, and strings the
  project omits;
- for a new actor sprite: every source sheet (present, the accepted PNG form, the
  declared frame count), every claimed free palette entry against the decoded
  corpus, the behaviour template against its map's own object array, and both
  placements. Validation runs the same materialization the build does, so the two
  cannot disagree about what may be authored.

A failure names the offending entity and field. Nothing is written when
validation fails.

## One plan per build

Stats and text produce their changes separately but are validated and applied as
a **single** write plan. Overlap detection is per-plan, so two subsystems in two
plans could each look valid while together writing the same bytes; merging turns
that into a hard error instead of silent last-writer-wins. Raw byte writes are
one more contributor to that plan, not a second writer: an authored raw write and
an authored stat edit are the same kind of thing to the plan and to the manifest.

## Protected ROM destinations

A write is refused when its destination would overwrite a protected ROM input,
by **file identity** rather than by content or by name
(`tools.webfoot.destination`). Identity is the rule because a derivative has
different bytes and a hard link has a different name, and both would otherwise
pass:

- the destination IS a protected input, by the filesystem's own identity or by
  resolved path;
- the destination is a **hard link** to one, which is one file under another name
  and cannot be written independently of it;
- the destination resolves inside a protected input directory, **including one
  reached through a directory junction or symlink**, because the destination is
  resolved before it is compared. The provenance manifest is a destination this
  path writes, so it is held to the same rule as the image.

The protected directory names are `destination.PROTECTED_INPUT_DIRECTORIES`: that
tuple is authoritative, and the tracked ignore rules are consulted only to confirm
a listed name is still declared there. A name dropped from the ignore file stops
being protected; a newly ignored directory is not protected until it is listed,
because `build/` is ignored as generated output and no parser can tell an input
directory from an output one.

What is not refused: a distinct derivative whose directory merely contains a ROM.
A directory holding an input is not itself an input, and an output chosen outside
a protected directory is written normally.

These checks are preventive: they stop a write before it happens. They are
complemented, not replaced, by the digest rules, which are detective - they
notice a wrong or damaged image after it exists.

## Not in this format

No anchors, pointer graph, relocation, allocator or free-space management appear
in the authored files of the table documents. Fixed-stride stat records need none
of them, and text relocation stays blocked on Buu's Fury for want of declared free
space; TOOLKIT-003 proves those mechanisms separately. `patch/edits.toml` is the
one opt-in exception, and it holds a request, not a placement: the address is
computed by the build's single allocator and recorded in the manifest, so no
authored file ever names one.
