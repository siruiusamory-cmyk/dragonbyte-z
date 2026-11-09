# Changelog

Notable changes to what a visitor or user of this project can see.

## 2026-11-08

### Runtime build checks

- Classified the ARM compiler process in the launch inventory and removed an
  extra assembly-source EOF line so the branch passes the existing CI checks.
- Selected flight/landing samples match retail; a normal movement and talk
  sequence also verifies the Krillin interaction with the dialogue backport.

### Small sprite rectangles select the exact hardware size

- Corrected 8x16 and 16x8 piece size codes. The previous longest-side inference
  selected 8x32 and 32x8 hardware objects and could read adjacent tile data.
  Explicit hardware-dimension tests and captured projectile tail pixels verify
  the correction; the five measured larger cell formats stay unchanged.

### Build the character runtime with the preserved dialogue presentation

- A [runtime build command](docs/sprite-runtime.md) now compiles the approved
  character replacements, exact palette composition, scoped two-object power-up,
  donor melee geometry and ki-flight adaptation into one LOG1 candidate. It keeps
  the 22 native fallback rows and uses the existing staged writer and provenance
  manifest. Two clean builds produce identical images and manifests.
- Controlled mGBA tests cover transformation under full actor and palette
  pressure, selected combat and projectile behavior, damage tint and dialogue.
  Natural story playback and broader gameplay coverage remain outstanding.

### Sprite bank selection keeps the retail shift

- The bank helper now returns a raw palette-bank number. The retail continuation
  performs the shift into the object attribute; shifting in both places made
  every sprite use bank zero. A forced transformation run in mGBA exposed the
  problem and confirmed restored donor and native colours after the correction.

### Sprite pieces preserve tile layout, palette indices and anchors

- Piece splitting now decodes tile order before inspecting rectangular regions,
  maps each piece into its own palette slots, and writes tile order again. Split
  cells retain the donor anchor, including mirrored offsets on flipped frames.
- The corrected partition has zero blocked Goku base, Roshi or Krillin frames.
  Four Super Saiyan rows share one blocked frame; the earlier 10/14/0/4/4 counts
  below came from treating tile data as a raster and are superseded. No pixel
  colour was changed. Runtime palette allocation and composition remain pending.

### Transformation frame-law tick correction

- The payload now accounts for the tick increment before its hook, preserving the
  eighty-tick window and the intended eleven-frame order. The assembly script also
  builds this payload. Tests cover the hook's retail context and all eighty ticks;
  this correction alone does not establish gameplay behavior.
- Sprite payloads now use the shared branch encoder, which rejects calls outside
  the ARMv4T range of four MiB in either direction. The previous duplicate encoder
  accepted unreachable targets and could silently wrap the destination.

### Legacy of Goku transformation clip: the advance law as a declared seam

- The clip's advance routine derives its frame as a shift of a per-object tick, so the
  eleven-frame clip could only ever run at sixteen ticks a frame. A four-byte call over the
  routine's increment mask is now a declared patch site, and the routine that replaces the
  law is in the tree as source: frame equals the tick divided by seven, clamped to ten, with
  the tick advanced and masked exactly as retail does and the eighty-tick cap untouched. The
  multiply-by-thirty-seven and shift-by-eight form is exact for every tick the cap allows.
- No image is emitted by this change: ten of the clip's eleven frames need two draw pieces and
  a state row names one cell per facing, so applying the law waits on that structural
  question rather than on the law.
### Legacy of Goku actor-sprite import: a frame is drawn as pieces, one bank each

- The importer now splits every carried donor frame into GBA boxes of at most fifteen
  colours, by exhaustive guillotine cuts over the boxes the GBA can actually draw, so a
  frame no longer has to fit inside one sixteen-colour bank. The split is deterministic,
  a frame that cannot be split raises an error naming the cell that makes it impossible,
  and no colour is ever trimmed or remapped to force a partition.
- The budget report measures the figures this route needs: the worst piece's colour
  count, the most pieces and the most banks any one frame draws, and how many carried
  frames have no partition at all. The approved mappings read 10, 14, 0, 4 and 4 such
  frames; Roshi partitions completely (32 frames, 46 boxes of 16x16 and 36 of 16x8, at
  most three pieces and three banks in a frame).
- Cell boxes the target's own art never draws (16x16, 16x8, 8x16 and 8x8) take their two
  attribute bytes from the law that reproduces all five measured pairs exactly: the side
  exponent of the longest side, then the shape.

### Legacy of Goku actor-draw payload: the guard owns the return

- The Legacy of Goku per-frame actor draw payload now saves `lr` in its guard
  prologue (`push {r4, r5, r6, r7, lr}`) and returns the copied retail body with
  `pop {pc}` instead of `bx lr`. The payload's `bl` into the per-piece bank
  selector left the body returning to its own continuation through the clobbered
  link register, which repeated the staging tail without bound. Both exits are
  now balanced: a refusal pops the register list it pushed, returns to the caller
  through the caller's `lr`, and writes no cursor word.
- `sprite_limits.compose_payload` replaces the copied body's final `bx lr`, and
  `sprite_limits.require_guard` decodes the assembled prologue's push, pops,
  branch targets and stores and refuses one that is unbalanced or writes through
  the render context. The ROM-gated suite covers the refusal path, the link
  register round trip and the ceiling stress, and asserts the two displaced
  retail sites instead of one.

### Legacy of Goku actor-sprite import: fallback rows as data, and the per-frame palette figure

- A sprite-import target may now declare `fallback_states`: the art-state rows that keep
  the target's own art instead of donor art. Each is verified populated in the target
  image, may not also be declared as a donor state, and is reported as `LOG1-FALLBACK`.
  The twenty-two parked rows (nine for Goku base, nine for Goku Super Saiyan, two each
  for Krillin art 46 and art 47) are now in the manifests, so the state-count check
  measures the rows that actually receive donor art: five, four, two and two.
- The budget report now also prints the worst number of distinct palette indices any one
  carried frame needs, separately from the union across every carried frame. The two
  figures answer two different questions, and the per-frame one is the binding one: a
  Legacy of Goku cell names a single sixteen-colour bank, so a frame needs at most fifteen.
  Every approved mapping fails that test as well as the union one (21, 22, 21, 18 and 18
  distinct indices in one frame for Goku base, Goku Super Saiyan, Roshi and the two
  Krillin slots), which makes the colour question a decision rather than a mapping choice.
- Nothing on this route writes an image or stores a ROM byte, and no verdict moved
  towards a pass: all five manifests still report DOES NOT FIT.

### Legacy of Goku actor-sprite import: manifest, adapter and budget

- Added `python -m tools.webfoot.sprite_import <manifest> --donor-rom <path>
  --target-rom <path>`. It reads a donor image in place, builds the Legacy of Goku
  art-cell and four-bit tile payload for every carried frame, and reports each
  target resource as FITS, DOES NOT FIT or UNKNOWN with the figure and the source
  of the limit. It exits non-zero unless every check fits, so an unmeasured limit
  stops a run instead of passing it.
- Added a versioned manifest, `webfoot.sprite-import/1`, naming the donor image by
  digest, the donor definition, the carried slots with their classification, the
  target art slot and the timing class of each animation. A timing label is never
  promoted: a MEASURED row must carry the run that measured it, an ASSUMED row the
  owner's acceptance, and a PLACEHOLDER row may carry no duration at all.
- Added the five approved mappings under `config/sprite-imports/`: Goku base and
  Super Saiyan, Master Roshi, Krillin into art 46, and art 47 as a declared
  swap-in that reuses the art 46 donor art until a custom sprite is supplied. All
  five report DOES NOT FIT on palette depth and four on the target art's own state
  count; the per-frame tile ceiling is UNKNOWN because no run has measured it. No
  image is written and no ROM byte is stored in this repository.
- A built cell now carries the target image's own object size and shape bytes for its box,
  measured across every art definition in the image (16x32 is size 2 shape 2, 32x32 is size 2
  shape 0, and three more boxes are measured). A box the image does not draw, sixteen by
  sixteen among them, is refused by name rather than given a guessed pair, and an adapted
  frame list for the Legacy of Goku II donor family is now read with that family's own
  piece reader.

## 2026-11-07

### Legacy of Goku declared-scene dialogue authoring

- Added the `scene` command group. `webfoot scene init` creates a project from a
  verified original image, optionally composing a donor dialogue presentation and
  an approved dialogue file; `webfoot scene show` prints the declared scene and
  any authored text; `webfoot scene set-text` writes one node's text into the
  project's raw document. A replacement is bounded by its own slot's measured
  capacity and is refused, not relocated, when it does not fit.
- Added `webfoot donor portrait`, `webfoot donor convert` and
  `webfoot payloads plan`. A composed patch document records payload bytes with
  their pinned digests (transferred, adapted or new) plus the relative, pointer
  and hook seams that reach them, each with the original bytes it expects.
- `validate` and `build` now consume the declared scene and the derived dialogue
  node plan. The plan is re-derived during validation, so a project whose
  declared digest was recomputed over a changed table is refused before any
  image is written.
- The declared-scene route is present in an installed build, not only when
  running from a checkout. The packaged ROM profile catalogue carries the same
  declared scene and patch sites as the in-repo copy, which is what
  `webfoot scene init` resolves against once the package is installed.

## 2026-11-06

### Trilogy direction and LOG1-first application

- Reframed the repository home around the trilogy initiative, the independent
  LOG1-first application goal, the existing SDK and all three disassemblies.
- Distinguished older desktop tools from planned authoring workflows and static
  recompilation research; clarified what the existing installation guide installs.

### Repository home and developer navigation

- Preserved the explicit original-engine acceptance boundary in the landing page.
- Replaced the long landing page with a concise SDK overview, verified Workbench
  screenshots, game-specific maturity and a direct Windows setup path.
- Consolidated installation guidance, indexed research by topic and retained the
  former homepage as historical evidence. Corrected missing documentation paths
  and labelled historical status records.
- Aligned the dependency lock with the existing Qt and test-tool requirements so
  the documented locked setup succeeds. SDK behavior and ROM identities are unchanged.

### The toolkit now has an install page and a path from a clone to a verified modification

- `INSTALL.md` states the prerequisites, the install command (`scripts\setup.ps1`,
  which installs Python 3.12 through `uv` when the host has none and runs
  `uv sync --locked` with the `dev`, `workbench` and `research` extras), how to
  verify the install, and how the `webfoot` entry point behaves. It marks the
  install commands it did not run and proves `python -m tools.webfoot --help` by
  execution.
- `docs/newcomer.md` walks five stages from supported features to validation. Each
  stage is marked executed, partially executed or not executed, with its command
  and exit code. Stages that need a game image are marked NOT EXECUTED, and the
  page says it does not demonstrate a complete workflow.
- `README.md` and `docs/README.md` route a reader to those pages and to the three
  standards below.

### A change now has a stated definition of done, a source-classification rule and a naming page

- `docs/definition-of-done.md` states what a finished change is here: an output
  reproducible from pinned inputs plus a manifest that names what changed, in
  eleven criteria, each naming how it is checked. Ten name a command or test;
  the last two are enforced by review rather than by a gate.
- `docs/source-classification.md` gives the path rule that assigns every tracked
  file exactly one of twelve classes, with the count per class and a list of what
  the rule does not classify.
- `docs/naming.md` records twelve identifier conventions with the evidence for
  each, and says which a gate enforces. It states that no gate checks module,
  class or function names.

### The capability figure says what it counts, in the visible text and the accessible name

- `src/components/ProgressStrip.astro` renders the ratio as editor capabilities
  shipped, titles the window `Editor capabilities: <percent>%`, names the progress
  bar "Editor capability coverage", and adds a scope line: the figure counts
  editor capabilities only, the acceptance target has not started, and the project
  itself is not complete.
- `src/data/project.ts` extends the percentage caveat to say the figure is not a
  measure of overall project completion.
- `src/components/Hero.astro` qualifies its buildout fraction as editor
  capabilities, and `src/components/LatestWins.astro` replaces the unqualified
  "proven at runtime or byte for byte" aside with "Newest first".
- No capability state or count changes, and no product code path, ROM profile or
  `roms.yaml` pin moves.

### The built site is built and checked in the pull-request gate

- The `prepare` job in `.github/workflows/ci.yml` builds the site (`npm ci`,
  `npm run build`), runs `tools.quality.site_check`, and runs the three test files
  that carry the site-not-built guard: `tests/unit/test_site_consistency.py`,
  `tests/unit/test_capability_registry.py` and `tests/unit/test_questline_rail.py`.
  The test partitions have no built site, so those rendered-page assertions used
  to skip there.
- Against the built page, `tests/unit/test_site_consistency.py` runs 23 tests with
  none skipped, and `tests/unit/test_capability_registry.py` asserts the qualified
  ratio and the scope disclaimer instead of the old unqualified sentence.
- The site is built and checked. This GitHub workflow does not publish or deploy
  it; the separate `deploy-site` job in `.gitlab-ci.yml`, unchanged here, remains
  the only automated publishing path and runs on the default branch only. The
  tracked `wrangler.jsonc` means a person with credentials can also publish by
  hand.
- `README.md` no longer calls the public progress site "always-current". It is
  republished when the deploy job runs, and that job does not run while the
  hosting quota is spent.

### The public-surface guard catches an identifier that begins with a screened term

- `tools/quality/_public_surface_tables.py` changes the boundary on each side of
  two of its fourteen screens: an identifier that begins with a screened term is
  caught even when an underscore follows it, while a term that sits inside a
  longer identifier is still allowed. `tests/unit/test_public_surface.py` pins both
  directions for both terms.
- Measured after the change: 1,331 tracked text files scanned, 0 findings, 24
  suppressed by a written exception. The other twelve screens are unchanged.

### A census-coupled change now reports every pin it can move

- `tools/dev/ci_tier.py` gains `measurement_lines()`, which prints every address
  pin and every exemption row a change can move, not only the one a brief names.
  The gate record writes them under a `measurements` heading.
- `tests/unit/test_ci_tier.py` pins the behaviour: a catalogue change names the
  whole-tree pin, the enforcement pin and the row counts; a change outside the
  measured set reports nothing.
- It is a report, not a gate: it does not compute a new pin for the author, and it
  does not fail a change for naming one pin.

## 2026-11-05

### The 18 Legacy of Goku script families load, decode and re-encode losslessly

- `tools/webfoot/formats/script_vm.py` decodes and re-encodes the first game's
  script records. A record is an activation-count byte followed by that many
  `0x00`-terminated segments; the byte is compared against a per-call counter by
  the interpreter, so it counts activations and not frames. Every one of the 282
  distinct record starts re-encodes to the same bytes it decoded from, unknown
  bytes included, and a structure the encoding does not cover fails with a named
  error instead of being reinterpreted.
- `tools/webfoot/data/script_specs.py` registers that encoding for the Legacy of
  Goku profile with operand widths and structure only. No opcode is given a name
  or an effect, because none has been established.
- `config/roms.yaml` and its packaged duplicate declare the 18 verified script
  families. The declaration is what makes them visible to profile validation and
  to the script loader; it grants no authoring capability.
- The interpreter keeps `record + 1` as its stream pointer, so a record start and
  a stream pointer are different addresses. A stream pointer offered as a record
  is refused for all 18 families rather than decoded at the wrong boundary.
- `webfoot event show` refuses a record-grammar family with a named, informative
  error instead of failing with an unhandled `KeyError`. It displays instruction
  blocks, and these families have none; the command does not pretend the two
  formats are the same.
- Legacy of Goku II and Buu's Fury script behaviour is unchanged. The record
  layer is opt-in per profile, and both of those codecs decode the same entry,
  block and instruction counts as before.

## 2026-11-02

### PR gate runs the selected tests in four jobs

- `.github/workflows/ci.yml` no longer runs the selected tests in one job. The
  former `gate` job is now `prepare`, which keeps every step that must happen once
  - checkout, Python setup, the classifier, the digest check and the four quality
  gates - and publishes the selected tests as the `pr-gate-selection` artifact.
  Four `partition` jobs then run that one selection under the existing
  `WEBFOOT_SHARD_COUNT` and `WEBFOOT_SHARD_INDEX` variables, with
  `--max-worker-restart=0` and the duration reporting unchanged, and a `record` job
  writes the run's one verdict and names every failing node. The selection travels
  as an artifact instead of being recomputed in each job, so the four partitions
  run the same nodes the concentrated job ran and no node is run twice, and the
  run still fails when any partition fails.
- A partition that owns no node of a small selection no longer fails the gate. A
  change touching one test file can select fewer nodes than there are partitions,
  which left a partition with nothing to run; pytest reports every node deselected
  and exits 5, and that exit used to redden an otherwise green change. Such a
  partition now says so and passes. The tolerance is narrow on purpose: it applies
  only to exit 5 with a deselected summary and no failure, error or collection
  problem, so a failing test, a missing path and a crashed worker all still fail
  the gate.
- The gate record calls a partition that was cancelled or timed out a failure. It
  previously tested only for an outright failure, so an interrupted run could be
  recorded as a successful gate.

### Test timing budgets removed

- The per-test timing guard is gone. A test that ran longer than its allowance
  used to fail the run on the GitHub runner, with a table of per-node budgets and
  exceptions maintained by hand in `tests/conftest.py`. Measured on gate run
  41398167492, five tests exceeded their allowances by one to fourteen percent on
  a slower hosted runner and failed an otherwise green suite; one of them turned
  an unrelated test red, because the session exit status the guard raised is the
  value that test reads. A wall-clock measurement of a shared runner is not a
  property of the code, so it no longer decides whether the suite passes.
- Removed with it: the budget constants, the hand-maintained exception table, the
  single-node re-run that tried to tell a regression from runner variance, the
  per-test duration recording, and the eight-minute shard ceiling in the
  full-regression workflow. Shard elapsed time is still printed, and no longer
  throws.
- Execution time stays visible. Every test-suite invocation now reports its
  twenty-five slowest tests over one second: the tiered CI selection, each
  full-regression shard, the integration runs and both local scripts. The
  adjacency runner is the one deliberate exception, because its argument vector is
  pinned by equality to forbid inserted filters. A test that gets slow shows up in
  the log without failing an otherwise green run. Two time-based failure
  conditions remain, neither a hand-maintained per-test allowance: the 120-second
  per-test cap in `pyproject.toml` and the GitHub Actions job timeouts, plus the
  local gate's own 45-minute budget.

### Qt test stability

- The text-tool theme installs its proxy style once per application instead of
  once per application call. Each reinstallation handed Qt a new style and
  destroyed the one it replaced, leaving Python wrappers of the destroyed style
  behind; that churn is the lifetime defect THEME-STYLE-CRASH-001 investigates. A
  second `apply_theme` now updates the palette and stylesheet only, and a test
  requires the installed proxy to remain the same, valid object.

### The desktop data page opens and saves a one-field project

- The data surface reports a project's authored state only for the fields a
  record's own format decodes, and the editor's save path rebuilds each enemy
  record by decoding the project's raw bytes through the codec its record size
  names. Legacy of Goku II projects therefore open and save in the desktop
  editor, and a save of an unedited project builds back to the canonical image
  byte for byte.
- A project entry that names a stat field its ROM's record format does not
  decode is reported by validation instead of being dropped without a message.
  A field the record does decode is not reported, whether or not the editor can
  edit it, so a project whose records carry a type id, a person or a technique
  count still validates and builds back to the canonical image byte for byte.
- The desktop save path refuses the same authored field rather than writing the
  project without it.

### Projects and commands for a profile that declares one stat table

- `webfoot extract` writes stat records for a profile whose enemy table decodes
  only HP, and a project built from it reproduces the canonical image exactly.
  A project record carries only the fields its own format decodes, so Legacy of
  Goku II projects hold `hp` and `raw` per enemy and no field no codec produced.
- A project that authors no stat records is treated as authoring none, matching
  how absent text and map files already behave, rather than being reported as
  missing every record it never mentioned. A project that authors some records
  is still held to the full set, so a half-written extraction is caught.
- The stat and string commands no longer name a game in their headings, and a
  stat listing now says what an identity is: a type id where the record format
  carries one, otherwise the table index.
- A supplied profile is compared with the packaged contract for every stat
  table, so one that adds a table the contract does not declare is refused as
  one that drops a table.

### Stat authoring serves a profile that declares only an enemy table

- A profile that declares an enemy stat table and no character base-stat table
  is now served by the semantic stat layer and by `webfoot stats` (`list`,
  `set`, `validate-round-trip`). Reading, editing and saving Legacy of Goku II
  enemy HP runs through the same path as Buu's Fury's: the table loads, a record
  is read, an HP edit is planned, emitted and reopened. A profile that declares
  no enemy table is still refused, and the refusal names the missing
  declaration.
- The character side is empty for such a profile rather than invented:
  `characters()` yields nothing and naming a character record is refused by
  name. A profile that declares both tables is unchanged, including its nine
  named characters.
- An enemy record is named by the identity its own record format carries. Buu's
  Fury's keys on `type_id` (`enemy:434`); Legacy of Goku II's record decodes no
  type id and has no unique field at all, so its keys are table indices
  (`enemy:41`).
- Only the fields a declared record format decodes can be edited: `hp` for
  Legacy of Goku II, with any other field name refused. `webfoot stats list`
  prints the columns a format carries, so that table lists identity, index,
  offset and HP.


## 2026-11-01

### Merge evidence

- The merge tool verifies a GitHub Actions run as test evidence: named by id and
  read through the API, it must have run against the pinned commit, have
  finished, have concluded success, and every job it reports must have
  succeeded. A run reporting no jobs is refused, because a success that cannot
  be attributed to anything that ran is not evidence. A local gate record is
  still accepted for a tree whose suite is not on Actions, and one of the two is
  required.
- Review evidence reads the verdicts the review document defines, so a review
  that approves with non-blocking notes is merge evidence and one that blocks is
  not. The older spelling is still read, so past records stay usable. The
  verdict is read by markup rather than by position: a verdict line inside a
  fenced block, behind a quote marker or in backticks is an example and is never
  read as the record's own, and findings that discuss approval cannot read as
  approval. A record that carries two verdicts disagreeing with each other is
  refused as ambiguous instead of being resolved by guessing which was meant.
- No flag accepts an asserted pass. One would read as a gate while checking
  nothing.
- A review whose verdict changes after a block is resolved states the new
  verdict in place of the old one. Two verdicts left disagreeing in one record
  are refused, because which of them is current cannot be read from the record.

### Legacy of Goku II 16 MiB runtime verification

- The Legacy of Goku II profile declares a 16 MiB generated expansion, so the
  SDK can produce a padded derivative whose first 8 MiB are the canonical image
  byte for byte and whose tail is `0xFF`. The canonical image is never written:
  every experiment runs against an independently copied fixture whose digest is
  recorded before and after.
- A padded derivative was driven through 5,520 emulated frames to an interactive
  overworld, counted from the emulator's own frame callback and driven through
  the emulator's own key API. `KEYINPUT` is read as confirmation only; nothing
  writes to it.
- A controlled derivative demonstrates a genuine guest CPU data read above the
  canonical 8 MiB boundary. A 12-byte read-only object was relocated to
  `0x08800000` and its single pointer literal rewritten; the same instructions,
  at the same program counters, retrieve the same values from the expanded
  region, and the original address stops being read. The read watchpoint channel
  is re-validated against a known boot-path load on every run, and the probe
  reports no result if that validation fails.
- The route is documented end to end in
  [`docs/research/LOGII_16MIB_RUNTIME.md`](docs/research/LOGII_16MIB_RUNTIME.md),
  including what it does not establish: one emulator in two builds, no hardware,
  a single verified expanded address rather than a range, and no claim about
  behaviour above 16 MiB or under any banking scheme.

## 2026-10-31

### Legacy of Goku II authored-image route

- The Legacy of Goku II profile declares a 384-byte free region at `0x007FEA01`,
  so the authored-image route allocates inside that profile's image rather than
  refusing for want of a declared region. The region is the window left between
  two relocation targets once the configured safety margin is taken off both
  ends, and it is zero at a 1,216-byte margin: a change to that margin re-derives
  the number rather than inheriting it.
- Declaring a free region grants no relocation capability. Legacy of Goku II text
  relocation stays refused, because its pointer table aliases - 260 slots reach
  246 distinct targets - and that is unaffected by how much room the image has.
- The route is documented end to end in
  [`docs/research/LOGII_AUTHORED_IMAGE_ROUTE.md`](docs/research/LOGII_AUTHORED_IMAGE_ROUTE.md),
  including what it does not establish: no engine was run against the declared
  region, and no claim is made about a 16 MiB image.

## 2026-10-29

### Map entries

- Added a headless 8x8 screen-entry model: it captures a rectangle of a layer's
  stitched entry plane with its map and layer identity and places it at 8x8 tile
  offsets, including across a 256x256 chunk boundary. Every destination chunk cell
  gets a copy-on-write body composed from that cell's current content with the
  rectangle rewritten and every other entry carried verbatim, so template chunks,
  canonical chunks and untouched cells keep their entries.
- The ordinal vocabulary is the map's assembled character block, not the layer's
  displayed set, so a referenced ordinal the layer never draws can be placed. An
  ordinal past the block, an assembled ordinal with no source tile, and an entry
  with palette-bank bits are refused, the last because no runtime observation of a
  non-zero bank exists. Flip bits are carried verbatim.
- Entry editing reads a cell whose layout value is an authored chunk ordinal, so an
  area the chunk placement model placed is captured and rewritten from the chunk
  that ordinal names rather than from the canonical chunk.
- The build accepts the same rule: an authored chunk body may use any ordinal the
  map's assembled character block backs, a flipped such entry included, and the
  built image carries the placed entry.
- An out-of-plane capture or destination, a shared layer record, a non-editable
  layer, a cross-map or cross-layer destination and an unresolvable authored value
  are each refused with a reason, leaving memory, history and disk unchanged. A
  placement that changes nothing adds no history entry.
- One gesture is one undo entry, undo and redo restore exact entries, and Save
  replaces the existing layout and chunk documents atomically, each on its own:
  Save is not a transaction across documents. An interrupted Save leaves a
  project that still opens, because the authored chunks are written before the
  layout that names them. A reopen reproduces
  the same entries, and two independent runs with the same edits produce
  byte-identical documents. Verified headless only: no emulator run has observed
  an authored entry or a flip bit in the game.

### Map placement

- Added a headless placement model for an editable map layer: it captures a block
  or a rectangle of chunk references, previews and places it within the same map,
  merges a drag stroke into one history entry, and replaces each project document
  atomically on its own, so a Save is not a transaction across documents;
  out-of-grid, read-only, cross-map, shared-record and unknown-chunk placements are
  refused with the SDK's own reason. It is tested without a window; no emulator run
  has observed a stamped rectangle in the game.
- The placement model refuses to open a project whose recorded base image digest
  differs from the digest the caller supplies, and a save reports the placements
  that differ from the saved document, including a placement removed by an undo
  before that save.
- Each project document is replaced atomically on Save, so a Save that fails partway
  can leave an earlier document updated, and the model stays unsaved until the Save
  reports success. A Save that reports success ends an open drag stroke; a Save that
  raises leaves it open.
- A capture reads the in-memory project, so a capture of an edited area copies what
  was placed there rather than the canonical image's blocks at those cells.

### Editor design package

- Added the first actionable design package for the native map editor under
  `docs/product/editor-design/`: one task (capture an existing feature, stamp it
  elsewhere, undo, save) specified input by input, with its capability ceiling
  quoted from the technical audit and eight annotated states drawn as SVG.
- The package records why it does not repeat the two rejected prototypes, and
  separates what is ready to build from what rests on an assumption and what is
  blocked.
- Corrections from the independent verification: a refusal the SDK does not raise
  is gone, the refusal surface and the History rows match the specification, and
  the package text passes the public-surface screen.
- The refused-preview diagram draws only the ghost cells that fit and names the
  two positions outside the layer in its inset, as the specification states.
- Placement contract corrected against the measured image: a 4 x 2 fixture layer
  with its chunk values and differing-position count replaces the impossible one,
  one block is defined as one 256 x 256-pixel chunk placement, the package states
  the chunk-arrangement scope, preview and placement and undo change memory while
  Save is the only write, and the blocking warning states what is unknown.
- The review report records those separately identified corrections beside the
  earlier findings, each marked as a correction rather than a finding.
- The independent review of those corrections is answered: the acceptance assertion
  names destination blocks beside their 0-based project-document cells, the numbering
  rule is stated once in the block definition, placements and undo apply to the
  in-memory project while Save is the only write to disk, and the two capture
  diagrams start at block 1, as the specification's well example does.
- The round two review's wording residue is gone: the drag assumption now assumes the
  in-memory cost of applying one stroke, the F26 resolution applies the batch to the
  in-memory project and re-applies its changes on redo, and the review report records
  both sentences as F36.
- The redo rule now states its invariant: while one layer authority is fixed for an
  editing session, the revalidation cannot fail, and a session that reads the layer
  authority again either starts with an empty history or revalidates every redo.
- The save count now points at the saved point rather than past it: undoing back to a
  save leaves nothing to count and disables Save, while undoing past it leaves the
  project Modified with those placements still to save.

### Continuous integration

- GitHub CI is two workflows instead of one. A pull request update starts a single
  one-job gate that classifies the change, runs the digests and the tests that tier
  selects, and runs the tree-wide quality gates; a superseded run of the same
  branch is cancelled instead of finishing.
- A documentation-only change runs all four tree-wide quality gates, architecture
  and public release included, because their rules read documentation paths.
- A deleted or renamed documentation path selects the broader `premerge` tier; an
  added or modified one stays documentation-only.
- The merge tool refuses a local gate record whose `record.sha256` digest is
  missing, malformed or does not match the record. The digest proves the record
  was not altered after the gate wrote it; it does not prove the record is
  authentic.
- The testing document states that a push to `master` runs the tiered gate only,
  and that a hosted full-suite pass is a manual dispatch.
- The full fourteen-job regression moved to a hand-dispatched workflow. The full
  suite stays mandatory before a merge through `.\scripts\local-ci.ps1` and the
  local-gate record the merge tool requires.
- The full local gate is fail-closed about its own record: it prints `PASS` only
  after `record.txt` exists and its digest was written, and a missing hashing
  cmdlet is a named failure instead of a green line with no record.

## 2026-10-28

### Repository hosting

- Development moved to GitHub: `origin` is `siruiusamory-cmyk/dragonbyte-z`, the
  GitLab remote is read-only history with its push disabled, and the merge tool
  and the workflow docs name pull requests instead of merge requests.
- The public site and the project links point at the GitHub repository.
- The merge tool pins the reviewed commit on GitHub's side, so a branch pushed
  between the review and the merge cannot land unreviewed code.

### Line endings

- The coverage documents are checked out with LF line endings on every platform,
  so a checkout matches what their renderer writes.

## 2026-10-03

### Public progress site

- Redesigned the progress site as a Frutiger Aero desktop. Each section opens
  in its own glass window, a taskbar links to every window, and sidebar
  gadgets show the buildout meter, the per-family tallies, the next phase and
  three headline measurements.
- The capability index and the latest verified wins are forum-style lists whose
  rows expand to show their detail; the roadmap to 1.0 reads as a thread with
  one post per phase.
- New hand-drawn wallpaper and icon set; every figure on the page is still
  derived from the capability registry and the project status data.
- All text meets WCAG AA contrast, interactive targets are at least 24 px tall,
  and the layout stacks into one column on phones without horizontal scrolling.

### Follow-up fixes

- The roadmap now shows Phase 3, graphics and actor authoring, as in progress,
  since graphics import has shipped; the desktop gadget reads "Working on now".
- Keyboard and reading order now follow the window layout, the taskbar no
  longer covers a focused element at the bottom of the screen, and the
  screenshot's caption is attached to its figure.
- On narrow screens the taskbar fades at its edge to show that more windows
  scroll into view.
- The taskbar is built from the site's navigation data, the wallpaper follows
  the configured base path, and a roadmap line marked as shipped without the
  expected separator now stops the build instead of rendering as planned.

### README

- Corrected the current status to the registry's 21 / 24 (88%), with AUTHOR
  4 / 7, and named the next capability after graphics import shipped.
