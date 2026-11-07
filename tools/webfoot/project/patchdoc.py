"""The authored patch document: allocated payloads and the two fixups they need.

LOG1-BUU-DIALOGUE-BACKPORT-001. A presentation adaptation needs three things no
declared table can express: bytes that have no canonical home (a code block, a
donor-derived resource blob), a branch or pointer into those bytes, and the
provenance of where those bytes came from. This module reads the document that
states them and mints ordinary :class:`~tools.webfoot.write.ByteChange` objects
from it, so a patch payload reaches the image through the SAME single plan,
allocator, overlap guard and expected-base check every other domain uses.

**Payloads only.** An in-place text edit is not here: it is a raw byte write the
existing ``raw/bytes.toml`` document already carries, and this toolkit does not
get a second interpreter for the same job. What this document adds is exactly the
part a raw write cannot state - "these bytes have no address yet, place them and
tell me where", and "these four bytes name that placement".

**Two seams, and only two.** A direct branch (:class:`Hook`) is a Thumb BL, which
on this CPU is ARMv4T: a 22-bit signed halfword offset, ±4 MiB from ``site + 4``.
The Thumb-2 J1/J2 form is not emitted and the range is checked, not assumed. A
typed pointer (:class:`Pointer`) writes the allocated address into a 4-byte word -
a retail function pointer, a vtable slot, or a zeroed slot inside another payload -
with the Thumb state bit when the target is code. Neither is a branch language and
neither is a linker: there is one encoder per seam.

**Provenance is structured, not prose.** A payload declares the closed class it
belongs to (``transferred`` / ``adapted`` / ``new``), the donor image digest and
donor span it came from, the named transform that produced it, and the digest of
the exact bytes. The build refuses a ``transferred``/``adapted`` payload without a
donor fingerprint, and the manifest records those fields plus the placement the
allocator chose. A note alone is not provenance and is never read as such.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
import re
import struct
from pathlib import Path
from typing import Mapping

from ..allocation import (
    ALLOCATABLE_REGION_CLASSES, Allocation, AllocationKind, AllocationRequest,
    InsufficientSpaceError, StorageModel, allocate,
)
from ..binary import GBA_ROM_BASE
from ..layout import AnchorId, FileOffset, OwnedRegion, RomRange
from ..profile import RomProfile
from ..write import ByteChange, GeneratedAllocationProvenance
from .format import ProjectFormatError, load_toml

PATCH_FILE = Path("patch") / "edits.toml"

PATCH_TABLES = frozenset({"payload", "hook", "pointer", "relative"})

SOURCE_CLASSES = ("transferred", "adapted", "new")

THUMB_BL_RANGE = 0x400000

_LABEL = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_TRANSFORM = re.compile(r"^[a-z0-9][a-z0-9./-]*$")
_DONOR_SPAN = re.compile(r"^0x[0-9A-Fa-f]+-0x[0-9A-Fa-f]+$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class PatchDocumentError(ProjectFormatError):
    """The patch document is unreadable, and a build must not proceed."""


@dataclass(frozen=True, slots=True)
class Payload:
    label: str
    path: Path
    file: str
    source_class: str
    origin_note: str
    sha256: str
    size: int
    alignment: int
    code: bool
    transform: str
    donor_sha256: str | None
    donor_span: str | None

    @property
    def owner(self) -> str:
        return f"payload:{self.label}"


@dataclass(frozen=True, slots=True)
class Hook:
    site: int
    expect: bytes
    target: str
    origin_note: str

    @property
    def owner(self) -> str:
        return f"hook:0x{GBA_ROM_BASE + self.site:08X}"


@dataclass(frozen=True, slots=True)
class Pointer:
    target: str
    state: str
    origin_note: str
    site: int | None = None
    expect: bytes | None = None
    container: str | None = None
    at: int | None = None

    @property
    def owner(self) -> str:
        if self.site is not None:
            return f"pointer:0x{GBA_ROM_BASE + self.site:08X}"
        return f"pointer:{self.container}+0x{self.at:04X}"


@dataclass(frozen=True, slots=True)
class Relative:
    """One signed branch offset into a method table, resolved to a payload.

    The LOG1 page object holds a table base and each method slot is a SIGNED
    32-bit offset from that base, which the consumer adds and hands to ``bx``
    in the canonical bytes at ``0x0800982c``: ``ldr r2,[r1,#8]`` / ``add r1,r2,r1``
    / ``bl 0x0800E4A2`` (``bx r1``). Writing an absolute address there would make
    the engine branch to ``table + address``, so this entry is a separate shape
    on purpose and the absolute :class:`Pointer` encoder refuses the site.

    The stored value is ``(payload_gba + 1) - base``: the low bit is the ARM7TDMI
    interworking state bit, which this consumer takes from the value itself.
    """

    site: int
    expect: bytes
    base: int
    target: str
    origin_note: str

    @property
    def owner(self) -> str:
        return f"relative:0x{GBA_ROM_BASE + self.site:08X}"


def encode_relative_thumb(payload_rom_address: int, base: int) -> bytes:
    """The signed 32-bit method-table entry that reaches `payload_rom_address`.

    Refuses a base outside the Game Pak window, a base that is not word aligned,
    a value that does not fit a signed 32-bit field, and a value that does not
    resolve back to the payload with its Thumb bit - the last is the guard the
    coordinator asked for, so a mis-scaled or mis-signed offset cannot ship.
    """
    if not GBA_ROM_BASE <= base < GBA_ROM_BASE + 0x02000000:
        raise PatchDocumentError(
            f"relative base 0x{base:08X} is outside the Game Pak ROM window"
        )
    if base % 4:
        raise PatchDocumentError(
            f"relative base 0x{base:08X} is not word aligned; a method table is"
        )
    if payload_rom_address % 2 == 0:
        raise PatchDocumentError(
            f"relative target 0x{payload_rom_address:08X} has no Thumb state bit"
        )
    value = payload_rom_address - base
    if not -(1 << 31) <= value < (1 << 31):
        raise PatchDocumentError(
            f"relative value {value} from base 0x{base:08X} does not fit signed 32"
        )
    resolved = (base + value) & ~1
    if resolved != payload_rom_address & ~1:
        raise PatchDocumentError(
            f"relative entry from base 0x{base:08X} resolves to 0x{resolved:08X}, "
            f"not to the payload at 0x{payload_rom_address & ~1:08X}"
        )
    return struct.pack("<i", value)


def decode_relative_thumb(data: bytes, base: int) -> int:
    """The GBA address a stored signed entry resolves to. Inverse of the above."""
    if len(data) != 4:
        raise PatchDocumentError("a relative entry is four bytes")
    value = struct.unpack("<i", data)[0]
    return base + value


@dataclass(frozen=True, slots=True)
class PatchDocument:
    payloads: tuple[Payload, ...] = ()
    hooks: tuple[Hook, ...] = ()
    pointers: tuple[Pointer, ...] = ()
    relatives: tuple[Relative, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.payloads or self.hooks or self.pointers
                    or self.relatives)

    def payload(self, label: str) -> Payload:
        for payload in self.payloads:
            if payload.label == label:
                return payload
        raise PatchDocumentError(f"no payload named {label!r}")


@dataclass(frozen=True, slots=True)
class PatchMaterialization:
    changes: tuple[ByteChange, ...]
    allocations: tuple[Allocation, ...]
    reservations: tuple[OwnedRegion, ...]
    generated_allocations: tuple[GeneratedAllocationProvenance, ...]
    payloads: tuple["PlacedPayload", ...]


@dataclass(frozen=True, slots=True)
class PlacedPayload:
    payload: Payload
    allocation: Allocation
    owners: tuple[str, ...]




def encode_thumb_bl(site_offset: int, target_offset: int) -> bytes:
    """The two halfwords of an ARMv4T Thumb ``bl`` from `site` to `target`.

    Both arguments are FILE offsets; the encoded offset is the byte distance from
    ``site + 4`` to the target, which must be even and inside ±4 MiB. A caller
    that gets this wrong is refused rather than given a wrapped branch.
    """
    delta = target_offset - (site_offset + 4)
    if delta % 2:
        raise PatchDocumentError(
            f"hook site 0x{site_offset:06X} and target 0x{target_offset:06X} are an "
            "odd distance apart; a Thumb branch needs halfword alignment"
        )
    immediate = delta >> 1
    if not -(1 << 21) <= immediate < (1 << 21):
        raise PatchDocumentError(
            f"hook site 0x{site_offset:06X} cannot reach target "
            f"0x{target_offset:06X}: {abs(delta):#x} bytes is outside the ARMv4T "
            f"Thumb BL range of ±{THUMB_BL_RANGE:#x}"
        )
    first = 0xF000 | ((immediate >> 11) & 0x7FF)
    second = 0xF800 | (immediate & 0x7FF)
    return struct.pack("<HH", first, second)


def decode_thumb_bl(site_offset: int, data: bytes) -> int:
    """The file offset a Thumb ``bl`` at `site` branches to. Inverse of the above."""
    if len(data) < 4:
        raise PatchDocumentError("a Thumb bl is four bytes")
    first, second = struct.unpack_from("<HH", data)
    immediate = ((first & 0x7FF) << 11) | (second & 0x7FF)
    if immediate & 0x200000:
        immediate -= 0x400000
    return site_offset + 4 + (immediate << 1)


def _pointer_word(allocated_rom_address: int, state: str) -> bytes:
    if state == "thumb":
        return struct.pack("<I", allocated_rom_address | 1)
    if state == "arm":
        return struct.pack("<I", allocated_rom_address & ~1)
    return struct.pack("<I", allocated_rom_address)




def _require(mapping: Mapping, key: str, where: str):
    if key not in mapping:
        raise PatchDocumentError(f"{where}: missing required key {key!r}")
    return mapping[key]


def _string(mapping: Mapping, key: str, where: str, *, allow_empty: bool = False) -> str:
    value = _require(mapping, key, where)
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise PatchDocumentError(f"{where}: {key} must be a non-empty string")
    return value.strip()


def _offset(mapping: Mapping, key: str, where: str) -> int:
    value = _require(mapping, key, where)
    if type(value) is not int or value < 0:
        raise PatchDocumentError(f"{where}: {key} must be a non-negative file offset")
    return value


def _offset_gba(mapping: Mapping, key: str, where: str) -> int:
    value = _require(mapping, key, where)
    if type(value) is not int or value < GBA_ROM_BASE:
        raise PatchDocumentError(
            f"{where}: {key} must be a GBA ROM address (0x08000000 or above)"
        )
    return value


def _hex4(mapping: Mapping, key: str, where: str) -> bytes:
    value = _string(mapping, key, where)
    try:
        data = bytes.fromhex(value)
    except ValueError as exc:
        raise PatchDocumentError(f"{where}: {key} is not hexadecimal") from exc
    if len(data) != 4:
        raise PatchDocumentError(f"{where}: {key} must be exactly 4 bytes")
    return data


def _hex_digest(mapping: Mapping, key: str, where: str) -> str:
    value = _string(mapping, key, where).lower()
    if not _DIGEST.match(value):
        raise PatchDocumentError(f"{where}: {key} must be a lowercase sha256")
    return value


def read_patch_document(directory: str | Path) -> PatchDocument:
    """Read a project's patch document, or nothing when it authors none.

    Absence is the only empty answer. A document that exists must parse, may hold
    only the three known tables, and every entry is validated here - including the
    payload's own digest, which is computed from the file on disk so the document
    pins the exact bytes a build will write.
    """
    path = Path(directory) / PATCH_FILE
    if not path.exists():
        return PatchDocument()
    try:
        document = load_toml(path.read_text(encoding="utf-8"))
    except (ProjectFormatError, OSError) as exc:
        raise PatchDocumentError(f"{path}: {exc}") from exc
    unknown = set(document) - PATCH_TABLES
    if unknown:
        raise PatchDocumentError(
            f"{path}: unknown top-level key(s) {sorted(unknown)}; a patch document "
            f"holds {sorted(PATCH_TABLES)}"
        )

    root = Path(directory)
    payloads: list[Payload] = []
    labels: set[str] = set()
    for index, item in enumerate(document.get("payload", []) or []):
        where = f"{path}: payload {index}"
        if not isinstance(item, Mapping):
            raise PatchDocumentError(f"{where} must be a table")
        label = _string(item, "label", where)
        if not _LABEL.match(label):
            raise PatchDocumentError(
                f"{where}: label {label!r} must be lower-case words joined by '-'"
            )
        if label in labels:
            raise PatchDocumentError(f"{where}: duplicate payload label {label!r}")
        labels.add(label)
        source_class = _string(item, "source_class", where)
        if source_class not in SOURCE_CLASSES:
            raise PatchDocumentError(
                f"{where}: source_class must be one of {SOURCE_CLASSES}"
            )
        transform = _string(item, "transform", where)
        if not _TRANSFORM.match(transform):
            raise PatchDocumentError(
                f"{where}: transform must be a name (lower-case, no spaces), not prose"
            )
        alignment = _require(item, "alignment", where)
        if type(alignment) is not int or not 4 <= alignment <= 256 or alignment & (alignment - 1):
            raise PatchDocumentError(f"{where}: alignment must be a power of two, 4..256")
        code = item.get("code", False)
        if not isinstance(code, bool):
            raise PatchDocumentError(f"{where}: code must be true or false")
        file_value = _string(item, "file", where)
        payload_path = (root / file_value).resolve()
        if not payload_path.is_file():
            raise PatchDocumentError(f"{where}: payload file {file_value!r} is absent")
        data = payload_path.read_bytes()
        if not data:
            raise PatchDocumentError(f"{where}: payload file {file_value!r} is empty")
        declared = _hex_digest(item, "sha256", where)
        actual = hashlib.sha256(data).hexdigest()
        if declared != actual:
            raise PatchDocumentError(
                f"{where}: payload file is {actual}, the document declares {declared}; "
                "the authored bytes are not the bytes on disk"
            )
        donor_sha256 = donor_span = None
        if source_class == "new":
            for key in ("donor_sha256", "donor_span"):
                if item.get(key) is not None:
                    raise PatchDocumentError(
                        f"{where}: a 'new' payload declares {key}; its origin is this "
                        "project, not a donor"
                    )
        else:
            donor_sha256 = _hex_digest(item, "donor_sha256", where)
            donor_span = _string(item, "donor_span", where)
            if not _DONOR_SPAN.match(donor_span):
                raise PatchDocumentError(
                    f"{where}: donor_span must be '0xSTART-0xEND'"
                )
        payloads.append(
            Payload(
                label=label,
                path=payload_path,
                file=file_value,
                source_class=source_class,
                origin_note=_string(item, "origin_note", where),
                sha256=actual,
                size=len(data),
                alignment=alignment,
                code=code,
                transform=transform,
                donor_sha256=donor_sha256,
                donor_span=donor_span,
            )
        )

    by_label = {payload.label: payload for payload in payloads}
    hooks: list[Hook] = []
    for index, item in enumerate(document.get("hook", []) or []):
        where = f"{path}: hook {index}"
        if not isinstance(item, Mapping):
            raise PatchDocumentError(f"{where} must be a table")
        site = _offset(item, "site", where)
        target = _string(item, "target", where)
        if target not in by_label:
            raise PatchDocumentError(f"{where}: target {target!r} is not a payload")
        if not by_label[target].code:
            raise PatchDocumentError(
                f"{where}: target {target!r} is not declared code"
            )
        if by_label[target].source_class == "transferred":
            raise PatchDocumentError(
                f"{where}: target {target!r} is transferred donor bytes; a branch into "
                "donor code is not an adaptation"
            )
        hooks.append(
            Hook(
                site=site,
                expect=_hex4(item, "expect", where),
                target=target,
                origin_note=_string(item, "origin_note", where),
            )
        )

    pointers: list[Pointer] = []
    for index, item in enumerate(document.get("pointer", []) or []):
        where = f"{path}: pointer {index}"
        if not isinstance(item, Mapping):
            raise PatchDocumentError(f"{where} must be a table")
        target = _string(item, "target", where)
        if target not in by_label:
            raise PatchDocumentError(f"{where}: target {target!r} is not a payload")
        site = item.get("site")
        container = item.get("in")
        if (site is None) == (container is None):
            raise PatchDocumentError(
                f"{where}: declare exactly one of site (a retail word) or in (a payload)"
            )
        if site is not None:
            site = _offset(item, "site", where)
            expect: bytes | None = _hex4(item, "expect", where)
            at = None
        else:
            container = _string(item, "in", where)
            if container not in by_label:
                raise PatchDocumentError(f"{where}: in {container!r} is not a payload")
            at = _offset(item, "at", where)
            if at + 4 > by_label[container].size:
                raise PatchDocumentError(
                    f"{where}: at 0x{at:X} leaves no 4-byte word inside {container!r}"
                )
            expect = None
            site = None
        default_state = "thumb" if by_label[target].code else "data"
        state = item.get("state", default_state)
        if state not in ("thumb", "arm", "data"):
            raise PatchDocumentError(f"{where}: state must be thumb, arm or data")
        if state == "data" and by_label[target].code:
            raise PatchDocumentError(
                f"{where}: target {target!r} is code; a pointer to it needs the Thumb bit"
            )
        if state == "arm" and not by_label[target].code:
            raise PatchDocumentError(f"{where}: arm state is for code targets only")
        pointers.append(
            Pointer(
                target=target,
                state=state,
                origin_note=_string(item, "origin_note", where),
                site=site,
                expect=expect,
                container=container,
                at=at,
            )
        )

    relatives: list[Relative] = []
    for index, item in enumerate(document.get("relative", []) or []):
        where = f"{path}: relative {index}"
        if not isinstance(item, Mapping):
            raise PatchDocumentError(f"{where} must be a table")
        target = _string(item, "target", where)
        if target not in by_label:
            raise PatchDocumentError(f"{where}: target {target!r} is not a payload")
        if not by_label[target].code:
            raise PatchDocumentError(
                f"{where}: target {target!r} is not declared code; a method-table "
                "entry must reach executable bytes"
            )
        relatives.append(
            Relative(
                site=_offset(item, "site", where),
                expect=_hex4(item, "expect", where),
                base=_offset_gba(item, "base", where),
                target=target,
                origin_note=_string(item, "origin_note", where),
            )
        )

    return PatchDocument(tuple(payloads), tuple(hooks), tuple(pointers),
                         tuple(relatives))




def patch_image_problems(document: PatchDocument, image: bytes) -> list[str]:
    """Every entry whose expected bytes are not the image's, named.

    The plan refuses these too, but by then a caller has paid for loading a
    project; this is the shape `validate` reports, and it says which site is
    wrong instead of which change.
    """
    problems: list[str] = []
    for hook in document.hooks:
        actual = image[hook.site : hook.site + 4]
        if len(actual) != 4:
            problems.append(
                f"hook site 0x{hook.site:06X} is past the image; it cannot hold 4 bytes"
            )
        elif actual != hook.expect:
            problems.append(
                f"hook site 0x{hook.site:06X} is {actual.hex()} in this image, but the "
                f"document expects {hook.expect.hex()}; the hook targets another revision"
            )
    for relative in document.relatives:
        actual = image[relative.site : relative.site + 4]
        if len(actual) != 4:
            problems.append(
                f"relative site 0x{relative.site:06X} is past the image"
            )
        elif actual != relative.expect:
            problems.append(
                f"relative site 0x{relative.site:06X} is {actual.hex()} in this "
                f"image, but the document expects {relative.expect.hex()}"
            )
    for pointer in document.pointers:
        if pointer.site is None:
            continue
        actual = image[pointer.site : pointer.site + 4]
        if len(actual) != 4:
            problems.append(
                f"pointer site 0x{pointer.site:06X} is past the image; it cannot hold 4 bytes"
            )
        elif actual != pointer.expect:
            problems.append(
                f"pointer site 0x{pointer.site:06X} is {actual.hex()} in this image, but "
                f"the document expects {pointer.expect.hex()}"
            )
    return problems




def _reachable_storage(profile: RomProfile, sites: tuple[int, ...]) -> StorageModel:
    """The declared regions a direct branch from every one of `sites` can reach.

    Reachability is a property of the region's start, which is the lowest address a
    placement there could take; the exact branch is checked again after placement.
    A profile with no reachable region is refused by name rather than handed a
    region the branch would wrap out of.
    """
    model = StorageModel.from_profile(profile)
    reachable = tuple(
        region for region in model.regions
        if region.classification in ALLOCATABLE_REGION_CLASSES
        and all(
            abs(region.range.start.value - (site + 4)) <= THUMB_BL_RANGE
            for site in sites
        )
    )
    if not reachable:
        raise InsufficientSpaceError(
            "no declared free region is within the ARMv4T Thumb BL range "
            f"(±{THUMB_BL_RANGE:#x}) of hook site(s) "
            + ", ".join(f"0x{site:06X}" for site in sites)
            + "; use a pointer seam or move the seam, not a longer branch"
        )
    return StorageModel(model.canonical_size, model.image_size, reachable)


def _request(payload: Payload) -> AllocationRequest:
    return AllocationRequest(
        anchor=AnchorId(payload.owner),
        owner=payload.owner,
        size=payload.size,
        alignment=payload.alignment,
        kind=AllocationKind.PATCH_PAYLOAD,
        evidence=f"patch payload {payload.label} ({payload.source_class}, "
                 f"{payload.transform})",
    )


def unauthorized_retail_sites(
    document: PatchDocument, profile: RomProfile
) -> list[str]:
    """Seams the document rewrites that its profile does not authorise.

    A profile that declares ``patch_sites`` admits exactly those retail offsets.
    Matching ``expect`` bytes are never an authorisation: the same four bytes can
    sit in a table this project has no business rewriting. Pointer words INSIDE an
    allocated payload are not retail bytes at all, so they are always allowed.
    """
    declared = profile.patch_sites
    if declared is None or not document:
        return []
    allowed = {(site.kind, site.site): site for site in declared}
    problems: list[str] = []
    for entry in document.hooks:
        if ("hook", entry.site) not in allowed:
            problems.append(
                f"{entry.owner}: the profile authorises no hook at file 0x{entry.site:06X}"
            )
    for entry in document.pointers:
        if entry.site is None:
            continue
        if ("absolute", entry.site) not in allowed:
            problems.append(
                f"{entry.owner}: the profile authorises no pointer at file 0x{entry.site:06X}"
            )
    for entry in document.relatives:
        site = allowed.get(("relative", entry.site))
        if site is None:
            problems.append(
                f"{entry.owner}: the profile authorises no relative entry at file "
                f"0x{entry.site:06X}"
            )
        elif site.base != entry.base:
            problems.append(
                f"{entry.owner}: the profile's relative site at 0x{entry.site:06X} uses base "
                f"0x{(site.base or 0):08X}, the document says 0x{entry.base:08X}"
            )
    if problems:
        named = ", ".join(
            f"{site.kind}@0x{site.site:06X}" for site in declared)
        problems.append(f"the profile's authorised retail seams are: {named}")
    return problems


def materialize_patch(
    document: PatchDocument,
    profile: RomProfile,
    image: bytes,
    *,
    reserved: tuple[OwnedRegion, ...] = (),
) -> PatchMaterialization:
    """Place every payload and emit the changes the document describes.

    Constrained payloads (the targets of a direct branch) are placed first, from
    the regions every one of their hook sites can reach; the rest then take the
    lowest free addresses the profile declares, clear of what the first group
    took. Both passes are the ONE allocator, so a placement is still the lowest
    aligned first fit and still deterministic.
    """
    if not document:
        return PatchMaterialization((), (), reserved, (), ())

    unauthorized = unauthorized_retail_sites(document, profile)
    if unauthorized:
        raise PatchDocumentError("; ".join(unauthorized))

    hook_sites: dict[str, list[int]] = {}
    for hook in document.hooks:
        hook_sites.setdefault(hook.target, []).append(hook.site)
    constrained = tuple(p for p in document.payloads if p.label in hook_sites)
    free = tuple(p for p in document.payloads if p.label not in hook_sites)

    placed: list[Allocation] = []
    if constrained:
        sites = tuple(sorted({site for payload in constrained
                             for site in hook_sites[payload.label]}))
        try:
            placed.extend(
                allocate(profile,
                         (_request(pay) for pay in constrained),
                         storage=_reachable_storage(profile, sites),
                         occupied=reserved)
            )
        except InsufficientSpaceError as exc:
            raise PatchDocumentError(str(exc)) from exc
    occupied = reserved + tuple(
        OwnedRegion(allocation.range, f"allocated:{allocation.request.owner}")
        for allocation in placed
    )
    if free:
        try:
            placed.extend(allocate(profile, (_request(pay) for pay in free),
                                   occupied=occupied))
        except InsufficientSpaceError as exc:
            raise PatchDocumentError(str(exc)) from exc

    by_label = {allocation.request.owner: allocation for allocation in placed}
    address_of = {
        label: allocation.range.start.value + GBA_ROM_BASE
        for label, allocation in by_label.items()
    }

    owners: dict[str, list[str]] = {label: [] for label in by_label}
    changes: list[ByteChange] = []
    generated: list[GeneratedAllocationProvenance] = []

    for payload in document.payloads:
        label = payload.owner
        allocation = by_label[label]
        data = bytearray(payload.path.read_bytes())
        for pointer in document.pointers:
            if pointer.container != payload.label:
                continue
            slot = pointer.at
            if any(data[slot:slot + 4]):
                raise PatchDocumentError(
                    f"pointer slot {pointer.owner} is not zero in {payload.label!r}; "
                    "a fixup slot must be reserved, not overwrite authored bytes"
                )
            data[slot:slot + 4] = _pointer_word(
                address_of[_target_owner(pointer.target, document)], pointer.state
            )
            owners[label].append(pointer.owner)
        offset = allocation.range.start.value
        if allocation.is_expanded:
            padding = profile.generated_expansion
            if padding is None:
                raise PatchDocumentError("expanded allocation without a profile expansion")
            old = bytes([padding.padding_byte]) * len(data)
            generated.append(
                allocation.generated_allocation_provenance(
                    domain="patch",
                    resource=payload.label,
                    pointer_offset=None,
                    source_range=RomRange(FileOffset(0), payload.size),
                )
            )
        else:
            old = image[offset:offset + len(data)]
            if len(old) != len(data):
                raise PatchDocumentError(
                    f"payload {payload.label!r} at 0x{offset:06X} runs past the image"
                )
        changes.append(
            ByteChange(
                offset=offset,
                old=old,
                new=bytes(data),
                owner=label,
                reason=f"{payload.source_class}: {payload.transform} "
                       f"(payload sha256 {payload.sha256})",
            )
        )
        owners[label].append(label)

    for hook in document.hooks:
        actual = image[hook.site:hook.site + 4]
        if actual != hook.expect:
            raise PatchDocumentError(
                f"{hook.owner}: this image holds {actual.hex()} there, the document "
                f"expects {hook.expect.hex()}"
            )
        target = by_label[_target_owner(hook.target, document)]
        try:
            new = encode_thumb_bl(hook.site, target.range.start.value)
        except PatchDocumentError as exc:
            raise PatchDocumentError(f"{hook.owner}: {exc}") from exc
        changes.append(
            ByteChange(offset=hook.site, old=hook.expect, new=new, owner=hook.owner,
                       reason=f"branch into {hook.target}"
                              f"{' - ' + hook.origin_note if hook.origin_note else ''}")
        )
        owners[target.request.owner].append(hook.owner)

    for pointer in document.pointers:
        if pointer.site is None:
            continue
        actual = image[pointer.site:pointer.site + 4]
        if actual != pointer.expect:
            raise PatchDocumentError(
                f"{pointer.owner}: this image holds {actual.hex()} there, the document "
                f"expects {pointer.expect.hex()}"
            )
        target = by_label[_target_owner(pointer.target, document)]
        new = _pointer_word(target.range.start.value + GBA_ROM_BASE, pointer.state)
        changes.append(
            ByteChange(offset=pointer.site, old=pointer.expect, new=new,
                       owner=pointer.owner,
                       reason=f"typed {pointer.state} pointer to {pointer.target}"
                              f"{' - ' + pointer.origin_note if pointer.origin_note else ''}")
        )
        owners[target.request.owner].append(pointer.owner)

    for relative in document.relatives:
        actual = image[relative.site:relative.site + 4]
        if actual != relative.expect:
            raise PatchDocumentError(
                f"{relative.owner}: this image holds {actual.hex()} there, the "
                f"document expects {relative.expect.hex()}"
            )
        target = by_label[_target_owner(relative.target, document)]
        new = encode_relative_thumb(
            target.range.start.value + GBA_ROM_BASE + 1, relative.base)
        changes.append(
            ByteChange(offset=relative.site, old=relative.expect, new=new,
                       owner=relative.owner,
                       reason=f"signed relative Thumb entry to {relative.target} "
                              f"from base 0x{relative.base:08X}"
                              f"{' - ' + relative.origin_note if relative.origin_note else ''}")
        )
        owners[target.request.owner].append(relative.owner)

    reservations = tuple(
        OwnedRegion(allocation.range, f"allocated:{allocation.request.owner}")
        for allocation in placed
    )
    placed_payloads = tuple(
        PlacedPayload(payload=payload,
                      allocation=by_label[payload.owner],
                      owners=tuple(owners[payload.owner]))
        for payload in document.payloads
    )
    return PatchMaterialization(
        changes=tuple(sorted(changes, key=lambda change: change.offset)),
        allocations=tuple(placed),
        reservations=reservations,
        generated_allocations=tuple(generated),
        payloads=placed_payloads,
    )


def _target_owner(label: str, document: PatchDocument) -> str:
    return document.payload(label).owner


def write_patch_document(directory: str | Path, document: PatchDocument) -> Path:
    """Write the patch document `read_patch_document` parses.

    Authored by the semantic CLI, never by a person typing an offset. The output
    is deterministic (tables in a fixed order, keys in a fixed order) so a project
    saved twice is byte-identical, and `tests/unit/test_patch_document.py` proves
    a written document reads back as the same value.
    """
    path = Path(directory) / PATCH_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for payload in document.payloads:
        lines += [
            "[[payload]]",
            f'label = "{payload.label}"',
            f'file = "{payload.file}"',
            f'source_class = "{payload.source_class}"',
            f'origin_note = "{payload.origin_note}"',
            f'sha256 = "{payload.sha256}"',
        ]
        if payload.donor_sha256 is not None:
            lines.append(f'donor_sha256 = "{payload.donor_sha256}"')
        if payload.donor_span is not None:
            lines.append(f'donor_span = "{payload.donor_span}"')
        lines += [
            f'transform = "{payload.transform}"',
            f"alignment = {payload.alignment}",
            f"code = {'true' if payload.code else 'false'}",
            "",
        ]
    for hook in document.hooks:
        lines += [
            "[[hook]]",
            f"site = 0x{hook.site:06x}",
            f'expect = "{hook.expect.hex()}"',
            f'target = "{hook.target}"',
            f'origin_note = "{hook.origin_note}"',
            "",
        ]
    for relative in document.relatives:
        lines += [
            "[[relative]]",
            f"site = 0x{relative.site:06x}",
            f'expect = "{relative.expect.hex()}"',
            f"base = 0x{relative.base:08x}",
            f'target = "{relative.target}"',
            f'origin_note = "{relative.origin_note}"',
            "",
        ]
    for pointer in document.pointers:
        lines += ["[[pointer]]"]
        if pointer.site is not None:
            lines.append(f"site = 0x{pointer.site:06x}")
            lines.append(f'expect = "{pointer.expect.hex()}"')
        else:
            lines.append(f'in = "{pointer.container}"')
            lines.append(f"at = 0x{pointer.at:04x}")
        lines.append(f'state = "{pointer.state}"')
        lines.append(f'target = "{pointer.target}"')
        lines.append(f'origin_note = "{pointer.origin_note}"')
        lines.append("")
    path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8",
                    newline="\n")
    return path
