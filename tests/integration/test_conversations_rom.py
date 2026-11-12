"""ROM-gated proof that authored dialogue reaches the built image and nothing else moves."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.rom_support import canonical_rom_path, mutable_rom_copy
from tools.creator.model import jobs
from tools.creator.model.dialogue import DialogueStudio
from tools.creator.model.maps import MapStudio
from tools.creator.model.project import CreatorError, CreatorProject
from tools.webfoot import conversations as cv

pytestmark = pytest.mark.skipif(
    canonical_rom_path() is None, reason="the canonical Buu's Fury ROM is not present"
)

SPEECH_RECORDS = 2244
SPEECH_HANDLES = 2181
ROM_BYTES = 1 << 24


def _studio(tmp_path):
    rom = mutable_rom_copy(tmp_path)
    project = CreatorProject.create(rom, tmp_path / "Game", "Game")
    return rom, project, DialogueStudio(project.directory, rom)


def _build(rom, project) -> bytes:
    result = jobs.run_blocking("build", project.directory, rom, project.output)
    assert result["ok"], result
    return project.output.read_bytes()


def test_the_reader_finds_every_spoken_line_and_none_share_bytes(tmp_path):
    _rom, _project, studio = _studio(tmp_path)
    game = cv.read_conversations(studio.image, studio.profile)
    spoken = [entry for talk in game.values() for entry in talk.entries if entry.kind == cv.SPEECH]
    assert len(spoken) == SPEECH_RECORDS
    assert len({entry.handle for entry in spoken}) == SPEECH_HANDLES
    assert not any(cv.shared_text(game).values())
    locked = [page for row in studio.rows() if not row.mine for page in studio.pages(row.key)
              if not page.editable]
    assert locked and all(page.note for page in locked)


def test_edits_across_containers_and_a_new_conversation_build_and_leave_the_rest_alone(tmp_path):
    rom, project, studio = _studio(tmp_path)
    source = rom.read_bytes()
    game = cv.read_conversations(studio.image, studio.profile)
    chosen: dict[int, tuple[str, int]] = {}
    for event, talk in sorted(game.items()):
        for index, page in enumerate(studio.pages(f"event:{event:04d}")):
            selector = int(page.line.split(":")[0]) if page.line else -1
            if page.editable and selector >= 0 and selector not in chosen:
                chosen[selector] = (f"event:{event:04d}", index)
    assert len(chosen) >= 3
    keys = {studio.pages(key)[index].line for key, index in chosen.values()}
    carried = sum(1 for talk in game.values() for entry in talk.entries
                  if entry.kind == cv.SPEECH and cv.line_key(entry.handle) in keys)
    for key, index in chosen.values():
        studio.set_text(key, index, studio.pages(key)[index].original + " Edited.")

    first = studio.new_talk("First meeting")
    studio.set_text(first, 0, "Hello.\nA made conversation.{page}Second window.")
    studio.set_portrait(first, 0, 87)
    studio.add_page(first)
    studio.set_text(first, 1, "#At the bottom.")
    later = studio.new_talk("Later")
    studio.set_text(later, 0, "We have met.")
    studio.set_rule(first, "met", "met", later, 0)
    assert studio.document().flags == {"met": cv.free_flags(studio.profile)[0]}

    maps = MapStudio(project.directory, rom)
    where, person = next((row.key, item) for row in maps.maps() for item in maps.characters(row.key)
                         if item.says and item.key.startswith("game:"))
    maps.set_says(where, person.key, first)
    assert next(item.says for item in maps.characters(where) if item.key == person.key) == first
    assert studio.users(first)

    with pytest.raises(CreatorError):
        studio.delete(first)
    spare = studio.new_talk("Spare")
    with pytest.raises(CreatorError):
        [studio.undo() for _ in range(40)]
    assert first in studio.document().talks
    while studio.can_redo:
        studio.redo()
    studio.delete(spare)
    assert studio.new_talk("Other") != spare
    studio.set_text(first, 0, "{08:02}Hello.{08:07}\nA made conversation.{page}Second window.")

    built = _build(rom, project)
    assert rom.read_bytes() == source and len(built) == ROM_BYTES
    assert cv.retail_containers(built, studio.profile) == cv.retail_containers(source, studio.profile)
    changed = [at for at in range(len(source)) if source[at] != built[at]]
    assert 0 < len(changed) <= 4 * (carried + 2)
    after = cv.read_conversations(built, studio.profile)
    for key, index in chosen.values():
        event = int(key.split(":")[1])
        texts = [entry.text for entry in after[event].entries if entry.kind == cv.SPEECH]
        assert any(text is not None and cv.decode(text).endswith(" Edited.") for text in texts)
    untouched = sum(
        1 for event, talk in game.items() for before, now in zip(talk.entries, after[event].entries)
        if before.kind == cv.SPEECH and before.text == now.text)
    assert untouched == SPEECH_RECORDS - carried

    assert _build(rom, project) == built
    reopened = DialogueStudio(project.directory, rom)
    assert [page.text for page in reopened.pages(first)] == [
        "{08:02}Hello.{08:07}\nA made conversation.{page}Second window.", "#At the bottom."]

    studio.set_rule(first, "met", "met", later, 0)
    studio.set_rule(first, "", "", "", 1)
    studio.move_page(first, 1, 0)
    assert studio.rule(first)[3] == 0
    studio.undo()
    assert studio.rule(first)[3] == 1 and studio.can_redo


def test_unsafe_dialogue_is_refused_before_a_rom_is_made(tmp_path):
    rom, project, studio = _studio(tmp_path)
    key = studio.new_talk("Talk")
    for text in ("bad {zz} token", "", "x" * 5000, "{08:FFFF}ink", "{08:0B}ink", "{08:D800}ink"):
        with pytest.raises(CreatorError):
            studio.set_text(key, 0, text)
    with pytest.raises(CreatorError):
        studio.set_rule(key, "Not A Name")
    with pytest.raises(CreatorError):
        studio.set_rule(key, "", "", key)
    with pytest.raises(CreatorError):
        studio.delete("event:0001")

    document = studio.document()
    for broken in (
            replace(document, talks={key: replace(document.talks[key], portraits=(250,))}),
            replace(document, talks={key: replace(document.talks[key], sets="gone")}),
            replace(document, talks={key: replace(document.talks[key], when="met", then="talk-99")},
                    flags={"met": 157}),
            replace(document, talks={key: replace(document.talks[key], sets="taken")},
                    flags={"taken": 3}),
            replace(document, lines={"0:0x0000:2": cv.Line("Words.", "Not what the game says.")}),
    ):
        cv.write_document(project.directory, broken)
        result = jobs.run_blocking("build", project.directory, rom, project.output)
        assert not result["ok"], broken
        assert not project.output.exists()

    cv.write_document(project.directory, document)
    maps = MapStudio(project.directory, rom)
    where, person = next((row.key, item) for row in maps.maps() for item in maps.characters(row.key)
                         if item.says and item.key.startswith("game:"))
    maps.set_says(where, person.key, "talk-99")
    result = jobs.run_blocking("validate", project.directory, rom, project.output)
    assert not result["ok"]


def test_capacity_is_reported_and_an_overfull_project_is_refused(tmp_path):
    rom, project, studio = _studio(tmp_path)
    empty = cv.capacity_of(studio.document(), studio.profile)
    assert (empty.containers_used, empty.containers_total) == (0, 57)
    key = studio.new_talk("Talk")
    used = cv.capacity_of(studio.document(), studio.profile)
    assert used.containers_used == 1 and 0 < used.bytes_used < used.bytes_total
    assert "57" in studio.capacity()
    document = studio.document()
    pages = tuple(f"Page {number:05d} " + "word " * 180 for number in range(cv.MAX_ENTRIES - 3))
    talks = {f"talk-{number}": cv.Talk(f"Talk {number}", tuple(f"{number} {page}" for page in pages),
                                        (87,) * len(pages)) for number in range(1, 9)}
    cv.write_document(project.directory, replace(document, talks=talks))
    assert key in talks
    over = cv.capacity_of(cv.read_document(project.directory), studio.profile)
    assert over.containers_used > over.containers_total
    result = jobs.run_blocking("validate", project.directory, rom, project.output)
    assert not result["ok"]
