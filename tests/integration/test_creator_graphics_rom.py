"""ROM-gated proofs of painting and recolouring retail sprite 38 in the creator."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tests.rom_support import CANONICAL_ROM_SHA256, canonical_rom_path, mutable_rom_copy
from tools.creator.model import jobs
from tools.creator.model.graphics import NEW_COLOURS, OTHER_USES, SpriteEditor
from tools.creator.model.project import CreatorError, CreatorProject
from tools.webfoot.catalog import load_catalog
from tools.webfoot.formats import sprite_graphics as sg
from tools.webfoot.graphics import load_actor_sprites
from tools.webfoot.rom import identify_rom

pytestmark = pytest.mark.skipif(
    canonical_rom_path() is None, reason="the canonical Buu's Fury ROM is not present"
)

BROLY = 38


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture
def rom(tmp_path) -> Path:
    return mutable_rom_copy(tmp_path)


@pytest.fixture
def project(tmp_path, rom) -> CreatorProject:
    return CreatorProject.create(rom, tmp_path / "My Game", "My Game")


def _snapshot(directory: Path) -> dict[str, bytes]:
    graphics = directory / "graphics"
    return {path.relative_to(directory).as_posix(): path.read_bytes()
            for path in sorted(graphics.rglob("*")) if path.is_file()}


def test_a_new_project_has_no_graphics_until_a_sprite_is_opened(project):
    assert not (project.directory / "graphics").exists()
    editor = SpriteEditor(project, BROLY)
    assets = sorted(p.name for p in (project.directory / "graphics" / "assets").iterdir())
    assert assets == [f"graphic_{n:04d}.png" for n in range(776, 782)]
    frames = editor.frames()
    assert len(frames) == 24
    assert frames[0].label == "Animation 1, frame 1, direction 1 - picture 776"
    assert {frame.picture for frame in frames} == set(range(776, 782))
    width, height, pixels = editor.picture(776)
    assert (width, height) == (32, 64) and len(pixels) == 32 * 64


def test_paint_and_recolour_are_undone_and_redone_to_the_exact_bytes(project):
    editor = SpriteEditor(project, BROLY)
    original = _snapshot(project.directory)
    _w, _h, pixels = editor.picture(776)
    x = next(i for i, value in enumerate(pixels) if value not in (0, 1))
    point = (x % 32, x // 32)
    colour = editor.colours()[0]

    editor.paint(776, [point], 1)
    editor.recolour(colour, (255, 0, 255))
    assert editor.picture(776)[2][x] == 1 and editor.palette()[colour] == (255, 0, 255)
    project.save()
    edited = _snapshot(project.directory)
    assert edited != original and "graphics/overrides.toml" in edited

    project.undo()
    project.undo()
    assert editor.picture(776)[2] == pixels and project.dirty
    project.save()
    assert _snapshot(project.directory) == original

    project.redo()
    project.redo()
    project.save()
    assert _snapshot(project.directory) == edited


def test_a_stroke_is_one_undo_step(project):
    editor = SpriteEditor(project, BROLY)
    before = editor.picture(777)[2]
    editor.paint(777, [(10, 10)], 3, stroke="s1")
    editor.paint(777, [(11, 10)], 3, stroke="s1")
    project.undo()
    assert editor.picture(777)[2] == before and not project.can_undo


def test_the_shared_use_list_names_sprites_and_portraits_and_other_uses_are_unknown(project):
    editor = SpriteEditor(project, BROLY)
    uses = [editor.use(index) for index in editor.colours()]
    assert any(use.sprites for use in uses) and any(use.portraits for use in uses)
    assert all(BROLY not in use.sprites for use in uses)
    assert all(use.message.endswith(OTHER_USES) for use in uses)
    shared = next(use for use in uses if use.sprites)
    assert f"{shared.sprites[0]:04d}" in shared.message
    assert "not known" in OTHER_USES


def test_new_colours_cannot_be_made(project):
    editor = SpriteEditor(project, BROLY)
    unused = next(i for i in range(1, 256) if i not in editor.colours())
    with pytest.raises(CreatorError, match="New colours are not offered"):
        editor.recolour(unused, (1, 2, 3))
    assert NEW_COLOURS and not hasattr(editor, "allocate")
    assert not project.dirty


def test_no_project_file_holds_a_rom_offset(project, rom):
    editor = SpriteEditor(project, BROLY)
    editor.paint(776, [(16, 30)], 2)
    editor.recolour(editor.colours()[0], (10, 20, 30))
    project.save()
    sprites = load_actor_sprites(rom.read_bytes(), identify_rom(rom, load_catalog(None)))
    offsets = set()
    for number in range(776, 782):
        graphic = next(g for g in sprites.graphics() if g.identity.index == number)
        offsets.add(graphic.file_offset)
        offsets.update(c.piece_offset for c in graphic.consumers)
    spellings = set()
    for offset in offsets:
        spellings |= {f"0x{offset:x}", f"0x{offset:06X}", f"0x{offset + 0x08000000:08X}",
                      f"{offset}", f"{offset + 0x08000000}"}
    for path in project.directory.rglob("*"):
        if path.is_file() and path.suffix in (".toml", ".json"):
            text = path.read_text(encoding="utf-8").lower()
            assert not [s for s in spellings if s.lower() in text], path


def test_an_edited_sprite_builds_to_a_separate_file_with_the_pixel(project, rom):
    canonical = canonical_rom_path()
    before = _sha256(canonical)
    editor = SpriteEditor(project, BROLY)
    pixels = editor.picture(776)[2]
    x = next(i for i, value in enumerate(pixels) if value not in (0, 5))
    editor.paint(776, [(x % 32, x // 32)], 5)
    project.save()

    result = jobs.run_blocking("build", project.directory, rom, project.output)

    assert result["ok"], result
    assert result["grown"] is True
    built = project.output.read_bytes()
    sprites = load_actor_sprites(rom.read_bytes(), identify_rom(rom, load_catalog(None)))
    graphic = next(g for g in sprites.graphics() if g.identity.index == 776)
    piece = graphic.consumers[0].piece_offset + sg.PIECE_GRAPHICS
    address = int.from_bytes(built[piece:piece + 4], "little")
    back = sg.decode_graphic(built, address - 0x08000000, 32, 64, colour_256=True)
    assert back.pixels[x] == 5 and back.pixels == editor.picture(776)[2]
    assert _sha256(canonical) == before == CANONICAL_ROM_SHA256
    assert _sha256(rom) == CANONICAL_ROM_SHA256


def test_a_project_without_graphics_builds_the_same_image_as_before(project, rom):
    result = jobs.run_blocking("build", project.directory, rom, project.output)
    assert result["ok"] and result["grown"] is False
    assert not (project.directory / "graphics").exists()
    assert result["sha256"] == hashlib.sha256(rom.read_bytes()).hexdigest()
