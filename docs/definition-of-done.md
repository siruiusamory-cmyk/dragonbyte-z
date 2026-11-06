# Definition of done

A change is done when the **derived output is reproducible from pinned inputs** and
its provenance says exactly what it changed.

That is deliberately not the disassembly repositories' finish line. Their gate
rebuilds a retail image and requires its digest to equal the retail sha256, which
measures how faithfully a reconstruction reproduces a fixed binary. This toolkit
does not reproduce a retail image: it reads a user's own verified ROM, applies an
authored change, and writes a **new** image. The equivalent question is therefore
determinism: the same base, project and version produce the same bytes, every
time, plus a manifest that names the difference.

Two things follow, and they are the whole of this page: a done change emits a
reproducible image from a pinned base, and it can prove what it changed.

## The criteria, and how each one is checked

| # | criterion | how it is checked | enforced today |
| --- | --- | --- | --- |
| 1 | **Determinism.** Two builds of the same project and base are byte-identical. | `sha256` of both emitted images, compared; the property tests pin the write invariants (`tests/unit/test_write_invariants_property.py`, `tests/unit/test_authored_image.py`, `tests/integration/test_project_build_rom.py`). Measured on the synthetic delivery transaction: two runs, identical digest `26a7cc40…` | yes for the transaction; the two-build comparison is a documented step, not a single CI job |
| 2 | **Provenance.** The emitted image has a manifest naming the base digest, the output digest and every changed byte span. | read the manifest: `manifest.base.sha256`, `manifest.output.sha256`, `manifest.changes[]` with `offset`, `size`, `old`, `new`, `reason`. Printed by `webfoot relocation-proof`, exit 0 | yes |
| 3 | **Base immutability.** The source image is unchanged after a build, by hash. | `sha256` before and after; the build refuses to write over its source and stages before publishing (`journey` step 9, `docs/ROM_SAFETY.md`) | yes |
| 4 | **No-op equality.** A build whose project changes nothing is byte-identical to its input. | `sha256` of the input and the output, compared | yes |
| 5 | **Fail closed.** A refusal exits non-zero, states the reason, and writes nothing. | run the command and check the exit code and the absence of the output; measured examples: `webfoot identify` on a non-image exits 1 with `Reason: no configured cryptographic identity matched`; `webfoot extract` exits 2 with `extraction requires an exactly verified ROM` | yes |
| 6 | **Validate before build.** Validation reads the project and writes nothing. | exit code plus the absence of any new file; `webfoot validate <project> --rom <base>` | yes |
| 7 | **A capability change arrives with its registry edit.** `src/data/capabilities.json` and `src/data/project.ts` change in the same commit as the behaviour. | `python -m pytest tests/unit/test_capability_registry.py`, then `npm run check` and `npm run build` in the site | yes |
| 8 | **Repository gates pass.** `public_surface`, `readability`, `architecture`, `public_release`. | the four commands, each exit 0; `docs/REVIEW.md` | yes |
| 9 | **No game data is tracked.** | `tests/unit/test_project_safety.py` proves no proprietary path is tracked and the ignore rules hold | yes |
| 10 | **Claims are labelled and cited.** A binary claim is `CONFIRMED`, `INFERRED` or `UNKNOWN`, with `file:line` evidence. | review against `docs/DEVELOPMENT.md`; evidence belongs in `docs/research/` | yes by review |
| 11 | **A documented command still runs.** The command form a page publishes is executed by the change that publishes it, or the page says it was not. | run the command; `python -m tools.webfoot --help` is the form this repository can always run without an install | yes by review |

Criteria 1-6 are the derived-output contract. Criteria 7-11 keep the rest of the
repository honest around it.

## Aspirational, and kept separate on purpose

These are real goals. None is enforceable today, and mixing them into the table
above would make the page claim checks that do not exist.

- **A runtime observation for every shipped capability.** Measured from
  `src/data/capabilities.json`: 13 capabilities carry `proof: runtime`, 11 carry
  `proof: application`. An application proof is a real proof of its own class; it
  is not an observation in the game.
- **Derivative reopen for every authored domain.** One change class is declared
  (dominant-layer chunk replacement, ADR 0002). Every other emitted image is
  launchable but is refused as a derivative, which is the designed outcome and not
  a done state.
- **Determinism across machines.** Reproducibility is measured on one host. A
  byte-identical build across a different OS, Python patch level or filesystem
  ordering is not measured.
- **Environment reproducibility from the lock.** `uv.lock` pins the set and setup
  installs `--locked`, but no job proves a clean machine reproduces the same
  installed set.
- **Automatic verification that every documented command resolves to an entry
  point.** The check is a manual table today, not a test.

## What done is not

- Not a test count, and not a green suite: a passing test establishes what it
  asserts, never that a workflow ran.
- Not a digest match against a retail image. That is the disassembly repos' gate
  and it measures reconstruction, not authorship.
- Not a ticket state. A change is done when the checks above pass on the change,
  whatever the tracker says.
