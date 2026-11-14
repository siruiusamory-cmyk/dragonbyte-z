"""The added-enemy placement document, the retail refusal, and the object policy."""

from __future__ import annotations

import pytest

from tools.webfoot import map_objects as mo
from tools.quality.architecture import REPOSITORY_ROOT

KEY = "map:0033"


def test_enemy_placement_document_round_trip(tmp_path):
    key = mo.place_enemy(tmp_path, KEY, "ghoul", "enemy:ghoul", 176, 152,
                         appears="!met_ghoul", sprite=209)
    edits = mo.read_document(tmp_path)
    made = edits[KEY].made[key]
    assert (made.type, made.x, made.y, made.appears, made.sprite_id) == (
        "enemy:ghoul", 176, 152, "!met_ghoul", 209)
    assert made.donor_map is None and made.donor_slot is None
    assert "type = \"enemy:ghoul\"" in (tmp_path / mo.OBJECTS_FILE).read_text(encoding="utf-8")


def test_enemy_placement_move_duplicate_remove(tmp_path):
    key = mo.place_enemy(tmp_path, KEY, "ghoul", "enemy:ghoul", 176, 152)
    mo.move_enemy(tmp_path, KEY, key, 200, 160)
    made = mo.read_document(tmp_path)[KEY].made[key]
    assert (made.x, made.y) == (200, 160)

    copy = mo.duplicate_enemy(tmp_path, KEY, key, "ghoul", 120, 120)
    assert copy != key
    edits = mo.read_document(tmp_path)[KEY]
    assert sorted(edits.made) == sorted([key, copy])
    assert (edits.made[copy].x, edits.made[copy].y) == (120, 120)
    assert edits.made[copy].type == edits.made[key].type

    mo.remove_enemy(tmp_path, KEY, key)
    assert list(mo.read_document(tmp_path)[KEY].made) == [copy]
    mo.remove_enemy(tmp_path, KEY, copy)
    assert KEY not in mo.read_document(tmp_path)
    assert not (tmp_path / mo.OBJECTS_FILE).exists()


def test_retail_enemy_placement_is_not_editable(tmp_path):
    mo.place_enemy(tmp_path, KEY, "ghoul", "enemy:ghoul", 176, 152)
    before = (tmp_path / mo.OBJECTS_FILE).read_text(encoding="utf-8")
    for call in (
        lambda: mo.move_enemy(tmp_path, KEY, "game:4", 8, 8),
        lambda: mo.duplicate_enemy(tmp_path, KEY, "game:4", "twin", 8, 8),
        lambda: mo.remove_enemy(tmp_path, KEY, "game:4"),
    ):
        with pytest.raises(mo.MapObjectError, match="a retail placement cannot be moved"):
            call()
    assert (tmp_path / mo.OBJECTS_FILE).read_text(encoding="utf-8") == before
    with pytest.raises(mo.MapObjectError, match="no added enemy named 'ghoul-9'"):
        mo.move_enemy(tmp_path, KEY, "ghoul-9", 8, 8)


def test_enemy_placement_appears_rule_is_written(tmp_path):
    key = mo.place_enemy(tmp_path, KEY, "ghoul", "enemy:ghoul", 176, 152)
    mo.set_enemy_appears(tmp_path, KEY, key, "!met_ghoul")
    assert mo.read_document(tmp_path)[KEY].made[key].appears == "!met_ghoul"
    mo.set_enemy_appears(tmp_path, KEY, key, "always")
    assert mo.read_document(tmp_path)[KEY].made[key].appears == "always"
    with pytest.raises(mo.MapObjectError, match="a retail placement cannot be moved"):
        mo.set_enemy_appears(tmp_path, KEY, "game:4", "met_ghoul")


def test_enemy_added_placement_rejects_unknown_fields(tmp_path):
    (tmp_path / "maps").mkdir()
    (tmp_path / mo.OBJECTS_FILE).write_text(
        '[objects."map:0033".made."enemy-1"]\ntype = "enemy:ghoul"\nx = 8\ny = 8\n'
        'colour = "red"\n', encoding="utf-8")
    with pytest.raises(mo.MapObjectError, match="which an added enemy does not name"):
        mo.read_document(tmp_path)


def test_enemy_placement_name_rule_refused(tmp_path):
    with pytest.raises(mo.MapObjectError, match="small letters and digits"):
        mo.place_enemy(tmp_path, KEY, "Ghoul", "enemy:ghoul", 8, 8)


def test_enemy_object_limit_is_one_policy_constant():
    source = (REPOSITORY_ROOT / "tools" / "webfoot" / "map_objects.py").read_text(
        encoding="utf-8")
    assert mo.BUILT_OBJECT_POLICY == 23
    assert source.count("BUILT_OBJECT_POLICY") > 1
    assert sum(line.startswith("BUILT_OBJECT_POLICY") for line in source.splitlines()) == 1


def test_enemy_policy_is_not_described_as_a_hardware_or_engine_limit():
    roots = ("docs/research/ENEMY_PLACEMENT.md", "tools/webfoot/map_objects.py",
             "README.md", "CHANGELOG.md")
    for name in roots:
        path = REPOSITORY_ROOT / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8").lower()
        for phrase in ("hardware limit", "engine limit"):
            assert phrase not in text, f"{name} calls the object policy a {phrase}"
    assert "no object count" in (
        REPOSITORY_ROOT / "tools" / "webfoot" / "map_objects.py").read_text(
            encoding="utf-8")
