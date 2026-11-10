import json
import os
from pathlib import Path

import pytest

from tests.integration.test_sprite_import_rom import image_path
from tools.webfoot import pause_menu, sprite_runtime

RUNTIME_SHA256 = "b7f21dad45cd429fc31f25342063d5d09e1cf5472474fd540bd8d249330f6b53"


def test_the_pause_page_composes_on_the_character_runtime_image(tmp_path):
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
        output = tmp_path / f"combined-{iteration}.gba"
        report = pause_menu.compose(
            *paths, output, tmp_path / f"project-{iteration}", manifests, compiler
        )
        assert report["runtime_rom_sha256"] == RUNTIME_SHA256
        assert report["rom_sha256"] == sprite_runtime.digest(output)
        document = json.loads(
            Path(str(output) + ".manifest.json").read_text(encoding="utf-8")
        )
        spans = sorted(
            (entry["allocated_range"] for entry in document["generated_allocations"]),
            key=lambda span: span["file_offset"],
        )
        for left, right in zip(spans, spans[1:]):
            assert left["file_offset"] + left["size"] <= right["file_offset"], (
                left,
                right,
            )
        owners = {entry["label"] for entry in document["patch_payloads"]}
        assert "pause-menu" in owners
        assert "runtime" in owners
        results.append((output.read_bytes(), report["payload_address"]))
    assert results[0] == results[1]
    assert [sprite_runtime.digest(path) for path in paths] == before
