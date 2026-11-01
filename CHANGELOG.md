# Changelog

Notable changes to what a visitor or user of this project can see.

## 2026-11-01

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
