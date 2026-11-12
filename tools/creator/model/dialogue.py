"""The dialogue editor's model: game conversations, the creator's own, and undo.

A base-game conversation is ``event:NNNN``. One the creator made is ``talk-N``.
Every edit is written to the project at once through the SDK's validated
document, and undo and redo restore that document as it was.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from tools.dragonbyte.session import Session
from tools.webfoot import conversations as cv
from tools.webfoot import map_objects as mo
from tools.webfoot import map_view

from . import library
from .project import CreatorError

PORTRAITS = range(8, 163)
STEP_NOTES = {
    0: "The game runs a script here. DragonByte Z keeps it as it is.",
    3: "The game shows a menu here. DragonByte Z keeps it as it is.",
    4: "The game runs a script here. DragonByte Z keeps it as it is.",
    6: ("The game fills numbers or names into this line while it plays. Editing lines "
        "like this has not been proven in the running game, so it is shown and kept."),
    7: "The game jumps to another conversation here. DragonByte Z keeps it as it is.",
}
PARTY = "Party member {0}: the game picks the face from the save file."
POSITION_NOTES = {
    "top": "The box is drawn at the top of the screen.",
    "middle": "The box is drawn in the middle of the screen.",
    "bottom": "The box is drawn at the bottom of the screen.",
    "low": "With no portrait the words are centred and the box sits low on the screen.",
    "": "Where the box sits on screen for this kind of page has not been measured.",
}


@dataclass(frozen=True)
class Row:
    key: str
    title: str
    mine: bool
    edited: bool
    search: str


@dataclass(frozen=True)
class Page:
    """One step of a conversation. Only an editable one can be typed into."""

    index: int
    text: str
    portrait: int
    editable: bool
    note: str
    original: str
    line: str = ""

    @property
    def changed(self) -> bool:
        return self.editable and self.text != self.original


def _friendly(exc: Exception) -> str:
    text = str(exc).strip()
    return text[:1].upper() + text[1:] if text else "That change could not be made."


class DialogueStudio:
    def __init__(self, project_dir: Path, rom_path: Path) -> None:
        self.directory = Path(project_dir)
        self.image = Path(rom_path).read_bytes()
        session = Session()
        session.open_rom(Path(rom_path))
        self.profile = session.profile
        self.font = cv.Font(self.image, self.profile)
        self._game = cv.read_conversations(self.image, self.profile)
        self._by_address = {item.address: f"event:{event:04d}" for event, item in self._game.items()}
        self._labels = map_view.read_map_index(self.image, self.profile)
        self._census = None
        self._undo: list[tuple] = []
        self._redo: list[tuple] = []
        self._document: cv.Document | None = None
        self._stamp = None
        self._highest = 0

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def _path(self) -> Path:
        return self.directory / cv.CONVERSATIONS_FILE

    def _bytes(self):
        return self._path().read_bytes() if self._path().is_file() else None

    def _restore(self, data) -> None:
        self._document = None
        if data is None:
            self._path().unlink(missing_ok=True)
        else:
            self._path().parent.mkdir(parents=True, exist_ok=True)
            self._path().write_bytes(data)

    def _step(self, source: list, target: list, side: int) -> None:
        """Move one step through history, unless it would take away a conversation in use."""
        if not source:
            return
        before = self._bytes()
        self._restore(source[-1][side])
        gone = [key for key in self._said() if key.startswith("talk-")
                and key not in self.document().talks]
        if gone:
            self._restore(before)
            raise CreatorError(
                "That step would remove a conversation a character says. Give the "
                "character another conversation in Maps first.")
        target.append(source.pop())

    def undo(self) -> None:
        self._step(self._undo, self._redo, 0)

    def redo(self) -> None:
        self._step(self._redo, self._undo, 1)

    def _said(self) -> set[str]:
        """Every conversation reference the project's map characters carry."""
        try:
            edits = mo.read_document(self.directory)
        except ValueError:
            return set()
        return {reference for item in edits.values()
                for reference in [*item.says.values(), *(made.says for made in item.made.values())]
                if reference}

    def document(self) -> cv.Document:
        """The document on disk; read again whenever the file changed, whoever wrote it."""
        path = self._path()
        stamp = (path.stat().st_mtime_ns, path.stat().st_size) if path.is_file() else None
        if self._document is None or stamp != self._stamp:
            try:
                self._document = cv.read_document(self.directory)
            except ValueError as exc:
                raise CreatorError(_friendly(exc)) from exc
            self._stamp = stamp
        return self._document

    def _write(self, **fields) -> None:
        before = self._bytes()
        current = self.document()
        try:
            cv.write_document(self.directory, cv.Document(**{
                name: fields.get(name, getattr(current, name))
                for name in ("lines", "talks", "flags")}))
        except (ValueError, OSError) as exc:
            self._restore(before)
            raise CreatorError(_friendly(exc)) from exc
        self._document = None
        after = self._bytes()
        if after != before:
            self._undo.append((before, after))
            self._redo.clear()

    def speaker(self, portrait: int) -> str:
        if portrait in PORTRAITS:
            key = f"portrait:{portrait:03d}"
            return library.read_names(self.directory).get(key) or f"Portrait {portrait}"
        if portrait == 0:
            return "No portrait"
        return "Small box" if portrait == cv.SMALL_BOX else f"Party member {portrait}"

    def portrait_choices(self) -> list[tuple[int, str]]:
        return [(0, "No portrait"), (cv.SMALL_BOX, "Small box, no portrait")] + [
            (slot, self.speaker(slot)) for slot in PORTRAITS]

    def rows(self) -> list[Row]:
        document = self.document()
        rows = []
        for key in sorted(document.talks, key=cv.talk_order):
            talk = document.talks[key]
            rows.append(Row(key, talk.name or "Unnamed conversation", True, False,
                            " ".join((talk.name,) + talk.pages).lower()))
        for event, item in self._game.items():
            key = f"event:{event:04d}"
            spoken = [entry for entry in item.entries if entry.text is not None]
            if not spoken:
                continue
            texts = [self._line(entry)[0] for entry in spoken]
            first = cv.decode(spoken[0].text).replace("\n", " ").replace("{page}", " ").strip()
            rows.append(Row(
                key, f"{self.speaker(spoken[0].argument)}: {first[:60]}", False,
                any(cv.line_key(entry.handle) in document.lines for entry in spoken),
                " ".join(texts + [self.speaker(entry.argument) for entry in spoken]).lower()))
        return rows

    def _line(self, entry) -> tuple[str, str]:
        original = cv.decode(entry.text)
        edit = self.document().lines.get(cv.line_key(entry.handle))
        return (edit.text if edit and entry.kind == cv.SPEECH else original), original

    def name(self, key: str) -> str:
        return next((row.title for row in self.rows() if row.key == key), key)

    def _talk(self, key: str) -> cv.Talk:
        talk = self.document().talks.get(key)
        if talk is None:
            raise CreatorError("That conversation is gone.")
        return talk

    def pages(self, key: str) -> list[Page]:
        if key.startswith("talk-"):
            talk = self._talk(key)
            return [Page(index, text, portrait, True, "", text)
                    for index, (text, portrait) in enumerate(zip(talk.pages, talk.portraits))]
        item = self._game[int(key[6:])]
        pages = []
        for index, entry in enumerate(item.entries):
            if entry.kind == cv.SPEECH and entry.text is not None:
                text, original = self._line(entry)
                pages.append(Page(index, text, entry.argument, True, "", original,
                                  cv.line_key(entry.handle)))
            else:
                shown = cv.decode(entry.text) if entry.text is not None else ""
                pages.append(Page(index, shown, entry.argument if entry.text is not None else 0,
                                  False, STEP_NOTES.get(entry.kind, STEP_NOTES[0]), shown))
        return pages

    def structure_note(self, key: str) -> str:
        if key.startswith("talk-"):
            return ""
        if any(not page.editable for page in self.pages(key)):
            return ("This game conversation has steps besides plain speech. Its speech can "
                    "be edited; its steps and their order are kept as they are.")
        return "The pages of a game conversation can be reworded. Their order and portraits are kept."

    def problem(self, text: str, original: str | None = None) -> str:
        """Why this wording cannot be built, or an empty string."""
        try:
            return cv.text_problem(self.font, cv.encode(text),
                                   None if original is None else cv.encode(original))
        except ValueError as exc:
            return _friendly(exc)

    def windows(self, text: str, portrait: int) -> tuple:
        """The page as the game shows it, one tuple of stored lines per press of A."""
        try:
            return cv.windows(self.font, cv.encode(text), portrait)
        except ValueError:
            return ()

    def preview_notes(self, text: str, portrait: int) -> list[str]:
        notes = []
        shown = self.windows(text, portrait)
        if len(shown) > 1:
            notes.append(f"This page takes {len(shown)} presses of A.")
        limit = cv.LIMITS[portrait == cv.SMALL_BOX][0]
        for window in shown:
            for line in window:
                if sum(self.font.advance(ord(unit)) for unit in line.replace(cv.INK, "")) > limit:
                    notes.append("A word here is wider than the box, so the game cuts it.")
        try:
            raw = cv.encode(text)
        except ValueError:
            return notes
        notes.append(POSITION_NOTES[cv.box_position(raw, portrait)])
        if raw[:1] in cv.POSITION_CODES:
            notes.append(f"The first character {raw[0]!r} sets the box position and is not drawn.")
        if cv._options(raw):
            notes.append("Lines that start with - are drawn by the game as choices with a "
                         "cursor. The preview shows them as plain lines.")
        if 0 < portrait < cv.SMALL_BOX:
            notes.append(PARTY.format(portrait))
        notes.append("The frame art and the typing speed are not shown.")
        return notes

    def glyph(self, code: int):
        return self.font.glyph(code)

    def advance(self, code: int) -> int:
        return self.font.advance(code)

    def set_text(self, key: str, index: int, text: str) -> None:
        page = self.pages(key)[index]
        if not page.editable:
            raise CreatorError(page.note)
        problem = self.problem(text, page.original if page.line else None)
        if problem:
            raise CreatorError(problem)
        if page.line:
            lines = dict(self.document().lines)
            if text == page.original:
                lines.pop(page.line, None)
            else:
                lines[page.line] = cv.Line(text, page.original)
            self._write(lines=lines)
        else:
            self._change(key, lambda talk: replace(
                talk, pages=talk.pages[:index] + (text,) + talk.pages[index + 1:]))

    def restore_line(self, key: str, index: int) -> None:
        page = self.pages(key)[index]
        if page.line:
            self.set_text(key, index, page.original)

    def _change(self, key: str, change) -> None:
        if not key.startswith("talk-"):
            raise CreatorError(
                "The order and portraits of a game conversation are kept. Duplicate it "
                "to get one of your own that you can change freely.")
        self._write(talks={**self.document().talks, key: change(self._talk(key))})

    def set_portrait(self, key: str, index: int, portrait: int) -> None:
        self._change(key, lambda talk: replace(
            talk, portraits=talk.portraits[:index] + (int(portrait),) + talk.portraits[index + 1:]))

    def add_page(self, key: str, after: int = -1, text: str = "New page.", portrait: int | None = None) -> int:
        def change(talk: cv.Talk) -> cv.Talk:
            at = len(talk.pages) if after < 0 else after + 1
            face = portrait if portrait is not None else (talk.portraits[at - 1] if at else 0)
            return replace(talk, pages=talk.pages[:at] + (text,) + talk.pages[at:],
                           portraits=talk.portraits[:at] + (face,) + talk.portraits[at:])
        self._change(key, change)
        return len(self._talk(key).pages) - 1 if after < 0 else after + 1

    def duplicate_page(self, key: str, index: int) -> int:
        talk = self._talk(key)
        return self.add_page(key, index, talk.pages[index], talk.portraits[index])

    def delete_page(self, key: str, index: int) -> None:
        if len(self._talk(key).pages) < 2:
            raise CreatorError("A conversation needs at least one page.")
        self._change(key, lambda talk: replace(
            talk, pages=talk.pages[:index] + talk.pages[index + 1:],
            portraits=talk.portraits[:index] + talk.portraits[index + 1:],
            resume=min(talk.resume, len(talk.pages) - 2)))

    def move_page(self, key: str, index: int, to: int) -> None:
        def change(talk: cv.Talk) -> cv.Talk:
            pages, portraits = list(talk.pages), list(talk.portraits)
            if not 0 <= to < len(pages):
                raise CreatorError("That page cannot move further.")
            pages.insert(to, pages.pop(index))
            portraits.insert(to, portraits.pop(index))
            order = list(range(len(pages)))
            order.insert(to, order.pop(index))
            return replace(talk, pages=tuple(pages), portraits=tuple(portraits),
                           resume=order.index(talk.resume))
        self._change(key, change)

    def _next_key(self) -> str:
        taken = [*self.document().talks, *(key for key in self._said() if key.startswith("talk-"))]
        self._highest = max([self._highest, *(cv.talk_order(key) for key in taken)]) + 1
        return f"talk-{self._highest}"

    def new_talk(self, name: str) -> str:
        key = self._next_key()
        self._write(talks={**self.document().talks, key: cv.Talk(
            " ".join(name.split())[:40] or "New conversation", ("Hello.",), (0,))})
        return key

    def duplicate(self, key: str, name: str = "") -> str:
        """A conversation of the creator's own with the same speech pages."""
        spoken = [page for page in self.pages(key) if page.editable]
        if not spoken:
            raise CreatorError("This conversation has no speech to copy.")
        new = self._next_key()
        title = name or (self._talk(key).name + " copy" if key.startswith("talk-")
                         else self.name(key)[:34] + " copy")
        self._write(talks={**self.document().talks, new: cv.Talk(
            title[:40], tuple(page.text for page in spoken),
            tuple(page.portrait for page in spoken))})
        return new

    def rename(self, key: str, name: str) -> None:
        self._change(key, lambda talk: replace(talk, name=" ".join(name.split())[:40]))

    def delete(self, key: str) -> None:
        self._talk(key)
        users = self.users(key) + [
            f"the conversation {talk.name or other!r}, once a flag is remembered"
            for other, talk in self.document().talks.items() if talk.then == key]
        if users:
            raise CreatorError(
                "This conversation is still used by " + "; ".join(users[:6])
                + ". Give them another conversation first.")
        self._write(talks={other: talk for other, talk in self.document().talks.items()
                           if other != key})

    def flags(self) -> list[str]:
        return sorted(self.document().flags)

    def rule(self, key: str) -> tuple[str, str, str, int]:
        talk = self._talk(key)
        return talk.sets, talk.when, talk.then, talk.resume

    def set_rule(self, key: str, sets: str = "", when: str = "", then: str = "",
                 resume: int = 0) -> None:
        """Remember a flag after this conversation, and say another once one is remembered."""
        talk = self._talk(key)
        flags = dict(self.document().flags)
        for name in (sets, when):
            if not name:
                continue
            if not cv.FLAG_NAME.fullmatch(name):
                raise CreatorError(
                    "Name the flag with small letters, digits and _, starting with a letter.")
            if name not in flags:
                free = [number for number in cv.free_flags(self.profile)
                        if number not in flags.values()]
                if not free:
                    raise CreatorError(
                        f"All {len(cv.free_flags(self.profile))} flags the base game leaves "
                        "unused are taken.")
                flags[name] = free[0]
        if bool(when) != bool(then):
            raise CreatorError("Choose both the flag and the conversation to say once it is remembered.")
        changed = replace(talk, sets=sets, when=when, then=then, resume=resume)
        try:
            cv._checked_talks(cv.Document(
                self.document().lines, {**self.document().talks, key: changed}, flags),
                self.font, self.profile)
        except ValueError as exc:
            raise CreatorError(_friendly(exc)) from exc
        self._write(talks={**self.document().talks, key: changed}, flags=flags)

    def reference_of(self, address: int) -> str:
        return self._by_address.get(address, "")

    def _title(self, index: int) -> str:
        return f"{index:03d} {self._labels[index].name or 'Unnamed map'}"

    def users(self, key: str) -> list[str]:
        """Every character that says this conversation, as 'map: character'."""
        if self._census is None:
            self._census = mo.census(self.image, self.profile)
        try:
            edits = mo.read_document(self.directory)
        except ValueError:
            edits = {}
        base = {}
        for index, objects in self._census.items():
            for item in objects:
                if item.family == mo.NPC:
                    base[(index, item.slot)] = self.reference_of(
                        cv._u32(self.image, item.record_offset + mo.CONVERSATION_OFFSET))
        found = []
        claimed = set()
        for identity, item in sorted(edits.items()):
            where = identity[8:] if identity.startswith("map-new:") else self._title(int(identity[4:]))
            for slot, reference in item.says.items():
                if identity.startswith("map:"):
                    claimed.add((int(identity[4:]), slot))
                if reference == key:
                    found.append(f"{where}: game character {slot}")
            for name, made in item.made.items():
                if (made.says or base.get((made.donor_map, made.donor_slot))) == key:
                    found.append(f"{where}: {made.name or name}")
        found += [f"{self._title(index)}: game character {slot}"
                  for (index, slot), reference in sorted(base.items())
                  if reference == key and (index, slot) not in claimed]
        return found

    def capacity(self) -> str:
        used = cv.capacity_of(self.document(), self.profile)
        return (f"Your dialogue uses {used.bytes_used // 2:,} of about "
                f"{used.bytes_total // 2:,} characters "
                f"({used.containers_used} of {used.containers_total} containers).")
