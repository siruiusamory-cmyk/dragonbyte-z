from __future__ import annotations

import re
import struct

from . import sprite_import as si
from .sprite_limits import ART_TABLE
from .formats.sprite_graphics import unswizzle_tiles, swizzle_tiles

BINDINGS = {
    "goku-base": {0: 0, 1: 1, 3: 4, 4: 5, 9: 10},
    "goku-super-saiyan": {0: 0, 1: 1, 3: 6, 4: 4},
    "roshi": {0: 0, 1: 1, 6: 12},
    "krillin-art46": {0: 0, 1: 1},
    "krillin-art47-swap-in": {0: 0, 1: 1},
}
FALLBACK_STATES = {
    "goku-base": (2, 5, 6, 7, 12, 13, 14, 15, 16),
    "goku-super-saiyan": (2, 5, 6, 7, 12, 13, 14, 15, 16),
    "roshi": (),
    "krillin-art46": (2, 6),
    "krillin-art47-swap-in": (2, 6),
}
DEFINITIONS = {
    "goku-base": 0x086AD1CC,
    "goku-super-saiyan": 0x086AD3B8,
    "roshi": 0x086B0A00,
    "krillin-art46": 0x082E94B4,
    "krillin-art47-swap-in": 0x082E94B4,
}


def transformation_assets(image, draw):
    lines = [
        "typedef unsigned char u8; typedef unsigned short u16; typedef unsigned int u32;",
        "typedef void (*Draw)(u8 *,void *);",
        "struct Cell {short x,y; u16 w,h; u8 tiles,a,size,shape; const u8 *data;};",
        '_Static_assert(sizeof(struct Cell)==16,"cell size");',
        "struct Frame {const u32 *primary,*follower; const u16 *palette,*follower_palette;};",
        f"const Draw bounded_draw=(Draw){draw};",
    ]
    entries = []
    source_frames = si.donor_frames(image, "webfoot-animation", 0x086AD1CC, 10, 0)
    assert all(
        si.donor_frames(image, "webfoot-animation", 0x086AD1CC, 10, d) == source_frames
        for d in range(4)
    )
    for index, frame in enumerate(
        si.donor_frames(image, "webfoot-animation", 0x086AD1CC, 10, 0)
    ):
        parts = si.frame_pieces(image, frame)
        payloads = si.build_frame_piece_payloads(
            image, frame, slot=10, direction=0, frame_index=index
        )
        assert len(parts) == len(payloads) and len(parts) <= 2
        names = []
        for n, (part, payload) in enumerate(zip(parts, payloads, strict=True)):
            name = f"f{index}p{n}"
            lines.append(
                f"static const u8 {name}tiles[]={{"
                + ",".join(map(str, payload.tiles))
                + "};"
            )
            palette = [0] + [
                image.u16(0x0805652C + 2 * c) & 0x7FFF for c in part.colours
            ]
            palette += [0] * (16 - len(palette))
            lines.append(
                f"static const u16 {name}pal[16]={{"
                + ",".join(map(str, palette))
                + "};"
            )
            c = payload.cell
            values = [
                c.x,
                c.y,
                c.width,
                c.height,
                c.tiles,
                c.attributes[0],
                c.attributes[1] & 3,
                c.attributes[2],
            ]
            lines.append(
                f"static const struct Cell {name}cell={{"
                + ",".join(map(str, values))
                + f",{name}tiles"
                + "};"
            )
            lines.append(
                f"static const u32 {name}table[4]={{"
                + ",".join([f"(u32)&{name}cell"] * 4)
                + "};"
            )
            names.append(name)
        second = f"{names[1]}table" if len(names) > 1 else "0"
        second_pal = f"{names[1]}pal" if len(names) > 1 else "0"
        entries.append(
            "{" + f"{names[0]}table,{second},{names[0]}pal,{second_pal}" + "}"
        )
    lines.append("const struct Frame frames[11]={" + ",".join(entries) + "};")
    return "\n".join(lines)


def projectile_assets(image):
    lines = []
    directions = []
    boxes = []
    for direction in range(4):
        frames = []
        frame_boxes = []
        for frame in range(5):
            address = (
                0x087137CC if frame == 4 else 0x0871370C + direction * 48 + frame * 12
            )
            x, y, w, h, attr, gfx = struct.unpack("<bbBBII", image.span(address, 12))
            assert attr & 0x2000 and w * h <= 256
            source = unswizzle_tiles(image.span(gfx, w * h), w, h, colour_256=True)
            raster = bytes(
                source[
                    (h - 1 - j if attr & 0x20000000 else j) * w
                    + (w - 1 - i if attr & 0x10000000 else i)
                ]
                for j in range(h)
                for i in range(w)
            )
            colours = sorted(set(raster) - {0})
            assert len(colours) <= 15
            mapped = bytes(colours.index(v) + 1 if v else 0 for v in raster)
            assert bytes(colours[v - 1] if v else 0 for v in mapped) == raster
            data = swizzle_tiles(mapped, w, h, colour_256=False)
            palette = [0] + [image.u16(0x0805652C + 2 * v) & 0x7FFF for v in colours]
            palette += [0] * (16 - len(palette))
            name = f"projectile_{direction}_{frame}"
            section = '__attribute__((section(".bf_assets"),aligned(4)))'
            lines.append(
                f"static const u8 {name}_tiles[] {section}={{"
                + ",".join(map(str, data))
                + "};"
            )
            lines.append(
                f"static const u16 {name}_palette[16] {section}={{"
                + ",".join(map(str, palette))
                + "};"
            )
            size, shape = si.cell_geometry(w, h)
            values = [-x, -y, w, h, w * h // 64, 0, size, shape]
            lines.append(
                f"static const struct Cell {name}_cell {section}={{"
                + ",".join(map(str, values))
                + f",{name}_tiles"
                + "};"
            )
            lines.append(
                f"static const u32 {name}_table[4] {section}={{"
                + ",".join([f"(u32)&{name}_cell"] * 4)
                + "};"
            )
            lines.append(
                f"static const struct Piece {name}_piece {section}={{"
                + f"{name}_table,{name}_palette"
                + "};"
            )
            frames.append("{1,&" + name + "_piece}")
            if frame < 4:
                frame_boxes.append("{" + ",".join(map(str, [-x, -y, w, h])) + "}")
        directions.append("{" + ",".join(frames) + "}")
        boxes.append("{" + ",".join(frame_boxes) + "}")
    lines.append(
        'const struct RenderFrame projectile_frames[4][5] __attribute__((section(".bf_assets"),aligned(4)))={'
        + ",".join(directions)
        + "};"
    )
    lines.append(
        'const signed char projectile_boxes[4][4][4] __attribute__((section(".bf_assets"),aligned(4)))={'
        + ",".join(boxes)
        + "};"
    )
    bodies = []
    for definition in [0x086AD30C, 0x086AD464]:
        directions = []
        for direction in range(4):
            values = struct.unpack(
                "<4i", image.span(definition + 0x10 + direction * 16, 16)
            )
            assert all(-32768 <= value <= 32767 for value in values)
            directions.append("{" + ",".join(map(str, values)) + "}")
        bodies.append("{" + ",".join(directions) + "}")
    lines.append(
        'const short donor_player_bodies[2][4][4] __attribute__((section(".bf_assets"),aligned(4)))={'
        + ",".join(bodies)
        + "};"
    )
    melee = []
    for direction in range(4):
        values = struct.unpack("<4i", image.span(0x083C344C + direction * 16, 16))
        assert all(-32768 <= value <= 32767 for value in values)
        melee.append("{" + ",".join(map(str, values)) + "}")
    lines.append(
        'const short donor_melee_rects[4][4] __attribute__((section(".bf_assets"),aligned(4)))={'
        + ",".join(melee)
        + "};"
    )
    return lines


def groups(colours):
    best = None

    def place(index, packed):
        nonlocal best
        if best is not None and len(packed) >= len(best):
            return
        if index == len(colours):
            best = tuple(packed)
            return
        for i, palette in enumerate(packed):
            merged = palette | colours[index]
            if len(merged) <= 15:
                place(index + 1, packed[:i] + [merged] + packed[i + 1 :])
        place(index + 1, packed + [colours[index]])

    place(0, [])
    assert best and all(len(palette) <= 15 for palette in best)
    return best


def actor_assets(manifests, base_image, bf_image, log2_image):
    lines = [
        "typedef unsigned char u8; typedef unsigned short u16; typedef unsigned int u32;",
        "struct Cell {short x,y;u16 w,h;u8 tiles,a,size,shape;const u8 *data;};",
        "struct Piece {const u32 *table;const u16 *palette;};",
        "struct RenderFrame {u32 count;const struct Piece *pieces;};",
        "struct Binding {u32 art,row,kind,count;const struct RenderFrame *directions[4];};",
    ]
    emitted = {}
    records = []
    serial = 0

    def emit(kind, values, section):
        nonlocal serial
        key = (kind, values, section)
        if key not in emitted:
            name = f"g{serial}"
            serial += 1
            qualifier = f'__attribute__((section(".{section}"),aligned(4)))'
            lines.append(f"static const {kind} {name} {qualifier}={values};")
            emitted[key] = name
        return emitted[key]

    for name, bindings in BINDINGS.items():
        document = si.load_manifest(manifests / f"{name}.json")
        entry = document.imports[0]
        expected_art = {
            "goku-base": 32,
            "goku-super-saiyan": 72,
            "roshi": 68,
            "krillin-art46": 46,
            "krillin-art47-swap-in": 47,
        }[name]
        image = bf_image if entry.donor == "buus-fury" else log2_image
        if (
            len(document.imports) != 1
            or entry.target.art_id != expected_art
            or tuple(entry.target.states) != tuple(bindings)
            or tuple(entry.target.fallback_states) != FALLBACK_STATES[name]
            or entry.target.art_table != ART_TABLE
            or entry.donor
            != ("legacy-of-goku-2" if name.startswith("krillin") else "buus-fury")
        ):
            raise si.SpriteImportError(
                f"{name}: runtime target mapping differs from the approved manifest"
            )
        if (
            document.donor(entry.donor).sha256 != image.sha256
            or entry.target.sha256 != base_image.sha256
        ):
            raise si.SpriteImportError(f"{name}: runtime source identities differ")
        if entry.definition != DEFINITIONS[
            name
        ] or entry.target.art_definition != base_image.u32(
            ART_TABLE + expected_art * 4
        ):
            raise si.SpriteImportError(
                f"{name}: runtime appearance differs from the approved manifest"
            )
        if name == "krillin-art47-swap-in":
            for row in records[:]:
                if row[0] == 46:
                    records.append((47, *row[1:]))
            continue
        is_bf = entry.donor == "buus-fury"
        image = bf_image if is_bf else log2_image
        target = base_image
        art = si.read_log1_art(
            target, entry.target.art_table, entry.target.art_id, entry.target.states
        )
        family = document.donor(entry.donor).family
        section = "bf_assets" if is_bf else "lg2_assets"
        for state, slot in bindings.items():
            if state == 9:
                continue
            directions = []
            frame_count = None
            for direction in range(4):
                donor_frames = si.donor_frames(
                    image, family, entry.definition, slot, direction
                )
                if not is_bf:
                    donor_frames = donor_frames[: 2 if slot == 0 else 4]
                assert frame_count is None or frame_count == len(donor_frames)
                frame_count = len(donor_frames)
                rendered = []
                for index, frame in enumerate(donor_frames):
                    parts = si.frame_pieces(image, frame)
                    payloads = si.build_frame_piece_payloads(
                        image, frame, slot=slot, direction=direction, frame_index=index
                    )
                    packed = groups([frozenset(part.colours) for part in parts])
                    pieces = []
                    for part, payload in zip(parts, payloads, strict=True):
                        palette = tuple(
                            sorted(next(p for p in packed if set(part.colours) <= p))
                        )
                        indices = unswizzle_tiles(
                            payload.tiles, part.width, part.height, colour_256=False
                        )
                        source = [part.colours[v - 1] if v else 0 for v in indices]
                        mapped = bytes(palette.index(v) + 1 if v else 0 for v in source)
                        assert [palette[v - 1] if v else 0 for v in mapped] == source
                        tiles = swizzle_tiles(
                            mapped, part.width, part.height, colour_256=False
                        )
                        tile = emit(
                            f"u8", "{" + ",".join(map(str, tiles)) + "}", section
                        )
                        colour_values = [0] + [
                            image.u16((0x0805652C if is_bf else 0x081DA6C8) + 2 * c)
                            & 0x7FFF
                            for c in palette
                        ]
                        colour_values += [0] * (16 - len(colour_values))
                        pal = emit(
                            "u16",
                            "{" + ",".join(map(str, colour_values)) + "}",
                            section,
                        )
                        c = payload.cell
                        values = [
                            c.x,
                            c.y,
                            c.width,
                            c.height,
                            c.tiles,
                            c.attributes[0],
                            c.attributes[1] & 3,
                            c.attributes[2],
                        ]
                        cell = emit(
                            "struct Cell",
                            "{" + ",".join(map(str, values)) + f",{tile}" + "}",
                            section,
                        )
                        table = emit(
                            "u32", "{" + ",".join([f"(u32)&{cell}"] * 4) + "}", section
                        )
                        pieces.append("{" + f"{table},{pal}" + "}")
                    piece_array = emit(
                        "struct Piece", "{" + ",".join(pieces) + "}", section
                    )
                    rendered.append("{" + f"{len(pieces)},{piece_array}" + "}")
                direction_array = emit(
                    "struct RenderFrame", "{" + ",".join(rendered) + "}", section
                )
                directions.append(direction_array)
            timing = next(a.timing for a in entry.animations if a.slot == slot)
            durations = timing.durations_video_frames
            kind = 0 if state == 0 else 1 if state == 1 else 2
            if frame_count == 2 and durations == (8, 8):
                kind = 3
            elif frame_count == 2 and durations == (241, 15):
                kind = 0
            records.append(
                (
                    entry.target.art_id,
                    state,
                    kind,
                    frame_count,
                    tuple(directions),
                    art.animation_table + state * 16,
                )
            )
    target = base_image
    binding_rows = []
    for art_id, state, kind, count, directions, row in records:
        definition = target.u32(ART_TABLE + art_id * 4)
        if art_id == 47:
            row = target.u32(definition + 0x28) + state * 16
        binding_rows.append(
            "{"
            + f"{definition},{row},{kind},{count},"
            + "{"
            + ",".join(directions)
            + "}"
            + "}"
        )
    lines.append("const struct Binding bindings[]={" + ",".join(binding_rows) + "};")
    lines.append(f"const u32 binding_count={len(binding_rows)};")
    lines.extend(projectile_assets(bf_image))
    text = "\n".join(lines)
    text = re.sub(
        r"(static const (?:u8|u16|u32|struct Piece|struct RenderFrame) g\d+)( )",
        r"\1[]\2",
        text,
    )
    return text
