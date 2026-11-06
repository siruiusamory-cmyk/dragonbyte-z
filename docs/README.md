# Documentation

Start with [Install and launch](../INSTALL.md), then choose a workflow below.
The [repository README](../README.md) explains the product and support maturity.

## Getting started

| Read | Purpose |
| --- | --- |
| [Installation](../INSTALL.md) | Windows prerequisites, clone, locked setup, launch and ROM identification. |
| [Newcomer walkthrough](newcomer.md) | Extract, edit, build and validate; measured commands and explicit evidence limits. |
| [Supported ROM profiles](rom-profiles.md) | Exact identities and per-image support. |
| [ROM safety](ROM_SAFETY.md) | Mandatory read-only inputs, new outputs, identity and provenance rules. |

## SDK and Workbench usage

| Read | Purpose |
| --- | --- |
| [Authoring journeys](journeys/README.md) | Dialogue, map layout, scenes, safe build and derivative reopen. |
| [Workbench](workbench.md) | Existing engineering editor, Layout operations and output reopen constraints. |
| [Project format](project-format.md) | Durable edits, serialization and deterministic rebuilds. |
| [Asset export](asset-export.md) | Resource-library export as a separate tool. |
| [Warp randomizer](warprand/README.txt) / [enemy randomizer](enemyrand/README.txt) | Packaged application usage and limits. |
| [Release artifacts](release-artefacts.md) | Outputs, patches, packaging and distribution constraints. |

## Development and architecture

| Read | Purpose |
| --- | --- |
| [Contributing](../CONTRIBUTING.md) | The change path and where to work. |
| [Development policy](DEVELOPMENT.md) | Governing engineering and evidence rules. |
| [Independent review](REVIEW.md) | Required review, verdicts and closure. |
| [Architecture](architecture.md) / [Workbench architecture](workbench-architecture.md) | SDK boundaries and existing client structure. |
| [Relocation](relocation.md) | Allocation and pointer-repair trust boundaries. |
| [GitHub workflow](git-workflow.md) | Branches, pull requests and pinned-candidate merge checks. |
| [Developer tools](dev-tools.md) | Existing maintenance and verification commands. |
| [Naming](naming.md) / [source classification](source-classification.md) | Identifier evidence and source roles. |
| [Desktop UI](desktop-ui.md) | Interaction and accessibility expectations. |

## Formats and reverse-engineering evidence

| Read | Purpose |
| --- | --- |
| [Reverse engineering](reverse-engineering.md) | Consolidated measured formats and unresolved semantics. |
| [Research catalogue](research/README.md) | Topic routes, provenance records and historical reports. |
| [Consumer analysis](consumer-analysis.md) | Executable evidence behind the data model. |
| [Research conventions](research-conventions.md) | Claim labels and promotion rules. |
| [Runtime capture](runtime-capture.md) / [mandatory mGBA procedure](skills/mgba-runtime.md) | Controlled observations and evidence limits. |
| [Ghidra workflow](ghidra-workflow.md) | Static analysis and calibration. |
| [Save catalogue](save-catalogue.md) / [hash investigation](hash-investigation.md) | Private input indexing and identity interpretation. |
| [Upstream audit](upstream-audit.md) | Prior work, provenance and licensing boundaries. |

## Testing, verification and reproducibility

- [Testing](testing.md): focused selections, local gate entry point and historical timing measurements.
- [Definition of done](definition-of-done.md): deterministic derived outputs with provenance.
- [Line endings](line-endings.md): byte-preserving edits.
- [Capability registry](capability-registry.md): scope and proof level of each shipped capability.

## Roadmaps and limitations

- [SDK roadmap](ROADMAP_TO_1_0.md): accepted authoring contract and remaining release work.
- [Desktop product specification](product/DRAGONBYTE_Z_PRODUCT_SPEC.md) and
  [implementation roadmap](product/DRAGONBYTE_Z_IMPLEMENTATION_ROADMAP.md): design targets,
  not proof that every planned interaction exists in the current editor.
- [Measured project state](PROJECT_STATE.md): binary facts and open questions;
  dated milestones are evidence snapshots, not a global completion score.
- [Editor design package](product/editor-design/README.md): interaction studies and annotated states.

## Decisions and historical material

- [Architecture decisions](decisions/README.md) retain accepted safety and design rationale.
- [Historical records](history/README.md) separate superseded presentation from current instructions.
- [Research catalogue](research/README.md#historical-and-verification-records) explains how to read
  dated audits, integration notes and verification records without treating them as current guidance.

Evidence stays at stable paths where tests and other documents cite it. A dated
report's command output and capability count describe its measured baseline.
Current installation is maintained in one place, [INSTALL.md](../INSTALL.md);
current capability claims are checked against the [registry](../src/data/capabilities.json).
