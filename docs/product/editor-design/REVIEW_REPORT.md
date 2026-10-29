# Review report

Deliverable 6 of the DragonByte Z editor design package. Companion to
[`README.md`](README.md).

This report records an independent review of design v0.2, what each finding changed,
and the decisions still open for the owner. It is written by the designer of the
package that was reviewed, about a review the designer did not perform.

## Reviewer independence

The review was made by a separate reviewer (a5) in a different session and a different
preset from the one that produced the design. It wrote none of the files it reviewed
and edited none of them: its own report records a read-only review with no write of
any kind in the worktree. The designer did not see the findings before they were
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
| F5 | non-blocking | the Escape ladder never says whether a press is spent on an empty level, so the number of presses needed to drop a capture is not stated | fixed: one press falls through to the next applicable level, stated, with the capture drop owned by level 4 | spec section 4 |
| F6 | non-blocking | one control had two names ("Hand" and "Pan") and one panel two titles | fixed: the tool is Pan (`H`) and the panel is "Pictures this map uses", matching the diagrams | spec sections 2, 4, 5.2 and 11 |
| F7 | non-blocking | the keyboard map covers every pointer step except zoom and pan | fixed: zoom gets `Ctrl+Plus`, `Ctrl+Minus` and `Ctrl+0`, and pan is stated as replaced by moving the focus block, with the reason | spec section 11 |
| F8 | non-blocking | S2's document line read "3 Saved" with no glyph, and S3's retained outline was solid where the study said dashed | fixed in both diagrams | `diagrams/state-2-selecting.svg`; `diagrams/state-3-captured.svg` |
| F9 | blocking | the walkability sentence claims more than OPS-13 and OPS-14 support | fixed: the format fact and the warning replace the reassurance; stamped blocks do not block, and no per-map blocking data exists. **Correction note (DRAGONBYTE-PLACEMENT-001, C6):** the finding and this correction stand, but the replacement sentence over-read the evidence in the same direction the finding named: a failed search for a collision format is not proof that the engine carries no blocking data. The warning now says that blocking for stamped blocks is unknown rather than that stamped blocks do not block. Spec section 10 W1 and `VISUAL_STUDY.md` S6 carry the corrected sentence | spec section 10, W1; `diagrams/state-6-placed.svg`; `VISUAL_STUDY.md`, S6 |
| F10 | blocking | W2 specifies a warning whose trigger needs a census that has not been run, and readiness said the opposite | fixed by withdrawing W2 from v0.2, with its return condition named | spec section 10, W2; readiness section 3 |
| F11 | non-blocking | R1 claims cross-map reuse is impossible, which is stronger than the evidence | fixed: the refusal names the real reason, that the two maps' tile numbers are not proved to mean the same pictures | spec section 10, R1 |
| F12 | non-blocking | R5 says "the whole map" where the SDK's condition is the editable layers' vocabulary | fixed, and the code citation corrected to the block it came from | spec section 10, R5 |
| F13 | non-blocking | S4's "What the click writes" panel repeats the well, the status line and the disclosure | fixed: the panel now carries one decision only, that this gesture is one undo step, and the study says so | `diagrams/state-4-preview-valid.svg`; `VISUAL_STUDY.md`, S4 |
| F14 | non-blocking | the technical disclosure still carried an evidence category, which is the anti-reference fault this package removes | fixed: the disclosure holds coordinates and offsets and no proof category, and the anti-reference table says so | spec section 2; `ANTI_REFERENCES.md`, section 2 table |
| F15 | non-blocking | Undo, Redo and Save are drawn in different places, and Save is never specified | fixed: one place for all three, the document line, specified once and now drawn the same way in all eight diagrams | spec section 3 ("Where the project actions live"); all eight diagrams |
| F16 | blocking | S7's acceptance said the document stays Modified, contradicting the undo rules and its own diagram | fixed: S7 reads Saved when the placement was the only unsaved edit, and Modified when other edits remain | spec section 12; `VISUAL_STUDY.md`, S7 |
| F17 | blocking | a History surface carried two acceptance observations, and the diagrams drew it two different ways (nested in the palette for S1 to S3, a panel of its own for S6 to S8) without its ever being specified | fixed by specifying it once as a read-only panel that appears with the first placement, and by removing the empty panel from S1 to S3 | spec section 8.1 and section 12; `diagrams/state-1`, `state-2`, `state-3`, `state-6`, `state-7`, `state-8`; `ANTI_REFERENCES.md` |
| F18 | blocking | the refusal signal was described two incompatible ways and the diagram drew a third | fixed: one rule, three parts, taken from the diagram's own checkable form | spec section 6; `VISUAL_STUDY.md`, S5 |
| F19 | non-blocking | "the placements made since the last save" is undefined after an undo | fixed: the count is the placements whose blocks differ from the saved document at save time, with the after-undo case named | spec section 9 |
| F20 | non-blocking | placement has no failure state, while the batch does write a document | fixed: a failed write refuses that position, writes nothing and adds no entry, and the readiness table carries it. **Correction note (DRAGONBYTE-PLACEMENT-001, C5):** a placement no longer writes a document; the failure it refuses is the batch the in-memory project cannot hold, which changes nothing in memory and adds no entry, and the disk failure belongs to Save | spec section 7; readiness section 1 |
| F21 | non-blocking | switching the target layer while holding a feature is unspecified | fixed: the capture survives and is re-validated on placement, with the refusal conditions named | spec section 5.3 |
| F22 | non-blocking | identity verification is a precondition with no failure state | fixed: the message and the read-only map entry are specified | spec section 3 |
| F23 | non-blocking | fixed strings are not pluralised, and the longest refusal cannot fit the banner as drawn | fixed: singular and plural forms for blocks and placements, a banner width with wrapping, and a status-line fallback for a long reason | spec sections 6, 7 and 9; `diagrams/state-5-preview-refused.svg` |
| F24 | non-blocking | "layout" and "blocking" are not in the vocabulary table, and one placement had two names | fixed: both are rows in the table, and one word per thing is stated, with the tool the only thing called Stamp | spec section 2 |
| F25 | non-blocking | the refusal inset cited blocks 13 and 17, which do not exist on a twelve-block grid | fixed: the inset names the blocks relative to the visible grid and to the block the ghost starts on | `diagrams/state-5-preview-refused.svg`; spec section 6 |

All 25 are fixed. None is recorded as accepted-and-unfixed, and none is deferred to a
later round. Two of them needed a second pass, and the section below records why.

## Round 2 verification: what the first pass left behind

The review re-checked every resolution above against the committed package and returned
**CHANGES REQUIRED** again. The reason is worth recording plainly: the six blocking
findings were all resolved, and then the corrections themselves were attacked for what
they had introduced, which produced one new blocking finding and five new non-blocking
ones. The reviewed state was the package at the commit that carries the round 1 fixes,
before any change described in this section.

Eight findings were open in that verdict: two that round 1 had only partly resolved
(F14, F21) and six new ones (F26 to F31). All eight are fixed in this revision, and the
severity below is the reviewer's.

| Id | Severity | Summary | Resolution | Where |
| --- | --- | --- | --- | --- |
| F14 | non-blocking, partly resolved | two sentences still said evidence categories live in the technical disclosure, which is the fault the finding removes | fixed: both sentences now say that no evidence category appears in the window at all, not even in the collapsed disclosure | `ANTI_REFERENCES.md`, section 2 table; `VISUAL_STUDY.md`, "What every state omits" |
| F21 | non-blocking, partly resolved | the layer-switch rule named a refusal the SDK does not raise, so the rule the finding asked for was there but wrong | fixed with F27: the capture survives a layer switch and is re-validated on placement against the map's vocabulary, and only the refusals that exist are named (read-only layer, out of its grid) | spec section 5.3 |
| F26 | non-blocking | the undo table still justified granularity with "the batch is one document write", and described redo as "re-applies the same batch", while the adopted drag rule makes a stroke many writes in one entry | fixed: each position in a stroke is one validated batch applied to the in-memory project, one stroke is one journal entry and one merged redo, and redo re-applies the changes the entry recorded | spec section 8 table |
| F27 | blocking | the layer-switch rule refused a placement carrying "a picture outside that layer's own vocabulary"; the SDK's vocabulary is the map's set, so no such refusal exists, and the rule contradicted the sentence it sat in | fixed: the three words are deleted and the citation narrowed to the refusals that do exist. Re-checked against `tools/webfoot/map_paint.py:585-606`, where the only vocabulary refusal is "a grid of N cell(s) using a single chunk", a read-only state, and against `:646-654`, which states the accepted replacement rule as "a chunk a dominant layer of this map already uses" | spec section 5.3 |
| F28 | non-blocking | three diagrams printed the design note "History appears with the first placement" inside a working panel, which is annotation text presented as interface copy | fixed: the note is gone from all three diagrams, and spec section 8.1 with the state table carries it instead | `diagrams/state-1-idle.svg`, `state-2-selecting.svg`, `state-3-captured.svg` |
| F29 | non-blocking | the History row template differed between spec ("3. Placed 4 blocks on Background 1") and diagrams ("1. Placed 2 x 2 blocks on BG1"): ordinal, unit and layer spelling all differed | fixed: one template, "Placed 4 blocks on BG0", numbered by position, in the spec and in all three diagrams. The short layer form is the one the document line introduces as "Background 0 (BG0)", and it is what the 228 px row draws without wrapping. **Correction note (DRAGONBYTE-PLACEMENT-001, C2):** the template's layer changed from BG1 to BG0 when the fixture moved to map 33; the unit, the ordinal rule and the width finding are unchanged | spec section 8.1; `state-6-placed.svg`, `state-7-undone.svg`, `state-8-saved.svg` |
| F30 | non-blocking | S5 drew three inspector panels where section 6 specifies one banner, and the third printed the SDK's raw reason string | fixed: one banner, carrying the refusal and the outcome; the raw-string panel is gone, because that string reads "chunk cell is outside Background 1's ... grid" and section 2 keeps "chunk" off the main path, so the banner's translated sentence is the SDK's reason; the inset stays and is now named in the spec as the refusal's checkable detail | `diagrams/state-5-preview-refused.svg`; spec section 6; `VISUAL_STUDY.md`, S5 |
| F31 | non-blocking | the keyboard map offered "middle-drag, or `Ctrl`+drag" without naming a button, and in Select a `Ctrl`+left-drag would pan where the same drag without the modifier captures | fixed by dropping the modifier path: middle-drag is the only pointer pan, which is what spec section 4 already states | spec section 11 |

Two summary sentences in the table above were also brought back to the reviewer's own
wording, at its request in the same verification: F5 (whether a press is spent on an
empty level) and F17 (two drawn placements of the panel, not three). Neither changed a
severity. No finding in this round was declined, so there is no reasoned non-fix.

## Round 3 verification: the picture against the rule

The review then checked the same eight resolutions again and judged all eight
**RESOLVED**, and it attacked the diff for what it had introduced. That produced one new
blocking finding, F32, which is not a wording slip: the refused-preview drawing showed
the cells that fit as the hatched ones, so the picture taught the opposite of the rule
section 6 states. The reviewed state was the package at the commit carrying the round 2
fixes.

| Id | Severity | Summary | Resolution | Where |
| --- | --- | --- | --- | --- |
| F32 | blocking | S5 hatched blocks 4 and 8, the last column inside the drawn grid, while section 6 and the S5 row said the hatched cells are the ones outside the grid; the ghost outline covered one column under a "2 of 4 blocks" count, and the two cells the inset called outside the grid were drawn nowhere | fixed by the reviewer's second correction, because the first cannot be drawn in this frame: the surround between the layer edge (x=600) and the inspector column (x=624) is 24 px, one sixth of a 144 px block, and there is no room above or below the canvas either. The ghost's two in-grid cells now carry ghost art with the outline and glyph, the hatch moved into the inset, which names the positions, and section 6 and the S5 row now state that the canvas shows only the cells that fit and the inset alone carries the two that do not | `diagrams/state-5-preview-refused.svg`; spec section 6; `VISUAL_STUDY.md`, S5 |

The geometry the resolution rests on, measured in the drawn frame: the canvas is the
rect x=24, y=76, width=576, height=394; its four columns start at x=24, 168, 312 and 456
and its three rows at y=76, 207 and 338, so the last in-grid column is x=456 to x=600 and
a fifth column would start at x=600; the ghost's visible cells are x=456, y=76, 144 x 131
(block 4) and x=456, y=207, 144 x 131 (block 8); the 5 px outline is x=454, y=74, 148 x
267. The free surround is x=600 to x=624, which is 24 px.

The same verification recorded three observations it did not score: two source titles in
the package README are now paraphrases above exact quote fragments, and the Refero
citation is a commit page rather than the file. Those are the price of the repository's
public-surface screen and this revision leaves them as they are.

## DRAGONBYTE-PLACEMENT-001 corrections

These are not review findings and carry no F number: the coordinator identified them
against PR #2 after the design review passed, and they correct the contract itself.
Each row names what changed and where.

| # | Correction | What changed, and where |
| --- | --- | --- |
| C1 | the fixture | the acceptance fixture is map 33, Background 0, a measured 4 x 2 chunk grid, with the source at blocks 1, 2, 5 and 6 and the destination at blocks 3, 4, 7 and 8, whose values differ at all four positions. The census and the command that produced it are in the ticket's `fixture-census.md`, outside this repository. Map 40 BG1 measures 2 x 2, so a 2 x 2 capture covers it and no non-overlapping placement exists there; it is no longer a fixture (readiness section 5). Two named assumptions carry the fixture (readiness section 2): that the renderer measured on maps 39 and 40 draws map 33 unchanged, and that this layer's own cell values hold where the census read them |
| C2 | the count | assertion 4 no longer claims "exactly the four cells are written"; it asserts the measured count of positions where the destination differs from the captured source, four for this fixture, and the status count is the blocks whose value changed rather than the blocks covered (spec section 0, section 7; readiness section 5) |
| C3 | the unit | one block is one chunk placement: a 4-byte cell pointing to a 32 x 32 plane of 8 x 8 tiles, 256 x 256 pixels, not an 8 x 8 graphics tile. The definition also fixes the numbering: blocks count from 1 in reading order, and the project document stores cell indices from 0 (spec section 2; package README) |
| C4 | the scope | v0.2 demonstrates chunk-arrangement stamping, not unrestricted environmental-feature selection; features that do not align to the 256 x 256 chunk grid cannot be captured, and the DRAGONBYTE-PLACEMENT-001 feasibility study is the open question (spec section 1; readiness, opening; package README) |
| C5 | persistence | one model: a preview changes nothing; a placement applies to in-memory project state and adds one history entry; undo and redo change memory only; Save is the only write to disk and it is atomic. The readiness assertions were rewritten to match (spec section 9.1; readiness section 5) |
| C6 | W1 and the evidence | the warning no longer states that the title carries no blocking data of its own, nor that stamped blocks are walked through; it says blocking is unknown because no collision format has been identified (spec section 10 W1; `VISUAL_STUDY.md` S6; readiness section 1) |

Two earlier resolutions were re-worded by these corrections and neither is reopened:
F9's replacement sentence, which now says blocking is unknown, and F20's failure row,
which now refuses in memory rather than at a write. Both rows carry a correction note
above, and the ticket report lists the change for each.

Five findings were raised by the independent reviews: four of this correction round (F33
to F36) and one of the headless model built on it (F39). They keep the reviewer's
severity and wording, and each is resolved here.

| # | Severity | Finding, in the reviewer's words | Resolution |
| --- | --- | --- | --- |
| F33 | BLOCKING | "assert the project document on disk now holds exactly cells 3, 4, 7 and 8" names the destination in block numbering while the project document's key is a 0-based row-major cell index, so the sentence names blocks 4, 5, 8 and 9 there, while an eight-cell grid has indices 0 to 7; "a test written literally from this assertion fails a correct implementation" | assertion 6 now reads "blocks 3, 4, 7 and 8 (cells 2, 3, 6 and 7)", the fixture paragraph pairs both numberings once, and the block definition states the rule: blocks are numbered from 1 in reading order, the project document stores cell indices from 0 (readiness sections 2 and 5; spec section 2; package README) |
| F34 | NON-BLOCKING | "Save is the only write" states an absolute rule while the same document uses "write" for an in-memory cell batch and justifies redo with "a redo is a write", so one word carries two meanings and the two cannot be read apart | "write" now means Save, the disk, a built image or patch, and the shipped batch API where the sentence cites that code. Every placement, drag position, redo, preview commit and capture is applied or changes, and Save reads "Save is the only write to disk" (spec sections 0, 5.1, 6, 7, 8, 9.1 and the performance row; readiness section 1; VISUAL_STUDY S2 and S4) |
| F35 | NON-BLOCKING | `state-2-selecting.svg` reads "From block 5, 2 x 2 blocks" and `state-3-captured.svg` reads "block 5.", while the spec's well example reads "from block 1" and the fixture's capture is blocks 1, 2, 5 and 6; on the named 4 x 2 layer "a 2 x 2 capture from block 5 cannot exist" | both diagrams now say block 1, and the drawn selection, its pattern fills, its dashed source outline and its callouts moved with the label so the picture cannot teach the opposite of the sentence (spec section 6; `diagrams/state-2-selecting.svg`; `diagrams/state-3-captured.svg`) |
| F36 | NON-BLOCKING | "one live readiness assumption row still assumes a drag stroke makes document writes and the review report's F26 resolution still uses "write" for an in-memory act": section 9.1 says a placement applies to memory and the disk changes on Save only, so a stroke makes no document writes, while `IMPLEMENTATION_READINESS.md:61` assumed that it does | the assumption row now assumes that the in-memory cost of applying one stroke stays affordable, and its falsifier speaks of the merge grain only, with the write-batching clause dropped; F26's resolution text now says one validated batch applied to the in-memory project whose changes a redo re-applies, and the reviewer's finding text in that row is left as quoted (readiness section 2; `REVIEW_REPORT.md:91`) |
| F39 | NON-BLOCKING | "redo installs the payload without revalidation" (`tools/dragonbyte/placement.py:363-368`; `journal.py:614-621`) against the redo row at `INTERACTION_SPEC_v0.2.md:326`: unreachable while the layer authority is fixed, "but that invariant is nowhere stated, and section 8 is a behavioural rule a later window will lean on" | section 8 now states the invariant directly after the undo table: the redo revalidation cannot fail while one layer authority is fixed for the session, and a session that reads the layer authority again either starts a new session with an empty history or revalidates every redo against that authority. The revalidation rule at `:326` is unchanged, and no code was touched (spec section 8) |

F34 is complete. The review of the previous round recorded it partly resolved at
`72adbbca`: the three collisions the finding named were fixed and twenty-one further
sentences were corrected, but two sentences still used "write" for an act that is not
Save, both named above as F36. Both are corrected in this round, and no sentence the
reviewer listed under F34 or F36 still speaks the old sense.

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

It does not claim the revised package is better; that is the reviewer's judgement on
the files as they are on disk now, and the reviewer sees them independently of this
report. It also does not claim the fixes are complete: it claims that each finding has
a stated resolution and that every resolution points at a file and a heading a reader
can open.

**The verdict on this revision is a5's fourth verification and nothing else.** This
report records resolutions; it does not issue the verdict.

## Cross-references

- The reviewed state and the reviewer's own evidence: the review report in the
  reviewer's folder, its sections V1 (hash table) and R5-1 to R5-7 (the seven
  checks).
- The one task: [`INTERACTION_SPEC_v0.2.md`](INTERACTION_SPEC_v0.2.md).
- Readiness after the fixes: [`IMPLEMENTATION_READINESS.md`](IMPLEMENTATION_READINESS.md).
- The engine ceiling every refusal rests on:
  [`COMPATIBILITY_MATRIX.md`](COMPATIBILITY_MATRIX.md).
