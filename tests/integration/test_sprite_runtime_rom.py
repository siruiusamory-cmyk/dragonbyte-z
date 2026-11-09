import json
import os
from pathlib import Path

import pytest

from tests.integration.test_sprite_import_rom import image_path
from tools.webfoot import sprite_runtime


def test_runtime_rebuilds_identically_through_the_validated_writer(tmp_path):
    paths = tuple(
        image_path(key) for key in ("legacy-of-goku", "buus-fury", "legacy-of-goku-2")
    )
    try:
        compiler = sprite_runtime.compiler_directory(
            os.environ.get("WEBFOOT_ARM_TOOLCHAIN")
        )
    except ValueError as error:
        pytest.skip(str(error))
    manifests = Path(__file__).resolve().parents[2] / "config/sprite-imports"
    before = [sprite_runtime.digest(path) for path in paths]
    results = []
    for iteration in range(2):
        output = tmp_path / f"runtime-{iteration}.gba"
        _manifest, report = sprite_runtime.build_runtime(
            *paths, output, tmp_path / f"project-{iteration}", manifests, compiler
        )
        document = json.loads(
            Path(str(output) + ".manifest.json").read_text(encoding="utf-8")
        )
        assert document["generated_image"]["output_size"] == 16 * 1024 * 1024
        assert len(document["generated_allocations"]) == 8
        assert len(document["patch_payloads"]) == 19
        assert report["source_sha256"] == before
        assert set(report["runtime_sources"]) == {
            "transform.c",
            "renderer.c",
            "combat.c",
            "bf_math.c",
            "trampoline.s",
        }
        results.append((output.read_bytes(), document))
    assert results[0] == results[1]
    assert [sprite_runtime.digest(path) for path in paths] == before
