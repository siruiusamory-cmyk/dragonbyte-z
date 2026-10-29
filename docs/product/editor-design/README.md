# DragonByte Z editor design package

Status: **design v0.2, not implemented.** Nothing under this directory is a
description of shipped behaviour. It is the first actionable design package for
the native Windows Map Editor and the Tileset Workshop, and it ends before any
application code exists and before any GUI framework is chosen.

The package is deliberately one task deep, not a whole-application mockup. A
sketch of the full product would be an invention; a specification of the
smallest real authoring loop can be built, tested and rejected on evidence.

## Scope

In scope:

- one editor task, specified to input level, with its states drawn as original
  diagrams;
- what the retail engine can support, quoted from the technical audit rather
  than assumed;
- the reference material the design rests on, attributed and summarised in
  words;
- why the design does not repeat the two rejected prototypes.

Out of scope: application code, prototypes, framework selection, palette or
keyboard-theme decisions for the whole application, warp and object authoring,
and any runtime claim about authored content.

Prior DragonByte Z design documents remain research material, not requirements:
[`DRAGONBYTE_Z_PRODUCT_SPEC.md`](../DRAGONBYTE_Z_PRODUCT_SPEC.md) and
[`DRAGONBYTE_Z_IMPLEMENTATION_ROADMAP.md`](../DRAGONBYTE_Z_IMPLEMENTATION_ROADMAP.md).
Where this package uses their vocabulary it says so.

## The one task

Verbatim from the owner: "Select an existing multi-tile environmental feature,
paint it elsewhere, undo it, and save the change."

In Buu's Fury data terms that is: capture a rectangle of chunk cells from one
layer of a map, stamp the same chunk pointers under a different origin on the
same map, undo one placement, and save the project. The engine mapping, and the
limits on it, are in [`COMPATIBILITY_MATRIX.md`](COMPATIBILITY_MATRIX.md); the
input-by-input behaviour is in
[`INTERACTION_SPEC_v0.2.md`](INTERACTION_SPEC_v0.2.md).

**One block is one chunk placement**: a 4-byte cell that points to a 32 x 32 plane
of 8 x 8 tiles, 256 x 256 pixels. It is not an 8 x 8 graphics tile. Blocks are
numbered from 1 in reading order; the project document stores cell indices from 0. A
"2 x 2 blocks" feature is 512 x 512 pixels of map rather than four hardware tiles.

**What v0.2 demonstrates.** v0.2 demonstrates chunk-arrangement stamping: capturing
and placing existing chunk references within one map. It is not unrestricted
environmental-feature selection; features that do not align to the 256 x 256 chunk
grid cannot be captured in v0.2. Whether an arbitrary existing 8 x 8-tile
arrangement can be placed is the open question the DRAGONBYTE-PLACEMENT-001
feasibility study exists to answer, and nothing in this package depends on its
outcome.

## Files

| File | What it is |
| --- | --- |
| [`REFERENCE_BOARD.md`](REFERENCE_BOARD.md) | Deliverable 1. Five desktop tile editors, each observation attributed to a source URL and a captured image, with the screenshot files held outside the repository. |
| [`COMPATIBILITY_MATRIX.md`](COMPATIBILITY_MATRIX.md) | Deliverable 2. Which proposed operations the retail engine supports, in three categories, each row cited. |
| [`INTERACTION_SPEC_v0.2.md`](INTERACTION_SPEC_v0.2.md) | Deliverable 3. Exact input, mode model, selection, brush preview, placement, undo, save and refusal messages. |
| [`VISUAL_STUDY.md`](VISUAL_STUDY.md) | Deliverable 4. Eight annotated states, each an original diagram in [`diagrams/`](diagrams/), with the evidence behind every choice. |
| [`ANTI_REFERENCES.md`](ANTI_REFERENCES.md) | Deliverable 5. Both rejected prototypes, hashed, analysed, and the decision in v0.2 that avoids each pattern. |
| [`IMPLEMENTATION_READINESS.md`](IMPLEMENTATION_READINESS.md) | Deliverable 7. What is ready to build, what needs a named assumption, what is blocked and by what. |
| [`REVIEW_REPORT.md`](REVIEW_REPORT.md) | Deliverable 6. The independent review, what each finding changed, and the owner decisions still open with a recommended default. |

Deliverable 6 is [`REVIEW_REPORT.md`](REVIEW_REPORT.md): the independent reviews of
this revision, the resolution of each of the 38 findings it records (25 from the first
verification, six the second added, one the third, four from the correction round, and
two from the reviews of the headless model built on it), and the decisions still open for
the owner with a recommended default.

## Design rules this package follows

The rules are short and each is traceable to a published source, because the
failure this package exists to avoid is a surface built from a model's default
taste. The sources were read this session; the quotes are exact.

| # | Rule | Traced to |
| --- | --- | --- |
| R1 | Every visual decision names a real product's observed behaviour or a measured limit. A decision with no source is cut, not drawn. | Refero design methodology: "No design from vibe memory." (S4) |
| R2 | State what the surface refuses to look like before drawing it, and check every state against that list. | "Decide what your brand refuses to look like." (S2) |
| R3 | One dominant reference owns a decision; others contribute bounded details. Never average five editors into a safe middle. | "Do not average references into a safe middle." (S4) |
| R4 | Show the product doing the job: the map, the art, the captured feature. No fixture counters, no dashboard invented to fill a window. | "often creates dashboard elements with multiple rounded rectangular outlines" (S1) |
| R5 | A reviewer who did not draw the surface checks it against named criteria and gives objective reasons, not preference. | "someone who was not involved in creating the design to be reviewed"; "objective explanations, not subjective criticisms" (S3) |
| R6 | Review single states and failure paths, not only the whole window. | a review can cover "an isolated segment of a design, such as a single dialog box or an exception-handling workflow" (S3) |
| R7 | Every state carries a brightness step, an outline weight, a drawn glyph and a word. Colour is never the difference between two states. | "Color is not used as the only visual means of conveying information" (S5) |
| R8 | Each state is written as a reviewable contract: what is on screen, what the user can do next, what the product refuses. | a review can inspect "a set of specifications or other more abstract versions of a user interface" (S3) |

## Research basis

Five sources, read this session. They are published arguments and a standard,
not empirical studies of this product; the weakness each one carries is stated.

**S1. Kyle Chayka, Substack column on generic web design, 2026-06-29.**
<https://kylechayka.substack.com/p/the-generic-style-of-ai-web-design>
Quote: "the generic output, the lowest common acceptable denominator of aesthetics
and taste". The piece also relays a designer's observation, quoted from the
accompanying New Yorker column, that the tool "often creates dashboard elements
with multiple rounded rectangular outlines, sometimes with a neon glow
underneath for good measure". Weakness: a culture column about marketing pages,
not desktop tools; it names the symptom, not the fix.

**S2. Melissa Rojas, design-process argument, dotCMS, 2026-09-22.**
<https://www.dotcms.com/blog/ai-slop-is-a-design-process-problem-not-an-ai-problem>
Quote: "It's proof that most of the people using it aren't giving it the right
guidelines, design tokens, and governed content to work from." It also quotes the
model vendor's own guidance that the default house style is "persistent", and
closes with "Decide what your brand refuses to look like." Weakness: vendor blog
with a product to sell; its own advice is about brand governance, which this
package translates into per-decision rules.

**S3. Aurora Harley, "UX Expert Reviews", Nielsen Norman Group, 2018-02-25.**
<https://www.nngroup.com/articles/ux-expert-reviews/>
Quote: "Design reviews work best when the examiner ... is someone who was not
involved in creating the design to be reviewed", and "All usability problems
noted in the expert review must be accompanied by objective explanations, not
subjective criticisms." Weakness: inspection methods find problems, they do not
show that a task is finished; this package therefore also names the acceptance
observation per state.

**S4. Refero design methodology, published skill document, commit a9b54a3.**
<https://github.com/referodesign/refero_skill/commit/a9b54a3e62a6391f5f5ab7a20e4ddb32fb79a27d>
Quote: "Research before design work. Every design must be grounded in references
before implementation. Do not rely on the model's generic design taste." Also
"Research output must be specific. Name the references, describe concrete
choices, and explain what will be adapted." Weakness: a tool vendor's
methodology document with no evidence of outcomes, and it is written for web
screens; only its research discipline is used here.

**S5. W3C WAI, "Understanding Success Criterion 1.4.1: Use of Color", WCAG 2.2.**
<https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html>
Quote: "Color is not used as the only visual means of conveying information,
indicating an action, prompting a response, or distinguishing a visual element."
The Understanding note adds that where content relies on discriminating a
particular colour, "an additional visual indicator will be required regardless
of the contrast ratio". Weakness: written for web content; applied here to a
desktop canvas, where it is a floor rather than a full accessibility argument.

No page was downloaded and kept from these sources; only the quotes above and
their URLs. Nothing from them is copied into the repository as an asset.

## Conventions

- File names follow the `docs/product/` neighbours
  ([`DRAGONBYTE_Z_PRODUCT_SPEC.md`](../DRAGONBYTE_Z_PRODUCT_SPEC.md)) rather
  than the lower-case rule for the rest of `docs/`: this directory sits beside
  them.
- Capability words are the technical audit's: RUNTIME-PROVEN,
  ENCODING-CAPABLE and UNSUPPORTED, defined in
  [`../../decisions/0004-proof-levels.md`](../../decisions/0004-proof-levels.md)
  and applied in [`COMPATIBILITY_MATRIX.md`](COMPATIBILITY_MATRIX.md).
- Every diagram is hand-written SVG with abstract block placeholders. No game
  graphics, no screenshot, and no `<image>` element appears in any of them.
- Screenshots of other products are referenced, never stored here. See
  [`REFERENCE_BOARD.md`](REFERENCE_BOARD.md) and
  [`../../decisions/0006-public-product-screenshots.md`](../../decisions/0006-public-product-screenshots.md).
