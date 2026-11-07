"""A bounded dialogue scene's text slots, resolved from the profile and the image.

LOG1-BUU-DIALOGUE-BACKPORT-001. Seven lines of an existing conversation are
rewritten in place: same nodes, same successors, same terminal, same string
ownership. The one property that matters and that the raw byte document cannot
express is the slot's CAPACITY - every one of these slots is exactly full, so a
replacement one byte longer would consume the terminating NUL and run into the
next line's text.

So the write is derived, never addressed by hand: the profile declares one record
and its node indices, this module resolves each node's text pointer through the
image's own bytes, measures the slot, and emits space-padded raw writes. A caller
that asks for too long a line is refused; a caller that asks for a node the
profile does not declare is refused; a caller that asks for a terminal node is
refused, because a terminal is an exit marker and never a page.
"""

from __future__ import annotations

from dataclasses import dataclass
import struct
from typing import Mapping

from .binary import GBA_ROM_BASE
from .layout import FileOffset, RomRange
from .profile import RomProfile, SceneTextProfile

MAX_SLOT_BYTES = 4096

PLAN_HEADER_BYTES = 4
PLAN_RECORD_BYTES = 12

PLAN_LABEL = "bf-dialogue-plan"

FLAG_TALK_START = 0x01
FLAG_FINAL = 0x02

PLAN_MAX_STAGES = 256


class SceneTextError(ValueError):
    """The declared scene cannot be resolved, or an authored line cannot fit it."""


@dataclass(frozen=True, slots=True)
class SceneNode:
    index: int
    kind: int
    next_node: int
    text_offset: int
    text: str
    capacity: int


@dataclass(frozen=True, slots=True)
class Scene:
    record_offset: int
    nodes: tuple[SceneNode, ...]

    def node(self, index: int) -> SceneNode:
        for node in self.nodes:
            if node.index == index:
                return node
        raise SceneTextError(
            f"node {index} is not in the declared scene; declared: "
            + ", ".join(str(node.index) for node in self.nodes)
        )


def _u32(image: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(image):
        raise SceneTextError(f"word at 0x{offset:06X} is outside the image")
    return struct.unpack_from("<I", image, offset)[0]


def _rom_offset(value: int, image: bytes, where: str) -> int:
    if not GBA_ROM_BASE <= value < GBA_ROM_BASE + len(image):
        raise SceneTextError(f"{where} is not a ROM pointer: 0x{value:08X}")
    return value - GBA_ROM_BASE


def record_offset(image: bytes, declaration: SceneTextProfile) -> int:
    """The scene record's file offset, through the declared row table."""
    table = declaration.table_address.to_file_offset(len(image))
    word = table + declaration.row_stride * declaration.row_index
    return _rom_offset(_u32(image, word), image, f"scene row {declaration.row_index}")


def _measure(image: bytes, start: int) -> int:
    for length in range(MAX_SLOT_BYTES):
        offset = start + length
        if offset >= len(image):
            break
        if image[offset] == 0:
            if length == 0:
                raise SceneTextError(f"slot at 0x{start:06X} is empty")
            return length
    raise SceneTextError(
        f"no NUL within {MAX_SLOT_BYTES} bytes of 0x{start:06X}; not a dialogue slot"
    )


def read_scene(image: bytes, profile: RomProfile) -> Scene:
    """Resolve the declared scene's nodes from the image's own bytes."""
    declaration = profile.scene_text
    if declaration is None:
        raise SceneTextError(f"profile {profile.id!r} declares no scene_text")
    base = record_offset(image, declaration)
    nodes = []
    for index in declaration.nodes:
        start = base + declaration.node_size * index
        end = start + declaration.node_size
        if end > len(image):
            raise SceneTextError(
                f"node {index} at 0x{start:06X} runs past the image"
            )
        kind = image[start + declaration.node_kind_offset]
        if kind == declaration.terminal_kind:
            raise SceneTextError(
                f"node {index} is kind 0x{kind:02X}, the terminal marker; a terminal "
                "is an exit, not a page, and its text pointer is not a slot"
            )
        next_node = image[start + declaration.node_next_offset]
        pointer = _u32(image, start + declaration.node_text_offset)
        text_offset = _rom_offset(pointer, image, f"node {index} text")
        capacity = _measure(image, text_offset)
        text = image[text_offset:text_offset + capacity]
        if any(byte < 0x20 or byte > 0x7E for byte in text):
            raise SceneTextError(
                f"node {index} at 0x{text_offset:06X} is not printable ASCII; this "
                "service edits plain text slots only"
            )
        nodes.append(
            SceneNode(
                index=index,
                kind=kind,
                next_node=next_node,
                text_offset=text_offset,
                text=text.decode("ascii"),
                capacity=capacity,
            )
        )
    return Scene(base, tuple(nodes))


def scene_slots(image: bytes, profile: RomProfile) -> tuple[RomRange, ...]:
    """The content span of every declared slot, NUL excluded.

    A raw byte write into the slot must land inside exactly one of these spans, so
    the build can refuse a write that would touch a terminator or a neighbour.
    """
    scene = read_scene(image, profile)
    return tuple(
        RomRange(FileOffset(node.text_offset), node.capacity) for node in scene.nodes
    )


def plan_text_writes(
    image: bytes, profile: RomProfile, texts: Mapping[int, str]
) -> dict[int, bytes]:
    """The raw writes that replace the declared nodes' text, space padded.

    The value is what the raw byte document stores: file offset -> replacement
    bytes, each exactly the slot's canonical length so the terminating NUL and
    every following line keep their offsets.
    """
    scene = read_scene(image, profile)
    writes: dict[int, bytes] = {}
    for index in sorted(texts):
        node = scene.node(index)
        value = texts[index]
        if not isinstance(value, str):
            raise SceneTextError(f"node {index}: text must be a string")
        try:
            encoded = value.encode("ascii")
        except UnicodeEncodeError as exc:
            raise SceneTextError(
                f"node {index}: {value!r} is not ASCII; these slots are plain ASCII"
            ) from exc
        if any(byte < 0x20 or byte > 0x7E for byte in encoded):
            raise SceneTextError(
                f"node {index}: control bytes are not authored here; the scene's own "
                "line breaks are the reader's"
            )
        if len(encoded) > node.capacity:
            raise SceneTextError(
                f"node {index}: {len(encoded)} bytes does not fit a {node.capacity}-byte "
                f"slot (canonical text is {node.text!r})"
            )
        if encoded == image[node.text_offset:node.text_offset + node.capacity]:
            raise SceneTextError(
                f"node {index}: the authored text is the canonical text, so it changes "
                "nothing; remove it or author different words"
            )
        writes[node.text_offset] = encoded.ljust(node.capacity, b" ")
    return writes


def dialogue_plan(image: bytes, profile: RomProfile) -> bytes:
    """The scene's bounded node plan, derived from the image's own record table.

    One record per stage that owns text, in stage order: the stage's text span (the
    pointer the record carries, and the address of the NUL that ends it), a flag
    word, and the kind byte of the stage's ACTUAL successor. The walk starts at the
    profile's first authored node and follows each stage's own successor until a
    stage repeats, so the terminal slots are traversed and skipped but never
    assumed to sit at ``s + 1``.

    Compatibility metadata, not retail behaviour: retail computes the same facts at
    runtime. It carries addresses and flags only - no text, art or graph byte - so a
    project that ships it still ships no proprietary content.
    """
    declaration = profile.scene_text
    if declaration is None:
        raise SceneTextError(f"profile {profile.id!r} declares no scene_text")
    base = record_offset(image, declaration)
    entry = declaration.node_size
    if not declaration.nodes:
        raise SceneTextError(f"profile {profile.id!r} declares no scene node to walk from")
    stages: list[int] = []
    stage = declaration.nodes[0]
    while stage not in stages:
        if len(stages) >= PLAN_MAX_STAGES:
            raise SceneTextError(
                f"the successor walk from node {declaration.nodes[0]} did not revisit a "
                f"stage within {PLAN_MAX_STAGES}; this record is not a conversation"
            )
        offset = base + entry * stage
        if offset + entry > len(image):
            raise SceneTextError(f"stage {stage} at 0x{offset:06X} runs past the image")
        stages.append(stage)
        stage = image[offset + declaration.node_next_offset]
    terminal = declaration.terminal_kind
    starts = {declaration.nodes[0]} | {
        image[base + entry * node + declaration.node_next_offset]
        for node in stages
        if image[base + entry * node + declaration.node_kind_offset] == terminal
    }
    records = []
    for node in stages:
        offset = base + entry * node
        pointer = _u32(image, offset + declaration.node_text_offset)
        if pointer == 0:
            continue
        start = _rom_offset(pointer, image, f"stage {node} text")
        successor = image[offset + declaration.node_next_offset]
        successor_kind = image[base + entry * successor + declaration.node_kind_offset]
        flags = (FLAG_TALK_START if node in starts else 0) | (
            FLAG_FINAL if successor_kind == terminal else 0)
        records.append(struct.pack(
            "<IIBBH", pointer, pointer + _measure(image, start), flags, 0, 0))
    return struct.pack("<HH", len(records), 0) + b"".join(records)
