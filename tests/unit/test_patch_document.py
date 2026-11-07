"""Unit proofs for the authored patch document and its two encoders.

LOG1-BUU-DIALOGUE-BACKPORT-001. These are the shape and arithmetic checks that do
not need an image: the document's refusals, the structured provenance it requires,
and the ARMv4T Thumb BL range. The ROM-gated family proves placement.
"""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

import pytest

from tools.webfoot.allocation import AllocationKind
from tools.webfoot.binary import GBA_ROM_BASE
from tools.webfoot.profile import RomProfileCatalog
from tools.webfoot.project import (
    PatchDocumentError,
    decode_relative_thumb,
    decode_thumb_bl,
    encode_relative_thumb,
    encode_thumb_bl,
    materialize_patch,
    read_patch_document,
    unauthorized_retail_sites,
)

PATCH = Path("patch") / "edits.toml"
DONOR = "940ad5f01db4465b8877dfe739510cbf34f4ea3d390f3df13519808bc36f059e"


def _payload(project: Path, name: str, data: bytes) -> str:
    path = project / "assets" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _write(project: Path, text: str) -> None:
    path = project / PATCH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _entry(body: str, digest: str = "0" * 64, **overrides) -> str:
    fields = {
        "label": "blob",
        "file": "assets/blob.bin",
        "source_class": "transferred",
        "origin_note": "donor blob",
        "sha256": digest,
        "donor_sha256": DONOR,
        "donor_span": "0x6B880C-0x6B980C",
        "transform": "bf-portrait-unpack/v1",
        "alignment": 4,
    }
    fields.update(overrides)
    lines = [body, ""]
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, str):
            lines.append(f'{key} = "{value}"')
        elif isinstance(value, bool):
            lines.append(f"{key} = {'true' if value else 'false'}")
        else:
            lines.append(f"{key} = {value}")
    return "\n".join(lines) + "\n"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return tmp_path / "project"


def test_a_document_with_no_payload_and_a_hook_is_refused(project: Path):
    _write(project, '[[hook]]\nsite = 0x530E\nexpect = "fdf7a4f8"\n'
                    'target = "blob"\norigin_note = "x"\n')
    with pytest.raises(PatchDocumentError, match="not a payload"):
        read_patch_document(project)


def test_a_payload_whose_digest_is_not_its_file_is_refused(project: Path):
    _payload(project, "blob.bin", b"\x01" * 16)
    _write(project, _entry("[[payload]]", digest="a" * 64))
    with pytest.raises(PatchDocumentError, match="not the bytes on disk"):
        read_patch_document(project)


def test_a_transferred_payload_without_a_donor_fingerprint_is_refused(project: Path):
    digest = _payload(project, "blob.bin", b"\x01" * 16)
    _write(project, _entry("[[payload]]", digest=digest, donor_sha256=None,
                           donor_span=None))
    with pytest.raises(PatchDocumentError, match="donor_sha256"):
        read_patch_document(project)


def test_a_new_payload_that_names_a_donor_is_refused(project: Path):
    digest = _payload(project, "blob.bin", b"\x01" * 16)
    _write(project, _entry("[[payload]]", digest=digest, source_class="new"))
    with pytest.raises(PatchDocumentError, match="its origin is this project"):
        read_patch_document(project)


def test_a_transform_written_as_prose_is_refused(project: Path):
    digest = _payload(project, "blob.bin", b"\x01" * 16)
    _write(project, _entry("[[payload]]", digest=digest,
                           transform="the box was converted"))
    with pytest.raises(PatchDocumentError, match="not prose"):
        read_patch_document(project)


def test_a_hook_may_not_branch_into_transferred_bytes(project: Path):
    digest = _payload(project, "blob.bin", b"\x01" * 16)
    body = _entry("[[payload]]", digest=digest, code=True)
    body += '\n[[hook]]\nsite = 0x530E\nexpect = "fdf7a4f8"\ntarget = "blob"\n' \
            'origin_note = "x"\n'
    _write(project, body)
    with pytest.raises(PatchDocumentError, match="not an adaptation"):
        read_patch_document(project)


def test_a_pointer_declaring_both_forms_is_refused(project: Path):
    digest = _payload(project, "blob.bin", b"\x00" * 16)
    body = _entry("[[payload]]", digest=digest)
    body += '\n[[pointer]]\nsite = 0x530E\nexpect = "fdf7a4f8"\nin = "blob"\n' \
            'at = 0\ntarget = "blob"\norigin_note = "x"\n'
    _write(project, body)
    with pytest.raises(PatchDocumentError, match="exactly one of"):
        read_patch_document(project)


def test_a_data_pointer_to_code_is_refused(project: Path):
    digest = _payload(project, "blob.bin", b"\x00" * 16)
    body = _entry("[[payload]]", digest=digest, code=True, source_class="new",
                  donor_sha256=None, donor_span=None)
    body += '\n[[pointer]]\nsite = 0x530E\nexpect = "fdf7a4f8"\nstate = "data"\n' \
            'target = "blob"\norigin_note = "x"\n'
    _write(project, body)
    with pytest.raises(PatchDocumentError, match="Thumb bit"):
        read_patch_document(project)


def test_an_unknown_top_level_key_is_refused(project: Path):
    _write(project, "[text]\noffset = 0\n")
    with pytest.raises(PatchDocumentError, match="unknown top-level key"):
        read_patch_document(project)




def test_the_thumb_bl_round_trips_and_keeps_its_state_bit():
    site = 0x530E
    target = 0x1519EC
    encoded = encode_thumb_bl(site, target)
    assert len(encoded) == 4
    assert decode_thumb_bl(site, encoded) == target
    assert encoded[1] & 0xF8 == 0xF0
    assert encoded[3] & 0xF8 == 0xF8


def test_the_thumb_bl_range_is_four_mebibytes_and_is_enforced():
    site = 0x530E
    inside = site + 4 + 0x3FFFFE
    assert decode_thumb_bl(site, encode_thumb_bl(site, inside)) == inside
    outside = site + 4 + 0x400000
    with pytest.raises(PatchDocumentError, match="ARMv4T Thumb BL range"):
        encode_thumb_bl(site, outside)


def test_a_thumb_bl_needs_halfword_alignment():
    with pytest.raises(PatchDocumentError, match="halfword alignment"):
        encode_thumb_bl(0x530E, 0x5313)




def _log1_profile(*, seams: bool = True):
    catalog = RomProfileCatalog.load("config/roms.yaml")
    profile = next(p for p in catalog.profiles if p.id == "legacy_of_goku_usa_a3c8c767")
    return profile if seams else dataclasses.replace(profile, patch_sites=None)


def _project_with(tmp_path: Path, body: str, blobs: dict[str, bytes]) -> Path:
    project = tmp_path / "placed"
    project.mkdir()
    for name, data in blobs.items():
        path = project / "assets" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (project / PATCH).parent.mkdir(parents=True, exist_ok=True)
    (project / PATCH).write_text(body, encoding="utf-8")
    return project


def test_a_payload_lands_in_a_declared_window_and_the_manifest_records_its_origin(
        tmp_path: Path):
    profile = _log1_profile()
    image = bytes([0xFF]) * profile.size
    portrait = bytes(range(16))
    digest = hashlib.sha256(portrait).hexdigest()
    holder = bytes(16)
    holder_digest = hashlib.sha256(holder).hexdigest()
    body = (
        "[[payload]]\nlabel = \"a-code\"\nfile = \"assets/holder.bin\"\n"
        f"source_class = \"new\"\norigin_note = \"compat\"\nsha256 = \"{holder_digest}\"\n"
        "transform = \"log1-compat/v1\"\nalignment = 4\ncode = true\n\n"
        "[[payload]]\nlabel = \"b-portrait\"\nfile = \"assets/portrait.bin\"\n"
        f"source_class = \"transferred\"\norigin_note = \"BF slot 97\"\n"
        f"sha256 = \"{digest}\"\ndonor_sha256 = \"{DONOR}\"\n"
        "donor_span = \"0x6B880C-0x6B980C\"\ntransform = \"bf-portrait-unpack/v1\"\n"
        "alignment = 4\n\n"
        "[[pointer]]\nin = \"a-code\"\nat = 4\ntarget = \"b-portrait\"\n"
        "origin_note = \"portrait address\"\n"
    )
    document = read_patch_document(
        _project_with(tmp_path, body, {"holder.bin": holder, "portrait.bin": portrait}))
    result = materialize_patch(document, profile, image)

    placed = {payload.payload.label: payload for payload in result.payloads}
    assert placed["a-code"].allocation.request.kind is AllocationKind.PATCH_PAYLOAD
    assert placed["b-portrait"].allocation.request.kind is AllocationKind.PATCH_PAYLOAD
    addresses = {label: placed[label].allocation.range.start.value + GBA_ROM_BASE
                 for label in placed}
    assert addresses["a-code"] != addresses["b-portrait"]
    code_change = next(c for c in result.changes if c.offset ==
                       placed["a-code"].allocation.range.start.value)
    assert code_change.new[4:8] == addresses["b-portrait"].to_bytes(4, "little")
    assert code_change.owner == "payload:a-code"
    assert "new: log1-compat/v1" in code_change.reason


def test_a_guarded_write_span_may_contain_unchanged_bytes(tmp_path: Path):
    """`changes` is the write set, not a diff: a span can repeat canonical bytes.

    The payload below ends in the same 0xFF fill as the free window it lands in, which
    is the normal case for code and for space-padded text. The span still records all
    16 bytes; only 4 of them differ. A verifier of diff confinement must therefore
    require every differing byte to lie inside a declared span, never every declared
    byte to differ.
    """
    profile = _log1_profile()
    image = bytes([0xFF]) * profile.size
    code = bytes([0x10]) * 4 + bytes([0xFF]) * 12
    document = read_patch_document(_project_with(tmp_path, (
        "[[payload]]\nlabel = \"helper\"\nfile = \"assets/code.bin\"\n"
        "source_class = \"new\"\norigin_note = \"compat\"\n"
        f"sha256 = \"{hashlib.sha256(code).hexdigest()}\"\n"
        "transform = \"log1-compat/v1\"\nalignment = 4\ncode = true\n"
    ), {"code.bin": code}))
    change = materialize_patch(document, profile, image).changes[0]
    assert change.size == 16
    assert change.old == bytes([0xFF]) * 16
    assert change.new == code
    assert sum(1 for a, b in zip(change.old, change.new) if a != b) == 4




def _update_project(tmp_path: Path, site: int, expect: str, base: int,
                    code: bytes) -> Path:
    body = (
        "[[payload]]\nlabel = \"controller\"\nfile = \"assets/code.bin\"\n"
        "source_class = \"new\"\norigin_note = \"update controller\"\n"
        f"sha256 = \"{hashlib.sha256(code).hexdigest()}\"\n"
        "transform = \"log1-compat/v1\"\nalignment = 4\ncode = true\n\n"
        "[[relative]]\n"
        f"site = 0x{site:06x}\nexpect = \"{expect}\"\nbase = 0x{base:08x}\n"
        "target = \"controller\"\norigin_note = \"NPC per-frame update method\"\n"
    )
    return _project_with(tmp_path, body, {"code.bin": code})


def test_the_per_frame_update_word_is_admitted_with_its_table_base(tmp_path: Path):
    """Entry +0x1C of table 0x0800EF28 resolves to update 0x08005392.

    Canonical word 0xFFFF646B, one occurrence in the image. E measured 1,319 entries in
    1,500 frames (one per frame, frames 181..1499) with lr = 0x08005BA3. The admission
    is this one offset WITH this base: the encoders refuse the site without it.
    """
    profile = _log1_profile()
    image = bytearray([0xFF]) * profile.size
    image[0xEF44:0xEF48] = bytes.fromhex("6b64ffff")
    document = read_patch_document(
        _update_project(tmp_path, 0xEF44, "6b64ffff", 0x0800EF28, bytes(24)))
    assert unauthorized_retail_sites(document, profile) == []
    result = materialize_patch(document, profile, bytes(image))
    change = next(c for c in result.changes if c.offset == 0xEF44)
    placed = result.payloads[0].allocation
    assert change.old == bytes.fromhex("6b64ffff")
    assert int.from_bytes(change.new, "little", signed=True) == \
        (placed.rom_address + 1) - 0x0800EF28
    assert decode_relative_thumb(change.new, 0x0800EF28) == placed.rom_address | 1


def test_another_word_of_the_same_method_table_is_still_refused(tmp_path: Path):
    """The +0x14 word is real table data, so only the declared offset is admitted."""
    profile = _log1_profile()
    image = bytearray([0xFF]) * profile.size
    image[0xEF40:0xEF44] = bytes.fromhex("85040000")
    document = read_patch_document(
        _update_project(tmp_path, 0xEF40, "85040000", 0x0800EF28, bytes(24)))
    with pytest.raises(PatchDocumentError,
                       match="authorises no relative entry at file 0x00EF40"):
        materialize_patch(document, profile, bytes(image))


def test_the_update_word_is_refused_against_a_different_table_base(tmp_path: Path):
    """A correct offset with the wrong base writes a value the consumer mis-resolves."""
    profile = _log1_profile()
    image = bytearray([0xFF]) * profile.size
    image[0xEF44:0xEF48] = bytes.fromhex("6b64ffff")
    document = read_patch_document(
        _update_project(tmp_path, 0xEF44, "6b64ffff", 0x0800F094, bytes(24)))
    with pytest.raises(PatchDocumentError,
                       match="uses base 0x0800EF28, the document says 0x0800F094"):
        materialize_patch(document, profile, bytes(image))


def test_the_update_word_is_refused_when_the_image_does_not_hold_it(tmp_path: Path):
    """A document written for another revision is refused by its guarded bytes."""
    profile = _log1_profile()
    image = bytearray([0xFF]) * profile.size
    image[0xEF44:0xEF48] = bytes.fromhex("6b64ffff")
    document = read_patch_document(
        _update_project(tmp_path, 0xEF44, "116cffff", 0x0800EF28, bytes(24)))
    with pytest.raises(PatchDocumentError,
                       match="this image holds 6b64ffff there, the document expects"):
        materialize_patch(document, profile, bytes(image))



def _geometry_project(tmp_path: Path, site: int, expect: str, code: bytes) -> Path:
    body = (
        "[[payload]]\nlabel = \"geometry\"\nfile = \"assets/code.bin\"\n"
        "source_class = \"new\"\norigin_note = \"page geometry\"\n"
        f"sha256 = \"{hashlib.sha256(code).hexdigest()}\"\n"
        "transform = \"log1-compat/v1\"\nalignment = 4\ncode = true\n\n"
        "[[pointer]]\n"
        f"site = 0x{site:06x}\nexpect = \"{expect}\"\ntarget = \"geometry\"\n"
        "origin_note = \"dialogue method table word\"\n"
    )
    return _project_with(tmp_path, body, {"code.bin": code})


def test_the_box_geometry_word_is_admitted_and_the_pointer_lands(tmp_path: Path):
    """Word +0x00 of the table 0x08011480 is a declared retail seam.

    Canonical bytes 09510008 point at 0x08005108, a bare `bx lr`, so the seam's own
    code had no behaviour. E measured 8 entries per 3600-frame run with lr = 0x08002465.
    The admission is exactly this one offset: the pointer lands there, guarded by its
    canonical expect bytes, and the document is authorised by the shipped profile.
    """
    profile = _log1_profile()
    image = bytearray([0xFF]) * profile.size
    image[0x11480:0x11484] = bytes.fromhex("09510008")
    document = read_patch_document(_geometry_project(tmp_path, 0x11480, "09510008",
                                                      bytes(8)))
    assert unauthorized_retail_sites(document, profile) == []
    result = materialize_patch(document, profile, bytes(image))
    change = next(c for c in result.changes if c.offset == 0x11480)
    placed = result.payloads[0].allocation
    assert change.old == bytes.fromhex("09510008")
    assert int.from_bytes(change.new, "little") == placed.rom_address | 1


def test_an_unrelated_word_of_the_same_table_is_still_refused(tmp_path: Path):
    """Matching expect bytes are not an authorisation: +0x04 is not declared.

    The word below is real table data (0x000AEFF9, the +0x04 entry), so a guard that
    only compared ``expect`` would accept it.
    """
    profile = _log1_profile()
    image = bytearray([0xFF]) * profile.size
    image[0x11484:0x11488] = bytes.fromhex("f9ae0008")
    document = read_patch_document(_geometry_project(tmp_path, 0x11484, "f9ae0008",
                                                      bytes(8)))
    with pytest.raises(PatchDocumentError, match="authorises no pointer at file 0x011484"):
        materialize_patch(document, profile, bytes(image))


def test_a_direct_branch_to_an_out_of_range_window_is_refused(tmp_path: Path):
    profile = _log1_profile(seams=False)
    image = bytes([0xFF]) * profile.size
    code = bytes(16)
    digest = hashlib.sha256(code).hexdigest()
    body = (
        "[[payload]]\nlabel = \"far\"\nfile = \"assets/code.bin\"\n"
        f"source_class = \"new\"\norigin_note = \"compat\"\nsha256 = \"{digest}\"\n"
        "transform = \"log1-compat/v1\"\nalignment = 4\ncode = true\n\n"
        "[[hook]]\nsite = 0x530E\nexpect = \"fdf7a4f8\"\ntarget = \"far\"\n"
        "origin_note = \"publish\"\n"
    )
    document = read_patch_document(_project_with(tmp_path, body, {"code.bin": code}))
    with pytest.raises(PatchDocumentError, match="Thumb BL range"):
        materialize_patch(document, profile, image)




RELATIVE_BASE = 0x0800F094


def test_the_relative_entry_round_trips_and_sets_the_thumb_bit():
    payload = 0x087E8DCC
    encoded = encode_relative_thumb(payload + 1, RELATIVE_BASE)
    assert len(encoded) == 4
    assert int.from_bytes(encoded, "little", signed=True) == payload + 1 - RELATIVE_BASE
    assert decode_relative_thumb(encoded, RELATIVE_BASE) == payload + 1


def test_a_negative_relative_entry_round_trips():
    payload = 0x08001000
    encoded = encode_relative_thumb(payload + 1, RELATIVE_BASE)
    assert int.from_bytes(encoded, "little", signed=True) < 0
    assert decode_relative_thumb(encoded, RELATIVE_BASE) == payload + 1


def test_a_relative_base_outside_the_rom_window_is_refused():
    with pytest.raises(PatchDocumentError, match="Game Pak ROM window"):
        encode_relative_thumb(0x087E8DCD, 0x02000000)


def test_a_relative_base_that_is_not_word_aligned_is_refused():
    with pytest.raises(PatchDocumentError, match="not word aligned"):
        encode_relative_thumb(0x087E8DCD, 0x0800F096)


def test_a_relative_target_without_a_thumb_bit_is_refused():
    with pytest.raises(PatchDocumentError, match="no Thumb state bit"):
        encode_relative_thumb(0x087E8DCC, RELATIVE_BASE)


def test_a_relative_document_entry_needs_declared_code(project: Path):
    digest = _payload(project, "blob.bin", b"\x00" * 16)
    body = _entry("[[payload]]", digest=digest)
    body += ('\n[[relative]]\nsite = 0xF09C\nexpect = "e35dffff"\n'
             'base = 0x0800F094\ntarget = "blob"\norigin_note = "page method"\n')
    _write(project, body)
    with pytest.raises(PatchDocumentError, match="must reach executable bytes"):
        read_patch_document(project)


def test_a_relative_entry_resolves_to_the_placed_payload(tmp_path: Path):
    profile = _log1_profile(seams=False)
    image = bytearray([0xFF]) * profile.size
    image[0xF09C:0xF0A0] = bytes.fromhex("e35dffff")
    code = bytes(24)
    digest = hashlib.sha256(code).hexdigest()
    project = _project_with(tmp_path, (
        "[[payload]]\nlabel = \"wrapper\"\nfile = \"assets/code.bin\"\n"
        f"source_class = \"new\"\norigin_note = \"compat\"\nsha256 = \"{digest}\"\n"
        "transform = \"log1-compat/v1\"\nalignment = 4\ncode = true\n\n"
        "[[relative]]\nsite = 0xF09C\nexpect = \"e35dffff\"\n"
        "base = 0x0800F094\ntarget = \"wrapper\"\n"
        "origin_note = \"page +0x08 method\"\n"
    ), {"code.bin": code})
    document = read_patch_document(project)
    result = materialize_patch(document, profile, bytes(image))
    placed = result.payloads[0].allocation
    change = next(c for c in result.changes if c.offset == 0xF09C)
    assert change.old == bytes.fromhex("e35dffff")
    assert change.owner == "relative:0x0800F09C"
    expected = placed.range.start.value + GBA_ROM_BASE + 1 - RELATIVE_BASE
    assert int.from_bytes(change.new, "little", signed=True) == expected
    assert decode_relative_thumb(change.new, RELATIVE_BASE) == placed.rom_address + 1
    assert "relative:0x0800F09C" in result.payloads[0].owners


def test_a_written_document_reads_back_as_the_same_value(tmp_path: Path):
    from tools.webfoot.project import write_patch_document

    digest = _payload(tmp_path, "blob.bin", b"\x01" * 24)
    body = _entry("[[payload]]", digest=digest, code=True, source_class="new",
                  donor_sha256=None, donor_span=None)
    body += ('\n[[relative]]\nsite = 0xEF30\nexpect = "5964ffff"\n'
             'base = 0x0800EF28\ntarget = "blob"\norigin_note = "NPC draw"\n')
    body += ('\n[[pointer]]\nin = "blob"\nat = 0x8\ntarget = "blob"\n'
             'origin_note = "self slot"\n')
    _write(tmp_path, body)
    first = read_patch_document(tmp_path)
    write_patch_document(tmp_path, first)
    assert read_patch_document(tmp_path) == first
    path = tmp_path / PATCH
    once = path.read_bytes()
    write_patch_document(tmp_path, first)
    assert path.read_bytes() == once
