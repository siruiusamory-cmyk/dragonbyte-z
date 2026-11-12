"""Conversations: what characters say, the project document, and the build domain.

DRAGONBYTE-Z-APP-005. A character record names a conversation: an array of
record pointers the engine steps through, ended by a word whose high half is
zero. A spoken page is one eight-byte record carrying a portrait and a packed
handle into one of the dialogue containers.

The seven base-game containers are never rewritten. Every edited or new page is
stored in authored containers on the selectors after them, rebuilt from the
project on every build, so an edit to one line cannot disturb another line that
reads the same stored bytes, and the same project always builds the same image.
The 64-slot container table is copied aside and the one word that names it is
repointed, because the table's own words past the seventh are live data.

Only structures the running game was observed to read are written: speech
records, flag-test and flag-set script records, pointer arrays, containers, the
table copy and its one naming word.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import struct
from types import MappingProxyType

from .allocation import (Addressability, AllocationError, AllocationKind,
                         AllocationRequest, allocate)
from .binary import GBA_ROM_BASE, FileOffset
from .compressed_dialogue import _container_table_offset
from .data.placement_contracts import CONTRACTS
from . import story_flags
from .donor_resources import DonorResourceError, dialogue_font
from .data.script_specs import OPCODE_SETS
from .formats.script_vm import assemble_source
from .formats.webfoot_lz import ContainerError, pack, unpack, validate_retail_termination
from .handles import (HANDLE_LENGTH_MAX_BYTES, HANDLE_SELECTOR_MASK, DialogueHandle,
                      unpack_handle)
from .layout import AnchorId, OwnedRegion, RomRange
from .project.atomic import replace_document
from .project.format import ProjectFormatError, dump_toml, load_toml
from .write import ByteChange

CONVERSATIONS_FILE = Path("dialogue") / "conversations.toml"
DOMAIN = "conversations"
TABLE_SLOTS = HANDLE_SELECTOR_MASK + 1
CONTAINER_BYTES = 1 << 16
SPEECH, VALUE_SPEECH, SCRIPT = 5, 6, 0
RECORD_BYTES = 8
MAX_ENTRIES = 255
SMALL_BOX = 7
LIMITS = {False: (144, 4), True: (128, 2)}
LINE_BREAK, PAGE_BREAK, INK = "\n", "\x0b", "\x08"
INKS = ("\x02", "\x07")
PORTRAIT_MAX = 162
POSITION_CODES = {"!": "top", "@": "middle", "#": "bottom"}
TALK_ID = re.compile(r"talk-[0-9]{1,6}")
FLAG_NAME = story_flags.FLAG_NAME
EVENT_REF = re.compile(r"event:(\d{4})")
_LINE_KEY = re.compile(r"(\d{1,2}):0x([0-9A-F]{4}):(\d{1,4})(?:@(\d{4}))?")
_TOKEN = re.compile(r"\{\{|\{page\}|\{08:([0-9A-Fa-f]{2,4})\}|\{([0-9A-Fa-f]{2})\}|\{")


class ConversationError(ProjectFormatError):
    """A conversation document or edit the build must not act on."""


def encode(text: str) -> str:
    """Authored text, with its named codes, as the units the game stores."""
    def unit(match: re.Match) -> str:
        token = match.group(0)
        if token == "{{":
            return "{"
        if token == "{page}":
            return PAGE_BREAK
        if match.group(1):
            return INK + chr(int(match.group(1), 16))
        if match.group(2) and int(match.group(2), 16) < 0x20:
            return chr(int(match.group(2), 16))
        raise ConversationError(
            "A { starts a code. Write {page} for a new page, {08:XX} for a colour, "
            "or {{ for a plain brace.")
    return _TOKEN.sub(unit, text)


def decode(raw: str) -> str:
    """Stored units as authored text. ``encode(decode(raw)) == raw``."""
    out, position = [], 0
    while position < len(raw):
        character = raw[position]
        if character == "{":
            out.append("{{")
        elif character == PAGE_BREAK:
            out.append("{page}")
        elif character == INK and position + 1 < len(raw):
            out.append(f"{{08:{ord(raw[position + 1]):02X}}}")
            position += 1
        elif character < " " and character != LINE_BREAK:
            out.append(f"{{{ord(character):02X}}}")
        else:
            out.append(character)
        position += 1
    return "".join(out)


class Font:
    """The dialogue font's widths and columns, read the way the engine reads them."""

    def __init__(self, image: bytes, profile) -> None:
        try:
            span = dialogue_font(image)
        except DonorResourceError as exc:
            raise ConversationError(f"profile {profile.id!r}: {exc}") from exc
        descriptor = (span.file_offset + len(span.payload) + 3) & ~3
        table, self.wide, _base = struct.unpack_from("<IHI", image, descriptor)
        self._image, self._table = image, table - GBA_ROM_BASE
        self._map = struct.unpack_from("<256H", image, self._table)

    def has_glyph(self, code: int) -> bool:
        return 0 <= code < 0xFF and bool(self._map[code])

    def glyph(self, code: int) -> tuple[int, tuple[int, ...]] | None:
        """Width and one 16-row column word per pixel column, or nothing to draw."""
        if not self.has_glyph(code):
            return None
        at = self._table + 2 * self._map[code]
        width = struct.unpack_from("<H", self._image, at)[0]
        return width, struct.unpack_from(f"<{width}H", self._image, at + 2)

    def advance(self, code: int) -> int:
        if code >= 0xFF:
            return self.wide + 1
        glyph = self.glyph(code)
        return 1 if glyph is None else glyph[0] + 1


def _options(raw: str) -> int:
    return sum(1 for line in raw.split(LINE_BREAK)[1:] if line.startswith("-"))


def _codes(raw: str) -> list[str]:
    return sorted(character for character in raw
                  if character < " " and character not in (LINE_BREAK, PAGE_BREAK))


def text_problem(font: Font, raw: str, original: str | None = None) -> str:
    """Why these units cannot be a page, in plain words, or an empty string."""
    if not raw.strip(" \n\x0b"):
        return "A page needs some words."
    if 2 * len(raw) > HANDLE_LENGTH_MAX_BYTES:
        return (f"This page has {len(raw)} characters. The game can hold "
                f"{HANDLE_LENGTH_MAX_BYTES // 2} in one page.")
    kept = set(original or "")
    position = 0
    while position < len(raw):
        character = raw[position]
        if character == INK:
            if position + 1 >= len(raw):
                return "A colour code at the very end has no colour after it."
            if raw[position + 1] not in INKS and raw[position + 1] not in kept:
                return ("The game's own lines use two colour codes, {08:02} and {08:07}. "
                        "No other is known to be safe.")
            position += 2
            continue
        if character in (LINE_BREAK, PAGE_BREAK) or character in kept:
            position += 1
            continue
        if character < " ":
            return f"The code {{{ord(character):02X}}} is not one DragonByte Z can add to a page."
        if not font.has_glyph(ord(character)):
            return f"The game's font has no character {character!r}."
        position += 1
    if original is not None:
        if _options(raw) != _options(original):
            return ("This line holds choices the player picks from (lines that start "
                    "with -). Keep the same number of them.")
        if _codes(raw) != _codes(original):
            return "This line carries game codes. Keep each of them."
    return ""


def box_position(raw: str, portrait: int) -> str:
    """Where the box was seen on screen for this page, or an empty string."""
    if raw[:1] in POSITION_CODES:
        return POSITION_CODES[raw[0]]
    if portrait == 0:
        return "low"
    return "top" if portrait > SMALL_BOX else ""


def windows(font: Font, raw: str, portrait: int) -> tuple[tuple[str, ...], ...]:
    """The page as the game shows it: one tuple of lines for each press of A.

    Measured in the running game: lines wrap at 144 pixels (128 in the small box),
    a window holds four lines (two in the small box), text past that is paged
    automatically, a page break starts a new window, and a first character of
    ``!``, ``@`` or ``#`` is consumed as the box position.
    """
    limit, rows = LIMITS[portrait == SMALL_BOX]
    if raw[:1] in POSITION_CODES:
        raw = raw[1:]
    shown = []
    for segment in raw.split(PAGE_BREAK):
        lines = _wrap(font, segment, limit)
        shown += [tuple(lines[start:start + rows]) for start in range(0, len(lines), rows)]
    return tuple(shown)


def _wrap(font: Font, text: str, limit: int) -> list[str]:
    lines, cursor = [], 0
    while True:
        while cursor < len(text) and text[cursor] in (" ", LINE_BREAK):
            cursor += 1
        if cursor >= len(text):
            return lines
        width, position, space, stop = 0, cursor, -1, None
        while position < len(text):
            character = text[position]
            if character == LINE_BREAK:
                stop = position
                break
            if character == INK:
                position = min(position + 2, len(text))
                continue
            if character == " ":
                space = position
            if width + font.advance(ord(character)) > limit:
                stop = space if space >= 0 else max(position, cursor + 1)
                break
            width += font.advance(ord(character))
            position += 1
        stop = position if stop is None else stop
        lines.append(text[cursor:stop])
        cursor = stop


@dataclass(frozen=True, slots=True)
class Entry:
    """One step of a base-game conversation."""

    record: int
    next: int
    kind: int
    argument: int
    handle: int | None = None
    text: str | None = None


@dataclass(frozen=True, slots=True)
class Conversation:
    event: int
    address: int
    entries: tuple[Entry, ...]
    end: int


def _text_profile(profile):
    text = profile.text_strings
    if text is None or None in (text.event_table, text.event_count, text.event_pool,
                                text.table_literal):
        raise ConversationError(f"profile {profile.id!r} declares no conversation table")
    return text


def _u32(image: bytes, offset: int) -> int:
    return struct.unpack_from("<I", image, offset)[0]


def retail_containers(image: bytes, profile) -> dict[int, bytes]:
    """The decoded bytes of each base-game dialogue container, by selector."""
    table = _container_table_offset(profile)
    found = {}
    for selector in range(_text_profile(profile).live_selectors or 0):
        found[selector] = bytes(unpack(image, _u32(image, table + 4 * selector) - GBA_ROM_BASE).data)
    return found


def read_conversations(image: bytes, profile) -> dict[int, Conversation]:
    """Every conversation the event table names, by its first event number."""
    text = _text_profile(profile)
    low, high = (int(address) for address in text.event_pool)
    containers: dict[int, bytes] = {}
    live = _u32(image, int(text.table_literal) - GBA_ROM_BASE) - GBA_ROM_BASE

    def stored(selector: int) -> bytes:
        """The container the image's own table names, which a built image has moved."""
        if selector not in containers:
            word = _u32(image, live + 4 * selector)
            try:
                containers[selector] = bytes(unpack(image, word - GBA_ROM_BASE).data)
            except (ContainerError, IndexError, struct.error, ValueError):
                containers[selector] = b""
        return containers[selector]

    table = int(text.event_table) - GBA_ROM_BASE
    found, seen = {}, set()
    for event in range(text.event_count):
        address = _u32(image, table + 4 * event)
        if address in seen or not low <= address < high:
            continue
        seen.add(address)
        entries, at = [], address - GBA_ROM_BASE
        while low <= _u32(image, at) < high and len(entries) <= MAX_ENTRIES * 16:
            record = _u32(image, at) - GBA_ROM_BASE
            step, kind, argument = struct.unpack_from("<HBB", image, record)
            handle = spoken = None
            if kind in (SPEECH, VALUE_SPEECH):
                handle = _u32(image, record + 4)
                selector, start, size = unpack_handle(handle)
                data = stored(selector)
                if size and start + size <= len(data):
                    spoken = data[start:start + size].decode("utf-16-le", "replace")
            entries.append(Entry(record, step, kind, argument, handle, spoken))
            at += 4
        found[event] = Conversation(event, address, tuple(entries), _u32(image, at))
    return found


def line_key(handle: int, event: int | None = None) -> str:
    """The document key of a spoken line; with an event, of that conversation's records only."""
    selector, start, size = unpack_handle(handle)
    return f"{selector}:0x{start:04X}:{size}" + ("" if event is None else f"@{event:04d}")


def shared_text(conversations) -> dict[int, int]:
    """For each spoken handle, how many other handles read some of the same bytes."""
    spans: dict[int, list] = {}
    for conversation in conversations.values():
        for entry in conversation.entries:
            if entry.handle is not None:
                selector, start, size = unpack_handle(entry.handle)
                spans.setdefault(selector, set()).add((start, start + size, entry.handle))
    counts = {}
    for group in spans.values():
        ordered = sorted(group)
        for index, (start, end, handle) in enumerate(ordered):
            counts[handle] = sum(1 for other in ordered[:index] if other[1] > start) + sum(
                1 for other in ordered[index + 1:] if other[0] < end)
    return counts


@dataclass(frozen=True, slots=True)
class Line:
    """An edit to one base-game line, with the wording it was made against."""

    text: str
    was: str


@dataclass(frozen=True, slots=True)
class Talk:
    """A conversation the project made. Pages and portraits run in parallel."""

    name: str = ""
    pages: tuple[str, ...] = ()
    portraits: tuple[int, ...] = ()
    resume: int = 0
    sets: str = ""
    when: str = ""
    then: str = ""


@dataclass(frozen=True, slots=True)
class Document:
    lines: dict = field(default_factory=dict)
    talks: dict = field(default_factory=dict)
    flags: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "lines", MappingProxyType(dict(self.lines)))
        object.__setattr__(self, "talks", MappingProxyType(dict(self.talks)))
        object.__setattr__(self, "flags", MappingProxyType(dict(self.flags)))

    def is_empty(self) -> bool:
        return not (self.lines or self.talks)


def talk_order(key: str) -> int:
    return int(key.rsplit("-", 1)[1])


def read_document(project_dir: str | Path) -> Document:
    """The project's conversations, or an empty document when it has none."""
    path = Path(project_dir) / CONVERSATIONS_FILE
    try:
        flags = dict(story_flags.read_flags(project_dir).names)
    except story_flags.StoryFlagError as exc:
        raise ConversationError(str(exc)) from exc
    if not path.exists():
        return Document(flags=flags)
    try:
        document = load_toml(path.read_text(encoding="utf-8"))
    except (ProjectFormatError, OSError) as exc:
        raise ConversationError(f"{path}: {exc}") from exc
    if set(document) - {"lines", "talks", "flags"} or not all(
            isinstance(value, dict) for value in document.values()):
        raise ConversationError(f"{path}: holds something that is not a conversation document")
    lines, talks = {}, {}
    for key, row in document.get("lines", {}).items():
        if not _LINE_KEY.fullmatch(key) or not isinstance(row, dict) or not all(
                isinstance(row.get(name), str) for name in ("text", "was")):
            raise ConversationError(f"{path}: line {key!r} is not an edited game line")
        lines[key] = Line(row["text"], row["was"])
    for key, row in document.get("talks", {}).items():
        where = f"{path}: {key}"
        if not TALK_ID.fullmatch(key) or not isinstance(row, dict):
            raise ConversationError(f"{where} is not a conversation")
        pages, portraits = row.get("pages", []), row.get("portraits", [])
        if not (isinstance(pages, list) and isinstance(portraits, list)
                and all(isinstance(page, str) for page in pages)
                and all(type(portrait) is int for portrait in portraits)
                and type(row.get("resume", 0)) is int
                and all(isinstance(row.get(name, ""), str)
                        for name in ("name", "sets", "when", "then"))):
            raise ConversationError(f"{where} holds a value of the wrong kind")
        talks[key] = Talk(row.get("name", ""), tuple(pages), tuple(portraits),
                          row.get("resume", 0), row.get("sets", ""), row.get("when", ""),
                          row.get("then", ""))
    return Document(lines, talks, flags)


def write_document(project_dir: str | Path, document: Document) -> Path:
    """Persist the conversation document, or remove it when nothing is left.

    Flags are kept in the story's registry, where a number once given is never
    given again. A flag this document introduces is added there; none is removed.
    """
    path = Path(project_dir) / CONVERSATIONS_FILE
    registry = story_flags.read_flags(project_dir)
    story_flags.write_flags(project_dir, story_flags.Flags(
        {**{name: number for name, number in document.flags.items()
            if number not in registry.used()}, **registry.names}, registry.retired))
    if document.is_empty():
        path.unlink(missing_ok=True)
        return path
    body: dict = {}
    if document.lines:
        body["lines"] = {key: {"text": line.text, "was": line.was}
                         for key, line in sorted(document.lines.items())}
    if document.talks:
        body["talks"] = {}
        for key in sorted(document.talks, key=talk_order):
            talk = document.talks[key]
            row: dict = {"name": talk.name, "pages": list(talk.pages),
                         "portraits": list(talk.portraits)}
            if talk.resume:
                row["resume"] = talk.resume
            for name in ("sets", "when", "then"):
                if getattr(talk, name):
                    row[name] = getattr(talk, name)
            body["talks"][key] = row
    path.parent.mkdir(parents=True, exist_ok=True)
    return replace_document(path, dump_toml(body))


free_flags = story_flags.free_flags


@dataclass(frozen=True, slots=True)
class Capacity:
    """How much of the authored dialogue space a project uses."""

    bytes_used: int
    containers_used: int
    bytes_total: int = (TABLE_SLOTS - 7) * CONTAINER_BYTES
    containers_total: int = TABLE_SLOTS - 7


def capacity_of(document: Document, profile) -> Capacity:
    """What the document's wording will take, by the rule the build fills containers with."""
    first = _text_profile(profile).live_selectors
    sizes, seen = [0], set()
    for text in [document.lines[key].text for key in sorted(document.lines)] + [
            page for key in sorted(document.talks, key=talk_order)
            for page in document.talks[key].pages]:
        try:
            raw = encode(text)
        except ConversationError:
            continue
        if raw in seen:
            continue
        seen.add(raw)
        if sizes[-1] + 2 * len(raw) > CONTAINER_BYTES:
            sizes.append(0)
        sizes[-1] += 2 * len(raw)
    return Capacity(sum(sizes), len(sizes) if seen else 0,
                    (TABLE_SLOTS - first) * CONTAINER_BYTES, TABLE_SLOTS - first)


@dataclass(frozen=True, slots=True)
class ConversationMaterialization:
    changes: tuple[ByteChange, ...] = ()
    reserved: tuple = ()
    generated_allocations: tuple = ()
    addresses: dict = field(default_factory=dict)
    capacity: Capacity = Capacity(0, 0)
    records: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "addresses", MappingProxyType(dict(self.addresses)))
        object.__setattr__(self, "records", MappingProxyType(dict(self.records)))


def resolver(image: bytes, profile, addresses):
    """Turn a character's conversation reference into the address its record holds."""
    text = _text_profile(profile)

    def resolve(reference: str, where: str) -> int:
        match = EVENT_REF.fullmatch(reference)
        if match and int(match.group(1)) < text.event_count:
            return _u32(image, int(text.event_table) - GBA_ROM_BASE + 4 * int(match.group(1)))
        if reference in addresses:
            return addresses[reference]
        raise ConversationError(
            f"{where}: it is set to say {reference!r}, which is not a conversation in "
            "this project")
    return resolve


def _checked_talks(document: Document, font: Font, profile) -> dict[str, tuple]:
    """Every authored conversation as validated stored pages, or one refusal."""
    free = set(free_flags(profile))
    numbers = list(document.flags.values())
    for name, number in document.flags.items():
        if number not in free or numbers.count(number) > 1:
            raise ConversationError(
                f"flag {name!r} is numbered {number}, which the base game uses or "
                "another flag already has")
    checked = {}
    for key, talk in document.talks.items():
        label = f"conversation {talk.name or key!r}"
        if not talk.pages or len(talk.pages) != len(talk.portraits):
            raise ConversationError(f"{label}: it needs at least one page, each with a portrait")
        pages = []
        for number, (page, portrait) in enumerate(zip(talk.pages, talk.portraits), start=1):
            raw = encode(page)
            problem = page_problem(font, raw, portrait)
            if problem:
                raise ConversationError(f"{label}, page {number}: {problem}")
            pages.append((raw, portrait))
        for name in (talk.sets, talk.when):
            if name and name not in document.flags:
                raise ConversationError(f"{label}: the flag {name!r} has no number")
        if talk.when:
            other = document.talks.get(talk.then)
            if other is None or talk.then == key or other.when:
                raise ConversationError(
                    f"{label}: what it says once {talk.when!r} is remembered must be "
                    "another conversation that has no such rule of its own")
        elif talk.then:
            raise ConversationError(f"{label}: it names a second conversation but no flag")
        if not 0 <= talk.resume < len(pages) or (talk.resume and (talk.when or talk.sets)):
            raise ConversationError(
                f"{label}: the page it starts from next time must be one of its pages, "
                "and the first when it uses a flag")
        checked[key] = tuple(pages)
    return checked


def page_problem(font: Font, raw: str, portrait: int) -> str:
    """Why these units and portrait cannot be a spoken page, or an empty string."""
    problem = text_problem(font, raw)
    if not problem and not 0 <= portrait <= PORTRAIT_MAX:
        problem = "Its portrait is not one the game can show."
    return problem


def materialize_conversations(image: bytes, profile, document: Document,
                              reserved=(), events=None) -> ConversationMaterialization:
    """Compile every edited line and authored conversation into attributed changes.

    ``events`` holds each event that is built as a conversation, by id: its pages
    are stored beside the project's other dialogue, and its records are placed as
    a conversation a character or a region can name.
    """
    events = events or {}
    if document.is_empty() and not events:
        return ConversationMaterialization()
    text = _text_profile(profile)
    font = Font(image, profile)
    spec = OPCODE_SETS[CONTRACTS[profile.id]["encoding"]]
    talks = _checked_talks(document, font, profile)

    sites: dict[int, list[int]] = {}
    spoken: dict[int, str] = {}
    scoped: dict[str, set[int]] = {}
    for event, conversation in read_conversations(image, profile).items():
        for entry in conversation.entries:
            if entry.kind == SPEECH and entry.text is not None:
                sites.setdefault(entry.handle, set()).add(entry.record)
                scoped.setdefault(line_key(entry.handle, event), set()).add(entry.record)
                spoken[entry.handle] = entry.text
    by_key = {line_key(handle): handle for handle in sites}
    claimed = {record for key in document.lines if "@" in key for record in scoped.get(key, ())}

    wanted: list[str] = []
    edits = []
    for key in sorted(document.lines):
        line = document.lines[key]
        handle = by_key.get(key.split("@")[0])
        records = scoped.get(key) if "@" in key else sites.get(handle, set()) - claimed
        if handle is None or records is None:
            raise ConversationError(f"line {key}: the base game has no such spoken line")
        if decode(spoken[handle]) != line.was:
            raise ConversationError(
                f"line {key}: the base-game wording is not the one this edit was made "
                "for, so it is not applied")
        raw = encode(line.text)
        problem = text_problem(font, raw, spoken[handle])
        if problem:
            raise ConversationError(f"line {key}: {problem}")
        edits.append((key, records, raw))
        wanted.append(raw)
    for key in sorted(talks, key=talk_order):
        wanted += [raw for raw, _portrait in talks[key]]
    for compiled in events.values():
        wanted += compiled.pages

    placed: dict[str, int] = {}
    containers: list[bytearray] = [bytearray()]
    first = text.live_selectors
    for raw in wanted:
        if raw in placed:
            continue
        stored = raw.encode("utf-16-le")
        if len(containers[-1]) + len(stored) > CONTAINER_BYTES:
            containers.append(bytearray())
        selector = first + len(containers) - 1
        if selector >= TABLE_SLOTS:
            raise ConversationError(
                f"the project's dialogue needs more than the {TABLE_SLOTS - first} "
                "containers the game can address; shorten or remove some")
        placed[raw] = DialogueHandle(selector, len(containers[-1]), len(stored)).encode()
        containers[-1] += stored
    capacity = Capacity(sum(len(data) for data in containers), len(containers),
                        (TABLE_SLOTS - first) * CONTAINER_BYTES, TABLE_SLOTS - first)

    literal_at = int(text.table_literal) - GBA_ROM_BASE
    table_at = _container_table_offset(profile)
    naming = (table_at + GBA_ROM_BASE).to_bytes(4, "little")
    if image[literal_at:literal_at + 4] != naming or sum(
            1 for at in range(0, len(image) - 3, 4) if image[at:at + 4] == naming) != 1:
        raise ConversationError(
            "the dialogue container table is not named by exactly one word in this "
            "image, so it cannot be moved aside")

    def flag_record(step: int, lines) -> bytes:
        body = struct.pack("<HB", step, SCRIPT) + assemble_source(tuple(lines), spec)
        return body + bytes(-len(body) % 4)

    blobs = {}
    for key in sorted(talks, key=talk_order):
        talk = document.talks[key]
        runs = [(talks[key], talk.sets)]
        if talk.when:
            runs.append((talks[talk.then], document.talks[talk.then].sets))
        total = bool(talk.when) + sum(len(pages) + bool(sets) for pages, sets in runs)
        if total > MAX_ENTRIES:
            raise ConversationError(
                f"conversation {talk.name or key!r} has {total} steps; the most is {MAX_ENTRIES}")
        records = []
        if talk.when:
            records.append(flag_record(1, (
                f"push_byte {document.flags[talk.when]}", "native_stack 27",
                "branch_if_zero 5", f"push_byte {1 + len(runs[0][0]) + bool(runs[0][1])}",
                "terminate", "terminate")))
        for pages, sets in runs:
            last = len(records) + len(pages) - 1
            for raw, portrait in pages:
                step = total if len(records) == last and not sets else len(records) + 1
                records.append(struct.pack("<HBBI", step, SPEECH, portrait, placed[raw]))
            if sets:
                records.append(flag_record(total, (
                    f"push_byte {document.flags[sets]}", "native_stack 29", "terminate")))
        blobs[key] = (records, talk.resume)
    names = {key: talk.name for key, talk in document.talks.items()}
    for key, compiled in events.items():
        blobs[key] = (compiled.records(placed), 0)

    def request(owner: str, size: int, kind, evidence: str, addressability=None):
        return AllocationRequest(AnchorId(owner), owner, size, 4, kind=kind,
                                 addressability=addressability, evidence=evidence)

    packed = []
    for data in containers:
        payload = pack(bytes(data))
        try:
            validate_retail_termination(payload)
        except ContainerError as exc:
            raise ConversationError(f"an authored container does not pack cleanly: {exc}") from exc
        packed.append(payload)
    table_owner = f"{DOMAIN}:table"
    requests = [request(f"{DOMAIN}:container-{first + index:02d}", len(payload),
                        AllocationKind.PACKED_STREAM,
                        "a dialogue container on a selector past the base game's, read "
                        "through the moved table by both container loaders",
                        Addressability.EXPANDED_ONLY)
                for index, payload in enumerate(packed)]
    requests.append(request(table_owner, 4 * TABLE_SLOTS, AllocationKind.CONVERSATION_DATA,
                            "the 64-slot container table copied aside, named by one word"))
    requests += [request(f"{DOMAIN}:{key}", sum(map(len, records)) + 4 * len(records) + 4,
                         AllocationKind.CONVERSATION_DATA,
                         "one authored conversation: its records, then its pointer array")
                 for key, (records, _resume) in blobs.items()]
    try:
        allocations = {item.request.owner: item for item in allocate(
            profile, tuple(requests),
            occupied=tuple(span if isinstance(span, OwnedRegion)
                           else OwnedRegion(span, "build reservation") for span in reserved))}
    except AllocationError as exc:
        raise ConversationError(f"there is not enough free ROM space: {exc}") from exc

    padding = profile.generated_expansion.padding_byte
    changes: list[ByteChange] = []
    generated: list = []
    source = RomRange(FileOffset(table_at), 4 * TABLE_SLOTS)

    def emit(owner: str, payload: bytes, reason: str, pointer_offset) -> int:
        allocation = allocations[owner]
        at = allocation.range.start.value
        old = image[at:at + len(payload)] if at < len(image) else bytes([padding]) * len(payload)
        changes.append(ByteChange(at, old, payload, owner, reason))
        if allocation.is_expanded:
            generated.append(allocation.generated_allocation_provenance(
                domain=DOMAIN, resource=owner, pointer_offset=pointer_offset,
                source_range=source))
        return allocation.rom_address

    table = bytearray(image[table_at:table_at + 4 * TABLE_SLOTS])
    table_file = allocations[table_owner].range.start.value
    for index, payload in enumerate(packed):
        selector = first + index
        address = emit(f"{DOMAIN}:container-{selector:02d}", payload,
                       f"authored dialogue container on selector {selector}",
                       table_file + 4 * selector)
        struct.pack_into("<I", table, 4 * selector, address)
    moved = emit(table_owner, bytes(table),
                 f"the container table with {len(packed)} authored selectors", literal_at)
    changes.append(ByteChange(literal_at, naming, moved.to_bytes(4, "little"), table_owner,
                              "the one word that names the container table"))
    for key, records, raw in edits:
        for record in sorted(records):
            changes.append(ByteChange(
                record + 4, image[record + 4:record + 8], placed[raw].to_bytes(4, "little"),
                f"{DOMAIN}:line:{key}", f"line {key}: its record now reads the edited wording"))
    addresses, placed_records = {}, {}
    for key, (records, resume) in blobs.items():
        owner = f"{DOMAIN}:{key}"
        base = allocations[owner].rom_address
        offsets, cursor = [], 0
        for record in records:
            offsets.append(base + cursor)
            cursor += len(record)
        payload = b"".join(records) + struct.pack(f"<{len(offsets)}I", *offsets) + struct.pack(
            "<I", resume)
        emit(owner, payload, f"conversation {names.get(key) or key!r}", None)
        addresses[key] = base + cursor
        placed_records[key] = tuple(zip(offsets, map(len, records)))
    return ConversationMaterialization(
        tuple(changes),
        tuple(OwnedRegion(allocation.range, owner) for owner, allocation in allocations.items()),
        tuple(generated), addresses, capacity, placed_records)
