# Changelog

Notable changes to what a visitor or user of this project can see.

## 2026-10-29

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
