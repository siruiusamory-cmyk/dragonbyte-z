"""LOG1 four-tab pause menu: native LOG2 panel art and the pause page's own code.

The retail LOG1 pause page is a four-layer mode-0 composition that owns the whole
screen while it is open: its install blanks the display, writes DISPCNT, BG0..BG3CNT,
BLDCNT and BLDALPHA, decodes a 51,840-byte 8bpp backdrop into character base 0 and
reloads the BG palette. Nothing about the page is saved in RAM; the exit path rebuilds
the field from ROM and from the field's own resume method.

This module produces one payload and two seams:

* ``pause-menu`` - Thumb code and its assets, linked at an allocated ROM address. It
  replaces the page's draw method (table +0x08) and its per-frame update method
  (table +0x0C) in the method table at ``0x0800EF84``. The install method (+0x00),
  the leave method (+0x04) and the resume method (+0x14) stay retail, so the entry
  request at ``0x08001212`` and the field's restore on exit are untouched.

* the whole page is composed at build time from a private LOG2 image supplied on
  the command line: the starfield backdrop, the frame strip, the header plate, the
  shoulder, corner and scroll arrows, the slider widgets, the two panel surfaces, the
  status portrait, the font and the BG palette, all in their native 8bpp indices.
  Nothing derived from the donor is committed: this module writes the payload into
  the project directory the build names, and the repository holds only the
  extractor, the layout and the expected digests.

The layout (which piece goes where, each text origin, the two chrome maps) was
measured against VRAM dumps of the donor's own four pages; ``ASSETS_SHA256`` is the
digest of the composition that reproduced them, and ``check`` re-derives it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

import yaml

from . import allocation as allocation_module
from .assembled_payloads import ensure_assembled
from .formats import webfoot_lz
from .profile import GeneratedExpansionProfile
from .project import ProjectMeta, write_project
from .project.patchdoc import materialize_patch, read_patch_document
from .write import (
    ByteChange,
    PatchPayloadProvenance,
    emit_image,
    plan_changes,
)

GBA_ROM_BASE = 0x08000000
LOG1_SHA256 = "3ba9919e26704b0f5fdc2bfabc7f7a0404c71413761d38abcd94224c3bd4b1b9"
LOG2_SHA256 = "6e6c370c339ec9171cb1956adf837a0d342a197f78964882ef46c3086656ff75"

PANEL_CONTAINER = 0x081D9638
PANEL_SHA256 = "7870671dcd6cd02fa097c744961840d184f8468a25a70516ace9ec8adb87bc37"
PANEL_BYTES = 0x4780
PANEL_WIDTH = 208
PANEL_HEIGHT = 88
LIST_CONTAINER = 0x081D99E0
STARFIELD_CONTAINER = 0x080E18B0
STARFIELD_SIDE = 128
PLATE_CONTAINER = 0x081D5D78
PLATE_WIDTH = 152
STRIP_CONTAINER = 0x081D90AC
STRIP_CELLS = 27
SLOPE_LEFT_CONTAINER = 0x081D948C
SLOPE_RIGHT_CONTAINER = 0x081D944C
SLOPE_WIDTH = 20
PORTRAIT_CONTAINER = 0x086B0C38
LIST_WELL_UP_CONTAINER = 0x081D9BE4
LIST_WELL_DOWN_CONTAINER = 0x081D9BC0
PORTRAIT_SIDE = 64

SHOULDER_LEFT = (0x081D567C, 32, 24)
SHOULDER_RIGHT = (0x081D5968, 32, 24)
CORNER_LEFT_IDLE = (0x081D5908, 16, 24)
CORNER_RIGHT_IDLE = (0x081D5C0C, 16, 24)
SCROLL_UP_IDLE = (0x081D5D20, 16, 24)
SCROLL_DOWN_IDLE = (0x081D5614, 16, 24)
SLIDER_ACTIVE = (0x081D5E70, 96, 24)
SLIDER_IDLE = (0x081D5F7C, 96, 24)
KNOB_ACTIVE = (0x081D5E08, 8, 16)
KNOB_IDLE = (0x081D5E38, 8, 16)

BG_PALETTE = 0x081D4F50
BG_PALETTE_SHA256 = "a12468c307da6df7f9ab6f719be30ee3c6016d62af779cfc15037c1a2d3760ac"
BG_PALETTE_BYTES = 0x200

FONT_TABLE = 0x08028724
FONT_SHA256 = "ae8c322790b9e46e7c5792e19fead67af1642e114fee527a8a0120b5c4795505"
FONT_BYTES = 0x2A00
STRING_TABLE = 0x080E2840
STRING_COUNT = 260

SCREEN_WIDTH = 240
SCREEN_HEIGHT = 160
PLATE_INDEX = 0x95
INK_WHITE = 2
INK_GOLD = 0x29
INK_SHADOW = 1
PAGE_TILE = 256
PANEL_ORIGIN = (16, 32)
OPTION_ROW_HEIGHT = 24
SLIDER_X = 112
ASSETS_SHA256 = "080597a6c336351a70daaef321bffe44205691592dc10c1e9373bddf2e3803c8"

TABS = ("options", "quests", "status", "items")
RING_LABEL = {"options": "options", "quests": "journal", "status": "status", "items": "items"}
TAB_TITLE = {"options": "options", "quests": "quests", "status": "name", "items": "items"}
OPTION_LABELS = ("text_speed", "sfx", "music")

SURFACES = (
    ("shoulder_left", 1, 0, 17, 4, 3),
    ("shoulder_right", 1, 26, 17, 4, 3),
    ("corner_left", 1, 1, 0, 2, 3),
    ("corner_right", 1, 27, 0, 2, 3),
    ("label_left", 2, 4, 18, 6, 1),
    ("label_centre", 2, 12, 17, 6, 1),
    ("label_right", 2, 20, 18, 6, 1),
    ("header", 2, 3, 1, 24, 2),
    ("name_tab", 2, 4, 3, 8, 1),
    ("panel", 2, 2, 4, 26, 11),
)

METHOD_TABLE = 0x0800EF84
SEAM_INSTALL = METHOD_TABLE
SEAM_DRAW = METHOD_TABLE + 0x08
SEAM_UPDATE = METHOD_TABLE + 0x0C
INSTALL_EXPECT = bytes.fromhex("6923ffff")
DRAW_EXPECT = bytes.fromhex("0d24ffff")
UPDATE_EXPECT = bytes.fromhex("e724ffff")
FIELD_INSTALL = 0x08001174
FIELD_INSTALL_EXPECT = bytes.fromhex("38b5051c8020c404")
FADE_IN = 0x08008D14
FADE_IN_EXPECT = bytes.fromhex("0178021c2432f84b")
PAGE_PUSH = 0x080097C8
PAGE_PUSH_EXPECT = bytes.fromhex("38b5294d041c2978")
FAR_ENTRY = bytes.fromhex("004b1847")

STRINGS = (
    ("options", 4),
    ("journal", 14),
    ("status", 16),
    ("items", 17),
    ("quests", 23),
    ("level", 25),
    ("hp", 26),
    ("ep", 27),
    ("exp", 31),
    ("next", 32),
    ("text_speed", 10),
    ("sfx", 11),
    ("music", 12),
    ("empty_inventory", 44),
    ("no_quests", 47),
    ("name", 52),
)
RUNTIME_STRINGS = ("level", "empty_inventory", "no_quests")

PAYLOAD_LABEL = "pause-menu"
PAYLOAD_FILE = "patch/pause-menu.bin"
SOURCE_DIR = Path(__file__).resolve().parent / "patchsource" / "log1-pause-menu"
SITES_FILE = Path(__file__).resolve().parent / "data" / "pause_menu_sites.yaml"
NOMINAL_ADDRESS = 0x08810000
FADE_CHAIN = 0x0800EF30
FADE_CHAIN_BASE = 0x0800EF28


class PauseMenuError(ValueError):
    """The donor, the payload or the image does not hold what this module documents."""


def digest(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def container(log2: bytes, address: int, size: int) -> bytes:
    data = webfoot_lz.unpack(log2, address - GBA_ROM_BASE).data
    if len(data) != size:
        raise PauseMenuError(f"the container at {address:#x} holds {len(data)} bytes, not {size}")
    return bytes(data)


def frame(log2: bytes, record: tuple[int, int, int]) -> list[bytes]:
    address, width, height = record
    data = webfoot_lz.unpack_raw_stream(log2, address - GBA_ROM_BASE, width * height)
    return rows(bytes(data), width)


def rows(data: bytes, width: int) -> list[bytes]:
    return [data[start : start + width] for start in range(0, len(data), width)]


def panel_surface(log2: bytes) -> bytes:
    surface = container(log2, PANEL_CONTAINER, PANEL_BYTES)
    if hashlib.sha256(surface).hexdigest() != PANEL_SHA256:
        raise PauseMenuError("the panel surface does not hash to the recorded digest")
    return surface


def tile_surface(surface: bytes, width: int = PANEL_WIDTH) -> bytes:
    """Row-major pixels to the PPU 8bpp tile order, one 64-byte tile per 8x8 cell."""
    height = len(surface) // width
    if width % 8 or height % 8 or width * height != len(surface):
        raise PauseMenuError("the surface is not a whole number of 8x8 cells")
    tiles = bytearray()
    for row in range(height // 8):
        for column in range(width // 8):
            for y in range(8):
                start = (row * 8 + y) * width + column * 8
                tiles += surface[start : start + 8]
    return bytes(tiles)


def palette(log2: bytes) -> bytes:
    offset = BG_PALETTE - GBA_ROM_BASE
    block = log2[offset : offset + BG_PALETTE_BYTES]
    if hashlib.sha256(block).hexdigest() != BG_PALETTE_SHA256:
        raise PauseMenuError("the BG palette does not hash to the recorded digest")
    return block


def font(log2: bytes) -> bytes:
    offset = FONT_TABLE - GBA_ROM_BASE
    block = log2[offset : offset + FONT_BYTES]
    if hashlib.sha256(block).hexdigest() != FONT_SHA256:
        raise PauseMenuError("the font table does not hash to the recorded digest")
    return block


def _string(log2: bytes, index: int) -> str:
    offset = STRING_TABLE - GBA_ROM_BASE + index * 4
    pointer = int.from_bytes(log2[offset : offset + 4], "little")
    if not GBA_ROM_BASE <= pointer < GBA_ROM_BASE + len(log2):
        raise PauseMenuError(f"string {index} is not a ROM pointer")
    start = pointer - GBA_ROM_BASE
    end = log2.index(b"\x00", start)
    return log2[start:end].decode("ascii")


def strings(log2: bytes) -> dict[str, str]:
    return {name: _string(log2, index) for name, index in STRINGS}


def glyph(table: bytes, code: int) -> tuple[int, ...]:
    index = int.from_bytes(table[code * 2 : code * 2 + 2], "little")
    if index == 0:
        return ()
    width = int.from_bytes(table[index * 2 : index * 2 + 2], "little")
    start = index * 2 + 2
    return tuple(
        int.from_bytes(table[start + column * 2 : start + column * 2 + 2], "little")
        for column in range(width)
    )


def advance(table: bytes, text: str) -> int:
    return sum(len(glyph(table, ord(code))) + 1 for code in text)


def canvas() -> list[bytearray]:
    return [bytearray(SCREEN_WIDTH) for _ in range(SCREEN_HEIGHT)]


def blit(target: list[bytearray], image: list[bytes], x: int, y: int,
         opaque: bool = False) -> None:
    for row, line in enumerate(image):
        for column, value in enumerate(line):
            if value or opaque:
                target[y + row][x + column] = value


def draw_text(target: list[bytearray], table: bytes, x: int, y: int, text: str,
              ink: int) -> None:
    for code in text:
        columns = glyph(table, ord(code))
        for colour, shift in ((INK_SHADOW, 1), (ink, 0)):
            for column, mask in enumerate(columns):
                for row in range(16):
                    px, py = x + column + shift, y + row + shift
                    if mask >> row & 1 and 0 <= px < SCREEN_WIDTH and 0 <= py < SCREEN_HEIGHT:
                        target[py][px] = colour
        x += len(columns) + 1


def chrome_maps() -> tuple[list[list[int]], list[list[int]], int, int]:
    """The two chrome screen maps as tile numbers, plus the first surface and panel tiles."""
    upper = [[0] * 30 for _ in range(20)]
    lower = [[0] * 30 for _ in range(20)]
    upper[17][4:10] = [1] * 6
    upper[17][10] = 2
    upper[17][19] = 8
    upper[17][20:26] = [1] * 6
    upper[18][10:20] = [3, 4, 5, 5, 5, 5, 5, 5, 6, 7]
    lower[3][1:4] = [9, 10, 24]
    lower[3][12] = 25
    lower[3][13:28] = [10] * 15
    lower[3][28:30] = [11, 12]
    for row in range(4, 15):
        lower[row][1] = 13
        lower[row][28:30] = [15, 16]
    lower[15][1] = 17
    lower[15][2:28] = [18] * 26
    lower[15][28:30] = [19, 20]
    lower[16][1] = 21
    lower[16][2:28] = [22] * 26
    lower[16][28] = 23
    for grid in (upper, lower):
        for line in grid:
            line[:] = [PAGE_TILE + value for value in line]
    tile = PAGE_TILE + STRIP_CELLS
    first = tile
    panel = tile
    for name, layer, left, top, columns, height in SURFACES:
        if name == "panel":
            panel = tile
        grid = upper if layer == 1 else lower
        for row in range(height):
            for column in range(columns):
                grid[top + row][left + column] = tile
                tile += 1
    return upper, lower, first, panel


class Art:
    """Every donor piece the page is composed from, decoded once."""

    def __init__(self, log2: bytes) -> None:
        self.font = font(log2)
        self.text = strings(log2)
        self.strip = rows(container(log2, STRIP_CONTAINER, STRIP_CELLS * 64), STRIP_CELLS * 8)
        self.plate = rows(container(log2, PLATE_CONTAINER, PLATE_WIDTH * 64), PLATE_WIDTH)
        self.slope_left = rows(container(log2, SLOPE_LEFT_CONTAINER, SLOPE_WIDTH * 16),
                               SLOPE_WIDTH)
        self.slope_right = rows(container(log2, SLOPE_RIGHT_CONTAINER, SLOPE_WIDTH * 16),
                                SLOPE_WIDTH)
        self.status = rows(panel_surface(log2), PANEL_WIDTH)
        self.listing = rows(container(log2, LIST_CONTAINER, PANEL_BYTES), PANEL_WIDTH)
        self.portrait = rows(container(log2, PORTRAIT_CONTAINER, PORTRAIT_SIDE ** 2),
                             PORTRAIT_SIDE)
        self.starfield = container(log2, STARFIELD_CONTAINER, STARFIELD_SIDE ** 2)
        self.well_up = rows(container(log2, LIST_WELL_UP_CONTAINER, 16 * 24), 16)
        self.well_down = rows(container(log2, LIST_WELL_DOWN_CONTAINER, 16 * 24), 16)
        for name in ("SHOULDER_LEFT", "SHOULDER_RIGHT", "CORNER_LEFT_IDLE", "CORNER_RIGHT_IDLE",
                     "SCROLL_UP_IDLE", "SCROLL_DOWN_IDLE", "SLIDER_ACTIVE", "SLIDER_IDLE",
                     "KNOB_ACTIVE", "KNOB_IDLE"):
            setattr(self, name.lower(), frame(log2, globals()[name]))


def upper_layer(art: Art) -> list[bytearray]:
    layer = canvas()
    rail = [line[8:16] for line in art.strip]
    for x in (0, 8, 16, 24, 208, 216, 224, 232):
        blit(layer, rail, x, 136)
    blit(layer, art.shoulder_left, 0, 136)
    blit(layer, art.shoulder_right, 208, 136)
    blit(layer, art.corner_left_idle, 8, 0)
    blit(layer, art.corner_right_idle, 216, 0)
    return layer


def lower_layer(art: Art, tab: str, selected: int | None = None) -> list[bytearray]:
    layer = canvas()
    left, top = PANEL_ORIGIN
    blit(layer, art.slope_left, 24, 8)
    blit(layer, [line[8:48] for line in art.plate[:16]], 44, 8)
    blit(layer, art.slope_right, 84, 8)
    blit(layer, [bytes([PLATE_INDEX]) * 64] * 8, 32, 24)
    title = art.text[TAB_TITLE[tab]]
    draw_text(layer, art.font, 32 + (64 - advance(art.font, title)) // 2, 10, title, INK_WHITE)
    order = TABS.index(tab)
    before = art.text[RING_LABEL[TABS[(order + 3) % 4]]]
    centre = art.text[RING_LABEL[tab]]
    after = art.text[RING_LABEL[TABS[(order + 1) % 4]]]
    draw_text(layer, art.font, 32, 139, before, INK_WHITE)
    draw_text(layer, art.font, 96 + (48 - advance(art.font, centre)) // 2, 131, centre, INK_WHITE)
    draw_text(layer, art.font, 208 - advance(art.font, after), 139, after, INK_WHITE)
    if tab == "status":
        blit(layer, art.status, left, top, opaque=True)
        blit(layer, art.scroll_up_idle, left + 8, top)
        blit(layer, art.scroll_down_idle, left + 8, top + 64)
        blit(layer, art.portrait, left + 144, top + 4)
        draw_text(layer, art.font, 64, 35, art.text["hp"], INK_WHITE)
        draw_text(layer, art.font, 64, 51, art.text["ep"], INK_WHITE)
        draw_text(layer, art.font, 160, 99, art.text["exp"], INK_GOLD)
        draw_text(layer, art.font, 160, 107, art.text["next"], INK_GOLD)
    elif tab == "options":
        blit(layer, [bytes([PLATE_INDEX]) * PANEL_WIDTH] * PANEL_HEIGHT, left, top)
        for row, name in enumerate(OPTION_LABELS):
            chosen = row == selected
            blit(layer, art.slider_active if chosen else art.slider_idle,
                 left + SLIDER_X, top + row * OPTION_ROW_HEIGHT)
            draw_text(layer, art.font, left, top - 1 + row * OPTION_ROW_HEIGHT, art.text[name],
                      INK_GOLD if chosen else INK_WHITE)
    else:
        blit(layer, art.listing, left, top, opaque=True)
        blit(layer, art.well_up, left + 8, top, opaque=True)
        blit(layer, art.well_down, left + 8, top + 64, opaque=True)
        blit(layer, art.scroll_up_idle, left + 8, top)
        blit(layer, art.scroll_down_idle, left + 8, top + 64)
    return layer


def cell(layer: list[bytearray], column: int, row: int) -> bytes:
    return b"".join(bytes(layer[row * 8 + y][column * 8 : column * 8 + 8]) for y in range(8))


def page_tiles(art: Art, upper: list[bytearray], lower: list[bytearray]) -> bytes:
    tiles = bytearray(tile_surface(b"".join(art.strip), STRIP_CELLS * 8))
    for _name, layer, left, top, columns, height in SURFACES:
        source_layer = upper if layer == 1 else lower
        for row in range(height):
            for column in range(columns):
                tiles += cell(source_layer, left + column, top + row)
    return bytes(tiles)


def assets(log2: bytes) -> dict[str, tuple[str, bytes]]:
    art = Art(log2)
    upper_map, lower_map, first, panel = chrome_maps()
    upper = upper_layer(art)
    pages = [page_tiles(art, upper, lower_layer(art, tab)) for tab in TABS]
    chosen = bytearray()
    left, top = PANEL_ORIGIN
    for row in range(len(OPTION_LABELS)):
        layer = lower_layer(art, "options", row)
        for line in range(OPTION_ROW_HEIGHT // 8):
            for column in range(PANEL_WIDTH // 8):
                chosen += cell(layer, left // 8 + column,
                               top // 8 + row * OPTION_ROW_HEIGHT // 8 + line)
    maps = b"".join(tile.to_bytes(2, "little")
                    for grid in (upper_map, lower_map) for line in grid for tile in line)
    layout = (first, panel, len(pages[0]) // 4, len(chosen) // 12)
    return {
        "palette": ("unsigned int", palette(log2)),
        "starfield": ("unsigned int", tile_surface(art.starfield, STARFIELD_SIDE)),
        "page": ("unsigned int", b"".join(pages)),
        "option_rows": ("unsigned int", bytes(chosen)),
        "map": ("unsigned short", maps),
        "font": ("unsigned short", art.font),
        "knob": ("unsigned char", b"".join(art.knob_active) + b"".join(art.knob_idle)),
        "layout": ("unsigned short", b"".join(value.to_bytes(2, "little") for value in layout)),
    }


def assets_digest(blob: dict[str, tuple[str, bytes]]) -> str:
    total = hashlib.sha256()
    for name in sorted(blob):
        total.update(name.encode("ascii") + b"\x00" + blob[name][1])
    return total.hexdigest()


def _array(name: str, kind: str, blob: bytes) -> str:
    size = {"unsigned char": 1, "unsigned short": 2, "unsigned int": 4}[kind]
    values = ",".join(str(int.from_bytes(blob[start : start + size], "little"))
                      for start in range(0, len(blob), size))
    return f"const {kind} {name}[{len(blob) // size}] = {{{values}}};\n"


def source(blob: dict[str, tuple[str, bytes]], labels: list[str]) -> str:
    """The generated translation unit: donor bytes and donor strings, nothing invented."""
    text = "".join(_array(f"asset_{name}", kind, body) for name, (kind, body) in blob.items())
    offsets = []
    packed = bytearray()
    for value in labels:
        offsets.append(len(packed))
        packed += value.encode("ascii") + b"\x00"
    offsets.append(len(packed))
    text += "const unsigned short asset_string_offset[] = {" + ",".join(
        str(value) for value in offsets) + "};\n"
    text += _array("asset_strings", "unsigned char", bytes(packed))
    return text


def compile_payload(directory: Path, tools: Path, address: int) -> dict[str, int]:
    source_dir = directory / "source"
    generated = directory / "generated_assets.c"
    flags = (
        "-mcpu=arm7tdmi",
        "-mthumb",
        "-O3",
        "-ffreestanding",
        "-fno-builtin",
        "-fno-unwind-tables",
        "-fno-asynchronous-unwind-tables",
        "-I",
        source_dir,
        "-Wa,-I," + str(source_dir),
    )
    for name in ("menu", "assets", "seam", "fade_guard"):
        target = (source_dir / f"{name}.s" if name in ("seam", "fade_guard")
                  else source_dir / f"{name}.c")
        if name == "assets":
            target = generated
        subprocess.check_call(
            [str(tools / "arm-none-eabi-gcc.exe"), *flags, "-c", str(target),
             "-o", str(directory / f"{name}.o")]
        )
    linker = directory / "pause.ld"
    linker.write_text(
        "SECTIONS {"
        f". = {address}; .text : {{ *(.text*) *(.rodata*) }} "
        "/DISCARD/ : { *(.comment) *(.ARM.attributes) } }",
        encoding="ascii",
    )
    subprocess.check_call(
        [str(tools / "arm-none-eabi-ld.exe"), "-T", str(linker),
         str(directory / "menu.o"), str(directory / "assets.o"), str(directory / "seam.o"),
         str(directory / "fade_guard.o"), "-o", str(directory / "pause.elf")]
    )
    subprocess.check_call(
        [str(tools / "arm-none-eabi-objcopy.exe"), "-O", "binary",
         "--only-section=.text", str(directory / "pause.elf"), str(directory / PAYLOAD_FILE)]
    )
    names = subprocess.check_output(
        [str(tools / "arm-none-eabi-nm.exe"), str(directory / "pause.elf")], text=True
    )
    return {
        name: int(value, 16)
        for value, _kind, name in re.findall(r"^([0-9a-f]+) (\w) (\w+)$", names, re.M)
    }


def compiler_directory(value: str | None) -> Path:
    if value:
        directory = Path(value)
    elif shutil.which("arm-none-eabi-gcc"):
        directory = Path(shutil.which("arm-none-eabi-gcc")).parent
    else:
        directory = Path("C:/devkitPro/devkitARM/bin")
    for name in ("gcc", "ld", "objcopy", "nm"):
        if not (directory / f"arm-none-eabi-{name}.exe").is_file():
            raise PauseMenuError(f"missing build tool: {name} in {directory}")
    return directory


def relative_entry(target: int, base: int) -> bytes:
    value = target - base
    return int(value).to_bytes(4, "little", signed=True)


def write_document(directory: Path, symbols: dict[str, int]) -> Path:
    payload = directory / PAYLOAD_FILE
    lines = [
        "[[payload]]",
        f'label = "{PAYLOAD_LABEL}"',
        'source_class = "new"',
        'origin_note = "four-tab pause page over the retail LOG1 pause state; LOG2 panel surface, palette, font and ring labels extracted at build time from a private donor image, which is not committed"',
        'transform = "pause-menu-runtime"',
        "alignment = 4",
        "code = true",
        f'file = "{PAYLOAD_FILE}"',
        f'sha256 = "{digest(payload)}"',
        "",
    ]
    document = directory / "patch" / "edits.toml"
    document.parent.mkdir(parents=True, exist_ok=True)
    document.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    return document


def build(log1_path: Path, log2_path: Path, output: Path, directory: Path,
          toolchain: str | None) -> dict:
    ensure_assembled()
    ensure_assembled()
    if digest(log1_path) != LOG1_SHA256:
        raise PauseMenuError("the target image is not the canonical LOG1 image")
    if digest(log2_path) != LOG2_SHA256:
        raise PauseMenuError("the donor image is not the canonical LOG2 image")
    log2 = Path(log2_path).read_bytes()
    image = Path(log1_path).read_bytes()
    plan, report = plan_page(image, log2, Path(directory), toolchain)
    if digest(log1_path) != LOG1_SHA256 or digest(log2_path) != LOG2_SHA256:
        raise PauseMenuError("a source image changed during the build")
    emit_image(log1_path, output, plan, manifest_path=str(output) + ".manifest.json")
    report["rom_sha256"] = digest(output)
    (Path(directory) / "pause-build.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def plan_page(image: bytes, log2: bytes, directory: Path, toolchain: str | None,
              reserved=(), fade_target: int | None = None):
    directory = Path(directory)
    if directory.exists() and any(directory.iterdir()):
        raise PauseMenuError(f"the build directory must be empty: {directory}")
    (directory / "source").mkdir(parents=True)
    (directory / "patch").mkdir()
    for name in ("menu.c", "seam.s", "fade_guard.s"):
        (directory / "source" / name).write_bytes((SOURCE_DIR / name).read_bytes())
    chain = FADE_CHAIN - GBA_ROM_BASE
    if fade_target is None:
        fade_target = FADE_CHAIN_BASE + int.from_bytes(
            image[chain : chain + 4], "little", signed=True)
    (directory / "source" / "generated_fade_target.inc").write_text(
        f".equ FADE_TARGET, 0x{fade_target & 0xFFFFFFFF:08X}\n", encoding="ascii")
    blob = assets(log2)
    if assets_digest(blob) != ASSETS_SHA256:
        raise PauseMenuError("the composed page does not hash to the recorded digest")
    names = strings(log2)
    labels = [names[name] for name in RUNTIME_STRINGS]
    (directory / "generated_assets.c").write_text(source(blob, labels), encoding="ascii")
    profile = read_profile()
    generated_profile = _expanded(profile)
    tools = compiler_directory(toolchain)
    write_project(directory, ProjectMeta(
        1, profile.id, profile.game, LOG1_SHA256, len(image),
        "LOG1 four-tab pause menu with native LOG2 panel art",
    ), enemies=[], characters=[])
    (directory / PAYLOAD_FILE).write_bytes(bytes(64))
    write_document(directory, {})
    first = materialize_patch(read_patch_document(directory), generated_profile, image,
                              reserved=tuple(reserved))
    address = first.payloads[0].allocation.rom_address
    symbols = compile_payload(directory, tools, address)
    write_document(directory, symbols)
    placed = materialize_patch(read_patch_document(directory), generated_profile, image,
                               reserved=tuple(reserved))
    if placed.payloads[0].allocation.rom_address != address:
        raise PauseMenuError("the payload address moved between allocation passes")
    changes = list(placed.changes)
    seams = []
    for seam, expect, function in (
        (SEAM_INSTALL, INSTALL_EXPECT, "menu_install"),
        (SEAM_DRAW, DRAW_EXPECT, "menu_draw"),
        (SEAM_UPDATE, UPDATE_EXPECT, "menu_update"),
    ):
        site = seam - GBA_ROM_BASE
        if image[site : site + 4] != expect:
            raise PauseMenuError(f"the retail method table differs at file 0x{site:06x}")
        value = relative_entry(symbols[function] | 1, METHOD_TABLE)
        changes.append(ByteChange(
            site, expect, value,
            f"pause-menu seam at file {site:#06x}",
            "replace the retail pause page draw/update method word with the payload's method",
        ))
        seams.append({"site": f"0x{seam:08X}", "function": function, "value": value.hex()})
    hook = FIELD_INSTALL - GBA_ROM_BASE
    if image[hook : hook + 8] != FIELD_INSTALL_EXPECT:
        raise PauseMenuError(f"the field install differs at file 0x{hook:06x}")
    value = FAR_ENTRY + (symbols["field_install"] | 1).to_bytes(4, "little")
    changes.append(ByteChange(
        hook, FIELD_INSTALL_EXPECT, value,
        "pause-menu close seam",
        "replace the field install's first four instructions with a far entry to the payload",
    ))
    seams.append({"site": f"0x{FIELD_INSTALL:08X}", "function": "field_install",
                  "value": value.hex()})
    fade = FADE_IN - GBA_ROM_BASE
    if image[fade : fade + 8] != FADE_IN_EXPECT:
        raise PauseMenuError(f"the field's per-frame mirror differs at file 0x{fade:06x}")
    value = FAR_ENTRY + (symbols["fade_in"] | 1).to_bytes(4, "little")
    changes.append(ByteChange(
        fade, FADE_IN_EXPECT, value,
        "pause-menu fade-in seam",
        "replace the field's per-frame mirror entry with a far entry to the fade step",
    ))
    seams.append({"site": f"0x{FADE_IN:08X}", "function": "fade_in", "value": value.hex()})
    push = PAGE_PUSH - GBA_ROM_BASE
    if image[push : push + 8] != PAGE_PUSH_EXPECT:
        raise PauseMenuError(f"the page push differs at file 0x{push:06x}")
    value = FAR_ENTRY + (symbols["page_push"] | 1).to_bytes(4, "little")
    changes.append(ByteChange(
        push, PAGE_PUSH_EXPECT, value,
        "pause-menu page push seam",
        "replace the page push entry with a far entry that clears the close fade before a page takes the frame loop",
    ))
    seams.append({"site": f"0x{PAGE_PUSH:08X}", "function": "page_push", "value": value.hex()})
    value = relative_entry(symbols["fade_guard"] | 1, FADE_CHAIN_BASE)
    changes.append(ByteChange(
        chain, image[chain : chain + 4], value,
        "pause-menu dialogue chain",
        "chain the dialogue's per-frame update method through the fade guard",
    ))
    seams.append({"site": f"0x{FADE_CHAIN:08X}", "function": "fade_guard",
                  "value": value.hex()})
    provenance = tuple(
        PatchPayloadProvenance(
            p.payload.label, p.payload.source_class, p.payload.transform,
            p.payload.sha256, p.payload.size, p.payload.alignment,
            p.allocation.range, p.allocation.rom_address,
            p.payload.donor_sha256, p.payload.donor_span, p.owners,
        )
        for p in placed.payloads
    )
    generated = placed.generated_allocations
    plan = plan_changes(
        image, changes,
        profile_id=profile.id,
        base_sha256=LOG1_SHA256,
        generated_image=generated_profile.generated_expansion.generated_image(
            len(image), tuple(p.allocated_range for p in generated)),
        generated_allocations=generated,
        patch_payloads=provenance,
    )
    report = {
        "payload_address": f"0x{address:08X}",
        "payload_bytes": (directory / PAYLOAD_FILE).stat().st_size,
        "payload_sha256": digest(directory / PAYLOAD_FILE),
        "assets": {name: len(body) for name, (_kind, body) in blob.items()},
        "assets_sha256": assets_digest(blob),
        "symbols": {name: f"0x{value:08X}" for name, value in symbols.items()},
        "seams": seams,
        "labels": labels,
    }
    return plan, report


def combine(runtime, page, image: bytes):
    from dataclasses import replace

    chain = FADE_CHAIN - GBA_ROM_BASE
    if not any(change.offset == chain for change in page.changes):
        raise PauseMenuError("the pause plan does not chain the dialogue's per-frame entry")
    runtime_changes = tuple(
        change for change in runtime.changes if change.offset != chain)
    spans = tuple(a.allocated_range for a in runtime.generated_allocations) + tuple(
        a.allocated_range for a in page.generated_allocations)
    ordered = sorted(spans, key=lambda span: (span.start.value, span.end))
    for left, right in zip(ordered, ordered[1:]):
        if left.overlaps(right):
            raise PauseMenuError(
                f"the runtime and the pause page claim the same bytes: {left} and {right}")
    return plan_changes(
        image,
        (*runtime_changes, *page.changes),
        profile_id=page.base_profile_id,
        base_sha256=LOG1_SHA256,
        relocations=runtime.relocations,
        generated_image=replace(page.generated_image, allocated_spans=ordered),
        generated_allocations=(*runtime.generated_allocations, *page.generated_allocations),
        patch_payloads=(*runtime.patch_payloads, *page.patch_payloads),
    )


def compose(log1_path: Path, buu_path: Path, log2_path: Path, output: Path,
            directory: Path, manifests: Path, toolchain: str | None) -> dict:
    ensure_assembled()
    from . import sprite_runtime
    from .allocation import OwnedRegion

    if digest(log1_path) != LOG1_SHA256:
        raise PauseMenuError("the target image is not the canonical LOG1 image")
    if digest(log2_path) != LOG2_SHA256:
        raise PauseMenuError("the donor image is not the canonical LOG2 image")
    directory = Path(directory)
    if directory.exists() and any(directory.iterdir()):
        raise PauseMenuError(f"the build directory must be empty: {directory}")
    runtime_image = directory / "runtime.gba"
    runtime_manifest, runtime_report = sprite_runtime.build_runtime(
        log1_path, buu_path, log2_path, runtime_image, directory / "runtime",
        manifests, toolchain)
    image = Path(log1_path).read_bytes()
    chain = FADE_CHAIN - GBA_ROM_BASE
    runtime_entry = next(
        (change for change in runtime_manifest.changes if change.offset == chain), None)
    if runtime_entry is None:
        raise PauseMenuError("the runtime plan holds no dialogue entry to chain")
    fade_target = FADE_CHAIN_BASE + int.from_bytes(runtime_entry.new, "little", signed=True)
    plan, report = plan_page(
        image, Path(log2_path).read_bytes(), directory / "pause", toolchain,
        reserved=tuple(OwnedRegion(a.allocated_range, f"allocated:{a.owner}")
                       for a in runtime_manifest.generated_allocations),
        fade_target=fade_target)
    combined = combine(runtime_manifest, plan, image)
    if digest(log1_path) != LOG1_SHA256 or digest(log2_path) != LOG2_SHA256:
        raise PauseMenuError("a source image changed during the build")
    emit_image(log1_path, output, combined, manifest_path=str(output) + ".manifest.json")
    report["rom_sha256"] = digest(output)
    report["runtime_rom_sha256"] = runtime_report["rom_sha256"]
    report["combined_allocations"] = [
        {"owner": a.owner, "address": a.allocated_rom_address,
         "size": a.allocated_range.end - a.allocated_range.start.value}
        for a in combined.generated_allocations]
    (directory / "pause-build.json").write_text(json.dumps(report, indent=2) + "\n",
                                               encoding="utf-8")
    return report


def read_profile():
    from .catalog import load_catalog
    from .profile import _optional_patch_sites
    from dataclasses import replace

    for profile in load_catalog(None).profiles:
        if profile.game == "legacy_of_goku":
            extra = SITES_FILE
            if not extra.is_file():
                raise PauseMenuError(f"the seam declaration is missing: {extra}")
            document = yaml.safe_load(extra.read_text(encoding="utf-8"))
            declared = _optional_patch_sites(document["patch_sites"])
            if declared is None or len(declared) != 6:
                raise PauseMenuError("the seam declaration does not hold six sites")
            return replace(profile, patch_sites=tuple(
                sorted(profile.patch_sites + declared, key=lambda site: site.site)))
    raise PauseMenuError("the catalogue holds no Legacy of Goku profile")


def _expanded(profile):
    from dataclasses import replace

    return replace(profile, free_regions=(), generated_expansion=GeneratedExpansionProfile(
        16 * 1024 * 1024, 255, "append-only LOG1 pause page; original extents retained"))


def check(log2_path: Path) -> dict:
    """Assert-based self-check over the donor facts the payload depends on."""
    log2 = Path(log2_path).read_bytes()
    if hashlib.sha256(log2).hexdigest() != LOG2_SHA256:
        raise PauseMenuError("the donor image is not the canonical LOG2 image")
    surface = panel_surface(log2)
    tiles = tile_surface(surface)
    assert len(tiles) == PANEL_BYTES, len(tiles)
    assert tiles[:64] == surface[:8] + surface[208:216] + surface[416:424] + \
        surface[624:632] + surface[832:840] + surface[1040:1048] + surface[1248:1256] + \
        surface[1456:1464], "tile order is the PPU's, not a copy of the row-major surface"
    names = strings(log2)
    expected = ("Options", "Journal", "Status", "Items")
    assert tuple(names[name] for name in ("options", "journal", "status", "items")) == expected
    assert names["level"].startswith("Level"), names["level"]
    assert len(palette(log2)) == 256 * 2
    table = font(log2)
    assert glyph(table, ord("!")) == (0x0BC0,), "one column mask per glyph column, bit = row"
    assert advance(table, names["status"]) == 36, advance(table, names["status"])
    blob = assets(log2)
    upper, lower, first, panel = chrome_maps()
    assert panel + PANEL_BYTES // 64 <= 0xC000 // 64, "the page stays below the retail atlas"
    assert len(blob["page"][1]) == len(TABS) * (panel + PANEL_BYTES // 64 - PAGE_TILE) * 64
    return {
        "panel_sha256": hashlib.sha256(surface).hexdigest(),
        "panel_bytes": len(surface),
        "assets_sha256": assets_digest(blob),
        "first_surface_tile": first,
        "panel_tile": panel,
        "labels": sorted(names.items()),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.webfoot.pause_menu")
    parser.add_argument("--rom", type=Path, help="canonical LOG1 image")
    parser.add_argument("--donor", type=Path, help="private LOG2 image")
    parser.add_argument("--buu", type=Path, help="private Buu's Fury image")
    parser.add_argument("--manifests", type=Path, help="sprite import manifests")
    parser.add_argument("--output", type=Path, help="built image")
    parser.add_argument("--directory", type=Path, help="empty build directory")
    parser.add_argument("--toolchain-dir", type=str)
    parser.add_argument("--compose", action="store_true")
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args(argv)
    if arguments.check:
        print(json.dumps(check(arguments.donor), indent=2))
        return 0
    if arguments.compose:
        for name in ("rom", "buu", "donor", "manifests", "output", "directory"):
            if getattr(arguments, name) is None:
                parser.error(f"--{name} is required to compose")
        report = compose(arguments.rom, arguments.buu, arguments.donor, arguments.output,
                         arguments.directory, arguments.manifests,
                         arguments.toolchain_dir)
        print(json.dumps({"rom_sha256": report["rom_sha256"],
                          "runtime_rom_sha256": report["runtime_rom_sha256"],
                          "payload_address": report["payload_address"],
                          "payload_bytes": report["payload_bytes"],
                          "seams": report["seams"]}, indent=2))
        return 0
    for name in ("rom", "donor", "output", "directory"):
        if getattr(arguments, name) is None:
            parser.error(f"--{name} is required to build")
    report = build(arguments.rom, arguments.donor, arguments.output,
                   arguments.directory, arguments.toolchain_dir)
    print(json.dumps({"rom_sha256": report["rom_sha256"],
                      "payload_address": report["payload_address"],
                      "payload_bytes": report["payload_bytes"],
                      "seams": report["seams"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
