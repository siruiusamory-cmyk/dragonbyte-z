"""LOG1 actor draw limits: the object-tile budget and the per-piece palette bank.

LOG1-BUU-SPRITE-BACKPORT-001 phase 3 (DBZ-033) SC2 and SC3.

Two defects and one payload. The retail per-frame actor draw method at
``0x0800B01E`` appends an OAM entry and stages that piece's tiles with no bound
test at all - 110 straight-line instructions, zero compare, zero conditional
branch - and it reads the palette bank from the ACTOR (``ldrb r6,[r0,#0xD]`` at
``0x0800B09A``), so a piece cannot name a second bank.

Neither can be fixed in place. The method's body has 2 bytes of unreachable
padding after its ``bx lr`` and no repointable literal word, and the method is a
leaf reached through 77 pointer words - a ``BL`` at its entry would destroy the
caller's return address its own ``bx lr`` needs. So the payload IS the method: a
guard prologue that saves ``lr``, the retail body copied except the two
instructions the selector displaces and that final ``bx lr`` (now ``pop {pc}``,
taking the caller's return address off the guard's frame), the retail literal
pool at its retail distance, then the selector; 77 pointer words repoint at it.

Nothing here is a new interpreter: the payload is bytes, the seams are the
project's ``patch/edits.toml`` entries, the placement is the one allocator, and
every retail offset touched is declared in the LOG1 profile's ``patch_sites``.
"""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path

from .project.patchdoc import encode_thumb_bl as thumb_bl

APPEND_ENTRY = 0x0800B01E
APPEND_BODY_END = 0x0800B104
APPEND_POOL_END = 0x0800B110
BANK_READ = 0x0800B09A
BANK_READ_BYTES = bytes.fromhex("467b3f03")
BODY_BANK_OFFSET = BANK_READ - APPEND_ENTRY
BODY_BX_LR = 0x0800B0F8 - APPEND_ENTRY
POOL_WORDS = (0x0202BE24, 0xFE00FFFF, 0x040000D4)
TILE_FIELD_LIMIT = 1024
OAM_ENTRY_LIMIT = 128
STAGING_BASE = 0x0200B024
OBJ_WINDOW_BYTES = 0x8000
CELL_BANK_MODE_SHIFT = 6
CELL_BANK_SHIFT = 2
CELL_BANK_MASK = 0xF
GBA_ROM_BASE = 0x08000000
LOG1_SHA256 = "3ba9919e26704b0f5fdc2bfabc7f7a0404c71413761d38abcd94224c3bd4b1b9"
ART_TABLE = 0x085C0C80
ART_COUNT = 84
STATE_LIMIT = 17
SOURCE_DIR = Path(__file__).resolve().parent / "patchsource" / "log1-sprite-limits"
PROLOGUE = SOURCE_DIR / "budget.bin"
BANK_HELPER = SOURCE_DIR / "bank.bin"
PAYLOAD_LABEL = "log1-sprite-limits"
PAYLOAD_FILE = "patch/log1-sprite-limits.bin"


class SpriteLimitsError(ValueError):
    """The payload or the image does not hold what this module documents."""


def thumb_branch(site_offset: int, target_offset: int) -> bytes:
    """A 16-bit unconditional Thumb branch, range-checked, never guessed."""
    delta = target_offset - (site_offset + 4)
    if delta % 2:
        raise SpriteLimitsError(f"odd branch delta {delta}")
    half = delta >> 1
    if not -(1 << 10) <= half < (1 << 10):
        raise SpriteLimitsError(f"branch delta {delta} is outside the 16-bit range")
    return struct.pack("<H", 0xE000 | (half & 0x7FF))


def canonical_bytes(image: bytes) -> tuple[bytes, bytes]:
    """The retail body and its literal pool, read from the image, never assumed."""
    body = image[APPEND_ENTRY - GBA_ROM_BASE:APPEND_BODY_END - GBA_ROM_BASE]
    pool = image[APPEND_BODY_END - GBA_ROM_BASE:APPEND_POOL_END - GBA_ROM_BASE]
    if len(body) != APPEND_BODY_END - APPEND_ENTRY or len(pool) != 12:
        raise SpriteLimitsError("the image is shorter than the method it must hold")
    if struct.unpack("<3I", pool) != POOL_WORDS:
        raise SpriteLimitsError(
            f"the method's literal pool is {struct.unpack('<3I', pool)}, "
            f"this module documents {POOL_WORDS}")
    if body[BODY_BANK_OFFSET:BODY_BANK_OFFSET + 4] != BANK_READ_BYTES:
        raise SpriteLimitsError(
            "the bank read is not where this module places its call: "
            f"{body[BODY_BANK_OFFSET:BODY_BANK_OFFSET + 4].hex()}")
    if body[BODY_BX_LR:BODY_BX_LR + 2] != bytes.fromhex("7047"):
        raise SpriteLimitsError("the retail body does not hold bx lr where it should")
    return body, pool


def compose_payload(image: bytes) -> bytes:
    """The guard prologue, the retail body, the retail pool, the bank selector."""
    prologue = PROLOGUE.read_bytes()
    helper = BANK_HELPER.read_bytes()
    if not prologue or not helper:
        raise SpriteLimitsError("an assembled part is missing or empty")
    if prologue[-2:] != bytes.fromhex("fee7"):
        raise SpriteLimitsError(
            "the prologue does not end in its placeholder branch (b .), so the "
            "generator cannot fill the body entry")
    body, pool = canonical_bytes(image)
    pad = (2 - len(prologue)) % 4
    body_offset = len(prologue) + pad
    pool_offset = body_offset + len(body)
    if (pool_offset + GBA_ROM_BASE) % 4:
        raise SpriteLimitsError("the copied pool would not be word-aligned")
    helper_offset = pool_offset + len(pool)
    patched = bytearray(body)
    patched[BODY_BANK_OFFSET:BODY_BANK_OFFSET + 4] = thumb_bl(
        body_offset + BODY_BANK_OFFSET, helper_offset)
    patched[BODY_BX_LR:BODY_BX_LR + 2] = bytes.fromhex("00bd")
    payload = bytearray(prologue[:-2])
    payload += thumb_branch(len(payload), body_offset)
    payload += b"\xc0\x46" * pad
    if len(payload) != body_offset:
        raise SpriteLimitsError(f"layout drift: body at {len(payload)}, wanted {body_offset}")
    payload += bytes(patched)
    payload += pool
    payload += helper
    return bytes(payload)


def pointer_sites(image: bytes) -> list[int]:
    """Every retail word that dispatches to the draw method, in image order."""
    needle = struct.pack("<I", APPEND_ENTRY | 1)
    sites: list[int] = []
    start = image.find(needle)
    while start != -1:
        if start % 4 == 0:
            sites.append(start)
        start = image.find(needle, start + 1)
    if len(sites) != 77:
        raise SpriteLimitsError(
            f"the image holds {len(sites)} draw-method words, this module documents 77")
    return sites


def cell_bank(attribute_a: int) -> int | None:
    """The per-piece bank a cell record names, or None for the retail path."""
    mode = (attribute_a >> CELL_BANK_MODE_SHIFT) & 0x3
    if mode == 0:
        return None
    return (attribute_a >> CELL_BANK_SHIFT) & CELL_BANK_MASK


def budgets_hold(oam_cursor: int, tile_cursor: int, tiles: int, staged: int,
                 block_tile: int) -> bool:
    """The prologue's predicate, restated in Python so a test can drive it."""
    if oam_cursor >= OAM_ENTRY_LIMIT:
        return False
    if tile_cursor + tiles > TILE_FIELD_LIMIT:
        return False
    return staged + tiles * 32 <= OBJ_WINDOW_BYTES - block_tile * 32


def declaration_block(image: bytes) -> str:
    """The `patch_sites` entries the LOG1 profile needs for these seams."""
    lines = []
    sites = pointer_sites(image)
    for site in sites:
        lines.extend([
            "      - kind: absolute",
            f"        file_offset: 0x{site:07x}",
            "        evidence: >-",
            "          Word +0x10 of a twenty-byte actor-class record in the draw-method",
            "          table: the retail per-frame actor draw method 0x0800B01E, Thumb bit",
            "          set. 77 such words exist in the image and every one of them names",
            "          that method; the phase 3 payload replaces all of them with one",
            "          bounded implementation, so this site is a pointer seam and not an",
            "          in-place byte edit. The word occurs at this offset only once.",
        ])
    return "\n".join(lines) + "\n"


def check(image: bytes) -> dict:
    """Assert-based self-check: every number this module relies on, re-derived."""
    payload = compose_payload(image)
    body, pool = canonical_bytes(image)
    sites = pointer_sites(image)
    prologue = PROLOGUE.read_bytes()
    pad = (2 - len(prologue)) % 4
    body_offset = len(prologue) + pad
    helper_offset = body_offset + len(body) + len(pool)
    branch = payload[len(prologue) - 2:len(prologue)]
    expected = thumb_branch(len(prologue) - 2, body_offset)
    assert branch == expected, (branch.hex(), expected.hex())
    copied = payload[body_offset:body_offset + len(body)]
    moved = [index for index in range(len(body)) if copied[index] != body[index]]
    assert moved == list(range(BODY_BANK_OFFSET, BODY_BANK_OFFSET + 4)) + list(
        range(BODY_BX_LR, BODY_BX_LR + 2)), moved
    assert copied[BODY_BX_LR:BODY_BX_LR + 2] == bytes.fromhex("00bd")
    assert copied[BODY_BX_LR - 2:BODY_BX_LR] == body[BODY_BX_LR - 2:BODY_BX_LR]
    assert payload[body_offset + len(body):helper_offset] == pool
    assert len(payload) == helper_offset + len(BANK_HELPER.read_bytes())
    assert payload[0:2] == prologue[0:2]
    assert cell_bank(0x00) is None
    assert cell_bank(0x40) == 0 and cell_bank(0x44) == 1 and cell_bank(0x7C) == 15
    assert not budgets_hold(128, 0, 1, 0, 0)
    assert not budgets_hold(0, 1008, 17, 0, 0)
    assert not budgets_hold(0, 0, 16, 0x8000 - 16 * 32 + 1, 0)
    assert budgets_hold(0, 1008, 16, 0, 0)
    return {
        "payload_bytes": len(payload),
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "body_bytes": len(body),
        "copied_body_bytes_changed": len(moved),
        "pointer_sites": len(sites),
        "first_pointer_site": f"0x{sites[0]:08X}",
        "last_pointer_site": f"0x{sites[-1]:08X}",
        "bank_helper_bytes": len(BANK_HELPER.read_bytes()),
        "prologue_bytes": len(prologue),
    }


def write_project_patch(project_dir: str | Path, image: bytes) -> Path:
    """Write the payload and the project's patch document, nothing else."""
    directory = Path(project_dir)
    payload = compose_payload(image)
    target = directory / PAYLOAD_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    lines = [
        "[[payload]]",
        f'label = "{PAYLOAD_LABEL}"',
        'source_class = "new"',
        'origin_note = "LOG1 actor draw method: guard prologue plus a byte-identical copy of the retail body and its literal pool, and a per-piece palette bank selector in place of two displaced instructions; no donor bytes and no donor address"',
        'transform = "thumb-guard-retail-body-copy"',
        "alignment = 4",
        "code = true",
        f'file = "{PAYLOAD_FILE}"',
        f'sha256 = "{digest}"',
        "",
    ]
    for site in pointer_sites(image):
        lines.extend([
            "[[pointer]]",
            f"site = 0x{site:06x}",
            'expect = "1fb00008"',
            f'target = "{PAYLOAD_LABEL}"',
            'state = "thumb"',
            'origin_note = "actor-class record draw-method word; retail 0x0800B01F"',
            "",
        ])
    document = directory / "patch" / "edits.toml"
    document.parent.mkdir(parents=True, exist_ok=True)
    document.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    return target


def stack_frame(block: bytes) -> tuple[int, tuple[tuple[int, int], ...]]:
    """The entry push and every pop of a Thumb block, decoded from its bytes.

    A hand-written prologue's stack balance is a property of the ASSEMBLED
    halfwords, so it is read here and never off the source. Every pop is
    reported as ``(offset, halfword)``.
    """
    halves = struct.unpack(f"<{len(block) // 2}H", block)
    push = halves[0]
    if push >> 8 != 0xB5:
        raise SpriteLimitsError(
            f"the block does not open by pushing its registers plus lr: {push:04x}")
    pops = tuple((index * 2, half) for index, half in enumerate(halves)
                 if (half >> 8) & 0xFE == 0xBC)
    return push, pops


def branch_targets(block: bytes) -> list[tuple[int, int]]:
    """Every Thumb branch in a block as ``(site, target)``, block-relative."""
    targets: list[tuple[int, int]] = []
    for index, half in enumerate(struct.unpack(f"<{len(block) // 2}H", block)):
        site = index * 2
        if (half & 0xF800) == 0xE000:
            imm = half & 0x7FF
            delta = imm - 0x800 if imm & 0x400 else imm
        elif (half & 0xF000) == 0xD000:
            imm = half & 0xFF
            delta = imm - 0x100 if imm & 0x80 else imm
        else:
            continue
        targets.append((site, site + 4 + 2 * delta))
    return targets


def store_sites(block: bytes) -> list[tuple[int, int]]:
    """Every Thumb store in a block as ``(base register, immediate five bits)``."""
    sites: list[tuple[int, int]] = []
    for half in struct.unpack(f"<{len(block) // 2}H", block):
        top = half >> 11
        if top in (0b01100, 0b01110, 0b10000):
            sites.append(((half >> 3) & 7, (half >> 6) & 0x1F))
        elif (half & 0xFE00) == 0x5000:
            sites.append(((half >> 3) & 7, 0))
    return sites


def require_guard(prologue: bytes) -> None:
    """Refuse a prologue that cannot return to its caller or could move a cursor.

    Read off the assembled halfwords, never off the source: one push that saves
    ``lr``, a refusal and an accept pop whose register lists match it, every
    branch landing on one of those two pops, and no store through r1 - the
    render context, whose tile cursor and staging pointer a refused piece must
    not touch.
    """
    push, pops = stack_frame(prologue)
    refusal = [half for _, half in pops if half >> 8 == 0xBD]
    accept = [half for _, half in pops if half >> 8 == 0xBC]
    if len(refusal) != 1 or len(accept) != 1:
        raise SpriteLimitsError(f"the prologue has {len(pops)} exits: {pops}")
    if push & 0x1FF != refusal[0] & 0x1FF:
        raise SpriteLimitsError(
            f"the prologue pushes {push:04x} but refuses through {refusal[0]:04x}")
    exits = {offset for offset, _ in pops}
    stray = [branch for branch in branch_targets(prologue[:-2]) if branch[1] not in exits]
    if stray:
        raise SpriteLimitsError(f"the prologue branches outside its exits: {stray}")
    through_r1 = [site for site in store_sites(prologue) if site[0] == 1]
    if through_r1:
        raise SpriteLimitsError(f"the prologue stores through the render context: {through_r1}")


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="python -m tools.webfoot.sprite_limits")
    parser.add_argument("image", help="a legacy-of-goku image to read")
    parser.add_argument("--declarations", action="store_true",
                        help="print the patch_sites entries for the LOG1 profile")
    arguments = parser.parse_args(argv)
    image = Path(arguments.image).read_bytes()
    if arguments.declarations:
        print(declaration_block(image), end="")
        return 0
    require_guard(PROLOGUE.read_bytes())
    for key, value in check(image).items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
