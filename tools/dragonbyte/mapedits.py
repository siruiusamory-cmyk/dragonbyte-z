"""The authored map documents, as one reversible journal payload.

The Maps destination edits three documents the project model already authors:
`maps/layout.toml`, the chunk cells a project paints, `maps/transitions.toml`,
the warps it retargets, and `maps/chunks.toml`, the chunk bodies a project
authors. This module is the journal's adapter for them, and it is deliberately
thin, because there is exactly one authored representation of these edits and it
belongs to `webfoot.project`. Nothing here parses, encodes or defines a document:

* `read` snapshots the project's own three documents;
* `install` puts a snapshot back, so undo and redo are the same operations the
  dialogues and data adapters use. Every other document is left alone: the
  authored structure and the created transitions belong to other writers and this
  adapter must not touch them;
* `write` calls the SDK's own narrow writers, which are the one place each
  document reaches disk. A document that became empty is removed by its writer
  rather than written as a table the reader would refuse.

A map HEADER record is deliberately not here: it is authored by the Data
destination's `data` target, and a second writer for it would be a second
authority over the same bytes.

No Qt is imported: the adapter is drivable from a headless test.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

from tools.webfoot.project import (
    AuthoredChunks,
    LayoutEdits,
    ProjectMeta,
    StatProject,
    TransitionEdits,
    read_project,
    write_authored_chunks,
    write_layout_edits,
    write_transition_edits,
)

#: The journal target the map documents are committed under. One target for both
#: documents: they are one authored subsystem, and a second target would give a
#: user two undos for one gesture.
MAPS_TARGET = "maps"


class MapsEditError(ValueError):
    """A map edit was refused; the message says which document and why."""


@dataclass(frozen=True, slots=True)
class AuthoredMaps:
    """The project's authored map documents, as one value.

    The documents are held exactly as they are read: a `LayoutEdits`, a
    `TransitionEdits` and an `AuthoredChunks` in the SDK's own types, so a second
    set of field names cannot drift from the SDK's readers and writers.
    """

    meta: ProjectMeta
    layout: LayoutEdits
    transitions: TransitionEdits
    chunks: AuthoredChunks = field(default_factory=AuthoredChunks)

    @property
    def edit_count(self) -> int:
        return len(self.layout.cells()) + len(self.transitions.edits())


def read(project: StatProject) -> AuthoredMaps:
    """Snapshot the map documents a project holds."""
    return AuthoredMaps(
        meta=project.meta,
        layout=project.layout,
        transitions=project.transitions,
        chunks=project.chunks,
    )


def install(project: StatProject, payload: object) -> StatProject:
    """The project with `payload`'s map documents, and every other document kept."""
    maps = _require_payload(payload)
    return replace(
        project,
        layout=maps.layout,
        transitions=maps.transitions,
        chunks=maps.chunks,
    )


def validate(project: StatProject, payload: object) -> None:
    """Refuse a payload that is not this project's own map documents.

    The identity check is the load-bearing one: `install` replaces `meta`, so a
    payload carrying another project's meta would move the session's own
    authority half way through an edit.
    """
    maps = _require_payload(payload)
    if maps.meta != project.meta:
        raise MapsEditError(
            "a map edit must carry the project's own identity; this payload names "
            f"{maps.meta.name!r} against {project.meta.name!r}"
        )


def write(directory: object, payload: object) -> None:
    """Persist the map documents through the SDK's own narrow writers.

    The chunks a layout can name are written before the layout, and the ones the
    previous layout named stay declared until it is replaced, so a save that stops
    between two documents leaves a project that still opens.
    """
    maps = _require_payload(payload)
    directory = Path(directory)
    declared = dict(read_project(directory).chunks.chunks)
    declared.update(maps.chunks.chunks)
    write_authored_chunks(
        directory, AuthoredChunks(chunks=dict(sorted(declared.items())))
    )
    write_layout_edits(directory, maps.layout)
    write_transition_edits(directory, maps.transitions)
    write_authored_chunks(directory, maps.chunks)


def _require_payload(payload: object) -> AuthoredMaps:
    if not isinstance(payload, AuthoredMaps):
        raise MapsEditError(
            "a map edit carries the project's authored map documents."
        )
    return payload
