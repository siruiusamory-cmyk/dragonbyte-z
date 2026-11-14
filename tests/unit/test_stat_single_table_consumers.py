"""The consumers of the stat layer against a profile that declares one table.

The semantic layer serves a profile whose enemy record decodes only HP. This
module pins the consumers that reach the same record through a different door:
the project writer and reader, project validation, the project build path, the
DragonByte data surface, and the stat CLI's own text. Each was written against
Buu's Fury's six-field record and assumed it.

The synthetic image and the packaged profiles come from
`tests/unit/test_stat_single_table.py`; nothing here reads a ROM.
"""

from __future__ import annotations

import inspect
from dataclasses import replace
from types import SimpleNamespace

import pytest

from tests.unit.test_stat_single_table import (
    _identification,
    _image_with,
    _single_table_profile,
    _single_table_records,
    _two_table_enemy_records,
    _two_table_profile,
)
from tools.dragonbyte import dataedits as dataedits
from tools.dragonbyte import datasurface as ds
from tools.webfoot import build as build_mod
from tools.webfoot import cli as cli_mod
from tools.webfoot.data.enemy_families import EXTENSION_START
from tools.webfoot.formats import stat_tables as st
from tools.webfoot.project import model as project_model
from tools.webfoot.project.model import ProjectMeta, read_project, write_project
from tools.webfoot.stats import stat_tables_from_image

SINGLE_TABLE_INDEX = 41


def _single_table_tables():
    profile = _single_table_profile()
    data = _image_with(profile, _single_table_records(profile.enemy_stats.count))
    return profile, data, stat_tables_from_image(_identification(profile), profile, data)


def _two_table_tables():
    profile = _two_table_profile()
    data = _image_with(profile, _two_table_enemy_records(profile.enemy_stats.count))
    return profile, data, stat_tables_from_image(_identification(profile), profile, data)


def _meta(profile) -> ProjectMeta:
    return ProjectMeta(
        format_version=project_model.PROJECT_FORMAT_VERSION,
        profile_id=profile.id,
        game=profile.game,
        base_rom_sha256=profile.sha256,
        base_rom_size=profile.size,
        name=profile.id,
    )


def test_the_enemy_document_carries_only_the_fields_the_record_decodes() -> None:
    """F1: the writer described Buu's record, so a one-field format crashed it."""
    raw = bytes(range(st.LOG2_ENEMY_RECORD_SIZE))
    record = st.decode_log2_enemy_record(raw, 0)
    document = project_model._enemy_document(
        [(st.StatIdentity(kind="enemy", key=SINGLE_TABLE_INDEX), record, raw, None)]
    )
    entry = document["enemy"][str(SINGLE_TABLE_INDEX)]
    assert set(entry) == {"hp", "raw"}
    assert "type_id" not in entry

    buu = st.decode_enemy_record(bytes(st.ENEMY_RECORD_SIZE), 0)
    detailed = project_model._enemy_document(
        [(st.StatIdentity(kind="enemy", key=1), buu, bytes(st.ENEMY_RECORD_SIZE), None)]
    )["enemy"]["1"]
    assert set(detailed) == {
        "type_id",
        "hp",
        "exp",
        "level",
        "strength",
        "power",
        "endurance",
        "raw",
    }


def test_a_one_field_project_round_trips_through_write_and_read(tmp_path) -> None:
    """F1 end to end: what extraction writes, the reader and validator accept."""
    profile, _, tables = _single_table_tables()
    enemies = [
        (entry.identity, entry.record, entry.original_bytes, None)
        for entry in tables.enemies()
    ]
    write_project(
        tmp_path, _meta(profile), enemies=enemies, characters=[], strings=[], maps=[]
    )
    project = read_project(tmp_path)
    values = project.enemies[st.StatIdentity(kind="enemy", key=SINGLE_TABLE_INDEX)]
    assert set(values) == {"hp", "raw", "alias"}
    assert values["hp"] == tables.enemy(
        st.StatIdentity(kind="enemy", key=SINGLE_TABLE_INDEX)
    ).record.hp
    assert build_mod._check_records(project, tables) == []


def test_a_project_that_authors_no_stat_records_is_authoring_none() -> None:
    """F2: a project made before the table was declared was missing all 109."""
    _, _, tables = _single_table_tables()
    project = SimpleNamespace(enemies={}, characters={})
    assert build_mod._check_records(project, tables) == []


def test_a_buu_project_that_authors_some_records_still_reports_the_omissions() -> None:
    """SF3: the missing-record guard survives for a two-table profile."""
    _, _, tables = _two_table_tables()
    first = next(tables.enemies())
    project = SimpleNamespace(
        enemies={first.identity: {"hp": first.record.hp, "raw": first.original_bytes}},
        characters={},
    )
    problems = build_mod._check_records(project, tables)
    missing = [item for item in problems if "project is missing this enemy record" in item]
    assert len(missing) == EXTENSION_START.get(
        tables.profile.id, tables.profile.enemy_stats.count) - 1
    assert any("project is missing this character record" in item for item in problems)


def test_a_one_field_project_that_authors_some_records_reports_the_omissions() -> None:
    """SF3: a partially authored single-table project is still held to the set."""
    _, _, tables = _single_table_tables()
    entry = tables.enemy(st.StatIdentity(kind="enemy", key=SINGLE_TABLE_INDEX))
    project = SimpleNamespace(
        enemies={entry.identity: {"hp": entry.record.hp, "raw": entry.original_bytes}},
        characters={},
    )
    problems = build_mod._check_records(project, tables)
    missing = [item for item in problems if "project is missing this enemy record" in item]
    assert len(missing) == tables.profile.enemy_stats.count - 1


def test_a_two_table_record_missing_a_decoded_field_is_reported() -> None:
    """The reader accepts a subset; the validator still names the absent field."""
    _, _, tables = _two_table_tables()
    entry = next(tables.enemies())
    project = SimpleNamespace(
        enemies={entry.identity: {"hp": entry.record.hp, "raw": entry.original_bytes}},
        characters={},
    )
    problems = build_mod._check_records(project, tables)
    named = [item for item in problems if item.startswith(str(entry.identity) + ".")]
    assert any("decodes this field" in item for item in named)
    assert any(item.startswith(f"{entry.identity}.exp") for item in named)


def test_a_complete_two_table_project_validates_clean(tmp_path) -> None:
    """F1: every fixed field was reported as one the record does not decode."""
    profile, _, tables = _two_table_tables()
    enemies = [
        (entry.identity, entry.record, entry.original_bytes, None)
        for entry in tables.enemies()
    ]
    characters = [
        (
            entry.identity,
            replace(entry.record, level=60),
            entry.original_bytes,
            entry.alias,
        )
        for entry in tables.characters()
    ]
    write_project(
        tmp_path,
        _meta(profile),
        enemies=enemies,
        characters=characters,
        strings=[],
        maps=[],
    )
    project = read_project(tmp_path)
    assert set(project.enemies[next(iter(project.enemies))]) == {
        "type_id",
        "hp",
        "exp",
        "level",
        "strength",
        "power",
        "endurance",
        "raw",
        "alias",
    }
    assert build_mod._check_records(project, tables) == []


def test_a_raw_blob_of_the_wrong_length_is_reported_against_the_rom() -> None:
    """The size check moved from load to validation, and still refuses."""
    _, _, tables = _two_table_tables()
    entry = next(tables.enemies())
    project = SimpleNamespace(
        enemies={entry.identity: {"hp": entry.record.hp, "raw": b"\x00\x11"}},
        characters={},
    )
    problems = build_mod._check_records(project, tables)
    assert any("authored raw bytes do not match this ROM" in item for item in problems)


def test_the_apply_path_edits_a_record_that_decodes_only_hp() -> None:
    """F3: the build path indexed Buu's field union and raised."""
    _, _, tables = _single_table_tables()
    identity = st.StatIdentity(kind="enemy", key=SINGLE_TABLE_INDEX)
    authored = {
        identity: {"hp": 4242, "raw": tables.enemy(identity).original_bytes}
    }
    build_mod._apply_project_to_tables(
        SimpleNamespace(enemies=authored, characters={}), tables
    )
    assert tables.enemy(identity).record.hp == 4242
    changes = tables.plan().effective_changes
    assert len(changes) == 1
    assert changes[0].owner == str(identity)


def test_the_data_surface_stages_a_record_that_decodes_only_hp() -> None:
    """F3: the DragonByte write path read the authored field union directly."""
    profile, data, tables = _single_table_tables()
    identity = st.StatIdentity(kind="enemy", key=SINGLE_TABLE_INDEX)
    authored = {
        identity: {"hp": 4242, "raw": tables.enemy(identity).original_bytes}
    }
    surface = ds.DataSurface(
        identification=_identification(profile),
        profile=profile,
        image=data,
        tables=tables,
    )
    changes = surface.changes(
        SimpleNamespace(enemies=authored, characters={}, maps={})
    )
    assert len(changes) == 1
    assert changes[0].owner == str(identity)
    assert changes[0].reason == "enemy edit: hp"


def test_the_stat_cli_names_no_game(capsys) -> None:
    """F4: the listings said Buu's Fury while editing a Legacy of Goku II image."""
    profile, _, tables = _single_table_tables()
    cli_mod._print_stats_list(tables, "all")
    cli_mod._print_round_trip(tables)
    output = capsys.readouterr().out
    assert "Buu" not in output
    assert f"Profile: {profile.id}" in output


def test_the_stat_cli_says_what_an_identity_actually_is(capsys) -> None:
    """F5: the footer claimed a durable identity for an index-keyed profile."""
    _, _, tables = _single_table_tables()
    cli_mod._print_stats_list(tables, "enemy")
    output = capsys.readouterr().out
    assert "Identity is durable" not in output
    assert "otherwise the table index" in output


def test_no_stat_printing_function_names_a_game_in_its_source() -> None:
    """F4 for the edit printer too, which needs a ROM to run through `main`."""
    for name in ("_print_stats_list", "_print_round_trip", "_print_stats_set"):
        source = inspect.getsource(getattr(cli_mod, name))
        assert "Buu" not in source, name


def _authored_payload(profile, tables):
    enemies = {
        entry.identity: {"hp": entry.record.hp, "raw": entry.original_bytes}
        for entry in tables.enemies()
    }
    return dataedits.AuthoredData(
        meta=_meta(profile), enemies=enemies, characters={}, maps={}
    )


def test_the_data_surface_serves_an_authored_one_field_project() -> None:
    """C1(a): every row's state check walked the Buu's Fury field union."""
    profile, data, tables = _single_table_tables()
    payload = _authored_payload(profile, tables)
    surface = ds.DataSurface(
        identification=_identification(profile),
        profile=profile,
        image=data,
        tables=tables,
    )
    rows = surface.rows(ds.ENEMY, payload)
    assert len(rows) == tables.profile.enemy_stats.count
    assert [field.name for field in rows[SINGLE_TABLE_INDEX].fields] == ["hp"]
    assert rows[SINGLE_TABLE_INDEX].editable is True


def test_the_editor_save_path_builds_the_record_type_the_codec_decodes(tmp_path) -> None:
    """C1(b): the save path constructed a fixed record type for every entry."""
    profile, _, tables = _single_table_tables()
    payload = _authored_payload(profile, tables)
    identity = st.StatIdentity(kind="enemy", key=SINGLE_TABLE_INDEX)
    records = dataedits._enemy_records(payload.enemies)
    record = dict((item[0], item[1]) for item in records)[identity]
    assert isinstance(record, st.Log2EnemyRecord)
    assert record.hp == tables.enemy(identity).record.hp
    assert not hasattr(record, "exp")

    dataedits.write(tmp_path, payload)
    saved = read_project(tmp_path)
    assert len(saved.enemies) == tables.profile.enemy_stats.count
    for identity, values in saved.enemies.items():
        assert values["raw"] == payload.enemies[identity]["raw"]
        assert set(values) == {"hp", "raw", "alias"}


def test_an_authored_field_the_record_does_not_decode_is_reported() -> None:
    """C2: a copied Buu's Fury field loaded, validated and vanished silently."""
    _, _, tables = _single_table_tables()
    identity = st.StatIdentity(kind="enemy", key=SINGLE_TABLE_INDEX)
    entry = tables.enemy(identity)
    project = SimpleNamespace(
        enemies={identity: {"hp": entry.record.hp, "exp": 5, "raw": entry.original_bytes}},
        characters={},
    )
    problems = build_mod._check_records(project, tables)
    named = [item for item in problems if item.startswith(f"{identity}.exp")]
    assert named == [
        f"{identity}.exp: the record format does not decode this field; a build "
        "would silently drop the authored value"
    ]


def test_the_editor_save_path_refuses_a_field_the_record_does_not_decode(
    tmp_path,
) -> None:
    """F2: the save path dropped the same field the validator reports."""
    profile, _, tables = _single_table_tables()
    payload = _authored_payload(profile, tables)
    identity = st.StatIdentity(kind="enemy", key=SINGLE_TABLE_INDEX)
    enemies = dict(payload.enemies)
    enemies[identity] = {**enemies[identity], "exp": 5}
    with pytest.raises(
        dataedits.DataEditError,
        match=r"enemy:41\.exp: the record format does not decode this field",
    ):
        dataedits.write(
            tmp_path,
            dataedits.AuthoredData(
                meta=payload.meta,
                enemies=enemies,
                characters=payload.characters,
                maps=payload.maps,
            ),
        )
