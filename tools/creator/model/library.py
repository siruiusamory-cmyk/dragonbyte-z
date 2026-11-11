"""The map library: every map's label, and thumbnails cached in the project.

Thumbnails are pictures of the retail maps, made once per project by a child
process and kept under the project's local folder. They are never built into a
ROM and nothing here writes to the source ROM.
"""

from __future__ import annotations

import os
from pathlib import Path
import struct
import zlib

from tools.webfoot import map_view

THUMBNAILS = Path(".dragonbyte") / "cache" / "maps"
LONG_SIDE = 512


def map_entries(rom_path: Path) -> list[tuple[int, str]]:
    """Every map as (index, label); a map the game gives no text has an empty label."""
    entries = map_view.read_map_index(Path(rom_path).read_bytes())
    return [(entry.index, " ".join((entry.name or "").split())) for entry in entries]


def thumbnail_path(project: Path, index: int) -> Path:
    return Path(project) / THUMBNAILS / f"map-{index:04d}.png"


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


def render_thumbnail(reader, index: int) -> bytes:
    """One map as a PNG no longer than LONG_SIDE pixels on its long side."""
    result = map_view.render_map(reader, index)
    step = max(1, -(-max(result.width, result.height) // LONG_SIDE))
    rows = [
        result.composite[y * result.width:(y + 1) * result.width:step]
        for y in range(0, result.height, step)
    ]
    table = map_view.rgba_table(result.palette)
    rgba = map_view.to_rgba(b"".join(rows), table, backdrop=result.palette[0])
    return _png(len(rows[0]), len(rows), rgba)


def write_thumbnails(rom_path: Path, project: Path, indices=None) -> dict:
    """Make every missing thumbnail; a map that cannot be drawn is counted, not fatal."""
    reader = map_view.reader_for(Path(rom_path).read_bytes())
    wanted = [index for index, _ in map_entries(rom_path)] if indices is None else list(indices)
    (Path(project) / THUMBNAILS).mkdir(parents=True, exist_ok=True)
    made, failed = 0, []
    for index in wanted:
        target = thumbnail_path(project, index)
        if target.is_file():
            continue
        try:
            picture = render_thumbnail(reader, index)
        except map_view.MapBrowserError:
            failed.append(index)
            continue
        pending = target.with_name(target.name + ".pending")
        pending.write_bytes(picture)
        os.replace(pending, target)
        made += 1
    return {"ok": True, "problems": [], "error": "", "made": made, "failed": failed}
