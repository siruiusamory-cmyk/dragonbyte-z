# Changelog

Notable changes to what a visitor or user of this project can see.

## 2026-11-02

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

### Legacy of Goku II enemy HP

- The Legacy of Goku II profile declares an enemy stat table: 109 records of
  `0x18` bytes at `0x086D56AC`, ending at `0x086D60E4`. HP is the unsigned
  32-bit value at `+0x04`, which is the only field in the record with a located
  reader: the enemy constructor at `0x0800E280` loads it and stores it to the
  entity's HP slot, and a runtime sweep found a live entity caching record 41's
  address with HP 130 matching the record's own word.
- Enemy records now come in two formats, and the one to use is read from the
  record size the profile declares rather than from which game the image is.
  Buu's Fury keeps its `0x1C`-byte record unchanged. A declared record size no
  codec implements is refused by name instead of being read through the nearest
  available layout.
- The declared record size is what keeps the two formats apart, and the
  recognisability tests are not. Buu's Fury's test accepts 109 of 109 Legacy of
  Goku II records: their small 32-bit values leave both its pad bytes zero,
  their `+0x0C` lands inside its level range, and it reads a `0x1C` window over
  `0x18`-stride data without checking stride. Reading this table through that
  codec would decode at the wrong stride with a 3-byte HP and scatter writes
  across record boundaries, so the Legacy of Goku II test is a positive
  structural check in its own right and inherits nothing from Buu's Fury's.
- Editing Legacy of Goku II enemy HP preserves every other byte of the record.
  The five remaining words are an HP-shaped value with no reader, two unknown
  fields, a near-constant enum and a pointer to a struct of code addresses;
  none is exposed as a stat, and the encoder copies the original record and
  rewrites only the four bytes of HP.
- The profile's notes previously said no Legacy of Goku II table matched this
  toolkit's stat record shapes. That was a statement about the Buu's Fury
  codec's record size and not about the ROM. The note now says so.
- A table declaration can carry an `evidence` string, as the script and string
  table declarations already could.

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
