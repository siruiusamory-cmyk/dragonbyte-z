"""The per-map transition inventory answers from the transition corpus.

ROM-gated on the user-supplied canonical image, like every other proof against
it. The positive control is a map whose door the image demonstrably has and
whose typed-slot answer is empty, which is the distinction this command exists
to make readable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.webfoot.cli import main


LOCAL_ROM = Path("roms/Dragon Ball Z - Buu's Fury (U).gba")

TRANSITION_COUNT = 735
SOURCE_MAP_COUNT = 348


def require_rom() -> None:
    if not LOCAL_ROM.is_file():
        pytest.skip("user-supplied Buu's Fury ROM is not present")


@pytest.fixture
def rom():
    require_rom()
    return LOCAL_ROM


def rows(captured: str) -> list[str]:
    return [line.strip() for line in captured.splitlines() if line.strip().startswith("map:")]


def test_the_whole_corpus_counts_the_records_and_their_source_maps(rom, capsys):
    assert main(["map", "transitions", str(rom)]) == 0
    captured = capsys.readouterr().out
    assert f"Records: {TRANSITION_COUNT}" in captured
    listed = rows(captured)
    assert len(listed) == TRANSITION_COUNT
    sources = {line.split("/")[0] for line in listed}
    assert len(sources) == SOURCE_MAP_COUNT


def test_the_office_door_is_named_for_the_map_that_owns_it(rom, capsys):
    assert main(["map", "transitions", str(rom), "map:0036"]) == 0
    captured = capsys.readouterr().out
    assert "Records: 1" in captured
    assert "map:0036/transition:0000" in captured
    assert "-> map:0035" in captured
    assert "region (104, 137)..(488, 505)" in captured


def test_the_typed_slot_answer_for_that_map_stays_empty(rom, capsys):
    assert main(["map", "connections", str(rom), "map:0036"]) == 0
    captured = capsys.readouterr().out
    assert "Connections: 0" in captured


def test_a_map_with_no_transition_says_so(rom, capsys):
    assert main(["map", "transitions", str(rom), "map:0000"]) == 0
    captured = capsys.readouterr().out
    assert "Records: 0" in captured
    assert rows(captured) == []
