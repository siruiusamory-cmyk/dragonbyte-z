from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from . import sprite_import as importer, sprite_limits
from .catalog import load_catalog
from .commands.backport import compose_presentation
from .destination import refuse_rom_destination
from .profile import GeneratedExpansionProfile
from .project import ProjectMeta, write_project
from .project.patchdoc import materialize_patch, read_patch_document
from .project.rawbytes import RawByteEdits, raw_byte_changes, write_raw_bytes
from .sprite_runtime_assets import actor_assets, transformation_assets
from .write import PatchPayloadProvenance, emit_image, plan_changes

SOURCE = Path(__file__).resolve().parent / "patchsource" / "log1-actor-runtime"
BF_SHA256 = "940ad5f01db4465b8877dfe739510cbf34f4ea3d390f3df13519808bc36f059e"
LOG2_SHA256 = "6e6c370c339ec9171cb1956adf837a0d342a197f78964882ef46c3086656ff75"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compiler_directory(value=None):
    if value:
        directory = Path(value)
    elif os.environ.get("DEVKITARM"):
        directory = Path(os.environ["DEVKITARM"]) / "bin"
    else:
        executable = shutil.which("arm-none-eabi-gcc")
        if not executable:
            raise ValueError(
                "arm-none-eabi-gcc is absent; pass --toolchain-dir or set DEVKITARM"
            )
        directory = Path(executable).parent
    for name in ("gcc", "as", "ld", "objcopy", "nm"):
        path = directory / (
            f"arm-none-eabi-{name}" + (".exe" if os.name == "nt" else "")
        )
        if not path.is_file():
            raise ValueError(f"missing runtime build tool: {path}")
    return directory


@dataclass
class RuntimeProject:
    directory: Path
    tools: Path
    manifests: Path
    images: tuple

    def run(self, tool, *arguments):
        executable = self.tools / (
            f"arm-none-eabi-{tool}" + (".exe" if os.name == "nt" else "")
        )
        return subprocess.check_output(
            [str(executable), *map(str, arguments)], text=True
        )

    def compile_at(self, addresses):
        source = transformation_assets(
            self.images[1], addresses["log1-sprite-limits"] | 1
        )
        source = re.sub(
            r"(static const .*?)(=)",
            r'\1 __attribute__((section(".bf_assets"),aligned(4)))\2',
            source,
        )
        source = source.replace(
            "const struct Frame frames[11]=",
            'const struct Frame frames[11] __attribute__((section(".bf_assets"),aligned(4)))=',
        )
        (self.directory / "transform_assets.c").write_text(source, encoding="utf-8")
        (self.directory / "generic_assets.c").write_text(
            actor_assets(self.manifests, *self.images), encoding="utf-8"
        )
        (self.directory / "all_runtime.c").write_text(
            '#include "transform.c"\n#include "bf_math.c"\n#include "renderer.c"\n#include "combat.c"\n',
            encoding="ascii",
        )
        flags = (
            "-mcpu=arm7tdmi",
            "-mthumb",
            "-O3",
            "-ffreestanding",
            "-fno-builtin",
            "-fno-unwind-tables",
            "-fno-asynchronous-unwind-tables",
            "-I",
            self.directory / "source",
        )
        for name in ("all_runtime", "transform_assets", "generic_assets"):
            self.run(
                "gcc",
                *flags,
                "-c",
                self.directory / f"{name}.c",
                "-o",
                self.directory / f"{name}.o",
            )
        self.run(
            "as",
            "-mcpu=arm7tdmi",
            "-mthumb",
            "-o",
            self.directory / "trampoline.o",
            self.directory / "source/trampoline.s",
        )
        linker = (
            "SECTIONS {"
            f". = {addresses['runtime']}; .text : {{ *(.text*) *(.rodata*) }} "
            f". = {addresses['bf-data']}; .bf_assets : {{ *(.bf_assets) }} "
            f". = {addresses['lg2-data']}; .lg2_assets : {{ *(.lg2_assets) }} "
            "/DISCARD/ : { *(.comment) *(.ARM.attributes) }}"
        )
        (self.directory / "runtime.ld").write_text(linker, encoding="ascii")
        library = Path(self.run("gcc", *flags[:2], "-print-libgcc-file-name").strip())
        if not library.is_file():
            raise ValueError(f"missing compiler runtime library: {library}")
        self.runtime_library = {"name": library.name, "sha256": digest(library)}
        self.run(
            "ld",
            "-T",
            self.directory / "runtime.ld",
            *(
                self.directory / f"{name}.o"
                for name in (
                    "all_runtime",
                    "transform_assets",
                    "generic_assets",
                    "trampoline",
                )
            ),
            library,
            "-o",
            self.directory / "runtime.elf",
        )
        for label, section in (
            ("runtime", ".text"),
            ("bf-data", ".bf_assets"),
            ("lg2-data", ".lg2_assets"),
        ):
            self.run(
                "objcopy",
                "-O",
                "binary",
                f"--only-section={section}",
                self.directory / "runtime.elf",
                self.directory / f"patch/{label}.bin",
            )
        return {
            name: int(value, 16)
            for value, _kind, name in re.findall(
                r"^([0-9a-f]+) (\w) (\w+)$",
                self.run("nm", self.directory / "runtime.elf"),
                re.M,
            )
        }

    def document(self):
        sprite_limits.write_project_patch(self.directory, self.images[0].data)
        path = self.directory / "patch/edits.toml"
        text = path.read_text(encoding="utf-8")
        text = re.sub(
            r"\[\[pointer\]\]\nsite = 0x542a64\n.*?(?=\n\[\[pointer\]\]|\Z)",
            "",
            text,
            flags=re.S,
        )
        text = text.replace('target = "log1-sprite-limits"', 'target = "generic-draw"')
        for label, donor in (
            ("runtime", None),
            ("bf-data", BF_SHA256),
            ("lg2-data", LOG2_SHA256),
            ("advance", None),
            ("visible", None),
            ("draw", None),
            ("generic-draw", None),
        ):
            text += f'\n[[payload]]\nlabel="{label}"\nsource_class="{"adapted" if donor else "new"}"\n'
            text += 'origin_note="approved character frames and original compatibility code; canonical sources pinned"\n'
            text += 'transform="actor-graphics-runtime"\nalignment=4\n'
            text += f'code={"false" if donor else "true"}\nfile="patch/{label}.bin"\n'
            text += f'sha256="{digest(self.directory / f"patch/{label}.bin")}"\n'
            if donor:
                text += f'donor_sha256="{donor}"\ndonor_span="0x000000-0x800000"\n'
        for label, site, expected in (
            ("advance", 0x542A5C, "e3c90008"),
            ("visible", 0x542A60, "81af0008"),
            ("draw", 0x542A64, "1fb00008"),
        ):
            text += f'\n[[pointer]]\nsite={site}\nexpect="{expected}"\ntarget="{label}"\nstate="thumb"\n'
            text += 'origin_note="scene state nine method"\n'
        path.write_text(text, encoding="utf-8")


def _far_entry(address):
    return (
        bytes.fromhex("014b1847c046")
        + (address | 1).to_bytes(4, "little")
        + bytes.fromhex("c046")
    )


def build_runtime(rom, buu, log2, output, directory, manifests, toolchain_dir=None):
    paths = tuple(map(Path, (rom, buu, log2)))
    images = tuple(
        importer.RomImage.open(path, expected)
        for path, expected in zip(
            paths, (sprite_limits.LOG1_SHA256, BF_SHA256, LOG2_SHA256), strict=True
        )
    )
    directory = Path(directory)
    for source in paths:
        refuse_rom_destination(source, directory / "project.toml")
        refuse_rom_destination(source, output)
    if directory.exists() and any(directory.iterdir()):
        raise ValueError(f"runtime project directory must be empty: {directory}")
    tools = compiler_directory(toolchain_dir)
    original = next(
        p for p in load_catalog(None).profiles if p.game == "legacy_of_goku"
    )
    profile = replace(
        original,
        free_regions=(),
        generated_expansion=GeneratedExpansionProfile(
            16 * 1024 * 1024,
            255,
            "append-only LOG1 character runtime; original extents retained",
        ),
    )
    meta = ProjectMeta(
        1,
        original.id,
        original.game,
        sprite_limits.LOG1_SHA256,
        len(images[0].data),
        "LOG1 character and presentation backport",
    )
    write_project(directory, meta, enemies=[], characters=[])
    source_dir = directory / "source"
    source_dir.mkdir()
    for path in sorted(SOURCE.iterdir()):
        if path.suffix in (".c", ".s"):
            (source_dir / path.name).write_bytes(path.read_bytes())
    context = RuntimeProject(directory, tools, Path(manifests), images)
    (directory / "patch").mkdir(exist_ok=True)
    for label in ("advance", "visible", "draw", "generic-draw"):
        (directory / f"patch/{label}.bin").write_bytes(bytes(8))
    context.compile_at(
        {
            "runtime": 0x08810000,
            "bf-data": 0x08820000,
            "lg2-data": 0x08860000,
            "log1-sprite-limits": 0x08800000,
        }
    )
    context.document()
    first = materialize_patch(read_patch_document(directory), profile, images[0].data)
    addresses = {p.payload.label: p.allocation.rom_address for p in first.payloads}
    symbols = context.compile_at(addresses)
    for label, function in (
        ("advance", "transform_advance"),
        ("visible", "transform_visible"),
        ("draw", "transform_draw"),
        ("generic-draw", "generic_draw"),
    ):
        (directory / f"patch/{label}.bin").write_bytes(
            bytes.fromhex("004b1847") + (symbols[function] | 1).to_bytes(4, "little")
        )
    context.document()
    graphics = materialize_patch(
        read_patch_document(directory), profile, images[0].data
    )
    if addresses != {
        p.payload.label: p.allocation.rom_address for p in graphics.payloads
    }:
        raise ValueError("runtime payload sizes changed between allocation passes")
    image = images[0].data
    if image[0x2556:0x2562] != bytes.fromhex("f0b5041c0d1ce5b007f0bef9"):
        raise ValueError("retail render entry differs")
    if image[0x5626:0x5632] != bytes.fromhex("fdf70eff0290082000ab185e"):
        raise ValueError("retail melee entry differs")
    if image[0x2F1E:0x2F2A] != bytes.fromhex("6879022803d13168aa6b9142"):
        raise ValueError("retail ki input entry differs")
    if image[0x74BE:0x74CA] != bytes.fromhex("05ab211c381c0ccbfff744ff"):
        raise ValueError("retail damage applier call differs")
    raw = {
        0x74BE: _far_entry(symbols["hit_apply"]),
        0x2556: _far_entry(symbols["render_frame"]),
        0x5626: _far_entry(symbols["melee_probe"]),
        0x2F1E: _far_entry(symbols["ki_request"]),
    }
    for site, function, expected in (
        (0x1669D4, "bf_ki_update", 0x08002B9B),
        (0x1669D8, "bf_ki_advance", 0x08002BB1),
        (0x1C7B14, "projectile_charge_init", 0x0800B4ED),
        (0x1C7B18, "projectile_charge_update", 0x0800B4FB),
        (0x1C7B1C, "projectile_charge_advance", 0x0800B4AF),
        (0x1C7B28, "projectile_init", 0x0800B555),
        (0x1C7B2C, "projectile_update", 0x0800B5A3),
        (0x1C7B30, "projectile_advance", 0x0800AEFB),
        (0x1C7B44, "projectile_impact", 0x0800B4CB),
        (0x1C7B34, "projectile_visible", 0x0800AF81),
        (0x1C7B48, "projectile_visible", 0x0800AF81),
    ):
        if int.from_bytes(image[site : site + 4], "little") != expected:
            raise ValueError(f"retail projectile method differs at file {site:#x}")
        raw[site] = (symbols[function] | 1).to_bytes(4, "little")
    visibility = [
        site
        for site in range(0, len(image) - 3, 4)
        if image[site : site + 4] == bytes.fromhex("81af0008")
    ]
    if len(visibility) != 61:
        raise ValueError("retail visibility method census differs")
    for site in visibility:
        if site != 0x542A60:
            raw.setdefault(site, (symbols["generic_visible"] | 1).to_bytes(4, "little"))
    write_raw_bytes(directory, RawByteEdits(raw))
    presentation_dir = directory / "presentation"
    write_project(presentation_dir, meta, enemies=[], characters=[])
    compose_presentation(presentation_dir, paths[1], image, original)
    presentation = materialize_patch(
        read_patch_document(presentation_dir), original, image
    )
    changes = (
        *graphics.changes,
        *raw_byte_changes(RawByteEdits(raw), image),
        *presentation.changes,
    )
    placed = (*graphics.payloads, *presentation.payloads)
    provenance = tuple(
        PatchPayloadProvenance(
            p.payload.label,
            p.payload.source_class,
            p.payload.transform,
            p.payload.sha256,
            p.payload.size,
            p.payload.alignment,
            p.allocation.range,
            p.allocation.rom_address,
            p.payload.donor_sha256,
            p.payload.donor_span,
            p.owners,
        )
        for p in placed
    )
    generated = graphics.generated_allocations
    plan = plan_changes(
        image,
        changes,
        profile_id=original.id,
        base_sha256=sprite_limits.LOG1_SHA256,
        generated_image=profile.generated_expansion.generated_image(
            len(image), tuple(p.allocated_range for p in generated)
        ),
        generated_allocations=generated,
        patch_payloads=provenance,
    )
    for path, expected in zip(
        paths, (sprite_limits.LOG1_SHA256, BF_SHA256, LOG2_SHA256), strict=True
    ):
        if digest(path) != expected:
            raise ValueError(f"source image changed during runtime preparation: {path}")
    compiler = context.run("gcc", "--version").splitlines()[0]
    manifest = emit_image(
        paths[0], output, plan, manifest_path=str(output) + ".manifest.json"
    )
    report = {
        "rom_sha256": digest(output),
        "allocations": addresses,
        "symbols": symbols,
        "compiler": compiler,
        "compiler_runtime": context.runtime_library,
        "source_sha256": [digest(path) for path in paths],
        "runtime_sources": {
            p.name: digest(p) for p in sorted(source_dir.iterdir()) if p.is_file()
        },
    }
    (directory / "runtime-build.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return manifest, report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build the approved LOG1 character and presentation backport"
    )
    for name in ("rom", "buu", "log2", "output", "project", "manifests"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--toolchain-dir", type=Path)
    args = parser.parse_args(argv)
    _manifest, report = build_runtime(
        args.rom,
        args.buu,
        args.log2,
        args.output,
        args.project,
        args.manifests,
        args.toolchain_dir,
    )
    print(
        json.dumps(
            {
                "rom_sha256": report["rom_sha256"],
                "manifest": str(args.output) + ".manifest.json",
                "project": str(args.project),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
