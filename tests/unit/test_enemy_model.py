"""The Enemies tab's model: the game's own types and the project's own types.

The game image is needed, so these skip cleanly when the canonical copy is
absent, and they read it read-only through a mutable copy per test.
"""

from __future__ import annotations

import re

import pytest

from tests.rom_support import canonical_rom_path, mutable_rom_copy
from tools.creator.model.enemies import EnemyStudio
from tools.creator.model.project import CreatorError, CreatorProject
from tools.webfoot import enemy_types, map_objects as mo

pytestmark = pytest.mark.skipif(
    canonical_rom_path() is None, reason="the canonical Buu's Fury ROM is not present"
)

DONOR = "enemy:434"
DONOR_HP = 175
LOOK = "sprite:0209"
PLACEMENTS = 1559
GAME_TYPES = 125


@pytest.fixture
def studio(tmp_path):
    rom = mutable_rom_copy(tmp_path)
    project = CreatorProject.create(rom, tmp_path / "Game", "Game")
    return EnemyStudio(project.directory, rom)


def _row_of(studio, name: str) -> tuple[int, int, bytes]:
    entry = enemy_types.read_types(
        studio.directory, studio.profile, studio.image).entries[f"enemy:{name}"]
    return entry.row, entry.donor, entry.raw


def _texts(studio) -> list[str]:
    found: list[str] = []
    for row in (*studio.game(), *studio.donors()):
        found.append(row.key)
    for row in studio.project():
        found += [row.name, row.key, row.donor]
        found.append(row.look.key if row.look else "")
        found += [title for title, _count in row.used_on]
    return found


def test_enemy_model_lists_retail_types_read_only(studio):
    game = studio.game()
    assert len(game) == GAME_TYPES
    assert [row for row in game if not row.key.startswith("enemy:")] == []
    assert next(row for row in game if row.key == DONOR).hp == DONOR_HP
    assert studio.pool == (0, 16)
    with pytest.raises(CreatorError, match="one of the game's own enemy types"):
        studio.set_statistic(DONOR, "hp", 1)


def test_enemy_model_usage_counts(studio):
    game = {row.key: row for row in studio.game()}
    assert game[DONOR].uses == 9
    assert sum(row.uses for row in game.values()) == PLACEMENTS
    assert min(row.uses for row in game.values()) >= 1


def test_enemy_model_create_from_donor(studio):
    assert studio.create(DONOR, "ghoul") == "enemy:ghoul"
    row = studio.project()[0]
    assert (row.name, row.donor, row.hp, row.strength, row.endurance) == (
        "ghoul", DONOR, DONOR_HP, 10, 20)
    assert row.experience == 225
    assert row.used_on == ()
    document = (studio.directory / enemy_types.TYPES_FILE).read_text(encoding="utf-8")
    assert '[type."enemy:ghoul"]' in document and "donor = 86" in document


def test_enemy_model_pool_counter(studio):
    assert studio.pool == (0, 16)
    studio.create(DONOR, "ghoul")
    assert studio.pool == (1, 16)
    studio.delete("ghoul")
    assert studio.pool == (0, 16)


def test_enemy_model_donor_list_is_the_eighty_nine(studio):
    donors = studio.donors()
    assert len(donors) == 89
    assert len({row.key for row in donors}) == 89
    assert [row for row in donors if row.hp <= 0] == []
    assert DONOR in [row.key for row in donors]


def test_enemy_look_refuses_unverified_pairing(studio):
    studio.create(DONOR, "ghoul")
    looks = studio.looks("ghoul")
    assert [(look.key, look.sprite) for look in looks] == [(LOOK, 209)]
    studio.set_look("ghoul", 209)
    with pytest.raises(CreatorError, match="the only sprite verified for this enemy"):
        studio.set_look("ghoul", 120)


def test_enemy_model_seventeenth_type_refused(studio):
    for index in range(16):
        studio.create(DONOR, f"spare-{index}")
    assert studio.pool == (16, 16)
    with pytest.raises(CreatorError, match="All 16 rows the base game never names are taken."):
        studio.create(DONOR, "one-more")


def test_enemy_model_edit_retail_type_refused(studio):
    with pytest.raises(CreatorError, match="one of the game's own enemy types"):
        studio.set_statistic(DONOR, "hp", 1)
    with pytest.raises(CreatorError, match="one of the game's own enemy types"):
        studio.rename(DONOR, "wolf")
    with pytest.raises(CreatorError, match="one of the game's own enemy types"):
        studio.delete(DONOR)


def test_enemy_model_delete_while_placed_refused(studio):
    studio.create(DONOR, "ghoul")
    mo.place_enemy(studio.directory, "map:0033", "ghoul", "enemy:ghoul", 176, 152)
    assert studio.project()[0].used_on == (("033 Snakeway", 1),)
    with pytest.raises(CreatorError, match="is named by maps/objects.toml"):
        studio.delete("ghoul")
    assert [row.name for row in studio.project()] == ["ghoul"]


def test_enemy_model_rename_keeps_identity(studio):
    studio.create(DONOR, "ghoul")
    row, donor, raw = _row_of(studio, "ghoul")
    mo.place_enemy(studio.directory, "map:0033", "ghoul", "enemy:ghoul", 176, 152)
    assert studio.rename("ghoul", "cave-wolf") == "enemy:cave-wolf"
    assert _row_of(studio, "cave-wolf") == (row, donor, raw)
    objects = (studio.directory / mo.OBJECTS_FILE).read_text(encoding="utf-8")
    assert "enemy:cave-wolf" in objects and "enemy:ghoul" not in objects
    assert studio.project()[0].used_on == (("033 Snakeway", 1),)


def test_enemy_model_never_exposes_a_row_number(studio):
    studio.create(DONOR, "ghoul")
    row, donor, _raw = _row_of(studio, "ghoul")
    texts = _texts(studio)
    tokens = [token for text in texts for token in re.split(r"[^0-9]+", text) if token]
    assert str(row) not in tokens
    assert str(donor) not in tokens
    assert [text for text in texts if "0x" in text.lower()] == []
    assert studio.project()[0].key == "enemy:ghoul"
