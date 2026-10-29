# Review report

Deliverable 6 of the DragonByte Z editor design package. Companion to
[`README.md`](README.md).

This report records an independent review of design v0.2, what each finding changed,
and the decisions still open for the owner. It is written by the design agent that
was reviewed, about a review it did not perform.

## Reviewer independence

The review was made by a separate agent (a5) in a different session and a different
preset from the one that produced the design. It wrote none of the files it reviewed
and edited none of them: its own report records a read-only review with no write of
any kind in the worktree. The design agent did not see the findings before they were
delivered, and did not request a specific verdict.

The reviewer's method was seven owner-facing checks (similarity to the rejected
prototypes, consistency with established editor interactions, accessibility and
keyboard, actual engine constraints, unnecessary panels and controls, error handling
and undo behaviour, and understandable without ROM-format knowledge), each answered
from files read in its own session, with the engine statements quarried against the
technical audit's categories one by one.

## The reviewed state

The reviewed revision was the package as committed in the first round, before any
change in this report: seven documents, eight diagrams, one `docs/README.md` row and
one `CHANGELOG.md` entry, at the repository commit named in the round 1 report. The
reviewer re-hashed every one of those 17 paths against the round 1 hash table and
found no drift, which is its V1 table; its finding identifiers (F1 to F25, and the
seven checks) are the ones used below. Nothing in this report restates paths outside
the repository.

Its verdict on that revision was **CHANGES REQUIRED**: 6 blocking findings and 19
non-blocking ones, every one of them a correction inside this package's own files.

## Findings and their resolution

Severity is the reviewer's. "Fixed" means the correction is on disk in this
revision; the file and heading say where.

| Id | Severity | Summary | Resolution | Where |
| --- | --- | --- | --- | --- |
| F1 | non-blocking | three devices survive from the rejected files unnamed: a document line carrying map, state and measurement; a thumbnail palette of the map's pictures; a four-slot layer selector | fixed, and each is now traced to the real editor it comes from rather than left to the reader | `ANTI_REFERENCES.md`, section 3 |
| F2 | non-blocking | "both make the canvas a third of the window" is contradicted by the files' own column widths | fixed: the measured column widths replace the claim, and the defensible one is kept (the canvas is the largest single region) | `ANTI_REFERENCES.md`, section 3 |
| F3 | non-blocking | the refusal banner was drawn over map blocks 2 and 3, hiding content the user has to judge against | fixed: the banner moved into the inspector column, with the glyph on the ghost and the count in the header carrying the association | `diagrams/state-5-preview-refused.svg`; `VISUAL_STUDY.md`, S5; spec section 6 |
| F4 | blocking | the no-drag rationale is a false dichotomy, contradicted by `docs/desktop-ui.md`, the engine study and the reference analysis | fixed by adopting the gesture: drag repeats and the whole stroke is one merged undo entry, with the authority's two citations quoted | spec section 7 and the undo table in section 8; `VISUAL_STUDY.md`, S4 and S6; readiness section 7, decision 3 |
| F5 | non-blocking | the Escape ladder never says whether a press lands on an empty level, so dropping a capture is unpredictable | fixed: one press falls through to the next applicable level, stated, with the capture drop owned by level 4 | spec section 4 |
| F6 | non-blocking | one control had two names ("Hand" and "Pan") and one panel two titles | fixed: the tool is Pan (`H`) and the panel is "Pictures this map uses", matching the diagrams | spec sections 2, 4, 5.2 and 11 |
| F7 | non-blocking | the keyboard map covers every pointer step except zoom and pan | fixed: zoom gets `Ctrl+Plus`, `Ctrl+Minus` and `Ctrl+0`, and pan is stated as replaced by moving the focus block, with the reason | spec section 11 |
| F8 | non-blocking | S2's document line read "3 Saved" with no glyph, and S3's retained outline was solid where the study said dashed | fixed in both diagrams | `diagrams/state-2-selecting.svg`; `diagrams/state-3-captured.svg` |
| F9 | blocking | the walkability sentence claims more than OPS-13 and OPS-14 support | fixed: the format fact and the warning replace the reassurance; stamped blocks do not block, and no per-map blocking data exists | spec section 10, W1; `diagrams/state-6-placed.svg`; `VISUAL_STUDY.md`, S6 |
| F10 | blocking | W2 specifies a warning whose trigger needs a census that has not been run, and readiness said the opposite | fixed by withdrawing W2 from v0.2, with its return condition named | spec section 10, W2; readiness section 3 |
| F11 | non-blocking | R1 claims cross-map reuse is impossible, which is stronger than the evidence | fixed: the refusal names the real reason, that the two maps' tile numbers are not proved to mean the same pictures | spec section 10, R1 |
| F12 | non-blocking | R5 says "the whole map" where the SDK's condition is the editable layers' vocabulary | fixed, and the code citation corrected to the block it came from | spec section 10, R5 |
| F13 | non-blocking | S4's "What the click writes" panel repeats the well, the status line and the disclosure | fixed: the panel now carries one decision only, that this gesture is one undo step, and the study says so | `diagrams/state-4-preview-valid.svg`; `VISUAL_STUDY.md`, S4 |
| F14 | non-blocking | the technical disclosure still carried an evidence category, which is the anti-reference fault this package removes | fixed: the disclosure holds coordinates and offsets and no proof category, and the anti-reference table says so | spec section 2; `ANTI_REFERENCES.md`, section 2 table |
| F15 | non-blocking | Undo, Redo and Save are drawn in different places, and Save is never specified | fixed: one place for all three, the document line, specified once and now drawn the same way in all eight diagrams | spec section 3 ("Where the project actions live"); all eight diagrams |
| F16 | blocking | S7's acceptance said the document stays Modified, contradicting the undo rules and its own diagram | fixed: S7 reads Saved when the placement was the only unsaved edit, and Modified when other edits remain | spec section 12; `VISUAL_STUDY.md`, S7 |
| F17 | blocking | a History surface carried two acceptance observations and appeared in three places in the diagrams without ever being specified | fixed by specifying it once as a read-only panel that appears with the first placement, and by removing the empty panel from S1 to S3 | spec section 8.1 and section 12; `diagrams/state-1`, `state-2`, `state-3`, `state-6`, `state-7`, `state-8`; `ANTI_REFERENCES.md` |
| F18 | blocking | the refusal signal was described two incompatible ways and the diagram drew a third | fixed: one rule, three parts, taken from the diagram's own checkable form | spec section 6; `VISUAL_STUDY.md`, S5 |
| F19 | non-blocking | "the placements made since the last save" is undefined after an undo | fixed: the count is the placements whose blocks differ from the saved document at save time, with the after-undo case named | spec section 9 |
| F20 | non-blocking | placement has no failure state, while the batch does write a document | fixed: a failed write refuses that position, writes nothing and adds no entry, and the readiness table carries it | spec section 7; readiness section 1 |
| F21 | non-blocking | switching the target layer while holding a feature is unspecified | fixed: the capture survives and is re-validated on placement, with the refusal conditions named | spec section 5.3 |
| F22 | non-blocking | identity verification is a precondition with no failure state | fixed: the message and the read-only map entry are specified | spec section 3 |
| F23 | non-blocking | fixed strings are not pluralised, and the longest refusal cannot fit the banner as drawn | fixed: singular and plural forms for blocks and placements, a banner width with wrapping, and a status-line fallback for a long reason | spec sections 6, 7 and 9; `diagrams/state-5-preview-refused.svg` |
| F24 | non-blocking | "layout" and "blocking" are not in the vocabulary table, and one placement had two names | fixed: both are rows in the table, and one word per thing is stated, with the tool the only thing called Stamp | spec section 2 |
| F25 | non-blocking | the refusal inset cited blocks 13 and 17, which do not exist on a twelve-block grid | fixed: the inset names the blocks relative to the visible grid and to the block the ghost starts on | `diagrams/state-5-preview-refused.svg`; spec section 6 |

All 25 are fixed. None is recorded as accepted-and-unfixed, and none is deferred to a
later round.

## What the fixes changed in the shape of the design

Two of the blocking findings changed behaviour rather than wording, and they are
worth naming because a reader of round 1 would otherwise be surprised:

1. **Drag-repeat now exists.** Round 1 refused it with an argument that did not hold.
   v0.2 takes the gesture the repository's UI authority prescribes and the engine
   study records working: holding the button places a copy at each block the pointer
   enters, and the whole stroke is one merged undo entry. It remains a product-feel
   call for the owner (decision 3 below), and it is the recommended default.
2. **The History panel now exists as a specified surface**, described in the
   interaction spec section 8.1 as a read-only list that appears with the first
   placement. Round 1 relied on it in its acceptance rows without ever defining it.

## Outstanding owner decisions

Six decisions are the owner's, not the evidence's. Each carries the recommendation
this package would ship if nothing is said; the same table appears in
[`IMPLEMENTATION_READINESS.md`](IMPLEMENTATION_READINESS.md) section 7.

| # | Decision | Recommended default |
| --- | --- | --- |
| 1 | the GUI framework | none proposed: owner-reserved, and the model milestone does not depend on it |
| 2 | what "multi-tile environmental feature" means | the rectangle of 32 x 32 blocks, because the title has no metatile object; if the phrase meant metatile semantics, the task needs re-scoping first |
| 3 | whether drag-repeat ships | **yes**, one merged undo entry per stroke: it is the authority's prescribed gesture, the engine study records it working, and the reference analysis recommends it |
| 4 | whether a visible History panel ships | **yes**, as specified: one read-only panel that appears with the first placement, so it is a timeline and not a second undo mechanism |
| 5 | whether any evidence category may appear in user-facing chrome | **no**: proof levels stay in the repository's documents, and the window shows coordinates behind a disclosure instead |
| 6 | whether cross-map reuse is worth a G2 probe | **not for v0.2**: the refusal is right until character-block equality is measured, and the refusal now says exactly that |

Decision 2 is the one that could change the task itself. Decisions 3 and 4 are the
two the owner asked to have taken to a position rather than left open.

## What this report does not claim

It does not claim the revised package is better; that is the reviewer's judgement in
round 2, on the files as they are on disk now, and the reviewer sees them
independently of this report. It also does not claim the fixes are complete: it
claims that each finding has a stated resolution and that every resolution points at
a file and a heading a reader can open.

**The verdict on this revision is a5's round 2 verification and nothing else.** This
report records resolutions; it does not issue the verdict.

## Cross-references

- The reviewed state and the reviewer's own evidence: the review report in the
  reviewer's folder, its sections V1 (hash table) and R5-1 to R5-7 (the seven
  checks).
- The one task: [`INTERACTION_SPEC_v0.2.md`](INTERACTION_SPEC_v0.2.md).
- Readiness after the fixes: [`IMPLEMENTATION_READINESS.md`](IMPLEMENTATION_READINESS.md).
- The engine ceiling every refusal rests on:
  [`COMPATIBILITY_MATRIX.md`](COMPATIBILITY_MATRIX.md).
