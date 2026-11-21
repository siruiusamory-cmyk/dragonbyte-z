"""DRAGONBYTE-Z-MAPS-DESTINATION-001: the map documents in the one journal.

Three things are proved here, and they are the whole contract between the Maps
destination and the journal:

* the adapter is lossless, so a Save writes what the project already held plus
  the edit, and every document this destination does not own is left alone;
* one map edit is one journal entry, and one undo restores both documents
  exactly;
* the payload may not carry another project's identity, because `install`
  replaces the project's meta.

The project fixture is a real extraction; the suite skips without the canonical
image.
"""

from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from tools.dragonbyte import mapedits
from tools.dragonbyte.journal import DOCUMENT_ADAPTERS
from tools.webfoot.build import extract_project
from tools.webfoot.catalog import load_catalog
from tools.webfoot.project import read_project
from tools.webfoot.rom import identify_rom

from tests.unit.test_dragonbyte_state import CANONICAL_SHA256, SIBLING_CHECKOUT


@pytest.fixture(scope="module")
def catalog():
    return load_catalog(None)


@pytest.fixture(scope="module")
def canonical_rom(catalog):
    roms = SIBLING_CHECKOUT / "roms"
    for candidate in sorted(roms.glob("*.gba")) if roms.is_dir() else []:
        try:
            identification = identify_rom(candidate, catalog)
        except Exception:  # noqa: BLE001 - any unreadable file is simply not it
            continue
        if identification.hashes.sha256 == CANONICAL_SHA256:
            return candidate
    pytest.skip(f"no canonical image in {roms}")


@pytest.fixture(scope="module")
def extracted_project(tmp_path_factory, catalog, canonical_rom):
    directory = tmp_path_factory.mktemp("dbz-mapedits") / "source"
    extract_project(canonical_rom, directory, catalog, graphics=False)
    return directory


@pytest.fixture
def project_dir(tmp_path, extracted_project):
    target = tmp_path / "project"
    shutil.copytree(extracted_project, target)
    return target


def test_the_journal_registers_the_maps_target_as_a_reversible_document():
    assert mapedits.MAPS_TARGET in DOCUMENT_ADAPTERS


def test_a_payload_carrying_another_projects_identity_is_refused(project_dir):
    project = read_project(project_dir)
    payload = mapedits.read(project)
    stranger = replace(payload, meta=replace(project.meta, name="another-project"))

    with pytest.raises(mapedits.MapsEditError):
        mapedits.validate(project, stranger)


def test_a_payload_that_is_not_authored_map_documents_is_refused(project_dir):
    project = read_project(project_dir)

    with pytest.raises(mapedits.MapsEditError):
        mapedits.validate(project, {"layout": {}})
    with pytest.raises(mapedits.MapsEditError):
        mapedits.install(project, None)
    with pytest.raises(mapedits.MapsEditError):
        mapedits.write(Path("."), None)
