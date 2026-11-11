"""The library: every map, character sprite and portrait in the game, with pictures.

A child process reads the ROM once per project and writes an index and one
picture per asset under the project's local folder. Nothing here is built into a
ROM and nothing writes to the source ROM. Every "where it is used" line states a
relationship the SDK has verified, or says plainly that the link is not known.

Names a creator gives are kept in the project, apart from the game's own data.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import struct
import zlib

from tools.dragonbyte.session import Session
from tools.webfoot import donor_resources, map_objects, map_view
from tools.webfoot.formats import sprite_graphics
from tools.webfoot.formats.webfoot_lz import ContainerError, unpack
from tools.webfoot.graphics import GraphicsError, load_actor_sprites
from tools.webfoot.sprite_identity import SPRITE_ID_FLOOR

CACHE = Path(".dragonbyte") / "cache" / "library"
INDEX = CACHE / "index.json"
INDEX_VERSION = 2
NAMES = Path("library") / "names.json"
LONG_SIDE = 512
KINDS = ("map", "sprite", "portrait")
LISTED = 8
NO_MAPS = "No map places it. Whether a story scene brings it in is not known."
NO_OBJECTS = "Nothing is placed on this map. Whether a story scene brings anything in is not known."
DRAW_ERRORS = (
    map_view.MapBrowserError,
    GraphicsError,
    sprite_graphics.SpriteFormatError,
    donor_resources.DonorResourceError,
    ContainerError,
)


def picture_path(project: Path, key: str) -> Path:
    return Path(project) / CACHE / (key.replace(":", "-") + ".png")


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".pending")
    pending.write_bytes(data)
    os.replace(pending, path)


def _read(path: Path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def read_names(project: Path) -> dict[str, str]:
    document = _read(Path(project) / NAMES)
    if not isinstance(document, dict):
        return {}
    return {key: value for key, value in document.items() if isinstance(key, str) and isinstance(value, str)}


def set_name(project: Path, key: str, name: str) -> dict[str, str]:
    """Give one asset the creator's own name; an empty name removes it."""
    path = Path(project) / NAMES
    if path.exists() and not isinstance(_read(path), dict):
        raise OSError(0, f"{NAMES} is damaged. Fix or delete that file, then name it again")
    names = read_names(project)
    name = " ".join(name.split())
    if name:
        names[key] = name
    else:
        names.pop(key, None)
    _write(Path(project) / NAMES, (json.dumps(names, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return names


def read_index(project: Path) -> list[dict] | None:
    document = _read(Path(project) / INDEX)
    if not isinstance(document, dict) or document.get("version") != INDEX_VERSION:
        return None
    return document["assets"]


def _png(width: int, height: int, rgba: bytes) -> bytes:
    stride = width * 4
    rows = b"".join(b"\x00" + rgba[y * stride:(y + 1) * stride] for y in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def _map_picture(reader, index: int) -> bytes:
    result = map_view.render_map(reader, index)
    step = max(1, -(-max(result.width, result.height) // LONG_SIDE))
    rows = [
        result.composite[y * result.width:(y + 1) * result.width:step]
        for y in range(0, result.height, step)
    ]
    table = map_view.rgba_table(result.palette)
    rgba = map_view.to_rgba(b"".join(rows), table, backdrop=result.palette[0])
    return _png(len(rows[0]), len(rows), rgba)


def _sprite_picture(sprites, character, table: bytes) -> bytes:
    for animation in sprites.get_actor_animations(character.identity):
        for frame in animation.frames:
            for identity in frame.graphics:
                if identity is not None:
                    graphic = sprites.graphic(identity)
                    return _png(graphic.width, graphic.height, map_view.to_rgba(graphic.pixels, table))
    graphic = sprites.graphic(character.graphics[0])
    return _png(graphic.width, graphic.height, map_view.to_rgba(graphic.pixels, table))


def _portrait_picture(image: bytes, slot: int, table: bytes) -> bytes:
    offset = donor_resources.portrait_container_offset(image, slot)
    pixels = unpack(image, offset, maximum_output=len(image)).data
    if len(pixels) != donor_resources.PORTRAIT_BYTES:
        raise donor_resources.DonorResourceError(f"portrait {slot} is not 64x64")
    return _png(donor_resources.PORTRAIT_W, donor_resources.PORTRAIT_H, map_view.to_rgba(pixels, table))


def _listed(items: list[str]) -> str:
    extra = len(items) - LISTED
    return ", ".join(items[:LISTED]) + (f" and {extra} more" if extra > 0 else "")


def _names_of(rows) -> list[str]:
    return list(dict.fromkeys(" ".join(row.name.split()) for row in rows if row.name.strip()))


def build_index(rom_path: Path) -> tuple[list[dict], dict]:
    """Every asset with its game-given label and verified uses, and how to draw each."""
    image, _ = donor_resources.load_donor(rom_path)
    session = Session()
    session.open_rom(Path(rom_path))
    sprites = load_actor_sprites(image, session.identification)
    table = map_view.rgba_table(sprites.palette.rgb)
    definitions = donor_resources.appearance_records(image)
    reader = map_view.reader_for(image)
    placed = map_objects.census(image, session.profile)
    assets: list[dict] = []
    painters: dict = {}

    def add(key: str, label: str, uses: list[str], painter) -> None:
        assets.append({"key": key, "kind": key.split(":")[0], "label": label, "uses": uses})
        painters[key] = painter

    for character in sprites.characters():
        index = character.identity.index
        users = [row for row in definitions if row.sprite_id == index + SPRITE_ID_FLOOR]
        names = _names_of(users)
        portraits = sorted({row.portrait_slot for row in users if row.portrait_slot})
        sharing = sorted(
            {other.index for graphic in character.graphics for other in sprites.graphic(graphic).characters}
            - {index}
        )
        uses = [
            f"Character definitions that use this sprite: {_listed(names)}."
            if names
            else "No character definition uses this sprite. Whether anything else uses it is not known.",
        ]
        if portraits:
            uses.append("Portraits shown with it: " + _listed([f"portrait:{slot:03d}" for slot in portraits]) + ".")
        if sharing:
            uses.append("Shares artwork with: " + _listed([f"sprite:{other:04d}" for other in sharing]) + ".")
        maps = sorted(number for number, objects in placed.items()
                      if any(item.sprite_id == index + SPRITE_ID_FLOOR for item in objects))
        uses.append("Maps that place it: " + _listed([f"map:{number:04d}" for number in maps]) + "."
                    if maps else NO_MAPS)
        add(
            f"sprite:{index:04d}",
            ", ".join(names),
            uses,
            lambda character=character: _sprite_picture(sprites, character, table),
        )

    for slot in range(donor_resources.PORTRAIT_SLOT_FIRST, donor_resources.PORTRAIT_SLOT_LAST + 1):
        users = [row for row in definitions if row.portrait_slot == slot]
        names = _names_of(users)
        shown_with = sorted({row.sprite_id - SPRITE_ID_FLOOR for row in users})
        uses = (
            [
                f"Character definitions that use this portrait: {_listed(names)}.",
                "Sprites shown with it: " + _listed([f"sprite:{index:04d}" for index in shown_with]) + ".",
            ]
            if users
            else ["No character definition uses this portrait. Whether anything else shows it is not known."]
        )
        add(
            f"portrait:{slot:03d}",
            ", ".join(names),
            uses,
            lambda slot=slot: _portrait_picture(image, slot, table),
        )

    for entry in map_view.read_map_index(reader):
        uses = [
            f"Its name is game text number {entry.text_index}."
            if entry.text_index is not None and entry.name
            else "The game gives this map no name.",
            "Placed on this map: " + _listed(sorted({
                f"sprite:{item.sprite_id - SPRITE_ID_FLOOR:04d}" for item in placed[entry.index]
                if item.sprite_id >= SPRITE_ID_FLOOR})) + "."
            if entry.index in placed else NO_OBJECTS,
        ]
        add(
            f"map:{entry.index:04d}",
            " ".join((entry.name or "").split()),
            uses,
            lambda index=entry.index: _map_picture(reader, index),
        )
    return assets, painters


def write_library(rom_path: Path, project: Path, only=None) -> dict:
    """Write the index, then every missing picture; one that cannot be drawn is counted."""
    assets, painters = build_index(rom_path)
    _write(
        Path(project) / INDEX,
        json.dumps({"version": INDEX_VERSION, "assets": assets}).encode("utf-8"),
    )
    made, failed = 0, []
    for key, painter in painters.items():
        target = picture_path(project, key)
        if (only is not None and key not in only) or target.is_file():
            continue
        try:
            _write(target, painter())
        except DRAW_ERRORS:
            failed.append(key)
            continue
        made += 1
    return {"ok": True, "problems": [], "error": "", "made": made, "failed": failed}
