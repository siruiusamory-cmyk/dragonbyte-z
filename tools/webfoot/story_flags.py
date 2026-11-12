"""Story flags: the project's permanent registry of named save flags.

DRAGONBYTE-Z-APP-006. A save file holds a flag by its number, so a number given
to a name is never given to another: renaming keeps it, deleting retires it, and
a new flag takes the lowest number that was never used. Nothing here renumbers.

Projects made before the registry kept their flags inside the conversation
document. Those names and numbers are read as part of the registry and move
into it the first time the project is saved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from types import MappingProxyType

from .data.save_flags import FREE_SAVE_FLAGS
from .project.atomic import replace_document
from .project.format import ProjectFormatError, dump_toml, load_toml

FLAGS_FILE = Path("story") / "flags.toml"
FLAG_NAME = re.compile(r"[a-z][a-z0-9_]{0,31}")
NAME_RULE = "Name the flag with small letters, digits and _, starting with a letter."


class StoryFlagError(ProjectFormatError):
    """A flag registry or change the project must not act on."""


def free_flags(profile) -> tuple[int, ...]:
    """Save flags no decoded base-game script names, lowest first."""
    return tuple(number for low, high in FREE_SAVE_FLAGS.get(profile.id, ())
                 for number in range(low, high + 1))


@dataclass(frozen=True, slots=True)
class Flags:
    names: dict = field(default_factory=dict)
    retired: tuple = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "names", MappingProxyType(dict(self.names)))
        object.__setattr__(self, "retired", tuple(sorted(set(self.retired))))

    def used(self) -> set[int]:
        return set(self.names.values()) | set(self.retired)


def _legacy(project_dir: Path) -> dict:
    """Flags an older project keeps in its conversation document."""
    path = project_dir / "dialogue" / "conversations.toml"
    if not path.is_file():
        return {}
    try:
        table = load_toml(path.read_text(encoding="utf-8")).get("flags", {})
    except (ProjectFormatError, OSError):
        return {}
    return dict(table) if isinstance(table, dict) else {}


def read_flags(project_dir: str | Path) -> Flags:
    """The registry, with any flags an older conversation document still holds."""
    project_dir = Path(project_dir)
    path = project_dir / FLAGS_FILE
    names, retired = {}, []
    if path.exists():
        try:
            document = load_toml(path.read_text(encoding="utf-8"))
        except (ProjectFormatError, OSError) as exc:
            raise StoryFlagError(f"{path}: {exc}") from exc
        names, retired = document.get("flags", {}), document.get("retired", [])
        if set(document) - {"flags", "retired"} or not isinstance(names, dict) or not (
                isinstance(retired, list) and all(type(item) is int for item in retired)):
            raise StoryFlagError(f"{path}: holds something that is not a flag registry")
        names = dict(names)
    for name, number in _legacy(project_dir).items():
        if number in retired:
            continue
        if names.setdefault(name, number) != number:
            raise StoryFlagError(
                f"flag {name!r} has one number in {FLAGS_FILE.as_posix()} and another in "
                "the conversation document")
    for name, number in names.items():
        if not isinstance(name, str) or not FLAG_NAME.fullmatch(name) or type(number) is not int:
            raise StoryFlagError(f"{path}: flag {name!r} is not a named flag")
    numbers = list(names.values()) + list(retired)
    if len(set(numbers)) != len(numbers):
        raise StoryFlagError(
            f"{path}: two flags share one number, or a retired number is in use again")
    return Flags(names, tuple(retired))


def write_flags(project_dir: str | Path, flags: Flags) -> Path:
    path = Path(project_dir) / FLAGS_FILE
    if not flags.names and not flags.retired:
        path.unlink(missing_ok=True)
        return path
    body: dict = {}
    if flags.retired:
        body["retired"] = list(flags.retired)
    if flags.names:
        body["flags"] = dict(sorted(flags.names.items()))
    path.parent.mkdir(parents=True, exist_ok=True)
    return replace_document(path, dump_toml(body))


def assign(flags: Flags, name: str, profile) -> Flags:
    """The registry with ``name`` in it, on the lowest number never used before."""
    if name in flags.names:
        return flags
    if not FLAG_NAME.fullmatch(name) or name == "always":
        raise StoryFlagError(NAME_RULE)
    pool = free_flags(profile)
    free = [number for number in pool if number not in flags.used()]
    if not free:
        raise StoryFlagError(
            f"All {len(pool)} flags the base game leaves unused are taken or retired.")
    return Flags({**flags.names, name: free[0]}, flags.retired)


def renamed(flags: Flags, old: str, new: str) -> Flags:
    """The same flag under another name; its number, and so every save, is kept."""
    if old not in flags.names:
        raise StoryFlagError(f"There is no flag named {old!r}.")
    if new == old:
        return flags
    if not FLAG_NAME.fullmatch(new) or new == "always":
        raise StoryFlagError(NAME_RULE)
    if new in flags.names:
        raise StoryFlagError(f"A flag named {new!r} already exists.")
    return Flags({(new if name == old else name): number
                  for name, number in flags.names.items()}, flags.retired)


def retired(flags: Flags, name: str) -> Flags:
    """The registry without ``name``; its number is kept out of use for good."""
    if name not in flags.names:
        raise StoryFlagError(f"There is no flag named {name!r}.")
    return Flags({other: number for other, number in flags.names.items() if other != name},
                 flags.retired + (flags.names[name],))


def problems(flags: Flags, profile) -> list[str]:
    """Numbers the base game uses, in plain words."""
    free = set(free_flags(profile))
    return [f"flag {name!r} is numbered {number}, which the base game uses"
            for name, number in sorted(flags.names.items()) if number not in free]
