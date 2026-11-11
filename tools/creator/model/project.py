"""One open creator project: its ROM, its text records, its edits and its build state.

The project folder is the only editable truth. Unsaved edits are mirrored to a
recovery file inside it on every change, so an abnormal exit loses nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import re

from tools.dragonbyte import textedits
from tools.dragonbyte.journal import EditKind
from tools.dragonbyte.session import RomNotRecognizedError, Session, SessionError
from tools.webfoot.build import BuildError, extract_project
from tools.webfoot.catalog import load_catalog
from tools.webfoot.formats import text_tables as tt
from tools.webfoot.text import TextStrings, load_text_strings

SUPPORTED_GAME = "buus_fury"
LOCAL_DIRECTORY = ".dragonbyte"
ROM_LINK = Path(LOCAL_DIRECTORY) / "rom.json"
RECOVERY_FILE = Path(LOCAL_DIRECTORY) / "recovery.json"
BUILD_DIRECTORY = "build"
NAMES_DIRECTORY = "library"
BUILD_STATE = Path(BUILD_DIRECTORY) / "last-build.json"
PROJECT_FILE = "project.toml"
DIALOGUE_NOTE = (
    "Spoken dialogue is shown for reference. Editing it arrives in a later "
    "version of DragonByte Z."
)


class CreatorError(Exception):
    """Something the creator asked for could not be done; the message says why."""


class RomMissingError(CreatorError):
    """The project is fine, but its Buu's Fury ROM has to be located again."""


@dataclass(frozen=True, slots=True)
class RomCheck:
    compatible: bool
    title: str
    detail: str


@dataclass(frozen=True, slots=True)
class TextRecord:
    key: str
    number: int
    kind: str
    original: str
    text: str
    editable: bool
    note: str = ""

    @property
    def changed(self) -> bool:
        return self.text != self.original

    @property
    def description(self) -> str:
        first = (self.original or self.text).strip().splitlines()
        summary = first[0] if first else "(empty)"
        return f"{self.kind} {self.number}: {summary[:60]}"


def _write_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".tmp")
    pending.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    os.replace(pending, path)


def _read_json(path: Path) -> dict | None:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) else None


def check_rom(path: Path) -> RomCheck:
    """Say in plain words whether this file can start a DragonByte Z project."""
    path = Path(path)
    if not path.is_file():
        return RomCheck(False, "File not found", f"There is no file at {path}.")
    session = Session()
    try:
        session.open_rom(path)
    except RomNotRecognizedError:
        return RomCheck(
            False,
            "Not a recognized game",
            "This file is not the retail Dragon Ball Z: Buu's Fury (USA) ROM. "
            "A modified, trimmed or different-region copy cannot be used.",
        )
    except SessionError as exc:
        return RomCheck(False, "This file could not be read", str(exc))
    profile = session.profile
    if profile.game != SUPPORTED_GAME:
        return RomCheck(
            False,
            "A different game",
            f"This is a verified ROM of another game ({profile.game.replace('_', ' ')}). "
            "DragonByte Z projects are built on Buu's Fury.",
        )
    return RomCheck(
        True,
        "Dragon Ball Z: Buu's Fury (USA) - verified",
        "This is the retail ROM. It will only ever be read, never changed.",
    )


def source_digest(directory: Path) -> str:
    """One hash over every authored file, so a build can tell if it is stale."""
    directory = Path(directory)
    digest = hashlib.sha256()
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(directory)
        if not path.is_file() or relative.parts[0] in (LOCAL_DIRECTORY, BUILD_DIRECTORY, NAMES_DIRECTORY):
            continue
        digest.update(relative.as_posix().encode("utf-8") + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def output_path(directory: Path, name: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9 _-]+", "_", name).strip() or "project"
    return Path(directory) / BUILD_DIRECTORY / f"{safe}.gba"


class CreatorProject:
    def __init__(self, session: Session, checker: TextStrings, dialogue: tuple) -> None:
        self._session = session
        self._base = checker
        self._originals = {entry.identity: entry.text for entry in checker.entries()}
        self._dialogue = dialogue
        self._saved = dict(session.project.strings)
        self.recovered: dict[str, str] = {}

    @classmethod
    def create(cls, rom_path: Path, directory: Path, name: str) -> "CreatorProject":
        rom_path, directory, name = Path(rom_path), Path(directory), name.strip()
        if not name:
            raise CreatorError("Give the project a name.")
        check = check_rom(rom_path)
        if not check.compatible:
            raise CreatorError(f"{check.title}. {check.detail}")
        try:
            extract_project(
                rom_path, directory, load_catalog(None), name=name, graphics=False
            )
        except BuildError as exc:
            raise CreatorError(
                f"{directory} already has files in it. Choose an empty or new folder."
            ) from exc
        except OSError as exc:
            raise CreatorError(
                f"The project folder could not be created at {directory}: {exc.strerror}."
            ) from exc
        return cls.open(directory, rom_path)

    @classmethod
    def open(cls, directory: Path, rom_path: Path | None = None) -> "CreatorProject":
        directory = Path(directory)
        if not (directory / PROJECT_FILE).is_file():
            raise CreatorError(
                f"{directory} is not a DragonByte Z project folder: it has no "
                f"{PROJECT_FILE}."
            )
        if rom_path is None:
            link = _read_json(directory / ROM_LINK) or {}
            rom_path = Path(link["path"]) if isinstance(link.get("path"), str) else None
        if rom_path is None or not Path(rom_path).is_file():
            raise RomMissingError(
                "This project's Buu's Fury ROM was not found. Locate the ROM to continue."
            )
        session = Session()
        try:
            session.open_rom(Path(rom_path))
            session.open_project(directory)
        except SessionError as exc:
            raise CreatorError(f"The project could not be opened: {exc}") from exc
        if session.identification.hashes.sha256 != session.project.meta.base_rom_sha256:
            raise RomMissingError(
                "That ROM is not the one this project was created from. Locate the "
                "retail Buu's Fury ROM."
            )
        try:
            _write_json(directory / ROM_LINK, {"path": str(Path(rom_path).resolve())})
            checker = load_text_strings(Path(rom_path), session.catalog)
        except (OSError, ValueError) as exc:
            raise CreatorError(f"The project could not be opened: {exc}") from exc
        project = cls(session, checker, _dialogue_rows(session))
        recovery = _read_json(directory / RECOVERY_FILE) or {}
        text = recovery.get("text")
        if isinstance(text, dict):
            project.recovered = {
                key: value
                for key, value in text.items()
                if isinstance(key, str) and isinstance(value, str)
            }
        return project

    @property
    def name(self) -> str:
        return self._session.project.meta.name

    @property
    def directory(self) -> Path:
        return self._session.project_dir

    @property
    def rom_path(self) -> Path:
        return self._session.rom_path

    @property
    def dirty(self) -> bool:
        return self._session.journal.is_dirty

    @property
    def can_undo(self) -> bool:
        return self._session.journal.can_undo

    @property
    def can_redo(self) -> bool:
        return self._session.journal.can_redo

    @property
    def output(self) -> Path:
        return output_path(self.directory, self.name)

    def _current(self) -> dict:
        return self._session.project.strings or self._originals

    def records(self) -> list[TextRecord]:
        current = self._current()
        rows = [
            TextRecord(
                key=identity.key,
                number=identity.index,
                kind="Game text",
                original=original,
                text=current.get(identity, original),
                editable=True,
            )
            for identity, original in self._originals.items()
        ]
        return rows + list(self._dialogue)

    def record(self, key: str) -> TextRecord:
        for row in self.records():
            if row.key == key:
                return row
        raise CreatorError(f"There is no text record {key}.")

    def problem_with(self, key: str, text: str, strings: dict | None = None) -> str:
        """Why this text cannot be used for this record, or an empty string."""
        from tools.dragonbyte.textsurface import _clone_strings

        target = _identity(key)
        checker = _clone_strings(self._base)
        for identity, other in (self._current() if strings is None else strings).items():
            if identity != target and other != self._originals.get(identity):
                try:
                    checker.set_text(identity, other)
                except ValueError:
                    continue
        try:
            checker.set_text(target, text)
        except ValueError as exc:
            return friendly_problem(str(exc))
        return ""

    def set_text(self, key: str, text: str) -> None:
        identity = _identity(key)
        if identity not in self._originals:
            raise CreatorError("This record is read-only.")
        problem = self.problem_with(key, text)
        if problem:
            raise CreatorError(problem)
        strings = dict(self._current())
        if strings.get(identity) == text:
            return
        strings[identity] = text
        self._apply(strings, f"edit {key}")

    def _apply(self, strings: dict, reason: str) -> None:
        payload = textedits.read(self._session.project)
        try:
            self._session.apply_edit(
                kind=EditKind.SEMANTIC,
                target=textedits.TEXT_TARGET,
                after=replace(payload, strings=strings),
                reason=reason,
            )
        except SessionError as exc:
            raise CreatorError(str(exc)) from exc
        self._write_recovery()

    def undo(self) -> None:
        self._step(self._session.undo_edit)

    def redo(self) -> None:
        self._step(self._session.redo_edit)

    def _step(self, move) -> None:
        try:
            move()
        except SessionError as exc:
            raise CreatorError(str(exc)) from exc
        self._write_recovery()

    def save(self) -> None:
        try:
            self._session.save_project()
        except SessionError as exc:
            raise CreatorError(f"The project could not be saved: {exc}") from exc
        self._saved = dict(self._session.project.strings)
        self.discard_recovery()

    def _write_recovery(self) -> None:
        current = self._current()
        pending = {
            identity.key: text
            for identity, text in current.items()
            if self._saved.get(identity, self._originals.get(identity)) != text
        }
        if not pending or not self.dirty:
            self.discard_recovery()
            return
        _write_json(self.directory / RECOVERY_FILE, {"text": pending})

    def restore_recovery(self) -> None:
        strings = dict(self._current())
        for key, text in self.recovered.items():
            identity = _identity(key)
            if identity in self._originals and not self.problem_with(key, text, strings):
                strings[identity] = text
        self.recovered = {}
        self._apply(strings, "restore unsaved edits")

    def discard_recovery(self) -> None:
        self.recovered = {}
        (self.directory / RECOVERY_FILE).unlink(missing_ok=True)

    def discard_changes(self) -> "CreatorProject":
        """Throw away every unsaved edit and return the project as it is on disk."""
        fresh = CreatorProject.open(self.directory, self.rom_path)
        fresh.discard_recovery()
        return fresh

    def build_status(self) -> str:
        """``current``, ``outdated`` or ``none``."""
        state = _read_json(self.directory / BUILD_STATE)
        if state is None or not self.output.is_file():
            return "none"
        if self.dirty or state.get("digest") != source_digest(self.directory):
            return "outdated"
        return "current"


def _identity(key: str) -> tt.TextIdentity:
    prefix, _, digits = key.partition(":")
    if prefix != "text" or not digits.isdigit():
        raise CreatorError("This record is read-only.")
    return tt.TextIdentity(int(digits, 10))


def _dialogue_rows(session: Session) -> tuple:
    from tools.dragonbyte.textsurface import load_text_surface

    try:
        surface = load_text_surface(
            session.rom_path,
            session.catalog,
            session.identification,
            session.profile,
            session.base_image,
        )
        rows = surface.dialogue_rows()
    except (ValueError, OSError):
        return ()
    return tuple(
        TextRecord(
            key=f"dialogue:{number}",
            number=number,
            kind="Spoken dialogue",
            original=row.text,
            text=row.text,
            editable=False,
            note=DIALOGUE_NOTE,
        )
        for number, row in enumerate(rows, start=1)
    )


_TOO_LONG = re.compile(r"^(text:\d{4}): encoded text needs \d+ bytes")
_RECORD = re.compile(r"^(text:\d{4})\b:?\s*")


def problem_record(message: str) -> str:
    """The record a validation message is about, or an empty string."""
    match = _RECORD.match(message)
    return match.group(1) if match else ""


def friendly_problem(message: str) -> str:
    too_long = _TOO_LONG.match(message)
    if too_long:
        return (
            "This text is too long for the game to store. Shorten it."
        )
    if "malformed control token" in message:
        return (
            "A { starts a control code. Write it as {08:XX} with two hex digits, "
            "or type {{ for a plain brace."
        )
    key = problem_record(message)
    if key:
        return f"Game text {int(key[5:])}: {_RECORD.sub('', message)}"
    return message
