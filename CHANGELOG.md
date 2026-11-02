# Changelog

Notable changes to what a visitor or user of this project can see.

## 2026-11-02

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
- Execution time stays visible. Every pytest invocation, in the tiered CI
  selection, in each full-regression shard and in `scripts/local-ci.ps1`, now
  reports its twenty-five slowest tests over one second. A slow test shows up in
  the log without failing the run; the GitHub Actions job timeouts remain the
  only time-based stop.

### Qt test stability

- The text-tool theme installs its proxy style once per application instead of
  once per application call. Each reinstallation handed Qt a new style and
  destroyed the one it replaced, leaving Python wrappers of the destroyed style
  behind; that churn is the lifetime defect THEME-STYLE-CRASH-001 investigates. A
  second `apply_theme` now updates the palette and stylesheet only, and a test
  requires the installed proxy to remain the same, valid object.

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
- The review report records those coordinator-identified corrections beside the
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
