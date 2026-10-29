# Changelog

Notable changes to what a visitor or user of this project can see.

## 2026-10-29

### Runtime evidence

- A read-only mGBA observer records live map, layer and screenblock state for the fine-grained map-authoring probes, and `tools/research/screenblock_fit.py` compares a capture with a layer's entry plane and reproduces the earlier positive controls.
- `tools/runtime/fine001_route_driver.lua` is the reviewed, allowlisted input driver for those probes: eight declared steps, live map and camera conditions, a 5165-frame budget, and a named failure instead of a guessed PASS.
- `tools/runtime/mgba_session.ps1` starts that driver from a clean checkout with no variables exported by hand: it supplies the observer path, the observer sha256 the driver pins, and the staged state's sha256, and clears them after the launch.
- The route driver's camera step now ends on a guard that the BG1 vertical scroll stays at most 1, the value this scene carries in every settled frame; it does not show the camera reaching the map's top edge, and the route reaches its observation hold instead of spending the step budget.

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
