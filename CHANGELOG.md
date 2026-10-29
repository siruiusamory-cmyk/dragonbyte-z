# Changelog

Notable changes to what a visitor or user of this project can see.

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
  Save is not a transaction across documents. A reopen reproduces
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
