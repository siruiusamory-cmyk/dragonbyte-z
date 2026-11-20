"""The creator's one new character: make, draw, import, check, undo, place."""

from __future__ import annotations

import pytest

from tests.helpers import write_truecolour_png
from tests.rom_support import canonical_rom_path, mutable_rom_copy
from tools.creator.model import characters as ch
from tools.creator.model.library import _png, read_names
from tools.creator.model.maps import MapStudio
from tools.creator.model.project import CreatorError
from tools.webfoot.formats import rgb_png
from tools.webfoot.project.model import SPRITES_FILE

pytestmark = pytest.mark.skipif(
    canonical_rom_path() is None, reason="the canonical Buu's Fury ROM is not present"
)

SIZE = "32 by 32 pixels"


@pytest.fixture(scope="module")
def rom(tmp_path_factory):
    return mutable_rom_copy(tmp_path_factory.mktemp("rom"))


@pytest.fixture()
def maker(tmp_path, rom):
    return ch.CharacterMaker(tmp_path / "game", rom)


def _fill(maker, slot, facing, frame, index, x0=0):
    picture = next(f.picture for f in maker.frames()
                   if (f.animation, f.direction, f.frame) == (slot, facing, frame))
    maker.paint(picture, [(x, y) for x in range(x0, x0 + 4) for y in range(8)], index)


def _drawn_walker(maker):
    maker.create("Gohan Jr", ch.WALKS, SIZE)
    for facing in range(4):
        _fill(maker, 0, facing, 0, 5)
        _fill(maker, 1, facing, 0, 5, 0)
        _fill(maker, 1, facing, 1, 5, 8)
    return maker


def test_a_walker_is_made_blank_with_both_animations_and_no_address_or_donor(maker):
    """Pins the creator document: no ROM address, no donor id, no embedded actor."""
    character = maker.create("Gohan Jr", ch.WALKS, SIZE)
    assert (character.name, character.behaviour, character.frames) == ("gohan-jr", "Walks", (1, 2))
    text = (maker.directory / SPRITES_FILE).read_text(encoding="utf-8")
    assert "donor" not in text and "actor" not in text and "_raw" not in text
    assert "0x" not in text.lower() and "134" not in text
    assert read_names(maker.directory)[f"sprite:{maker.sprite:04d}"] == "Gohan Jr"
    labels = [frame.label for frame in maker.frames()]
    assert labels[0] == "Stand pose, facing down, frame 1"
    assert labels[4] == "Walk animation, facing down, frame 1"
    assert labels[-1] == "Walk animation, facing right, frame 2"
    assert not any("slot" in label or "direction" in label for label in labels)


def test_a_second_new_character_is_refused_in_plain_words(maker):
    maker.create("Gohan Jr", ch.WALKS, SIZE)
    with pytest.raises(CreatorError, match="A project can have one new character"):
        maker.create("Other", ch.STANDS, SIZE)


def test_only_square_sizes_a_game_character_draws_are_offered(maker):
    assert maker.sizes(ch.WALKS) == ["8 by 8 pixels", "16 by 16 pixels", SIZE, "64 by 64 pixels"]
    assert set(maker.sizes(ch.WALKS)) <= set(maker.sizes(ch.STANDS))
    with pytest.raises(CreatorError, match="No character"):
        maker.create("Big", ch.WALKS, "48 by 48 pixels")


def test_a_blank_character_lists_every_missing_pose_and_frame(maker):
    """Pins the refusal wording: Stand pose, Walk animation and the facing, per facing."""
    maker.create("Gohan Jr", ch.WALKS, SIZE)
    problems = maker.problems()
    for facing in ch.FACINGS:
        assert f"The Stand pose facing {facing} is empty. Draw it." in problems
        assert f"The Walk animation facing {facing} needs at least two different frames." in problems


def test_two_identical_walk_frames_are_refused(maker):
    maker.create("Gohan Jr", ch.WALKS, SIZE)
    for facing in range(4):
        _fill(maker, 0, facing, 0, 5)
        _fill(maker, 1, facing, 0, 5)
        _fill(maker, 1, facing, 1, 5)
    assert maker.problems() == [
        f"The Walk animation facing {facing} needs at least two different frames."
        for facing in ch.FACINGS]


def test_no_walk_frame_is_ever_made_from_the_stand_pose(maker):
    """Pins no-fallback: drawing only the Stand pose leaves the Walk animation empty."""
    maker.create("Gohan Jr", ch.WALKS, SIZE)
    for facing in range(4):
        _fill(maker, 0, facing, 0, 5)
    blank = bytes(32 * 32)
    for frame in maker.frames():
        if frame.animation == 1:
            assert maker.picture(frame.picture)[2] == blank
    assert len(maker.problems()) == 4


def test_a_drawn_walker_and_a_drawn_stander_have_no_problems(maker, tmp_path, rom):
    _drawn_walker(maker)
    assert maker.problems() == []
    stander = ch.CharacterMaker(tmp_path / "other", rom)
    stander.create("Guard", ch.STANDS, SIZE)
    assert stander.problems()[0] == "The Stand pose facing down is empty. Draw it."
    for facing in range(4):
        _fill(stander, 0, facing, 0, 7)
    assert stander.problems() == []
    with pytest.raises(CreatorError, match="has no Walk animation"):
        stander.set_frames(1, 2)


def test_undo_redo_and_reopening_keep_the_character(maker, rom):
    maker.create("Gohan Jr", ch.WALKS, SIZE)
    _fill(maker, 0, 0, 0, 5)
    drawn = maker.picture(0)[2]
    maker.undo()
    assert not any(maker.picture(0)[2])
    maker.redo()
    assert maker.picture(0)[2] == drawn
    reopened = ch.CharacterMaker(maker.directory, rom)
    assert reopened.character == maker.character
    assert reopened.picture(0)[2] == drawn
    maker.undo()
    maker.undo()
    assert maker.character is None and not (maker.directory / SPRITES_FILE).exists()
    maker.redo()
    assert maker.character.name == "gohan-jr"


def test_one_stroke_is_one_undo_step(maker):
    maker.create("Gohan Jr", ch.STANDS, SIZE)
    maker.paint(0, [(0, 0)], 5, stroke="s1")
    maker.paint(0, [(1, 0)], 5, stroke="s1")
    maker.undo()
    assert not any(maker.picture(0)[2])


def _sheet(maker, frames, colour_of):
    side = 32
    width = side * 4 * frames
    rgba = bytearray(width * side * 4)
    for cell in range(4 * frames):
        for y in range(side):
            for x in range(side):
                rgb = colour_of(cell, x, y)
                if rgb is not None:
                    at = 4 * (y * width + cell * side + x)
                    rgba[at:at + 4] = bytes(rgb) + b"\xff"
    return _png(width, side, bytes(rgba))


def test_an_imported_sheet_keeps_every_supported_colour_exactly(maker, tmp_path):
    """Pins exact-colour import: each pixel reads back as the same RGB it was drawn in."""
    maker.create("Gohan Jr", ch.WALKS, SIZE)
    palette = maker.palette()
    colours = [palette[index] for index in maker.colours()[:40]]
    path = tmp_path / "walk.png"
    path.write_bytes(_sheet(maker, 4, lambda cell, x, y: colours[(cell + x) % len(colours)]
                            if y < 16 else None))
    maker.import_sheet(1, path)
    assert maker.character.frames == (1, 4)
    for frame in maker.frames():
        if frame.animation != 1:
            continue
        cell = frame.direction * 4 + frame.frame
        _w, _h, pixels = maker.picture(frame.picture)
        for x in range(32):
            assert palette[pixels[x]] == colours[(cell + x) % len(colours)]
        assert not any(pixels[16 * 32:])
    written, width, height, _alpha = rgb_png.decode_truecolour(
        (maker.directory / "sprites/gohan-jr/walk.png").read_bytes())
    assert (width, height) == (512, 32)
    assert tuple(written[0:3]) == colours[0]


def test_an_unsupported_colour_is_listed_and_nothing_is_written(maker, tmp_path):
    """Pins the diagnostic and the no-partial-write rule for a colour the game lacks."""
    maker.create("Gohan Jr", ch.WALKS, SIZE)
    palette = set(maker.palette())
    odd = next((r, 1, 2) for r in range(256) if (r, 1, 2) not in palette)
    good = maker.palette()[maker.colours()[0]]
    path = tmp_path / "walk.png"
    path.write_bytes(_sheet(maker, 2, lambda cell, x, y: odd if cell == 5 and x == 3 else good))
    before = (maker.directory / "sprites/gohan-jr/walk.png").read_bytes()
    with pytest.raises(CreatorError) as caught:
        maker.import_sheet(1, path)
    message = str(caught.value)
    assert message.startswith("Nothing was imported.")
    assert f"#{odd[0]:02X}0102 (facing left, frame 2)" in message
    assert (maker.directory / "sprites/gohan-jr/walk.png").read_bytes() == before
    assert maker.character.frames == (1, 2)


def test_a_sheet_of_the_wrong_size_is_refused_plainly(maker, tmp_path):
    maker.create("Gohan Jr", ch.WALKS, SIZE)
    path = tmp_path / "walk.png"
    path.write_bytes(_png(100, 32, bytes(100 * 32 * 4)))
    with pytest.raises(CreatorError, match="facing down, then up, then left, then right"):
        maker.import_sheet(1, path)
    path.write_bytes(_png(128, 32, bytes(128 * 32 * 4)))
    with pytest.raises(CreatorError, match="256 pixels wide for 2 frame"):
        maker.import_sheet(1, path)


@pytest.mark.parametrize("name", ["../evil", "a/b", "2nd", ""])
def test_a_name_that_could_leave_the_project_is_refused(maker, name):
    """Pins containment: the only files written are under sprites/<name>/."""
    with pytest.raises(CreatorError, match="A name starts with a letter"):
        maker.create(name, ch.STANDS, SIZE)
    assert not (maker.directory / SPRITES_FILE).exists()
    assert not (maker.directory.parent / "evil").exists()


def test_maps_offers_the_new_character_only_for_its_own_kind(tmp_path, rom):
    """Pins placement: a walker is a character that wanders, a stander a character."""
    from tools.creator.model.project import CreatorProject

    CreatorProject.create(rom, tmp_path / "game", "Game")
    maker = _drawn_walker(ch.CharacterMaker(tmp_path / "game", rom))
    studio = MapStudio(maker.directory, rom)
    choice = studio.character_choices()[0]
    assert choice.new and choice.sprite == maker.sprite
    assert choice.title == "character that wanders, your new character gohan-jr"
    key = "map:0033"
    added = studio.add_character(key, choice.donor_map, choice.donor_slot, 40, 184, choice.sprite)
    row = next(item for item in studio.characters(key) if item.key == added)
    assert (row.sprite, row.kind) == (maker.sprite, "character that wanders")
    standing = next(c for c in studio.character_choices()
                    if not c.new and c.title.startswith("character,")
                    and maker.fits(c.donor_map, c.donor_slot) == ch.STANDS)
    other = studio.add_character(key, standing.donor_map, standing.donor_slot, 120, 200)
    with pytest.raises(CreatorError, match="gohan-jr walks, so on .* it can only be a character that wanders"):
        studio.set_look(key, other, maker.sprite)
    studio.set_look(key, added, None)
    studio.set_look(key, added, maker.sprite)
    objects = (maker.directory / "maps" / "objects.toml").read_text(encoding="utf-8")
    assert f"sprite = {maker.sprite + 10}" in objects
    assert ch.CharacterMaker(maker.directory, rom).problems() == []


def test_undoing_a_stroke_keeps_a_library_rename_made_after_it(maker):
    """B1: a later rename of another sprite survives undo and redo of a character stroke."""
    from tools.creator.model.library import set_name

    maker.create("Gohan Jr", ch.WALKS, SIZE)
    _fill(maker, 0, 0, 0, 5)
    set_name(maker.directory, "sprite:0010", "My renamed sprite")
    maker.undo()
    assert read_names(maker.directory)["sprite:0010"] == "My renamed sprite"
    maker.redo()
    assert read_names(maker.directory)["sprite:0010"] == "My renamed sprite"
    assert read_names(maker.directory)[f"sprite:{maker.sprite:04d}"] == "Gohan Jr"


def test_undoing_a_stroke_keeps_a_rename_of_the_character_itself(maker):
    """A stroke does not change the name, so undoing it keeps a rename made after it.

    Undoing the creation itself still removes the character's name.
    """
    from tools.creator.model.library import set_name

    maker.create("Gohan Jr", ch.WALKS, SIZE)
    _fill(maker, 0, 0, 0, 5)
    key = f"sprite:{maker.sprite:04d}"
    set_name(maker.directory, key, "Renamed Gohan")
    maker.undo()
    assert read_names(maker.directory)[key] == "Renamed Gohan"
    maker.undo()
    assert key not in read_names(maker.directory)
    maker.redo()
    assert read_names(maker.directory)[key] == "Gohan Jr"


@pytest.mark.parametrize("name", ["con", "NUL", "Aux", "prn", "com1", "LPT9", "nul.txt", "con.png"])
def test_a_windows_device_name_is_refused_in_plain_words(maker, name):
    with pytest.raises(CreatorError, match="Windows keeps for itself"):
        maker.create(name, ch.STANDS, SIZE)
    assert not (maker.directory / "sprites").exists()


@pytest.mark.parametrize("name", ["Gohan.", "Gohan ", "Gohan. "])
def test_a_name_ending_in_a_dot_or_a_space_is_refused(maker, name):
    with pytest.raises(CreatorError, match="A name starts with a letter"):
        maker.create(name, ch.STANDS, SIZE)


def test_a_failed_write_is_worded_plainly_and_leaves_no_empty_folder(maker, monkeypatch):
    def refuse(path, data):
        raise FileNotFoundError(2, "No such file or directory", str(path))

    monkeypatch.setattr(ch, "_write", refuse)
    with pytest.raises(CreatorError) as raised:
        maker.create("Gohan Jr", ch.STANDS, SIZE)
    assert str(raised.value) == ("The new character could not be saved: No such file or "
                                 "directory. Nothing was changed.")
    assert not (maker.directory / "sprites").exists()


def test_a_sprite_document_the_sdk_wrote_with_free_palette_entries_is_not_a_creator_problem(
        maker, rom):
    """S3: colours the palette lacks are the SDK's free entries to fill, not a creator problem."""
    unused = next(colour for colour in ((r, 8, 8) for r in range(0, 256, 8))
                  if colour not in maker._index and colour != ch.HOLE)
    sheet = maker.directory / "sprites" / "cui" / "stand.png"
    sheet.parent.mkdir(parents=True)
    rgb = bytes(unused) * (32 * 4 * 32)
    write_truecolour_png(sheet, rgb, 32 * 4, 32)
    (maker.directory / SPRITES_FILE).write_text(
        "[sprite.cui]\nsprite_id = 307\ndonor_sprite_id = 10\nfree_palette_entries = [200]\n"
        '\n[sprite.cui.animation.stand]\nsheet = "sprites/cui/stand.png"\nframes = 1\n',
        encoding="utf-8")
    reread = ch.CharacterMaker(maker.directory, rom)
    assert reread.problems() == []
    assert reread.character is None
    with pytest.raises(CreatorError, match="already has a sprite"):
        reread.create("Gohan Jr", ch.STANDS, SIZE)

def _huge_header_sheet(path):
    import struct
    import zlib

    write_truecolour_png(path, bytes(3 * 4), 4, 1)
    data = bytearray(path.read_bytes())
    data[16:24] = struct.pack(">II", 0x7FFFFFFF, 0x7FFFFFFF)
    data[29:33] = struct.pack(">I", zlib.crc32(bytes(data[12:29])) & 0xFFFFFFFF)
    path.write_bytes(bytes(data))


def test_importing_or_reopening_a_sheet_with_a_huge_header_is_refused_in_words(maker, rom):
    character = maker.create("Gohan Jr", ch.STANDS, SIZE)
    bad = maker.directory / "huge.png"
    _huge_header_sheet(bad)
    with pytest.raises(CreatorError, match="too large"):
        maker.import_sheet(0, bad)
    _huge_header_sheet(maker.directory / "sprites" / character.name / "stand.png")
    with pytest.raises(CreatorError, match="too large"):
        ch.CharacterMaker(maker.directory, rom)


def test_undo_with_a_damaged_names_file_is_refused_and_changes_nothing(maker, rom):
    maker.create("Gohan Jr", ch.STANDS, SIZE)
    (maker.directory / "library" / "names.json").write_text("[1]", encoding="utf-8")
    before = maker.character
    with pytest.raises(CreatorError, match="names.json is damaged"):
        maker.undo()
    assert maker.character == before and maker.can_undo and not maker.can_redo
    assert (maker.directory / SPRITES_FILE).is_file()
    assert ch.CharacterMaker(maker.directory, rom).character == before
