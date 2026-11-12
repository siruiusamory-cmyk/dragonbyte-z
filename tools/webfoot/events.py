"""Events: what happens in the story, the project document, and the build domain.

DRAGONBYTE-Z-APP-006. The game has no event system of its own to extend. It has
one script interpreter and a handful of places on a map that start it, and each
of those places is plain data. An authored event is a list of steps and one
trigger, and it is built into the structure the game already reads for that
trigger:

* talking to a character, or walking into a region, runs a conversation: an
  array of records the engine steps through, where a spoken page is one record
  and every other step is a script record whose result picks the next record;
* entering or leaving a map runs one script body named by the map's row.

Nothing in the engine is replaced and no base-game script is rewritten. A map
row's script word, region count and region list word are the only base-game
bytes an event changes, and a region list is re-emitted as a longer copy so the
list the base game reads elsewhere stays as it was.

A step is offered only when the running game was seen to do it. ``PROVEN``
names what has passed; anything else is refused with the reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import struct
from types import MappingProxyType

from .allocation import (Addressability, AllocationError, AllocationKind,
                         AllocationRequest, allocate)
from .binary import GBA_ROM_BASE, FileOffset
from .conversations import encode
from .data.placement_contracts import CONTRACTS
from .data.script_specs import OPCODE_SETS
from .formats import map_entry as me
from .formats.script_vm import ScriptError, assemble_source, decode_instruction
from .layout import AnchorId, OwnedRegion, RomRange
from .map_authoring import read_records, record_size, table_offset
from .project.atomic import replace_document
from .project.format import ProjectFormatError, dump_toml, load_toml
from .write import ByteChange

EVENTS_FILE = Path("events") / "events.toml"
DOMAIN = "events"
EVENT_ID = re.compile(r"evt-[0-9]{1,6}")
_CANONICAL = re.compile(r"map:(\d{4})")
_AUTHORED = re.compile(r"map-new:([a-z][a-z0-9_-]*)")
TALK, ENTER, LEAVE, REGION = "talk", "enter", "leave", "region"
TRIGGERS = (TALK, ENTER, LEAVE, REGION)
SPEECH, SCRIPT = 5, 0
MAX_RECORDS = 255
MAX_REGIONS = 0xFF
ITEM_MAX = 0x0FFFFFFF
CELL = 8
REGION_RECORD = struct.Struct("<II4hI")
REGION_CONVERSATION = 0x0800742D
REGION_SCRIPT = 0x08007387
REGION_ACTIVATIONS = {"walk_in": 0x08007791, "once": 0x080077DF, "press_a": 0x0800770D}
NATIVES = {"set": 29, "clear": 30, "give": 147, "take": 148, "open": 43, "close": 44,
           "music": 35}
SHAPES = {
    "say": (int, str), "ask": (int, str, str, str),
    "set": (str,), "clear": (str,), "give": (int,), "take": (int,),
    "open": (int, int, int, int), "close": (int, int, int, int), "music": (int,),
    "else": (), "end_if": (), "end": (),
}
TESTS = {"flag": (str,), "not_flag": (str,), "item": (int, int), "answer": (int,)}
PROVEN = frozenset({
    "say", "ask", "set", "clear", "give", "take", "open", "close", "else", "end_if", "end",
    "if flag", "if not_flag", "if item", "if answer", "appears",
    TALK, ENTER, LEAVE, REGION, "region walk_in", "region once", "region press_a", "chain"})
NOT_PROVEN = ("has not been seen working in the running game by this version of "
              "DragonByte Z, so it is not built")


class EventError(ProjectFormatError):
    """An event document or step the build must not act on."""


@dataclass(frozen=True, slots=True)
class Event:
    """One authored event. ``steps`` is a flat list; If, Else and End If nest it."""

    name: str = ""
    group: str = ""
    trigger: str = TALK
    map: str = ""
    rect: tuple = ()
    activation: str = ""
    steps: tuple = ()


def event_order(key: str) -> int:
    return int(key.rsplit("-", 1)[1])


def label(key: str, event: Event) -> str:
    return f"event {event.name or key!r}"


def read_document(project_dir: str | Path) -> dict[str, Event]:
    """The project's events by id, or nothing when it has none."""
    path = Path(project_dir) / EVENTS_FILE
    if not path.exists():
        return {}
    try:
        document = load_toml(path.read_text(encoding="utf-8"))
    except (ProjectFormatError, OSError) as exc:
        raise EventError(f"{path}: {exc}") from exc
    table = document.get("events")
    if set(document) != {"events"} or not isinstance(table, dict):
        raise EventError(f"{path}: holds something that is not an event document")
    events = {}
    for key, row in table.items():
        where = f"{path}: {key}"
        if not EVENT_ID.fullmatch(key) or not isinstance(row, dict):
            raise EventError(f"{where} is not an event")
        steps, rect = row.get("steps", []), row.get("rect", [])
        if set(row) - {"name", "group", "trigger", "map", "rect", "activation", "steps"} or not (
                all(isinstance(row.get(name, ""), str)
                    for name in ("name", "group", "trigger", "map", "activation"))
                and isinstance(rect, list) and all(type(item) is int for item in rect)
                and isinstance(steps, list)
                and all(isinstance(step, list) and step and isinstance(step[0], str)
                        and all(type(item) in (int, str) for item in step) for step in steps)):
            raise EventError(f"{where} holds a value of the wrong kind")
        events[key] = Event(row.get("name", ""), row.get("group", ""), row.get("trigger", TALK),
                            row.get("map", ""), tuple(rect), row.get("activation", ""),
                            tuple(tuple(step) for step in steps))
    return events


def write_document(project_dir: str | Path, events) -> Path:
    """Persist the event document, or remove it when no event is left."""
    path = Path(project_dir) / EVENTS_FILE
    if not events:
        path.unlink(missing_ok=True)
        return path
    table = {}
    for key in sorted(events, key=event_order):
        event = events[key]
        row: dict = {"name": event.name, "trigger": event.trigger}
        if event.group:
            row["group"] = event.group
        if event.map:
            row["map"] = event.map
        if event.rect:
            row["rect"] = list(event.rect)
        if event.activation:
            row["activation"] = event.activation
        row["steps"] = [list(step) for step in event.steps]
        table[key] = row
    path.parent.mkdir(parents=True, exist_ok=True)
    return replace_document(path, dump_toml({"events": table}))


@dataclass(slots=True)
class _Node:
    index: int
    step: tuple
    then: list = field(default_factory=list)
    other: list | None = None
    other_index: int = -1


def gate(step: tuple) -> str:
    """The name under which a step's proof is recorded."""
    return f"if {step[1]}" if step[0] == "if" and len(step) > 1 else step[0]


def step_problem(step: tuple, flags, trigger: str = TALK) -> str:
    """Why this one step cannot be built, in plain words, or an empty string."""
    kind = step[0]
    shape = TESTS.get(step[1] if len(step) > 1 else "") if kind == "if" else SHAPES.get(kind)
    values = step[2:] if kind == "if" else step[1:]
    if shape is None:
        return "It is not a step DragonByte Z knows."
    if len(values) != len(shape) or any(type(value) is not wanted
                                        for value, wanted in zip(values, shape)):
        return "It is missing a value, or holds one of the wrong kind."
    if gate(step) not in PROVEN:
        return f"This kind of step {NOT_PROVEN}."
    if kind in ("say", "ask") and trigger in (ENTER, LEAVE):
        return ("An event that runs while a map loads cannot show dialogue. Put the "
                "words on a character or a region instead.")
    if kind in ("set", "clear") or (kind == "if" and step[1] in ("flag", "not_flag")):
        if values[0] not in flags:
            return f"The flag {values[0]!r} is not in the story's flags."
    if kind in ("give", "take") or (kind == "if" and step[1] == "item"):
        if not 0 < values[0] <= ITEM_MAX:
            return "That is not an item number."
        if kind == "if" and not 1 <= values[1] <= 250:
            return "The count to test for must be between 1 and 250."
    if kind == "if" and step[1] == "answer" and values[0] not in (1, 2):
        return "An answer is 1 or 2: the first or the second choice."
    if kind in ("open", "close"):
        x1, y1, x2, y2 = values
        if not (0 <= x1 < x2 <= 0x7FFF and 0 <= y1 < y2 <= 0x7FFF) or any(
                value % CELL for value in values):
            return "A passage is a rectangle of whole 8-pixel squares on the map."
    if kind == "music" and not 0 <= values[0] <= 0xFFFF:
        return "That is not a music number."
    return ""


def tree(event: Event, flags, where: str) -> list[_Node]:
    """The flat step list as nested blocks, or one refusal naming the step."""
    if not event.steps:
        raise EventError(f"{where}: it needs at least one step")
    root: list[_Node] = []
    stack: list[tuple[list, _Node | None]] = [(root, None)]
    for index, step in enumerate(event.steps):
        here = f"{where}, step {index + 1}"
        kind = step[0]
        block, owner = stack[-1]
        if block and block[-1].step[0] == "end" and kind not in ("else", "end_if"):
            raise EventError(f"{here}: it comes after End, so it can never run")
        problem = step_problem(step, flags, event.trigger)
        if problem:
            raise EventError(f"{here}: {problem}")
        if kind == "if":
            node = _Node(index, step)
            block.append(node)
            stack.append((node.then, node))
        elif kind in ("else", "end_if"):
            if owner is None or (kind == "else" and owner.other is not None):
                raise EventError(f"{here}: there is no If for it to belong to")
            if not block:
                raise EventError(f"{here}: the branch before it is empty, so it does nothing")
            if kind == "else":
                owner.other, owner.other_index = [], index
                stack[-1] = (owner.other, owner)
            else:
                stack.pop()
        else:
            block.append(_Node(index, step))
    if len(stack) > 1:
        raise EventError(f"{where}: an If is never closed; add End If")
    return root


def _push(value: int) -> str:
    return f"push_byte {value}" if 0 <= value <= 255 else f"push_signed_magnitude {value}"


def _action(step: tuple, flags) -> list[str]:
    kind, values = step[0], step[1:]
    if kind in ("set", "clear"):
        return [_push(flags[values[0]]), f"native_stack {NATIVES[kind]}"]
    if kind in ("open", "close"):
        return ["push_many 4 " + " ".join(map(str, values)), f"native_stack {NATIVES[kind]}"]
    return [_push(values[0]), f"native_stack {NATIVES[kind]}"]


def _condition(step: tuple, flags) -> list[str]:
    form, values = step[1], step[2:]
    if form == "flag":
        return [_push(flags[values[0]]), "native_stack 27"]
    if form == "not_flag":
        return [_push(flags[values[0]]), "native_stack 28"]
    if form == "item":
        return [_push(values[0]), "native_stack 146", _push(values[1]), "greater_equal"]
    return ["native_stack 24", _push(values[0] - 1), "equal"]


def spoken(step: tuple) -> str:
    """The stored text of a Say or Ask step; an Ask carries its choices as - lines."""
    text = encode(step[2])
    return text + "".join(f"\n- {option}" for option in step[3:]) if step[0] == "ask" else text


@dataclass(slots=True)
class _Label:
    at: int = -1


@dataclass(frozen=True, slots=True)
class Compiled:
    """One event as a conversation: its pages, and its records once pages are stored."""

    pages: tuple[str, ...]
    plan: tuple
    spec: object

    def steps(self) -> tuple[int, ...]:
        """For each record, the step of the event it was built from."""
        return tuple(item[3] for item in self.plan)

    def records(self, placed) -> list[bytes]:
        built = []
        for index, (kind, payload, target, _step) in enumerate(self.plan):
            follows = index + 1 if target is None or kind == "test" else target.at
            if kind == "speech":
                built.append(struct.pack("<HBBI", follows, SPEECH, payload[0], placed[payload[1]]))
                continue
            lines = list(payload)
            if kind == "test":
                lines += ["branch_if_zero 3", "terminate", f"push_byte {target.at}"]
            body = struct.pack("<HB", follows, SCRIPT) + assemble_source(
                tuple(lines + ["terminate"]), self.spec)
            built.append(body + bytes(-len(body) % 4))
        return built


def uses_dialogue(event: Event) -> bool:
    return any(step[0] in ("say", "ask") for step in event.steps)


def as_conversation(event: Event) -> bool:
    """Whether this event is built as a conversation rather than one script body."""
    return event.trigger == TALK or (event.trigger == REGION and uses_dialogue(event))


def compile_conversation(key: str, event: Event, flags, profile, check_text) -> Compiled:
    """One talk or spoken-region event as conversation records, or one refusal."""
    where = label(key, event)
    plan: list = []
    pages: list[str] = []
    end = _Label()

    def emit(block: list[_Node]) -> None:
        for node in block:
            kind = node.step[0]
            if kind in ("say", "ask"):
                raw = spoken(node.step)
                problem = check_text(raw, node.step[1])
                if problem:
                    raise EventError(f"{where}, step {node.index + 1}: {problem}")
                pages.append(raw)
                plan.append(("speech", (node.step[1], raw), None, node.index))
            elif kind == "if":
                otherwise, done = _Label(), _Label()
                plan.append(("test", tuple(_condition(node.step, flags)), otherwise, node.index))
                emit(node.then)
                if node.other is not None:
                    plan.append(("script", (), done, node.other_index))
                    otherwise.at = len(plan)
                    emit(node.other)
                    done.at = len(plan)
                else:
                    otherwise.at = len(plan)
            elif kind == "end":
                plan.append(("script", (), end, node.index))
            else:
                plan.append(("script", tuple(_action(node.step, flags)), None, node.index))

    emit(tree(event, flags, where))
    end.at = len(plan)
    if len(plan) > MAX_RECORDS:
        raise EventError(f"{where}: it builds to {len(plan)} records; the most is {MAX_RECORDS}")
    return Compiled(tuple(pages), tuple(plan),
                    OPCODE_SETS[CONTRACTS[profile.id]["encoding"]])


def compile_talks(document, flags, profile, check_text) -> dict[str, Compiled]:
    """Every event that is built as a conversation, by id, in id order."""
    return {key: compile_conversation(key, document[key], flags, profile, check_text)
            for key in sorted(document, key=event_order) if as_conversation(document[key])}


def _size(lines, spec) -> int:
    return sum(3 if line.startswith("branch") else len(assemble_source((line, "terminate"), spec)) - 1
               for line in lines)


def compile_script(key: str, event: Event, flags, profile) -> tuple[bytes, tuple]:
    """One event as a single script body, and the byte span each step was built to."""
    where = label(key, event)
    spec = OPCODE_SETS[CONTRACTS[profile.id]["encoding"]]

    def emit(block: list[_Node]) -> list[tuple[list[str], int]]:
        chunks: list[tuple[list[str], int]] = []
        for node in block:
            kind = node.step[0]
            if kind == "if":
                then = emit(node.then)
                other = emit(node.other) if node.other is not None else []
                if other:
                    skip = 2 + sum(_size(lines, spec) for lines, _ in other)
                    then.append(([f"branch_forward {skip}"], node.other_index))
                skip = 2 + sum(_size(lines, spec) for lines, _ in then)
                chunks.append((_condition(node.step, flags) + [f"branch_if_zero {skip}"],
                               node.index))
                chunks += then + other
            elif kind == "end":
                chunks.append((["branch_forward end"], node.index))
            else:
                chunks.append((_action(node.step, flags), node.index))
        return chunks

    try:
        chunks = emit(tree(event, flags, where))
        total = sum(_size(lines, spec) for lines, _ in chunks)
        spans, cursor, source = [], 0, []
        for lines, step in chunks:
            size = _size(lines, spec)
            spans.append((step, cursor, cursor + size))
            cursor += size
            source += [f"branch_forward {total - cursor + 2}" if line == "branch_forward end"
                       else line for line in lines]
        body = assemble_source(tuple(source) + ("terminate",), spec)
    except ScriptError as exc:
        raise EventError(f"{where}: it is too long to build as one script ({exc})") from exc
    return body, tuple(spans)


def appearance(flags):
    """Turn a character's "appears" rule into the word the map loader tests.

    ``always`` is zero. A flag name is the loader's flag-set form and ``!name``
    its flag-clear form; both hold the flag's number in their low half.
    """
    def resolve(reference: str, where: str) -> int:
        if "appears" not in PROVEN:
            raise EventError(f"{where}: a rule to appear by {NOT_PROVEN}")
        if reference == "always":
            return 0
        name = reference.removeprefix("!")
        if name not in flags:
            raise EventError(
                f"{where}: it appears by the flag {name!r}, which is not in the story's flags")
        return (0x00020000 if reference.startswith("!") else 0x00010000) | flags[name]
    return resolve


def trace_path(output_path: str | Path) -> Path:
    return Path(output_path).with_suffix(".events.json")


def write_trace_table(output_path: str | Path, document, spans, flags) -> Path:
    """Beside a built image, where each authored step was built to.

    The debugger reads a running game's script cursor and looks it up here, so a
    step it reports is one the game ran and not one the project merely holds.
    """
    path = trace_path(output_path)
    if not document:
        path.unlink(missing_ok=True)
        return path
    table = {
        "flags": dict(sorted(flags.items())),
        "events": {key: {"name": document[key].name, "trigger": document[key].trigger,
                         "steps": [list(span) for span in spans.get(key, ())]}
                   for key in sorted(document, key=event_order)},
    }
    path.write_text(json.dumps(table, indent=1) + "\n", encoding="utf-8")
    return path


TRACE_LUA = """local log = io.open("{log}", "w")
local spans = {{{spans}}}
local flags = {{{flags}}}
local low, high = {low}, {high}
local last, seen = 0, {{}}
local function hit(address)
    if address < low or address >= high then return end
    for _, span in ipairs(spans) do
        if address >= span[1] and address < span[1] + span[2] then
            if last ~= span[1] then
                last = span[1]
                log:write("S " .. span[1] .. "\\n")
                log:flush()
            end
            return
        end
    end
end
local frame = 0
callbacks:add("frame", function()
    frame = frame + 1
    if frame == 2 then
        emu:setBreakpoint(function() hit(emu:readRegister("r1")) end, 0x08004066)
        emu:setBreakpoint(function() hit(emu:readRegister("r1")) end, 0x08012552)
    end
    if frame % 20 == 0 then
        for _, flag in ipairs(flags) do
            local value = (emu:read8({flag_bytes} + (flag >> 3)) >> (flag & 7)) & 1
            if seen[flag] ~= value then
                seen[flag] = value
                log:write("F " .. flag .. " " .. value .. "\\n")
                log:flush()
            end
        end
    end
end)
"""
FLAG_BYTES = 0x030010BD


def trace_log(output_path: str | Path) -> Path:
    return Path(output_path).with_suffix(".trace.txt")


def trace_script(output_path: str | Path) -> str:
    """An mGBA script that writes down each authored step the running game executes.

    It watches the interpreter's own cursor and the conversation runner's record,
    and reads the save flags from the game's memory, so nothing is added to the ROM.
    """
    table = json.loads(trace_path(output_path).read_text(encoding="utf-8"))
    spans = sorted((address, size) for event in table["events"].values()
                   for _step, address, size in event["steps"])
    return TRACE_LUA.format(
        log=trace_log(output_path).as_posix(),
        spans=", ".join(f"{{{address}, {size}}}" for address, size in spans),
        flags=", ".join(str(number) for number in sorted(table["flags"].values())),
        low=spans[0][0] if spans else 0, high=spans[-1][0] + spans[-1][1] if spans else 0,
        flag_bytes=FLAG_BYTES)


def read_trace(output_path: str | Path) -> list[tuple]:
    """What the game ran, in order: ``("step", event, step)`` and ``("flag", name, value)``."""
    try:
        table = json.loads(trace_path(output_path).read_text(encoding="utf-8"))
        lines = trace_log(output_path).read_text(encoding="utf-8").split("\n")
    except (OSError, ValueError):
        return []
    steps = {address: (key, step) for key, event in table["events"].items()
             for step, address, _size in event["steps"]}
    names = {number: name for name, number in table["flags"].items()}
    ran = []
    for line in lines:
        parts = line.split()
        if parts[:1] == ["S"] and int(parts[1]) in steps:
            ran.append(("step", *steps[int(parts[1])]))
        elif parts[:1] == ["F"] and int(parts[1]) in names:
            ran.append(("flag", names[int(parts[1])], parts[2] == "1"))
    return ran


def script_extent(image: bytes, start: int, spec) -> int:
    """The length of the base-game script at ``start``, when it is one unbroken run.

    Every reachable instruction must decode, every branch must land inside the
    run, and the run must have no gap, so that a copy of these bytes placed
    elsewhere behaves as the original does. Anything else is refused.
    """
    seen: dict[int, int] = {}
    todo = [start]
    while todo:
        at = todo.pop()
        while at not in seen:
            try:
                instruction = decode_instruction(image, at, spec)
            except (ScriptError, IndexError) as exc:
                raise EventError(f"the base-game script does not decode: {exc}") from exc
            seen[at] = instruction.encoded_length
            flow = spec.lookup(instruction.opcode).flow
            if instruction.target is not None:
                if flow == "count_back":
                    raise EventError("the base-game script loops, which is not copied")
                todo.append(instruction.target)
            if flow in ("stop", "forward"):
                break
            at += instruction.encoded_length
    end = max(at + size for at, size in seen.items())
    cursor = start
    while cursor < end:
        if cursor not in seen:
            raise EventError("the base-game script has bytes no path reaches, so its "
                             "extent is not certain")
        cursor += seen[cursor]
    return end - start


@dataclass(frozen=True, slots=True)
class EventMaterialization:
    changes: tuple[ByteChange, ...] = ()
    reserved: tuple = ()
    generated_allocations: tuple = ()
    authored_entry_patches: dict = field(default_factory=dict)
    spans: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "authored_entry_patches",
                           MappingProxyType(dict(self.authored_entry_patches)))
        object.__setattr__(self, "spans", MappingProxyType(dict(self.spans)))


def _field(name: str) -> int:
    return next(item.offset for item in me.MAP_ENTRY_LAYOUT if item.name == name)


def _u32(image: bytes, offset: int) -> int:
    return struct.unpack_from("<I", image, offset)[0]


def map_target(identity: str, authored_donors, total: int, where: str) -> tuple[int, str | None]:
    """The base-game row an event's map starts from, and the authored map's name if any."""
    canonical = _CANONICAL.fullmatch(identity)
    if canonical and int(canonical.group(1)) < total:
        return int(canonical.group(1)), None
    authored = _AUTHORED.fullmatch(identity)
    if authored and authored.group(1) in authored_donors:
        return authored_donors[authored.group(1)], authored.group(1)
    raise EventError(f"{where}: its map {identity!r} is not a map in this project")


def materialize_events(image: bytes, profile, document, flags, authored_donors,
                       conversations=None, records=None, reserved=()) -> EventMaterialization:
    """Compile every map-bound event into attributed changes.

    ``conversations`` gives the address of each event already built as a
    conversation, and ``records`` the address and size of each of its records;
    a region that speaks points at that conversation. ``authored_donors`` maps
    each authored map name to its donor's base-game index: an authored map
    starts from its donor's row, and what an event decides for it is returned as
    a patch to the row the authored-map domain emits.
    """
    conversations, records = conversations or {}, records or {}
    spec = OPCODE_SETS[CONTRACTS[profile.id]["encoding"]]
    rows = read_records(image, profile)
    stride, table_at = record_size(profile), table_offset(profile, len(image))
    fields = {ENTER: _field("entry_script_pointer_raw"), LEAVE: _field("exit_script_pointer_raw")}
    count_field, list_field = _field("variation_raw"), _field("triggers_pointer_raw")

    spans: dict[str, tuple] = {}
    for key, compiled in ((key, records.get(key)) for key in conversations):
        if compiled:
            spans[key] = tuple(compiled)
    scripts: dict[str, tuple] = {}
    claimed: dict[tuple, str] = {}
    regions: dict[str, list[str]] = {}
    targets: dict[str, tuple[int, str | None]] = {}
    requests = []

    def request(owner: str, size: int, evidence: str) -> None:
        requests.append(AllocationRequest(
            AnchorId(owner), owner, size, 4, kind=AllocationKind.EVENT_DATA,
            addressability=Addressability.EXPANDED_ONLY, evidence=evidence))

    for key in sorted(document, key=event_order):
        event = document[key]
        where = label(key, event)
        if event.trigger not in TRIGGERS:
            raise EventError(f"{where}: {event.trigger!r} is not a way to start an event")
        if event.trigger not in PROVEN:
            raise EventError(f"{where}: starting an event this way {NOT_PROVEN}")
        if event.trigger == TALK:
            if event.map or event.rect:
                raise EventError(f"{where}: an event a character says belongs to no map")
            continue
        base_index, name = targets.setdefault(
            event.map, map_target(event.map, authored_donors, len(rows), where))
        row_at = table_at + base_index * stride
        if event.trigger == REGION:
            if event.activation not in REGION_ACTIVATIONS or (
                    f"region {event.activation}" not in PROVEN):
                raise EventError(f"{where}: this way of setting off a region {NOT_PROVEN}")
            if len(event.rect) != 4 or not (
                    0 <= event.rect[0] < event.rect[2] <= 0x7FFF
                    and 0 <= event.rect[1] < event.rect[3] <= 0x7FFF):
                raise EventError(f"{where}: its region is not a rectangle on the map")
            regions.setdefault(event.map, []).append(key)
            request(f"{DOMAIN}:{key}:region", REGION_RECORD.size,
                    "one region record: its class, how it is set off, its rectangle and "
                    "the conversation or script it starts")
            if as_conversation(event):
                if key not in conversations:
                    raise EventError(f"{where}: its conversation was not built")
                continue
            tail = b""
        else:
            if event.rect or event.activation:
                raise EventError(f"{where}: only a region has a rectangle")
            other = claimed.setdefault((event.map, event.trigger), key)
            if other != key:
                raise EventError(
                    f"{where}: {label(other, document[other])} already runs when the "
                    f"player {'enters' if event.trigger == ENTER else 'leaves'} this map; "
                    "a map has one such event")
            word = _u32(image, row_at + fields[event.trigger])
            tail = b""
            if word:
                if "chain" not in PROVEN:
                    raise EventError(
                        f"{where}: the base game already runs a script of its own here, "
                        "and running an event before it has not been seen working, so "
                        "the game's script is left alone")
                start = word - GBA_ROM_BASE
                try:
                    tail = image[start:start + script_extent(image, start, spec)]
                except EventError as exc:
                    raise EventError(f"{where}: {exc}") from exc
        body, steps = compile_script(key, event, flags, profile)
        body = body[:-1] + tail if tail else body
        scripts[key] = (body, steps)
        request(f"{DOMAIN}:{key}:script", len(body),
                "one authored script body, named by a map row or a region record")

    for identity, keys in regions.items():
        base_index, name = targets[identity]
        total = rows[base_index].variation_raw + len(keys)
        if total > MAX_REGIONS:
            raise EventError(
                f"{identity} would hold {total} regions; the game counts a map's regions "
                f"in one byte, so {MAX_REGIONS} is the most a map can have")
        request(f"{DOMAIN}:{identity}:regions", 8 * total,
                "the map's region list re-emitted: every base-game entry in its "
                "original order, then the project's regions")
    if not requests:
        return EventMaterialization(spans=spans)

    try:
        allocations = {item.request.owner: item for item in allocate(
            profile, tuple(requests),
            occupied=tuple(span if isinstance(span, OwnedRegion)
                           else OwnedRegion(span, "build reservation") for span in reserved))}
    except AllocationError as exc:
        raise EventError(f"there is not enough free ROM space: {exc}") from exc
    padding = profile.generated_expansion.padding_byte
    changes: list[ByteChange] = []
    generated: list = []
    patches: dict[str, dict[int, bytes]] = {}

    def emit(owner: str, payload: bytes, reason: str, source: RomRange) -> int:
        allocation = allocations[owner]
        at = allocation.range.start.value
        changes.append(ByteChange(at, bytes([padding]) * len(payload), payload, owner, reason))
        generated.append(allocation.generated_allocation_provenance(
            domain=DOMAIN, resource=owner, pointer_offset=None, source_range=source))
        return allocation.rom_address

    def set_row(identity: str, offset: int, payload: bytes, owner: str, reason: str) -> None:
        base_index, name = targets[identity]
        if name is not None:
            patches.setdefault(name, {})[offset] = payload
            return
        at = table_at + base_index * stride + offset
        changes.append(ByteChange(at, image[at:at + len(payload)], payload, owner, reason))

    addresses = dict(conversations)
    for key, (body, steps) in scripts.items():
        event = document[key]
        row = RomRange(FileOffset(table_at + targets[event.map][0] * stride), stride)
        owner = f"{DOMAIN}:{key}:script"
        address = emit(owner, body, f"{label(key, event)}: its script", row)
        addresses[key] = address
        spans[key] = tuple((step, address + start, end - start) for step, start, end in steps)
        if event.trigger in fields:
            set_row(event.map, fields[event.trigger], address.to_bytes(4, "little"), owner,
                    f"{event.map}: the script the game runs when the player "
                    f"{'enters' if event.trigger == ENTER else 'leaves'}")
    for identity, keys in regions.items():
        base_index, name = targets[identity]
        row_at = table_at + base_index * stride
        row = RomRange(FileOffset(row_at), stride)
        count = rows[base_index].variation_raw
        old = _u32(image, row_at + list_field) - GBA_ROM_BASE if count else 0
        entries = bytearray(image[old:old + 8 * count])
        for key in keys:
            event = document[key]
            record = REGION_RECORD.pack(
                REGION_CONVERSATION if as_conversation(event) else REGION_SCRIPT,
                REGION_ACTIVATIONS[event.activation], *event.rect, addresses[key])
            entries += struct.pack("<II", 0, emit(
                f"{DOMAIN}:{key}:region", record, f"{label(key, event)}: its region", row))
        owner = f"{DOMAIN}:{identity}:regions"
        address = emit(owner, bytes(entries),
                       f"{identity}: its region list with {len(entries) // 8} entries", row)
        set_row(identity, count_field, bytes([len(entries) // 8]), owner,
                f"{identity}: the region count the engine's loop reads")
        set_row(identity, list_field, address.to_bytes(4, "little"), owner,
                f"{identity}: the field that names its region list")
    return EventMaterialization(
        tuple(changes),
        tuple(OwnedRegion(allocation.range, owner) for owner, allocation in allocations.items()),
        tuple(generated), patches, spans)
