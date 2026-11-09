from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.webfoot import sprite_import, sprite_runtime, sprite_runtime_assets


def inputs(tmp_path):
    paths = tuple(tmp_path / name for name in ("base.gba", "buu.gba", "log2.gba"))
    for index, path in enumerate(paths):
        path.write_bytes(bytes([index]) * 64)
    return paths


def synthetic_open(monkeypatch):
    monkeypatch.setattr(
        sprite_import.RomImage,
        "open",
        lambda path, expected: sprite_import.RomImage(
            Path(path), expected, Path(path).read_bytes()
        ),
    )


def test_wrong_source_identity_creates_no_project_or_image(tmp_path):
    paths = inputs(tmp_path)
    project = tmp_path / "project"
    output = tmp_path / "output.gba"
    before = [path.read_bytes() for path in paths]
    with pytest.raises(sprite_import.SpriteImportError, match="sha256"):
        sprite_runtime.build_runtime(*paths, output, project, tmp_path)
    assert not project.exists()
    assert not output.exists()
    assert [path.read_bytes() for path in paths] == before


@pytest.mark.parametrize("source_index", [0, 1, 2])
def test_output_cannot_alias_any_input(tmp_path, monkeypatch, source_index):
    paths = inputs(tmp_path)
    synthetic_open(monkeypatch)
    before = [path.read_bytes() for path in paths]
    with pytest.raises(ValueError):
        sprite_runtime.build_runtime(
            *paths, paths[source_index], tmp_path / "project", tmp_path
        )
    assert [path.read_bytes() for path in paths] == before
    assert not (tmp_path / "project").exists()


def test_nonempty_project_is_preserved(tmp_path, monkeypatch):
    paths = inputs(tmp_path)
    synthetic_open(monkeypatch)
    project = tmp_path / "project"
    project.mkdir()
    existing = project / "existing.txt"
    existing.write_text("keep this work", encoding="utf-8")
    with pytest.raises(ValueError, match="must be empty"):
        sprite_runtime.build_runtime(*paths, tmp_path / "output.gba", project, tmp_path)
    assert existing.read_text(encoding="utf-8") == "keep this work"
    assert not (tmp_path / "output.gba").exists()


def test_toolchain_requires_each_consumed_program(tmp_path):
    suffix = ".exe" if sprite_runtime.os.name == "nt" else ""
    for name in ("gcc", "as"):
        (tmp_path / f"arm-none-eabi-{name}{suffix}").write_bytes(b"")
    with pytest.raises(ValueError, match="arm-none-eabi-ld"):
        sprite_runtime.compiler_directory(tmp_path)


@pytest.mark.parametrize("site", [0x08002556, 0x08005626, 0x08002F1E, 0x080074BE, 0x0800802A, 0x080098C6])
def test_far_entries_load_the_linked_thumb_address(site):
    target = 0x08810000
    code = sprite_runtime._far_entry(target)
    instruction = int.from_bytes(code[:2], "little")
    literal = ((site + 4) & ~3) + (instruction & 255) * 4
    assert len(code) == 12
    assert instruction >> 11 == 0b01001
    assert (instruction >> 8) & 7 == 3
    assert code[2:4] == bytes.fromhex("1847")
    assert (
        int.from_bytes(code[literal - site : literal - site + 4], "little")
        == target | 1
    )


@pytest.mark.parametrize(
    ("colours", "expected"),
    [
        ([frozenset(range(1, 9)), frozenset(range(8, 16))], 1),
        ([frozenset(range(1, 9)), frozenset(range(9, 17))], 2),
    ],
)
def test_palette_grouping_respects_capacity_and_retains_every_colour(colours, expected):
    packed = sprite_runtime_assets.groups(colours)
    assert len(packed) == expected
    assert all(len(bank) <= 15 for bank in packed)
    assert all(any(source <= bank for bank in packed) for source in colours)


def test_changed_target_mapping_is_refused_before_donor_access(tmp_path, monkeypatch):
    entry = SimpleNamespace(
        donor="buus-fury", target=SimpleNamespace(art_id=999, states=())
    )
    monkeypatch.setattr(
        sprite_import, "load_manifest", lambda _path: SimpleNamespace(imports=[entry])
    )
    image = SimpleNamespace(sha256="synthetic")
    with pytest.raises(sprite_import.SpriteImportError, match="approved manifest"):
        sprite_runtime_assets.actor_assets(tmp_path, image, image, image)


def test_changed_manifest_source_identity_is_refused(tmp_path, monkeypatch):
    entry = SimpleNamespace(
        donor="buus-fury",
        target=SimpleNamespace(
            art_id=32,
            states=(0, 1, 3, 4, 9),
            fallback_states=sprite_runtime_assets.FALLBACK_STATES["goku-base"],
            art_table=sprite_runtime_assets.ART_TABLE,
            sha256="synthetic",
        ),
    )
    document = SimpleNamespace(
        imports=[entry], donor=lambda _name: SimpleNamespace(sha256="different")
    )
    monkeypatch.setattr(sprite_import, "load_manifest", lambda _path: document)
    image = SimpleNamespace(sha256="synthetic")
    with pytest.raises(sprite_import.SpriteImportError, match="source identities"):
        sprite_runtime_assets.actor_assets(tmp_path, image, image, image)


def test_all_approved_fallback_rows_remain_in_the_runtime_contract():
    assert sum(map(len, sprite_runtime_assets.FALLBACK_STATES.values())) == 22
    directory = Path(__file__).resolve().parents[2] / "config/sprite-imports"
    for name, expected in sprite_runtime_assets.FALLBACK_STATES.items():
        manifest = sprite_import.load_manifest(directory / f"{name}.json")
        assert manifest.imports[0].target.fallback_states == expected


def test_every_trampoline_resume_address_has_the_thumb_bit():
    source = Path(sprite_runtime.__file__).parent / "patchsource" / "log1-actor-runtime" / "trampoline.s"
    words = [
        int(line.split()[1], 16)
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith(".word 0x08")
    ]
    assert len(words) == 8
    assert all(word & 1 for word in words)
