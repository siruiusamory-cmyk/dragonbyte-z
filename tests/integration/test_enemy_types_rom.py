"""ROM-gated proofs for project enemy types and the type table's extent.

The claims that cannot be made on synthetic data: the table holds 150 records,
the spare rows are named by no map placement in the retail census, the donor
family is the 89 records whose callback is the one a type may be copied from,
and a build writes a claimed row and nothing else in the image.

These skip cleanly when the canonical image is absent, and read it read-only.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tests import rom_support
from tools.webfoot import enemy_types, stats
from tools.webfoot.build import build_project, validate_project
from tools.webfoot.entities import PlacementTypes
from tools.webfoot.maps import load_maps
from tools.webfoot.profile import RomProfileCatalog
from tools.webfoot.project.atomic import replace_document
from tools.webfoot.project.format import dump_toml
from tools.webfoot.rom import identify_rom
from tools.webfoot.stats import StatProfileError

PROFILE_ID = "buus_fury_usa_rev0_01c1707f"
TABLE_OFFSET = 0x08711274 - 0x08000000
RECORD_SIZE = 0x1C


@pytest.fixture
def rom_path() -> Path:
    path = rom_support.canonical_rom_path()
    if path is None:
        pytest.skip("canonical Buu's Fury ROM not present locally")
    return path


@pytest.fixture
def rom_bytes(rom_path: Path) -> bytes:
    return rom_support.canonical_rom_bytes()


@pytest.fixture
def catalog() -> RomProfileCatalog:
    return RomProfileCatalog.load("config/roms.yaml")


@pytest.fixture
def profile(catalog: RomProfileCatalog):
    return next(item for item in catalog.profiles if item.id == PROFILE_ID)


def _project(root: Path, profile) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    replace_document(root / "project.toml", dump_toml({
        "project": {"format_version": 1, "name": "enemy-types"},
        "base": {
            "profile_id": profile.id,
            "game": profile.game,
            "sha256": profile.sha256,
            "size": profile.size,
        },
    }))
    return root


def _row_offset(row: int) -> int:
    return TABLE_OFFSET + row * RECORD_SIZE


def test_enemy_type_table_extent(rom_path, catalog) -> None:
    tables = stats.load_stat_tables(rom_path, catalog)

    assert tables.profile.enemy_stats.count == 150
    entries = list(tables.enemies())
    assert len(entries) == 150
    assert len({entry.identity for entry in entries}) == 150
    assert entries[-1].location.index == 149


def test_enemy_pool_rows_are_unreferenced(rom_path, catalog, profile, rom_bytes) -> None:
    pool = set(enemy_types.spare_rows(profile))
    assert len(pool) == 16
    assert max(pool) < profile.enemy_stats.count

    types = PlacementTypes(load_maps(rom_path, catalog))
    selectors = {item.identity.selector for item in types.types()}
    assert pool & selectors == set()

    for row in pool:
        record = rom_bytes[_row_offset(row):_row_offset(row) + RECORD_SIZE]
        assert len(record) == RECORD_SIZE


def test_enemy_donor_family_is_the_eighty_nine(profile, rom_bytes) -> None:
    family = enemy_types.donor_family(profile, rom_bytes)

    assert len(family) == 89
    assert 24 not in family and 58 not in family and 60 not in family
    assert 61 not in family and 127 not in family and 140 not in family
    for row in family:
        record = rom_bytes[_row_offset(row):_row_offset(row) + RECORD_SIZE]
        assert int.from_bytes(record[4:7], "little") != 0


def test_project_without_enemies_builds_unchanged(
    tmp_path: Path, rom_path: Path, rom_bytes: bytes, catalog, profile
) -> None:
    project = _project(tmp_path / "project", profile)
    output = tmp_path / "out.gba"

    build_project(project, rom_path, output, catalog, manifest_path=None)

    assert output.read_bytes() == rom_bytes


def test_enemy_build_writes_claimed_row_only(
    tmp_path: Path, rom_path: Path, rom_bytes: bytes, catalog, profile
) -> None:
    project = _project(tmp_path / "project", profile)
    types = enemy_types.claim(enemy_types.Types(), "wolf", 86, profile, rom_bytes)
    types = enemy_types.edited(types, "wolf", "hp", 175)
    enemy_types.write_types(project, types)
    output = tmp_path / "out.gba"

    build_project(project, rom_path, output, catalog, manifest_path=None)

    image = output.read_bytes()
    assert len(image) == len(rom_bytes)
    row = types.entries["enemy:wolf"].row
    assert row == 30
    assert image[_row_offset(row):_row_offset(row) + RECORD_SIZE] == (
        types.entries["enemy:wolf"].record())
    changed = [index for index in range(len(image)) if image[index] != rom_bytes[index]]
    assert changed
    assert [index for index in changed
            if not _row_offset(row) <= index < _row_offset(row) + RECORD_SIZE] == []
    assert image[_row_offset(row) + 4:_row_offset(row) + 7] == (175).to_bytes(3, "little")


def test_enemy_build_deterministic(
    tmp_path: Path, rom_path: Path, rom_bytes: bytes, catalog, profile
) -> None:
    project = _project(tmp_path / "project", profile)
    types = enemy_types.claim(enemy_types.Types(), "wolf", 86, profile, rom_bytes)
    enemy_types.write_types(project, types)

    first, second = tmp_path / "one.gba", tmp_path / "two.gba"
    build_project(project, rom_path, first, catalog, manifest_path=None)
    build_project(project, rom_path, second, catalog, manifest_path=None)

    assert hashlib.sha256(first.read_bytes()).digest() == hashlib.sha256(
        second.read_bytes()).digest()


def test_enemy_claimed_row_shares_the_donors_behaviour_row(
    tmp_path: Path, rom_path: Path, rom_bytes: bytes, catalog, profile
) -> None:
    project = _project(tmp_path / "project", profile)
    types = enemy_types.claim(enemy_types.Types(), "wolf", 86, profile, rom_bytes)
    enemy_types.write_types(project, types)
    output = tmp_path / "out.gba"
    build_project(project, rom_path, output, catalog, manifest_path=None)

    image = output.read_bytes()
    row = types.entries["enemy:wolf"].row
    assert image[_row_offset(row) + 8:_row_offset(row) + 10] == rom_bytes[
        _row_offset(86) + 8:_row_offset(86) + 10]

    identification = identify_rom(rom_path, catalog)
    tables = stats.stat_tables_from_image(identification, profile, image)
    assert len(list(tables.enemies())) == 150
    assert len({entry.identity for entry in tables.enemies()}) == 150


def test_enemy_retail_duplicate_behaviour_row_refused(
    rom_path: Path, rom_bytes: bytes, catalog, profile
) -> None:
    identification = identify_rom(rom_path, catalog)
    data = bytearray(rom_bytes)
    data[_row_offset(4):_row_offset(4) + RECORD_SIZE] = rom_bytes[
        _row_offset(3):_row_offset(3) + RECORD_SIZE]

    with pytest.raises(StatProfileError) as refused:
        stats.stat_tables_from_image(identification, profile, bytes(data))
    assert "duplicate enemy type ids" in str(refused.value)


def test_validate_refuses_an_enemy_type_from_outside_the_donor_family(
    tmp_path: Path, rom_path: Path, rom_bytes: bytes, catalog, profile
) -> None:
    project = _project(tmp_path / "project", profile)
    raw = rom_bytes[_row_offset(86):_row_offset(86) + RECORD_SIZE]
    replace_document(project / enemy_types.TYPES_FILE, dump_toml({"type": {
        "enemy:ghost": {"row": 30, "donor": 24, "raw": raw.hex()}}}))

    report = validate_project(project, rom_path, catalog)

    assert not report.passed
    assert [message for message in report.problems
            if message.startswith("enemy types:") and "89" in message]


def test_validate_names_a_placement_whose_enemy_type_is_gone(
    tmp_path: Path, rom_path: Path, catalog, profile
) -> None:
    from tools.webfoot import map_objects as mo

    project = _project(tmp_path / "project", profile)
    mo.place_enemy(project, "map:0033", "ghost", "enemy:ghost", 176, 152)

    report = validate_project(project, rom_path, catalog)

    assert not report.passed
    assert [message for message in report.problems
            if message.startswith("map objects:")
            and "holds no enemy type for" in message]
