"""Authored conversation scripts: the code block a talk already runs.

A dialogue record that renders text cannot set a save flag from its text (no
control unit writes the bitfield), but it can carry code: the record's KIND
selects one of eight handlers, and four of them reach the VM interpreter (kinds 0,
1, 2 and 4). This capability supports only the two whose code block sits at a
fixed field of the record, kind 0 at `+3` and kind 2 at `+8`; kinds 1 and 4 hand
the interpreter an address this domain does not model, so a record of that kind is
refused rather than guessed at. With that, a project can attach a declared effect
to a conversation the engine already starts.

The author-facing identity is the conversation's word array plus one entry. The
array is the structure the dialogue runner holds as its first word, its entries
are record pointers, and a record pointer names a record whose code block begins
at the kind's offset. No ROM address is typed for the code: the build derives it
from the entry, and from the same array it derives the room the authored body
has, which is the distance to the next record the conversation can select. A
body that does not fill that room is refused, because a shorter body would leave
canonical instructions behind a terminate that a branch may still reach.

Room is measured, never authored. The office conversation's entry 0 runs a
fifteen-byte body followed by fourteen bytes that are NOT free: they hold a
second reachable body (the first body's forward branch lands on it). The
authored body therefore rewrites the whole span, carrying the canonical
instructions verbatim and changing only the displacement the relayout forces.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

from .binary import GBA_ROM_BASE
from .formats.script_vm import ScriptError, assemble_source, decode_instruction
from .layout import LayoutError
from .project.model import AuthoredConversationScript
from .write import ByteChange


class ConversationScriptError(LayoutError):
    """An authored conversation script cannot be resolved against this image."""


CONVERSATION_KEY = re.compile(r'^conversation:0x([0-9A-Fa-f]{8})$')

CODE_OFFSET = {0: 3, 2: 8}

MAX_ENTRIES = 4096


@dataclass(frozen=True, slots=True)
class ConversationScriptIdentity:
    """One entry of one conversation: the word array's address and an index."""

    conversation: int
    entry: int

    def __post_init__(self) -> None:
        if type(self.conversation) is not int or self.conversation < GBA_ROM_BASE:
            raise ConversationScriptError(
                f"a conversation address must be at or above 0x{GBA_ROM_BASE:08X}, "
                f"got {self.conversation!r}")
        if type(self.entry) is not int or self.entry < 0:
            raise ConversationScriptError(
                f"a conversation entry must be a non-negative index, got {self.entry!r}")

    @property
    def value(self) -> str:
        return f"conversation:0x{self.conversation:08X}/entry:{self.entry}"

    def __str__(self) -> str:
        return self.value

    @property
    def key(self) -> str:
        return f"conversation:0x{self.conversation:08X}"

    @classmethod
    def parse(cls, key: str, entry: int, where: object) -> "ConversationScriptIdentity":
        match = CONVERSATION_KEY.match(str(key))
        if match is None:
            raise ConversationScriptError(
                f"{where}: {key!r} is not a conversation identity; expected "
                "'conversation:0x<8 hex digits>'")
        return cls(int(match.group(1), 16), entry)


@dataclass(frozen=True, slots=True)
class ConversationScriptProvenance:
    identity: str
    capacity: int
    authored_bytes: int
    instructions: tuple[str, ...]

    def to_json(self) -> dict:
        return {"identity": self.identity, "capacity": self.capacity,
                "authored_bytes": self.authored_bytes,
                "instructions": list(self.instructions)}


@dataclass(frozen=True, slots=True)
class ConversationScriptApplication:
    changes: tuple[ByteChange, ...] = ()
    provenance: tuple[ConversationScriptProvenance, ...] = ()


def _word(image: bytes, offset: int, identity) -> int:
    if offset < 0 or offset + 4 > len(image):
        raise ConversationScriptError(
            f"{identity}: the word at file 0x{offset:06X} is outside the "
            f"{len(image)}-byte image")
    return int.from_bytes(image[offset:offset + 4], 'little')


def _file_offset(address: int, image: bytes, identity) -> int:
    offset = address - GBA_ROM_BASE
    if not 0 <= offset < len(image):
        raise ConversationScriptError(
            f"{identity}: 0x{address:08X} is outside the {len(image)}-byte image")
    return offset


def _entry_pointers(image: bytes, identity) -> tuple[list[int], int]:
    """Every record address the array holds, and the one this entry selects."""
    array_offset = _file_offset(identity.conversation, image, identity)
    if array_offset % 4:
        raise ConversationScriptError(
            f"{identity}: a conversation word array must be word aligned")
    pointers: list[int] = []
    selected = None
    for index in range(MAX_ENTRIES):
        offset = array_offset + index * 4
        if offset + 4 > len(image):
            break
        word = int.from_bytes(image[offset:offset + 4], 'little')
        if word >> 16 == 0:
            continue
        if not GBA_ROM_BASE <= word < GBA_ROM_BASE + len(image):
            if index == 0:
                raise ConversationScriptError(
                    f"{identity}: the array's first word 0x{word:08X} is not a "
                    "record pointer inside the image")
            if selected is None:
                raise ConversationScriptError(
                    f"{identity}: entry {identity.entry} names no record before the "
                    f"array's data ends at 0x{word:08X}")
            break
        if index == identity.entry:
            selected = word
        pointers.append(word)
    if selected is None:
        raise ConversationScriptError(
            f"{identity}: the array holds no record pointer at entry {identity.entry}")
    return pointers, selected


def _mnemonic(spec, instruction) -> str:
    name = spec.lookup(instruction.opcode).name
    operands = " ".join(str(operand.value) for operand in instruction.operands)
    return f"{name} {operands}" if operands else name


def _body(image: bytes, start: int, spec, identity) -> tuple[list[str], int]:
    """Decode one code block, from `start` to its terminating instruction."""
    instructions: list[str] = []
    offset = start
    while offset < len(image):
        try:
            instruction = decode_instruction(image, offset, spec)
        except ScriptError as exc:
            raise ConversationScriptError(
                f"{identity}: the canonical body does not decode at file "
                f"0x{offset:06X}: {exc}") from None
        instructions.append(_mnemonic(spec, instruction))
        offset += instruction.encoded_length
        if spec.lookup(instruction.opcode).flow == 'stop':
            return instructions, offset - start
    raise ConversationScriptError(
        f"{identity}: the canonical body at file 0x{start:06X} never terminates")


def _expand(source, profile, identity):
    from .authored_placements import _expand_semantic_source
    return _expand_semantic_source(source, profile, identity)


def _require_balanced(effect_name, effect, expansion, spec, identity) -> None:
    """Every declared effect leaves the VM stack exactly as it found it."""
    stack = effect.get('stack')
    if stack is None:
        return
    depth = 0
    for line in expansion:
        name = line.split()[0]
        if name.startswith('native_'):
            depth -= stack['pops']
            depth += stack['pushes']
            continue
        for opcode in spec.instructions:
            if opcode.name == name:
                pops, pushes = opcode.stack or (0, 0)
                depth += pushes - pops
                break
    if depth:
        raise ConversationScriptError(
            f"{identity}: {effect_name} changes the VM stack by {depth:+d}, so an "
            "authored body carrying it would not leave the stack as it found it")


def _plan_one(image: bytes, profile, spec, identity: ConversationScriptIdentity,
              script: AuthoredConversationScript):
    pointers, record = _entry_pointers(image, identity)
    record_offset = _file_offset(record, image, identity)
    if record_offset + 8 > len(image):
        raise ConversationScriptError(
            f"{identity}: the selected record 0x{record:08X} runs past the image")
    kind = image[record_offset + 2]
    if kind not in CODE_OFFSET:
        raise ConversationScriptError(
            f"{identity}: record 0x{record:08X} is kind {kind}; this capability "
            f"locates a code block only for kinds {sorted(CODE_OFFSET)}, whose block "
            "is a fixed field of the record, and refuses the other kinds that reach "
            "the interpreter rather than deriving an address it does not model")
    start = record_offset + CODE_OFFSET[kind]
    canonical, length = _body(image, start, spec, identity)
    if tuple(canonical) != script.prior_instructions:
        raise ConversationScriptError(
            f"{identity}: authored against {list(script.prior_instructions)}, but "
            f"this image's body at file 0x{start:06X} decodes to {canonical}; "
            "refusing a script computed against a different image")
    later = sorted(pointer for pointer in pointers if pointer > record)
    if not later:
        raise ConversationScriptError(
            f"{identity}: the conversation holds no later record, so the room this "
            "body may use is not measurable")
    capacity = _file_offset(later[0], image, identity) - start
    if capacity <= length:
        raise ConversationScriptError(
            f"{identity}: the record's own body already fills its {capacity} bytes")
    from .data.script_effects import SCRIPT_EFFECTS
    effects = SCRIPT_EFFECTS.get(profile.id, {})
    expanded = []
    for line in script.instructions:
        one = _expand((line,), profile, identity)
        effect = effects.get(line.split()[0])
        if effect is not None:
            _require_balanced(line.split()[0], effect, one, spec, identity)
        expanded.extend(one)
    try:
        authored = assemble_source(tuple(expanded), spec)
    except ScriptError as exc:
        raise ConversationScriptError(
            f"{identity}: authored script body rejected: {exc}") from None
    if len(authored) != capacity:
        raise ConversationScriptError(
            f"{identity}: the authored body is {len(authored)} bytes and the record "
            f"has {capacity} bytes of room; a body must fill the room exactly, "
            "because a shorter one leaves canonical instructions reachable after a "
            "terminate")
    last = decode_instruction(authored, len(authored) - 1, spec)
    if spec.lookup(last.opcode).flow != 'stop':
        raise ConversationScriptError(
            f"{identity}: the authored body must end with a terminating instruction")
    return ByteChange(
        offset=start,
        old=image[start:start + capacity],
        new=authored,
        owner=identity.value,
        reason="authored conversation script",
    ), length, capacity


def plan_conversation_scripts(
    image: bytes,
    profile,
    scripts: Mapping[ConversationScriptIdentity, AuthoredConversationScript],
) -> ConversationScriptApplication:
    """Resolve, bound and encode every authored conversation script."""
    from .data.placement_contracts import CONTRACTS
    from .data.script_specs import OPCODE_SETS
    if not scripts:
        return ConversationScriptApplication()
    contract = CONTRACTS.get(profile.id)
    if contract is None or contract['sha256'] != profile.sha256:
        raise ConversationScriptError(
            f"profile {profile.id!r} declares no verified script contract, so a "
            "conversation script cannot be encoded")
    spec = OPCODE_SETS[contract['encoding']]
    if profile.id not in spec.profiles:
        raise ConversationScriptError(
            f"the {spec.name} VM is not verified for profile {profile.id!r}")
    changes = []
    provenance = []
    for identity in sorted(scripts, key=lambda item: (item.conversation, item.entry)):
        change, length, capacity = _plan_one(image, profile, spec, identity,
                                             scripts[identity])
        changes.append(change)
        provenance.append(ConversationScriptProvenance(
            identity.value, capacity, len(change.new), scripts[identity].instructions))
    return ConversationScriptApplication(tuple(changes), tuple(provenance))
