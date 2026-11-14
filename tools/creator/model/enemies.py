"""The Enemies tab's model: the game's own enemy types and the project's own.

A project enemy is a copy of one of the game's donor types, so it keeps that
type's behaviour, and its permanent identity is the name the creator gives it.
The row a build writes is chosen once, by the SDK, and is never shown here. An
enemy the game itself places is listed with how many placements use it and is
never changed.

Every edit goes to the project documents at once through the SDK's validated
writers, and undo restores those documents as they were.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tools.dragonbyte.session import Session
from tools.webfoot import enemy_types as et
from tools.webfoot import map_objects as mo
from tools.webfoot import map_view
from tools.webfoot import stats
from tools.webfoot.formats import stat_tables as st

from .project import CreatorError

FILES = (et.TYPES_FILE, mo.OBJECTS_FILE)
FIELDS = ("hp", "experience", "strength", "endurance")


@dataclass(frozen=True)
class EnemyRow:
    """One of the game's own enemy types, as the game's own data names it."""

    key: str
    hp: int
    experience: int
    strength: int
    endurance: int
    uses: int


@dataclass(frozen=True)
class Look:
    """One sprite the game already draws a type with."""

    key: str
    sprite: int


@dataclass(frozen=True)
class ProjectEnemy:
    """One type the project owns. Its key is its identity and never its row."""

    name: str
    key: str
    donor: str
    hp: int
    experience: int
    strength: int
    endurance: int
    look: Look | None
    used_on: tuple[tuple[str, int], ...]


class EnemyStudio:
    """The enemy types of one open project, beside the game's own."""

    def __init__(self, project_dir: Path, rom_path: Path) -> None:
        self.directory = Path(project_dir)
        self.image = Path(rom_path).read_bytes()
        session = Session()
        session.open_rom(Path(rom_path))
        self.profile = session.profile
        self._tables = stats.stat_tables_from_image(
            session.identification, self.profile, self.image)
        self._titles = {
            f"map:{entry.index:04d}": f"{entry.index:03d} {entry.name or 'Unnamed map'}"
            for entry in map_view.read_map_index(self.image, self.profile)}
        self._placements: dict[int, tuple[int, ...]] | None = None
        self._undo: list[tuple] = []
        self._redo: list[tuple] = []

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def pool(self) -> tuple[int, int]:
        """How many of the rows the base game never names the project has taken."""
        return len(self._types().entries), len(self._spare_rows())

    @property
    def bounds(self) -> dict[str, tuple[int, int]]:
        """The range each editable field of a type record holds."""
        return {name: (0, (1 << (et.STAT_FIELDS[name][1] * 8)) - 1) for name in FIELDS}

    def game(self) -> tuple[EnemyRow, ...]:
        """The game's own enemy types that its maps place, for reference."""
        rows = self._rows()
        return tuple(self._row(rows[row], len(sprites))
                     for row, sprites in sorted(self._sprites().items()) if row in rows)

    def donors(self) -> tuple[EnemyRow, ...]:
        """The types a project enemy may be copied from, by the name the data gives."""
        rows = self._rows()
        sprites = self._sprites()
        return tuple(self._row(rows[row], len(sprites.get(row, ())))
                     for row in self._donor_rows() if row in rows)

    def project(self) -> tuple[ProjectEnemy, ...]:
        """The project's own enemy types, with the game's type each behaves like."""
        rows = self._rows()
        used = self._used()
        found = []
        for key, entry in sorted(self._types().entries.items()):
            donor = rows[entry.donor]
            record = st.decode_enemy_record(entry.record(), 0)
            found.append(ProjectEnemy(
                key.split(":", 1)[1], key, str(donor.identity),
                record.hp, record.exp, record.strength, record.endurance,
                self._look(entry.donor), used.get(key, ())))
        return tuple(found)

    def looks(self, name: str) -> tuple[Look, ...]:
        """The looks the game shows for a project enemy: its donor's own pairing."""
        look = self._look(self._project_entry(name).donor)
        return () if look is None else (look,)

    def written_records(self) -> tuple[tuple[int, bytes], ...]:
        """Where and what a build writes for this project's types, as the SDK plans it."""
        planned = self._guard(
            lambda: et.changes(self._types(), self.profile, self.image))
        return tuple((change.offset, change.new) for change in planned)

    def create(self, donor: str, name: str) -> str:
        """A new type copied from the game's type ``donor``."""
        key = self._type_key(name)
        row = self._row_by_key().get(donor)
        if row is None:
            raise CreatorError(f"{donor} is not one of the game's enemy types.")
        self._changed(lambda: et.claim(
            self._types(), key.split(":", 1)[1], row, self.profile, self.image))
        return key

    def duplicate(self, name: str, new_name: str) -> str:
        self._project_entry(name)
        self._changed(lambda: et.duplicated(
            self._types(), name, new_name, self.profile))
        return f"enemy:{new_name}"

    def rename(self, name: str, new_name: str) -> str:
        """Rename a type and everything that names it; its row and bytes stay."""
        self._project_entry(name)
        self._changed(lambda: et.rename(
            self.directory, self._types(), name, new_name))
        return f"enemy:{new_name}"

    def delete(self, name: str) -> None:
        self._project_entry(name)
        self._changed(lambda: et.deleted(self.directory, self._types(), name))

    def set_statistic(self, name: str, field_name: str, value: int) -> None:
        self._project_entry(name)
        self._changed(lambda: et.edited(self._types(), name, field_name, value))

    def set_look(self, name: str, sprite: int) -> None:
        """Keep the look the game draws this enemy with; another one is refused."""
        donor = self._project_entry(name).donor
        self._guard(lambda: mo.verified_sprite(
            self.image, self.profile, donor, sprite))

    def undo(self) -> None:
        self._step_back(self._undo, self._redo, 1, 0)

    def redo(self) -> None:
        self._step_back(self._redo, self._undo, 0, 1)

    def _used(self) -> dict[str, tuple[tuple[str, int], ...]]:
        """For each project type, the maps whose added enemies name it, and how many."""
        keys = set(self._types().entries)
        found: dict[str, dict[str, int]] = {}
        try:
            document = mo.read_document(self.directory)
        except ValueError as exc:
            raise CreatorError(str(exc)) from exc
        for identity, item in document.items():
            for made in item.made.values():
                if made.type in keys:
                    places = found.setdefault(made.type, {})
                    title = self._titles.get(identity, identity)
                    places[title] = places.get(title, 0) + 1
        return {key: tuple(sorted(places.items())) for key, places in found.items()}

    def _rows(self) -> dict[int, stats.EnemyEntry]:
        return {entry.location.index: entry for entry in self._tables.enemies()}

    def _row_by_key(self) -> dict[str, int]:
        return {str(entry.identity): entry.location.index
                for entry in self._tables.enemies()}

    def _row(self, entry: stats.EnemyEntry, uses: int) -> EnemyRow:
        record = entry.record
        return EnemyRow(str(entry.identity), record.hp, record.exp,
                        record.strength, record.endurance, uses)

    def _sprites(self) -> dict[int, tuple[int, ...]]:
        if self._placements is None:
            self._placements = mo.enemy_placements(self.image, self.profile)
        return self._placements

    def _look(self, donor_row: int) -> Look | None:
        if not self._sprites().get(donor_row):
            return None
        sprite = self._guard(lambda: mo.verified_sprite(
            self.image, self.profile, donor_row))
        return Look(f"sprite:{sprite:04d}", sprite)

    def _donor_rows(self) -> tuple[int, ...]:
        return self._guard(lambda: et.donor_family(self.profile, self.image))

    def _spare_rows(self) -> tuple[int, ...]:
        return self._guard(lambda: et.spare_rows(self.profile))

    def _project_entry(self, name: str) -> et.EnemyType:
        """The project's type ``name``, refusing the game's own types by name."""
        entry = self._types().entries.get(f"enemy:{name}")
        if entry is not None:
            return entry
        if name.startswith("enemy:") and name[6:].isdigit():
            raise CreatorError(
                f"{name} is one of the game's own enemy types. It can be looked at, "
                "never changed.")
        raise CreatorError(et.NAME_RULE)

    def _type_key(self, name: str) -> str:
        return self._guard(lambda: et.type_key(name))

    def _types(self) -> et.Types:
        return self._guard(lambda: et.read_types(
            self.directory, self.profile, self.image))

    def _guard(self, action):
        try:
            return action()
        except (et.EnemyTypeError, mo.MapObjectError) as exc:
            raise CreatorError(str(exc)) from exc

    def _changed(self, action) -> None:
        self._edit(lambda: et.write_types(self.directory, self._guard(action)))

    def _snapshot(self) -> dict:
        return {name: (self.directory / name).read_bytes()
                if (self.directory / name).is_file() else None for name in FILES}

    def _restore(self, snapshot: dict) -> None:
        for name, data in snapshot.items():
            path = self.directory / name
            if data is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)

    def _edit(self, action) -> None:
        before = self._snapshot()
        try:
            action()
        except CreatorError:
            self._restore(before)
            raise
        except (ValueError, OSError, IndexError) as exc:
            self._restore(before)
            text = str(exc).strip()
            raise CreatorError(text or "That change could not be made.") from exc
        after = self._snapshot()
        changed = [name for name in FILES if before[name] != after[name]]
        if changed:
            self._undo.append(({name: before[name] for name in changed},
                               {name: after[name] for name in changed}))
            self._redo.clear()

    def _step_back(self, here: list, there: list, was: int, now: int) -> None:
        """Move one edit between undo and redo, touching only the files it changed."""
        if not here:
            return
        current = self._snapshot()
        if any(current[name] != data for name, data in here[-1][was].items()):
            raise CreatorError(
                "Something this step changed was changed again in another tab. Undo "
                "that change there first.")
        self._restore(here[-1][now])
        there.append(here.pop())
