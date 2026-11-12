"""ROM-gated proof that an authored event is built into the structure the game reads."""

from __future__ import annotations

import json
import struct

import pytest

from tests.rom_support import canonical_rom_path, mutable_rom_copy
from tools.creator.model import jobs
from tools.creator.model.project import CreatorProject
from tools.dragonbyte.session import Session
from tools.webfoot import events as ev
from tools.webfoot import map_objects as mo
from tools.webfoot import story_flags as sf

pytestmark = pytest.mark.skipif(
    canonical_rom_path() is None, reason="the canonical Buu's Fury ROM is not present"
)

BASE = 0x08000000
STEPS = (("say", 0, "Hello."), ("if", "flag", "quest"), ("say", 0, "Again."), ("else",),
         ("say", 0, "First."), ("set", "quest"), ("end_if",))


def _project(tmp_path):
    rom = mutable_rom_copy(tmp_path)
    project = CreatorProject.create(rom, tmp_path / "Game", "Game")
    session = Session()
    session.open_rom(rom)
    return rom, project, session.profile


def _build(rom, project):
    return jobs.run_blocking("build", project.directory, rom, project.output)


def _npc(image, profile):
    return next((index, item) for index, objects in sorted(mo.census(image, profile).items())
                for item in objects if item.family == mo.NPC)


def test_a_talk_event_is_built_as_a_conversation_a_character_names(tmp_path):
    rom, project, profile = _project(tmp_path)
    source = rom.read_bytes()
    flags = sf.assign(sf.Flags(), "quest", profile)
    sf.write_flags(project.directory, flags)
    ev.write_document(project.directory, {"evt-1": ev.Event("Greeting", steps=STEPS)})
    index, person = _npc(source, profile)
    mo.write_document(project.directory, {
        mo.canonical_identity(index): mo.MapEdits(says={person.slot: "evt-1"})})

    result = _build(rom, project)
    assert result["ok"], result
    built = project.output.read_bytes()
    array = struct.unpack_from("<I", built, person.record_offset + mo.CONVERSATION_OFFSET)[0]
    assert array - BASE >= len(source)
    records = []
    at = array - BASE
    while struct.unpack_from("<I", built, at)[0] >> 16:
        records.append(struct.unpack_from("<I", built, at)[0] - BASE)
        at += 4
    kinds = [built[record + 2] for record in records]
    assert kinds == [ev.SPEECH, ev.SCRIPT, ev.SPEECH, ev.SCRIPT, ev.SPEECH, ev.SCRIPT]
    follows = [struct.unpack_from("<H", built, record)[0] for record in records]
    assert follows == [1, 2, 3, 6, 5, 6]
    number = flags.names["quest"]
    assert built[records[1] + 3:records[1] + 7] == bytes((0, number, 2, 27))
    assert built[records[5] + 3:records[5] + 8] == bytes((0, number, 2, 29, 17))

    table = json.loads(ev.trace_path(project.output).read_text(encoding="utf-8"))
    assert table["flags"] == {"quest": number}
    assert [step for step, _address, _size in table["events"]["evt-1"]["steps"]] == [0, 1, 2, 3, 4, 5]
    assert [address - BASE for _step, address, _size in table["events"]["evt-1"]["steps"]] == records

    again = tmp_path / "again.gba"
    assert jobs.run_blocking("build", project.directory, rom, again)["ok"]
    assert again.read_bytes() == built
    assert rom.read_bytes() == source


def test_map_events_regions_and_appears_rules_are_built_into_the_map(tmp_path):
    from tools.creator.model.events import EventStudio
    from tools.creator.model.maps import MapStudio

    rom, project, profile = _project(tmp_path)
    source = rom.read_bytes()
    maps, events = MapStudio(project.directory, rom), EventStudio(project.directory, rom)
    road, town = "map:0033", "map:0102"
    events.add_flag("open")
    donor = maps.character_choices()[0]
    guide = maps.add_character(town, donor.donor_map, donor.donor_slot, 192, 560)
    maps.set_appears(town, guide, "open")
    gate = events.new_event("Gate", ev.ENTER, town)
    events._set_steps(gate, (("if", "flag", "open"), ("open", 88, 568, 120, 608), ("end_if",)))
    events.new_event("First", ev.ENTER, road)
    events.new_event("Wire", ev.REGION, road, (232, 144, 244, 184), "walk_in")

    result = _build(rom, project)
    assert result["ok"], result
    built = project.output.read_bytes()
    number = events.registry().names["open"]

    def row(image, index, at, form="<I"):
        return struct.unpack_from(form, image, 0x8E2E0 + 0x38 * index + at)[0]

    assert row(source, 33, 0x30) == 0 and row(built, 33, 0x30) - BASE >= len(source)
    assert row(built, 33, 0x03, "<B") == row(source, 33, 0x03, "<B") + 1
    retail, chained = row(source, 102, 0x30) - BASE, row(built, 102, 0x30) - BASE
    spec = ev.OPCODE_SETS[ev.CONTRACTS[profile.id]["encoding"]]
    tail = source[retail:retail + ev.script_extent(source, retail, spec)]
    assert chained >= len(source) and tail in built[chained:chained + 64 + len(tail)]
    made = [item for item in mo.read_objects(built, profile, 102)
            if struct.unpack_from("<I", built, item.record_offset + mo.CONDITION_OFFSET)[0]
            == 0x00010000 | number]
    assert len(made) == 1
    assert rom.read_bytes() == source


def test_a_refused_or_undone_edit_loses_nothing(tmp_path):
    from tools.creator.model.dialogue import DialogueStudio
    from tools.creator.model.events import EventStudio
    from tools.creator.model.maps import MapStudio
    from tools.creator.model.project import CreatorError

    rom, project, profile = _project(tmp_path)
    events, maps = EventStudio(project.directory, rom), MapStudio(project.directory, rom)
    first = events.new_event("First", ev.ENTER, "map:0033")
    second = events.new_event("Second")
    with pytest.raises(CreatorError):
        events.set_trigger(second, ev.ENTER, "map:0033")
    assert set(events.document()) == {first, second}
    events.remove_step(second, 0)
    with pytest.raises(CreatorError):
        events.remove_step(second, 0)

    events.rename(second, "Renamed")
    donor = maps.character_choices()[0]
    maps.add_character("map:0033", donor.donor_map, donor.donor_slot, 176, 136)
    events.undo()
    assert events.event(second).name == "Second"
    assert len(mo.read_document(project.directory)["map:0033"].made) == 1

    for name in ("flag", "gone"):
        events.add_flag(name)
    with pytest.raises(CreatorError):
        events.add_flag("always")
    events._set_steps(second, (("if", "flag", "flag"), ("set", "flag"), ("end_if",)))
    events.rename_flag("flag", "seen")
    assert events.event(second).steps[:2] == (("if", "flag", "seen"), ("set", "seen"))
    number = events.registry().names["gone"]
    events.delete_flag("gone")
    talks = DialogueStudio(project.directory, rom)
    talk = talks.new_talk("Hello")
    talks.set_rule(talk, "fresh", "", "", 0)
    kept = sf.read_flags(project.directory)
    assert kept.names["fresh"] != number and number in kept.retired


def test_a_retired_flag_from_an_older_project_stays_retired(tmp_path):
    _rom, project, profile = _project(tmp_path)
    path = project.directory / "dialogue" / "conversations.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[flags]\nold_one = 157\nkeep = 158\n", encoding="utf-8")
    flags = sf.read_flags(project.directory)
    sf.write_flags(project.directory, sf.retired(flags, "old_one"))
    again = sf.read_flags(project.directory)
    assert again.names == {"keep": 158} and again.retired == (157,)


def test_steps_not_seen_working_in_the_game_are_refused_by_name(tmp_path):
    rom, project, profile = _project(tmp_path)
    ev.write_document(project.directory, {"evt-1": ev.Event("Gift", steps=(("music", 1),))})
    blocked = {"music"} - ev.PROVEN
    result = _build(rom, project)
    assert bool(blocked) != result["ok"]
    if blocked:
        assert "Gift" in str(result) and "step 1" in str(result)


def test_flag_numbers_are_permanent(tmp_path):
    _rom, project, profile = _project(tmp_path)
    flags = sf.Flags()
    for name in ("a", "b", "c"):
        flags = sf.assign(flags, name, profile)
    first = dict(flags.names)
    flags = sf.renamed(sf.retired(flags, "b"), "c", "sea")
    flags = sf.assign(flags, "b", profile)
    sf.write_flags(project.directory, flags)
    kept = sf.read_flags(project.directory)
    assert kept.names["a"] == first["a"] and kept.names["sea"] == first["c"]
    assert kept.names["b"] not in first.values() and first["b"] in kept.retired
