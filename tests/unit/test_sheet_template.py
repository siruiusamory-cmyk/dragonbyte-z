"""Exporting the new character as one sheet plus a .sprite.toml, and importing it back."""

from __future__ import annotations

import _winapi
import hashlib
import os
import time
import tracemalloc
import re
import struct
import zlib

import pytest

from tests.helpers import write_truecolour_png
from tests.rom_support import canonical_rom_path, mutable_rom_copy
from tools.creator.model import characters as ch
from tools.creator.model.library import read_names, set_name
from tools.creator.model.project import CreatorError
from tools.webfoot.formats import rgb_png
from tools.webfoot.project.format import dump_toml, load_toml

pytestmark = pytest.mark.skipif(
    canonical_rom_path() is None, reason="the canonical Buu's Fury ROM is not present"
)


@pytest.fixture(scope="module")
def rom(tmp_path_factory):
    return mutable_rom_copy(tmp_path_factory.mktemp("rom"))


@pytest.fixture()
def maker(tmp_path, rom):
    return ch.CharacterMaker(tmp_path / "game", rom)


def _content(maker):
    return {(f.animation, f.direction, f.frame): maker.picture(f.picture)[2]
            for f in maker.frames()}


def _drawn(maker, behaviour, size, walk_frames=3):
    """Every frame gets its own pattern of palette indices, holes included."""
    maker.create("Gohan Jr", behaviour, size)
    if behaviour == ch.WALKS:
        maker.set_frames(1, walk_frames)
    colours = maker.colours()
    side = maker.character.width
    for f in maker.frames():
        for shade in range(1, 6):
            points = [(x, y) for y in range(side) for x in range(side)
                      if (x * y + x + f.picture) % 6 == shade]
            maker.paint(f.picture, points, colours[(shade * 11 + f.picture) % len(colours)],
                        stroke=f"s{f.picture}")
    maker.set_attribution("Drawn by a test, free to share")
    return maker


@pytest.mark.parametrize("behaviour,size", [
    (ch.STANDS, "16 by 16 pixels"), (ch.STANDS, "32 by 32 pixels"),
    (ch.WALKS, "16 by 16 pixels"), (ch.WALKS, "32 by 32 pixels")])
def test_export_then_import_into_a_fresh_project_keeps_every_pixel_index(
        maker, tmp_path, rom, behaviour, size):
    """Pins the lossless round trip by content: pixels, frames, behaviour, size, name, credit."""
    _drawn(maker, behaviour, size)
    out = tmp_path / "out"
    out.mkdir()
    picture, sidecar = maker.export_sheet(out)
    assert sorted(p.name for p in out.iterdir()) == ["gohan-jr.png", "gohan-jr.sprite.toml"]
    fresh = ch.CharacterMaker(tmp_path / "fresh", rom)
    fresh.import_template(sidecar)
    assert fresh.character == maker.character
    assert _content(fresh) == _content(maker)
    assert fresh.attribution() == "Drawn by a test, free to share"
    assert read_names(fresh.directory)[fresh._name_key()] == "Gohan Jr"
    assert ch.CharacterMaker(fresh.directory, rom).character == maker.character
    side = maker.character.width
    _rgb, width, height, alpha = rgb_png.decode_truecolour(picture.read_bytes())
    assert (width, height) == (side * 4 * max(maker.character.frames),
                               side * len(maker.character.frames))
    assert alpha is not None and 0 in alpha


def test_the_sidecar_is_versioned_relative_and_free_of_rom_values(maker, tmp_path):
    """Pins portability: no offset, donor id, sprite id, absolute path, drive or user name."""
    _drawn(maker, ch.WALKS, "16 by 16 pixels", 2)
    _picture, sidecar = maker.export_sheet(tmp_path)
    text = sidecar.read_text(encoding="utf-8")
    document = load_toml(text)
    assert document["format"] == ch.TEMPLATE_FORMAT
    assert document["picture"] == "gohan-jr.png"
    assert document["behaviour"] == "Walks"
    assert document["animation"]["stand"]["facings"] == ["down", "up", "left", "right"]
    assert document["animation"]["walk"]["role"] == "walk"
    assert document["source"] == {}
    lowered = text.lower()
    for word in ("donor", "sprite_id", "offset", "address", "0x", "actor", "slot", "direction"):
        assert word not in lowered
    assert re.search(r"[a-z]:[\\/]", lowered) is None and "\\\\" not in text
    assert str(maker.sprite + 10) not in re.sub(r"frame_\w+ = \d+", "", text)
    for user in {os.environ.get("USERNAME"), os.environ.get("USER")} - {None, ""}:
        assert user.lower() not in lowered
    assert str(tmp_path).lower() not in lowered


def _exported(maker, tmp_path):
    _drawn(maker, ch.STANDS, "16 by 16 pixels")
    return maker.export_sheet(tmp_path)


def _edit(sidecar, **changes):
    document = load_toml(sidecar.read_text(encoding="utf-8"))
    document.update(changes)
    sidecar.write_text(dump_toml(document), encoding="utf-8")


@pytest.mark.parametrize("reference", [
    "C:\\Art\\gohan-jr.png", "C:gohan-jr.png", "../gohan-jr.png", "..\\gohan-jr.png",
    "//server/share/gohan-jr.png", "sub/gohan-jr.png", "/gohan-jr.png", "..",
    "gohan-jr.png.", "gohan-jr.png "])
def test_a_picture_reference_that_leaves_the_folder_is_refused(
        maker, tmp_path, rom, reference):
    """Pins containment: the picture is resolved next to the sidecar only."""
    _picture, sidecar = _exported(maker, tmp_path)
    _edit(sidecar, picture=reference)
    fresh = ch.CharacterMaker(tmp_path / "fresh", rom)
    with pytest.raises(CreatorError, match="names a picture in its own folder"):
        fresh.import_template(sidecar)
    assert fresh.character is None and not (fresh.directory / "sprites").exists()


def test_refused_templates_say_why_in_words_and_write_nothing(maker, tmp_path, rom):
    """Pins each refusal: missing picture, wrong size, unknown version, malformed TOML."""
    picture, sidecar = _exported(maker, tmp_path)
    fresh = ch.CharacterMaker(tmp_path / "fresh", rom)
    cases = []
    good = sidecar.read_bytes()
    _edit(sidecar, format=2)
    cases.append(("format this creator does not know", sidecar.read_bytes()))
    sidecar.write_bytes(b"format = 1\npicture = [\n")
    cases.append(("not a sheet description", sidecar.read_bytes()))
    sidecar.write_bytes(good)
    _edit(sidecar, frame_width=8, frame_height=8)
    cases.append(("describes 32 by 8 pixels", sidecar.read_bytes()))
    sidecar.write_bytes(good)
    _edit(sidecar, behaviour="Walks")
    cases.append(("has Stand pose and Walk animation only", sidecar.read_bytes()))
    for message, data in cases:
        sidecar.write_bytes(data)
        with pytest.raises(CreatorError, match=message):
            fresh.import_template(sidecar)
    sidecar.write_bytes(good)
    picture.unlink()
    with pytest.raises(CreatorError, match="gohan-jr.png could not be read"):
        fresh.import_template(sidecar)
    assert fresh.character is None and not (fresh.directory / "sprites").exists()
    assert not fresh.can_undo


def test_an_unsupported_colour_in_a_template_is_listed_and_nothing_is_written(
        maker, tmp_path, rom):
    """Pins exact colours: the diagnostic names colour, animation, facing and frame."""
    picture, sidecar = _exported(maker, tmp_path)
    rgb, width, height, alpha = rgb_png.decode_truecolour(picture.read_bytes())
    odd = next((r, 1, 2) for r in range(256) if (r, 1, 2) not in set(maker.palette()))
    at = 2 * 16 + 5
    rgb = rgb[:3 * at] + bytes(odd) + rgb[3 * at + 3:]
    rgba = b"".join(rgb[3 * i:3 * i + 3] + (b"\xff" if i == at else bytes([alpha[i]]))
                    for i in range(width * height))
    from tools.creator.model.library import _png
    picture.write_bytes(_png(width, height, rgba))
    _edit(sidecar, pixels_sha256=hashlib.sha256(ch._canonical(rgb, b"".join(
        rgba[4 * i + 3:4 * i + 4] for i in range(width * height)))).hexdigest())
    other = ch.CharacterMaker(tmp_path / "other", rom)
    other.create("Guard", ch.STANDS, "16 by 16 pixels")
    before = other._snapshot()
    with pytest.raises(CreatorError) as caught:
        other.import_template(sidecar)
    assert f"The Stand pose uses colours" in str(caught.value)
    assert f"#{odd[0]:02X}0102 (facing left, frame 1)" in str(caught.value)
    assert other._snapshot() == before and other.character.name == "guard"


def test_a_huge_header_picture_is_refused_in_words_not_an_overflow(maker, tmp_path, rom):
    """Pins the bounded decode: a lying PNG header is a plain refusal."""
    picture, sidecar = _exported(maker, tmp_path)
    write_truecolour_png(picture, bytes(3 * 4), 4, 1)
    data = bytearray(picture.read_bytes())
    data[16:24] = struct.pack(">II", 0x7FFFFFFF, 0x7FFFFFFF)
    data[29:33] = struct.pack(">I", zlib.crc32(bytes(data[12:29])) & 0xFFFFFFFF)
    picture.write_bytes(bytes(data))
    with pytest.raises(CreatorError, match="describes 64 by 16 pixels"):
        ch.CharacterMaker(tmp_path / "fresh", rom).import_template(sidecar)


@pytest.mark.parametrize("name", ["con", "nul.txt", "gohan."])
def test_a_device_or_trailing_dot_name_is_refused_at_export(maker, tmp_path, name):
    """Pins the name rules at export, for a character name edited outside the creator."""
    _drawn(maker, ch.STANDS, "16 by 16 pixels")
    out = tmp_path / "out"
    out.mkdir()
    maker.character = ch.replace(maker.character, name=name)
    with pytest.raises(CreatorError, match="Windows keeps|A name starts"):
        maker.export_sheet(out)
    assert not any(out.iterdir())


def test_existing_files_are_replaced_only_when_confirmed(maker, tmp_path):
    """Pins no silent overwrite, and that the destination must be a folder."""
    picture, sidecar = _exported(maker, tmp_path)
    sidecar.write_text("mine", encoding="utf-8")
    with pytest.raises(CreatorError, match="gohan-jr.png and gohan-jr.sprite.toml are already"):
        maker.export_sheet(tmp_path)
    assert sidecar.read_text(encoding="utf-8") == "mine"
    maker.export_sheet(tmp_path, replace_files=True)
    assert load_toml(sidecar.read_text(encoding="utf-8"))["format"] == 1
    with pytest.raises(CreatorError, match="not a folder"):
        maker.export_sheet(picture)
    assert not [p for p in tmp_path.iterdir() if p.name.endswith(".pending")]


def test_export_writes_nothing_outside_the_folder_even_through_a_junction(maker, tmp_path):
    """Pins containment: a junction named like the output file is never written through."""
    _drawn(maker, ch.STANDS, "16 by 16 pixels")
    out, elsewhere = tmp_path / "out", tmp_path / "elsewhere"
    out.mkdir()
    elsewhere.mkdir()
    link = out / "gohan-jr.png"
    _winapi.CreateJunction(str(elsewhere), str(link))
    try:
        for confirmed in (False, True):
            with pytest.raises(CreatorError, match="not a plain file"):
                maker.export_sheet(out, replace_files=confirmed)
        assert not any(elsewhere.iterdir())
        assert sorted(p.name for p in out.iterdir()) == ["gohan-jr.png"]
    finally:
        os.rmdir(link)
    via = tmp_path / "via"
    _winapi.CreateJunction(str(elsewhere), str(via))
    try:
        maker.export_sheet(via)
        assert sorted(p.name for p in elsewhere.iterdir()) == [
            "gohan-jr.png", "gohan-jr.sprite.toml"]
        assert sorted(p.name for p in tmp_path.iterdir()) == ["elsewhere", "game", "out", "via"]
    finally:
        os.rmdir(via)


def test_undoing_a_template_import_restores_the_character_and_keeps_a_rename(
        maker, tmp_path, rom):
    """Pins one undo step that restores the prior bytes and leaves other Library names."""
    _picture, sidecar = _exported(maker, tmp_path)
    other = ch.CharacterMaker(tmp_path / "other", rom)
    other.create("Guard", ch.WALKS, "32 by 32 pixels")
    other.paint(0, [(1, 1)], other.colours()[3])
    before = other._snapshot()
    other.import_template(sidecar)
    assert other.character.name == "gohan-jr" and other.character.behaviour == ch.STANDS
    set_name(other.directory, "sprite:0010", "My renamed sprite")
    other.undo()
    assert other._snapshot() == before
    assert other.character.name == "guard" and other.character.frames == (1, 2)
    assert read_names(other.directory)["sprite:0010"] == "My renamed sprite"
    assert not [p for p in (other.directory / "sprites").rglob("*")
                if p.is_file() and "gohan-jr" in p.parts]
    other.redo()
    assert other.character.name == "gohan-jr"
    assert not [p for p in (other.directory / "sprites").rglob("*")
                if p.is_file() and "guard" in p.parts]


def test_unknown_tables_and_source_survive_import_and_a_later_export(maker, tmp_path, rom):
    """Pins extensibility: [source] and unknown tables and keys are written back as read."""
    _picture, sidecar = _exported(maker, tmp_path)
    extra = {"later_key": "kept for later", "source": {"scale": 2, "keys": ["#FF00FF"]},
             "frames_of_tomorrow": {"thing": "x", "deep": {"n": 3}}}
    _edit(sidecar, **extra)
    fresh = ch.CharacterMaker(tmp_path / "fresh", rom)
    fresh.import_template(sidecar)
    assert _content(fresh) == _content(maker)
    out = tmp_path / "again"
    out.mkdir()
    again = load_toml(fresh.export_sheet(out)[1].read_text(encoding="utf-8"))
    assert {key: again[key] for key in extra} == extra
    fresh.undo()
    assert fresh.character is None


def test_extra_data_too_large_to_keep_is_refused(maker, tmp_path, rom):
    """Pins the bound on preserved extra data."""
    _picture, sidecar = _exported(maker, tmp_path)
    _edit(sidecar, later={"blob": "x" * (ch.MOST_EXTRAS + 1)})
    with pytest.raises(CreatorError, match="larger than the creator keeps"):
        ch.CharacterMaker(tmp_path / "fresh", rom).import_template(sidecar)


@pytest.mark.parametrize("text", [
    "a = " + "[" * 200000 + "]" * 200000 + "\n",
    "a = " + "{b = " * 5000 + "1" + "}" * 5000 + "\n"], ids=["arrays", "inline-tables"])
def test_a_deeply_nested_sidecar_is_refused_in_words(maker, tmp_path, rom, text):
    """B1: nesting deep enough to exhaust recursion is a plain refusal, not RecursionError."""
    sidecar = tmp_path / "deep.sprite.toml"
    sidecar.write_text(text, encoding="utf-8")
    with pytest.raises(CreatorError, match="not a sheet description"):
        ch.CharacterMaker(tmp_path / "fresh", rom).import_template(sidecar)


def test_a_small_picture_claiming_a_huge_size_is_refused_before_decoding(maker, tmp_path, rom):
    """B2: the header is compared with the declared sheet before any pixel is unpacked."""
    picture, sidecar = _exported(maker, tmp_path)
    side = 6000
    raw = zlib.compress(bytes((side * 4 + 1) * side), 9)
    header = struct.pack(">IIBBBBB", side, side, 8, 6, 0, 0, 0)

    def chunk(kind, body):
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))
    picture.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", raw)
                        + chunk(b"IEND", b""))
    assert picture.stat().st_size < 1_000_000
    fresh = ch.CharacterMaker(tmp_path / "fresh", rom)
    tracemalloc.start()
    started = time.perf_counter()
    try:
        with pytest.raises(CreatorError, match="6000 by 6000 pixels, but the sheet template"):
            fresh.import_template(sidecar)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert time.perf_counter() - started < 5
    assert peak < 8 * 1024 * 1024


def test_a_linked_picture_or_sidecar_is_refused(maker, tmp_path, rom):
    """S1: a picture or sidecar that is a junction or other reparse point is not followed."""
    picture, sidecar = _exported(maker, tmp_path)
    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "linked"
    _winapi.CreateJunction(str(real), str(linked))
    try:
        (real / sidecar.name).write_bytes(sidecar.read_bytes())
        (real / picture.name).write_bytes(picture.read_bytes())
        assert ch._linked(linked)
        _edit(sidecar, picture="linked")
        fresh = ch.CharacterMaker(tmp_path / "fresh", rom)
        with pytest.raises(CreatorError, match="linked is a link"):
            fresh.import_template(sidecar)
        with pytest.raises(CreatorError, match="link to somewhere else"):
            fresh.import_template(linked)
        assert fresh.character is None
    finally:
        os.rmdir(linked)


@pytest.mark.parametrize("changes", [
    {"format": True}, {"animation": {"stand": {"role": "stand", "row": True,
                                               "frames_per_facing": 1,
                                               "facings": ["down", "up", "left", "right"]}}}])
def test_a_boolean_where_a_whole_number_belongs_is_refused(maker, tmp_path, rom, changes):
    """S3: true is not 1 in a sheet template."""
    _picture, sidecar = _exported(maker, tmp_path)
    _edit(sidecar, **changes)
    with pytest.raises(CreatorError, match="does not know|not described"):
        ch.CharacterMaker(tmp_path / "fresh", rom).import_template(sidecar)


def test_an_attribution_with_a_control_character_is_refused_and_tabs_round_trip(
        maker, tmp_path, rom):
    """S4: refused at entry and at import; line breaks and tabs survive export and import."""
    _picture, sidecar = _exported(maker, tmp_path)
    with pytest.raises(CreatorError, match="tabs and line breaks only"):
        maker.set_attribution("a\x01b")
    text = sidecar.read_text(encoding="utf-8").replace(
        'attribution = "Drawn by a test, free to share"', 'attribution = "a\\u0001b"')
    sidecar.write_text(text, encoding="utf-8")
    fresh = ch.CharacterMaker(tmp_path / "fresh", rom)
    with pytest.raises(CreatorError, match="control character"):
        fresh.import_template(sidecar)
    maker.set_attribution("Line one\nLine\ttwo")
    out = tmp_path / "out"
    out.mkdir()
    fresh.import_template(maker.export_sheet(out)[1])
    assert fresh.attribution() == "Line one\nLine\ttwo"


def test_removing_the_character_removes_its_attribution_and_undo_brings_it_back(maker):
    """S5: a new character with the same name does not inherit the old credit."""
    _drawn(maker, ch.STANDS, "16 by 16 pixels")
    credits = maker.directory / "sprites" / "gohan-jr" / "attribution.txt"
    assert credits.is_file()
    maker.remove()
    assert not credits.exists()
    maker.undo()
    assert maker.attribution() == "Drawn by a test, free to share"
    maker.remove()
    maker.create("Gohan Jr", ch.STANDS, "16 by 16 pixels")
    assert maker.attribution() == ""


def test_a_half_replaced_pair_is_refused(maker, tmp_path, rom):
    """N1: a picture that is not the one the sidecar was exported with is refused."""
    picture, sidecar = _exported(maker, tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    maker.paint(0, [(0, 0), (1, 1)], maker.colours()[9])
    newer, _ = maker.export_sheet(other)
    picture.write_bytes(newer.read_bytes())
    with pytest.raises(CreatorError, match="only one of the two files was replaced"):
        ch.CharacterMaker(tmp_path / "fresh", rom).import_template(sidecar)


def test_a_duplicate_palette_colour_round_trips_to_the_lowest_index(maker, tmp_path, rom):
    """Pins determinism: a colour two indices share always reads back as the lower one."""
    _drawn(maker, ch.STANDS, "16 by 16 pixels")
    low, high = maker.colours()[3], maker.colours()[4]
    for target in (maker,):
        palette = list(target._palette)
        palette[high] = palette[low]
        target._palette = tuple(palette)
        target._index = {}
        for index in range(len(palette) - 1, 0, -1):
            target._index[palette[index]] = index
    maker.paint(0, [(0, 0)], high)
    assert maker.picture(0)[2][0] == low
    _picture, sidecar = maker.export_sheet(tmp_path)
    fresh = ch.CharacterMaker(tmp_path / "fresh", rom)
    fresh._palette, fresh._index = maker._palette, maker._index
    fresh.import_template(sidecar)
    assert _content(fresh) == _content(maker)
    assert fresh.picture(0)[2][0] == low


@pytest.mark.timeout(1200)
def test_attribution_and_kept_extras_do_not_change_the_built_game(tmp_path, rom):
    """Pins that attribution.txt and template-extra.toml never reach the ROM."""
    from tools.creator.model import jobs
    from tools.creator.model.project import CreatorProject

    CreatorProject.create(rom, tmp_path / "game", "Game")
    maker = _drawn(ch.CharacterMaker(tmp_path / "game", rom), ch.STANDS, "16 by 16 pixels")
    (maker.directory / "sprites" / "gohan-jr" / ch.EXTRAS).write_text(
        '[source]\nscale = 2\n', encoding="utf-8")
    first = jobs._run({"action": "build", "project": str(maker.directory), "rom": str(rom),
                       "output": str(tmp_path / "with.gba")})
    maker.set_attribution("")
    (maker.directory / "sprites" / "gohan-jr" / ch.EXTRAS).unlink()
    second = jobs._run({"action": "build", "project": str(maker.directory), "rom": str(rom),
                        "output": str(tmp_path / "without.gba")})
    assert first["ok"] and second["ok"], (first, second)
    assert first["sha256"] == second["sha256"]
