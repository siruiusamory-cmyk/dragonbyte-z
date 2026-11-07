"""Unit proofs for the shipped BF presentation payloads: pins, fixups, identity.

LOG1-BUU-DIALOGUE-BACKPORT-001. The payload code is lane B's; this file is D's
acceptance of it as BYTES: the shipped binary is the one ``sites.toml`` pins, its
three fixup words are reserved zeros, and every literal it loads is the closed set
its source names. The identity test is the discriminating one - it recomputes the
two speaker palette blobs from the canonical image's own table instead of
transcribing the literals, and it fails if the palette compare stops starting at
LIVE ENTRY 1 (the corrected off-by-one on the 464-byte block).
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tomllib

import pytest

REPO = Path(__file__).resolve().parents[2]
PAYLOAD_DIR = REPO / "tools" / "webfoot" / "patchsource" / "log1-bf-presentation"
SITES = PAYLOAD_DIR / "sites.toml"
BOX_SITES = PAYLOAD_DIR / "box-sites.toml"
TEXT_SITES = PAYLOAD_DIR / "text-sites.toml"
DECLARATIONS = (SITES, BOX_SITES, TEXT_SITES)
ASSEMBLER = Path("C:/devkitPro/devkitARM/bin/arm-none-eabi-as.exe")

LOG1_SHA256 = "3ba9919e26704b0f5fdc2bfabc7f7a0404c71413761d38abcd94224c3bd4b1b9"
DONOR = "940ad5f01db4465b8877dfe739510cbf34f4ea3d390f3df13519808bc36f059e"
DEFAULT_ROM = REPO / "roms" / "Dragon Ball Z - The Legacy of Goku (USA).gba"

PORTRAIT_RECORD_TABLE = 0x0815A4E8
ROSHI_KIND, GOKU_KINDS = 89, (52, 53)

PORTRAIT_LITERALS = frozenset({
    0x08011480,
    0x05000200,
    0x00007FFF,
    0x08541748,
    0x0853E4E8,
    0x00000380,
    0x0200B024,
    0x00001000,
    0x00008000,
    0x0202BE24,
    0x00002000,
    0x0000C000,
    0x08005119,
})
PRESENTATION_LITERALS = frozenset({0x08005381})


def _declaration() -> dict:
    return tomllib.loads(SITES.read_text(encoding="utf-8"))


def assembled_dir() -> Path:
    """Where the assembled payloads are, assembling them first if they are absent.

    The payloads are generated output and ignored, so a clean checkout has none and
    the shipping workflow assembles them before the first `scene init`. Tests that
    read assembled bytes call this and skip when the toolchain cannot produce them,
    which is the state on CI; the source-level tests beside them always run.
    """
    if all((PAYLOAD_DIR / item["file"]).is_file() for item in _declaration()["payload"]):
        return PAYLOAD_DIR
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if shell is None or not ASSEMBLER.is_file():
        pytest.skip("assembled payloads absent and no PowerShell or devkitARM "
                    "assembler on this machine to build them")
    for script in ("assemble.ps1", "assemble-box.ps1"):
        done = subprocess.run(
            [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             str(PAYLOAD_DIR / script), "-Out", str(PAYLOAD_DIR)],
            capture_output=True, text=True)
        assert done.returncode == 0, done.stderr + done.stdout
    return PAYLOAD_DIR


def _payload(label: str) -> tuple[dict, bytes]:
    where = assembled_dir()
    for item in _declaration()["payload"]:
        if item["label"] == label:
            return item, (where / item["file"]).read_bytes()
    raise AssertionError(f"no payload declared with label {label!r}")


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _literal_loads(data: bytes) -> dict[int, int]:
    """Every ``ldr Rd,[pc,#imm]`` in this Thumb block: pool address -> word."""
    halfwords = struct.unpack(f"<{len(data) // 2}H", data)
    loads: dict[int, int] = {}
    for index, halfword in enumerate(halfwords):
        if not 0x4800 <= halfword <= 0x4FFF:
            continue
        pc = ((index * 2) + 4) & ~3
        target = pc + (halfword & 0xFF) * 4
        if target + 4 <= len(data):
            loads[target] = _u32(data, target)
    return loads


def test_every_shipped_payload_is_the_bytes_its_declaration_pins() -> None:
    where = assembled_dir()
    for item in _declaration()["payload"]:
        data = (where / item["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == item["sha256"], item["label"]
        assert data, item["label"]


def test_the_tracked_declaration_sources_assemble_in_a_clean_checkout(
        tmp_path: Path) -> None:
    """The shipping workflow is assemble-then-init, and it needs only tracked files.

    The assembled payloads are generated output and ignored, so the documented flow runs
    the two assemblers before the first `scene init`. This copies EXACTLY the files git
    tracks in the declaration directory into an empty directory, runs both assemblers
    there, and checks every declared digest: nothing from the working tree that git does
    not track takes part, so the workflow cannot be standing on a workstation's
    leftovers. A source edit that was not re-assembled fails here too.
    """
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if shell is None or not ASSEMBLER.is_file():
        pytest.skip("no PowerShell or devkitARM assembler on this machine")
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--", str(PAYLOAD_DIR.relative_to(REPO))],
        cwd=REPO, capture_output=True, check=True).stdout.decode("utf-8").split("\0")
    names = [Path(path).name for path in listed if path]
    assert names, "git lists no tracked declaration file"
    clean = tmp_path / "checkout"
    clean.mkdir()
    for name in names:
        shutil.copy(PAYLOAD_DIR / name, clean / name)
    assert not list(clean.glob("*.bin")), (
        "an assembled payload is tracked; the workflow is supposed to generate it")
    for script in ("assemble.ps1", "assemble-box.ps1"):
        done = subprocess.run(
            [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             str(clean / script), "-Out", str(clean)],
            capture_output=True, text=True)
        assert done.returncode == 0, done.stderr + done.stdout
    for path in DECLARATIONS:
        for item in tomllib.loads(path.read_text(encoding="utf-8"))["payload"]:
            rebuilt = (clean / item["file"]).read_bytes()
            assert hashlib.sha256(rebuilt).hexdigest() == item["sha256"], item["label"]


def test_every_shipped_fixup_names_a_payload_declared_beside_it() -> None:
    """A fixup word is bound by identity: no shipped declaration may omit the name.

    Both lanes name the block each word lives in, which is what lets one offset sit in
    two payloads without the composition guessing. Declaration check only; the binding
    itself is proved by the composition and by `test_fixup_binding.py`.
    """
    for path in DECLARATIONS:
        declaration = tomllib.loads(path.read_text(encoding="utf-8"))
        labels = {item["label"] for item in declaration["payload"]}
        for fixup in declaration.get("fixup", []):
            assert fixup.get("payload") in labels, (path.name, fixup.get("symbol"))


def test_the_three_fixup_words_are_reserved_zeros() -> None:
    """An SDK build fills these; a non-zero word would carry a placeholder address."""
    _, portrait = _payload("bf-portrait")
    fixups = _declaration()["fixup"]
    assert [fixup["offset"] for fixup in fixups] == [0x1CC, 0x1D0, 0x1D4]
    for fixup in fixups:
        slot = fixup["offset"]
        assert portrait[slot:slot + 4] == bytes(4), fixup["symbol"]
    assert max(_literal_loads(portrait)) + 4 <= fixups[0]["offset"]


def test_the_portrait_loads_only_the_literals_its_source_names() -> None:
    _, portrait = _payload("bf-portrait")
    values = set(_literal_loads(portrait).values())
    assert values - PORTRAIT_LITERALS == set()
    _, presentation = _payload("bf-presentation")
    assert set(_literal_loads(presentation).values()) == PRESENTATION_LITERALS


def test_a_shared_bank_shorter_than_the_copied_extent_is_refused() -> None:
    """A 148 B bank must never reach a build: the block copies 39 words from it.

    That is the extent a two-piece conversion emits (both portraits, no box). The
    remaining 8 bytes would be whatever payload the allocator placed next, written
    into the palette window as colours. The guard is the composition's, and it is
    the reason the accepted composition converts the donor's three measured pieces.
    """
    from tools.webfoot.commands.backport import (
        PRESENTATION_PALETTE_COPY_BYTES,
        BackportCommandError,
        _require_shared_bank,
    )
    from tools.webfoot.project import Payload

    bank = Payload(
        label="bf-obj-palette-low128", path=Path("unused"), file="unused",
        source_class="adapted", origin_note="shared low bank", sha256="0" * 64,
        size=148, alignment=4, code=False, transform="bf-obj-palette-low128/v1",
        donor_sha256=DONOR, donor_span="0x05652C-0x05672C",
    )
    with pytest.raises(BackportCommandError, match="copies 156"):
        _require_shared_bank(bank)
    assert PRESENTATION_PALETTE_COPY_BYTES == 156


def test_both_identity_compares_start_at_live_entry_one() -> None:
    """The correction on the 464-byte block: live +2, ROM +2, 15 halfwords.

    Roshi's and Goku's blobs share entry 0 and differ from entry 1 on, so a compare
    built from entry 0 would be off by one halfword on the live side - the defect the
    previous 464-byte candidate carried. Both macro expansions must carry it.
    """
    _, portrait = _payload("bf-portrait")
    halfwords = struct.unpack(f"<{len(portrait) // 2}H", portrait)
    starts = [index for index, halfword in enumerate(halfwords) if halfword == 0x1CA8]
    assert len(starts) == 2, "adds r0, r5, #2 is the live entry-1 base, twice"
    for index in starts:
        load = halfwords[index + 1]
        assert 0x4800 <= load <= 0x4FFF, "the ROM side is loaded, not inlined"
        pc = (((index + 1) * 2) + 4) & ~3
        blob = _u32(portrait, pc + (load & 0xFF) * 4)
        assert blob in (0x08541748, 0x0853E4E8)
        assert halfwords[index + 2] in (0x1C89, 0x3102), hex(halfwords[index + 2])


def _rom() -> bytes:
    value = os.environ.get("WEBFOOT_LOG1_ROM")
    path = Path(value) if value else DEFAULT_ROM
    if not path.is_file():
        pytest.skip("canonical Legacy of Goku image not present locally")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != LOG1_SHA256:
        pytest.skip("local LOG1 image is not canonical")
    return data


def _blob(image: bytes, kind: int) -> int:
    record = _u32(image, PORTRAIT_RECORD_TABLE - 0x08000000 + 4 * kind)
    return _u32(image, record - 0x08000000)


def test_the_identity_literals_are_the_images_own_speaker_blobs() -> None:
    image = _rom()
    roshi = _blob(image, ROSHI_KIND)
    goku = {_blob(image, kind) for kind in GOKU_KINDS}
    assert roshi == 0x08541748
    assert goku == {0x0853E4E8}, "kinds 52 and 53 share one record and one art"
    _, portrait = _payload("bf-portrait")
    assert {roshi, *goku} <= set(_literal_loads(portrait).values())
    assert _u32(image, 0x11490) == 0x08005119


def test_the_two_blobs_are_told_apart_by_entries_one_to_fifteen_only() -> None:
    """Why the compare starts at +2: entry 0 is shared, entries 1..15 are not."""
    image = _rom()
    blobs = {"roshi": _blob(image, ROSHI_KIND), "goku": _blob(image, GOKU_KINDS[0])}
    masked = {
        name: [struct.unpack_from("<H", image, address - 0x08000000 + 2 * index)[0]
               & 0x7FFF for index in range(16)]
        for name, address in blobs.items()
    }
    assert masked["roshi"][0] == masked["goku"][0]
    assert sum(1 for left, right in zip(masked["roshi"][1:], masked["goku"][1:])
               if left != right) >= 1
