"""Semantic authoring surface for a dialogue-scene project. No offsets from a person.

LOG1-BUU-DIALOGUE-BACKPORT-001. Three command groups that make the backport
buildable through the shipping SDK alone:

* ``scene init`` - create a project for a verified image (no extraction needed),
  and with ``--presentation`` compose the declared dialogue presentation into it:
  the donor resources it needs, the code payloads its declarations pin, and the
  seams and fixups that reach them;
* ``scene show`` - print the profile's declared scene: nodes, capacities, text;
* ``scene set-text`` - author one node's words, space padded to its own slot;
* ``patch plan`` - place and resolve the project's payloads without emitting an image;
* ``donor portrait`` - extract one exact donor portrait into the project, with its
  donor fingerprint, span and transform recorded as machine-checkable provenance.

Nothing here takes a file offset, a slot number that names art, or a pre-patched
image. The image is an explicit input, the project holds portable relative paths,
and every write goes through the documents the build already reads.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace

from ..catalog import load_catalog
from ..donor_resources import (
    ADAPTED_TRANSFORM,
    BOX_TRANSFORM,
    FONT_TRANSFORM,
    OPAQUE_CAPACITY,
    PALETTE_FILE_OFFSET,
    PALETTE_TRANSFORM,
    DonorResourceError,
    adapt_pieces,
    dialogue_box,
    dialogue_font,
    load_donor,
    portrait,
)
from ..profile import RomProfile, RomProfileCatalog, VerificationStatus
from ..project import (
    PROJECT_FORMAT_VERSION,
    Hook,
    PatchDocument,
    PatchDocumentError,
    Payload,
    Pointer,
    ProjectMeta,
    RawByteEdits,
    Relative,
    load_toml,
    materialize_patch,
    read_patch_document,
    read_raw_bytes,
    write_patch_document,
    write_raw_bytes,
    write_project,
)
from ..rom import identify_rom
from ..scene_edits import (
    PLAN_LABEL,
    SceneTextError,
    dialogue_plan,
    plan_text_writes,
    read_scene,
)

PRESENTATION_SOURCE = (
    Path(__file__).resolve().parents[1] / "patchsource" / "log1-bf-presentation"
)
PRESENTATION_DECLARATIONS = ("sites.toml", "box-sites.toml", "text-sites.toml")

PRESENTATION_PALETTE_LABEL = "bf-obj-palette-low128"

PRESENTATION_BOX_LABEL = "bf-box"

PRESENTATION_FONT_LABEL = "bf-font"

PRESENTATION_PLAN_LABEL = PLAN_LABEL
PLAN_TRANSFORM = "scene-node-metadata/v1"

PRESENTATION_PALETTE_COPY_BYTES = 39 * 4

_FIXUP_RESOURCES = {
    "raster_roshi": ("portrait", "Master Roshi", 97),
    "raster_goku": ("portrait", "Goku", 57),
    "palette_low128": ("palette", None, None),
    "box_raster": ("box", None, None),
    "portrait_payload": ("payload", "bf-portrait", None),
    "font_blob": ("font", None, None),
    "lifecycle_table": ("plan", None, None),
}



class BackportCommandError(ValueError):
    """A command cannot proceed; the message is the reason to show a person."""


def _catalog(args) -> RomProfileCatalog:
    return load_catalog(getattr(args, "profiles", None))


def _profile(args) -> tuple[RomProfile, bytes, str]:
    path = Path(args.rom)
    identification = identify_rom(path, _catalog(args))
    match = identification.profile_match
    if match.status is not VerificationStatus.VERIFIED or match.profile is None:
        raise BackportCommandError(f"{path} is not an exactly verified image: {match.reason}")
    return match.profile, path.read_bytes(), identification.hashes.sha256


def _require_project_dir(path: Path) -> Path:
    directory = Path(path)
    if not (directory / "project.toml").is_file():
        raise BackportCommandError(
            f"{directory} holds no project.toml; run `scene init` first"
        )
    return directory


def scene_init(args) -> dict:
    if args.dialogue is not None and args.presentation is None:
        raise BackportCommandError(
            "--dialogue needs --presentation <donor image>: rewritten words alone "
            "cannot reach a screen, and a project that ships no presentation is the "
            "withdrawn dialogue-only milestone"
        )
    profile, image, digest = _profile(args)
    directory = Path(args.project)
    if directory.exists() and any(directory.iterdir()):
        raise BackportCommandError(
            f"{directory} is not empty; init writes a new project into a clean directory"
        )
    write_project(
        directory,
        ProjectMeta(
            format_version=PROJECT_FORMAT_VERSION,
            profile_id=profile.id,
            game=profile.game,
            base_rom_sha256=digest,
            base_rom_size=_size_of(args.rom),
            name=args.name or f"{profile.id}-scene",
        ),
        enemies=[],
        characters=[],
    )
    result = {"project": str(directory), "profile_id": profile.id,
              "base_sha256": digest, "base_size": _size_of(args.rom)}
    if args.presentation is not None:
        result["presentation"] = compose_presentation(
            directory, args.presentation, image, profile)
    if args.dialogue is not None:
        result["text"] = _author_dialogue(directory, image, profile, args.dialogue)
    return result


def _fixup_resource(fixup: dict) -> tuple[str, str | None, int | None]:
    symbol = fixup.get("symbol")
    if symbol not in _FIXUP_RESOURCES:
        raise BackportCommandError(
            f"fixup symbol {symbol!r} has no resource binding here; bind it in "
            f"_FIXUP_RESOURCES: declared set is {sorted(_FIXUP_RESOURCES)}"
        )
    return _FIXUP_RESOURCES[symbol]


def _plan_fixups(fixups: list[dict], blocks: dict[str, bytes]) -> list[dict]:
    """Bind every declared fixup word to the payload its declaration NAMES.

    A fixup word is located by identity, never by geometry. "The smallest composed
    payload that contains this offset" is a guess that goes wrong as soon as two
    payloads share the offset - and they do: the box strip words (0x190/0x194) sit
    inside both the 408-byte box block and lane B's 464-byte portrait block, which is
    the larger-then-smaller trap in the other direction. So each ``[[fixup]]`` names
    its ``payload`` and every failure names the declaration, the symbol and the
    field to add.
    """
    planned: list[dict] = []
    claimed: dict[tuple[str, int], str] = {}
    for fixup in fixups:
        symbol = fixup.get("symbol")
        declared = int(fixup["offset"])
        where = f"{fixup.get('from')}: fixup {symbol!r} at 0x{declared:X}"
        label = fixup.get("payload")
        if label not in blocks:
            raise BackportCommandError(
                f"{where} names no payload; add payload = \"<label>\" to its [[fixup]] "
                f"table (composed payloads: {sorted(blocks)})"
            )
        block = blocks[label]
        if declared < 0 or declared + 4 > len(block):
            raise BackportCommandError(
                f"{where}: {label!r} is {len(block)} bytes, so it holds no 4-byte word "
                f"at 0x{declared:X}"
            )
        if any(block[declared:declared + 4]):
            raise BackportCommandError(
                f"{where}: the word in {label!r} is not reserved - the source bytes "
                f"there are {block[declared:declared + 4].hex()}, not 00000000"
            )
        if (label, declared) in claimed:
            raise BackportCommandError(
                f"{where}: {claimed[(label, declared)]!r} already fills that word in "
                f"{label!r}; one slot holds one address"
            )
        claimed[(label, declared)] = symbol
        planned.append({"symbol": symbol, "payload": label, "offset": declared})
    return planned


def _bank_slot(bank: bytes, colour: int) -> int:
    """The single slot of the emitted shared bank that holds ``colour``.

    A donor palette index is not a target slot. The conversion sorts the opaque colours
    into slots 1.., so donor index 2 lands wherever that colour sorted and 0x7FFF white
    is the highest colour, hence the last slot. Deriving the slot from the emitted bytes
    is the only closed way to name the ink.
    """
    slots = [index for index in range(len(bank) // 2)
             if int.from_bytes(bank[index * 2:index * 2 + 2], "little") == colour]
    if len(slots) != 1:
        raise BackportCommandError(
            f"the emitted shared bank holds 0x{colour:04X} in {len(slots)} slots; a text "
            "payload needs exactly one slot to ink with")
    return slots[0]


def _require_shared_bank(entry: Payload) -> None:
    """The shared bank must be exactly the extent the shipped block copies.

    The block copies 39 words from the allocated bank. The bank is converted from the
    same three donor pieces lane C measured (both portraits and the BF box), which is
    what makes it 78 entries; a composition producing any other extent would leave the
    copy reading past its payload or dropping colours, so it is refused rather than
    accepted on the assembler's non-zero guard alone.
    """
    if entry.size != PRESENTATION_PALETTE_COPY_BYTES:
        raise BackportCommandError(
            f"{entry.label!r} is {entry.size} bytes; the shipped portrait block copies "
            f"{PRESENTATION_PALETTE_COPY_BYTES} (39 words) from it, so a composition of "
            "this extent would read past its own payload"
        )


def _declarations() -> list[tuple[Path, dict]]:
    found = [(PRESENTATION_SOURCE / name,
              load_toml((PRESENTATION_SOURCE / name).read_text(encoding="utf-8")))
             for name in PRESENTATION_DECLARATIONS
             if (PRESENTATION_SOURCE / name).is_file()]
    if not found:
        raise BackportCommandError(
            f"no payload declaration in {PRESENTATION_SOURCE}; expected one of "
            f"{list(PRESENTATION_DECLARATIONS)}")
    return found


def _fixup_payload(kind: str, name: str | None) -> str:
    """The payload label a fixup symbol binds to, in this composition's terms."""
    if kind == "palette":
        return PRESENTATION_PALETTE_LABEL
    if kind == "box":
        return PRESENTATION_BOX_LABEL
    if kind == "font":
        return PRESENTATION_FONT_LABEL
    if kind == "plan":
        return PRESENTATION_PLAN_LABEL
    if kind == "payload":
        return name or ""
    return _slug(name or "")


def emit_dialogue_plan(directory: str | Path, image: bytes,
                       profile: RomProfile) -> Payload:
    """Derive the scene's node plan and persist it as an allocated data payload.

    The derivation is the canonical image's own record table (``scene_edits``), so
    the table cannot disagree with the graph the project ships against. Emitted only
    when a declaration binds ``lifecycle_table``: a payload nothing reaches is not
    composed, which is why a build without A's fixup word carries no plan at all.
    """
    directory = Path(directory)
    payload = dialogue_plan(image, profile)
    path = directory / "assets" / f"{PRESENTATION_PLAN_LABEL}.bin"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    document = read_patch_document(directory)
    if any(entry.label == PRESENTATION_PLAN_LABEL for entry in document.payloads):
        raise BackportCommandError(
            f"{directory} already holds a {PRESENTATION_PLAN_LABEL} payload; a scene "
            "has one node plan, and rewriting it would orphan the fixup bound to it")
    entry = Payload(
        label=PRESENTATION_PLAN_LABEL, path=path,
        file=f"assets/{PRESENTATION_PLAN_LABEL}.bin", source_class="new",
        origin_note=(
            "derived structural metadata of the canonical scene record: every talk "
            "stage's text span, its talk-start and final flags and the actual "
            "successor kind, walked from the image's own record table; no text, art "
            "or graph byte"),
        sha256=hashlib.sha256(payload).hexdigest(), size=len(payload), alignment=4,
        code=False, transform=PLAN_TRANSFORM, donor_sha256=None, donor_span=None,
    )
    write_patch_document(directory, PatchDocument(
        document.payloads + (entry,), document.hooks, document.pointers,
        document.relatives))
    return entry


def compose_presentation(directory: str | Path, donor_path, image: bytes | None = None,
                         profile: RomProfile | None = None) -> dict:
    """Compose every declared presentation payload into a project, documents only.

    Declarations are read from :data:`PRESENTATION_SOURCE` in :data:`PRESENTATION_PAYLOADS`
    order and never written. A later declaration that claims a retail seam an earlier
    one already claims SUPERSEDES it, and a payload nothing reaches is not composed:
    that is how lane A's box hook replaces the behaviour-preserving pass-through at the
    same method-table entry without either lane's source being edited. Everything the
    composition cannot bind is refused by name.
    """
    directory = Path(directory)
    declarations = _declarations()
    seams: dict[tuple[str, int], dict] = {}
    superseded: list[dict] = []
    payload_tables: list[dict] = []
    fixups: list[dict] = []
    for path, declaration in declarations:
        payload_tables.extend(declaration.get("payload") or [])
        fixups.extend({"from": path.name, **item}
                      for item in declaration.get("fixup") or [])
        for kind in ("relative", "absolute", "hook"):
            for item in declaration.get(kind) or []:
                key = (kind, int(item["site"]))
                previous = seams.get(key)
                if previous is not None and previous["target"] != item["target"]:
                    superseded.append({
                        "seam": f"{kind} 0x{int(item['site']):06X}",
                        "dropped": previous["target"], "kept": item["target"],
                        "declared_by": path.name})
                seams[key] = {**item, "kind": kind, "from": path.name}
    if not payload_tables:
        raise BackportCommandError(f"{PRESENTATION_SOURCE} declares no payload")

    declared_labels = {item["label"] for item in payload_tables}
    missing = {item["target"] for item in seams.values()} - declared_labels
    if missing:
        raise BackportCommandError(
            f"a seam targets payload(s) no declaration carries: {sorted(missing)}")

    bound_fixups = [(fixup, _fixup_resource(fixup)) for fixup in fixups]
    wanted = [name for _, (kind, name, _slot) in bound_fixups if kind == "portrait"]
    slots = [slot for _, (kind, _name, slot) in bound_fixups if kind == "portrait"]
    if wanted:
        donor_convert(SimpleNamespace(
            project=directory, donor=donor_path, name=wanted, slot=slots,
            box=True, palette_label=PRESENTATION_PALETTE_LABEL,
        ))
    document = read_patch_document(directory)
    resources = {payload.label: payload for payload in document.payloads}

    donor_entries: list[Payload] = []
    if any(kind == "font" for _, (kind, _n, _s) in bound_fixups):
        donor, donor_digest = load_donor(donor_path)
        extracted = dialogue_font(donor)
        font_path = directory / "assets" / "bf-font.bin"
        font_path.parent.mkdir(parents=True, exist_ok=True)
        font_path.write_bytes(extracted.payload)
        donor_entries.append(Payload(
            label=PRESENTATION_FONT_LABEL, path=font_path, file="assets/bf-font.bin",
            source_class="transferred",
            origin_note=(
                "the donor's raw dialogue font span: 8x14 column-bitmask glyphs, "
                "descriptor line 14, advance width +1, wrap 144; no atlas, no report"),
            sha256=extracted.sha256, size=len(extracted.payload), alignment=4,
            code=False, transform=FONT_TRANSFORM, donor_sha256=donor_digest,
            donor_span=extracted.donor_span,
        ))

    plan_entries: list[Payload] = []
    if any(kind == "plan" for _, (kind, _n, _s) in bound_fixups):
        if image is None or profile is None:
            raise BackportCommandError(
                "a lifecycle_table fixup needs the base image and its profile: the plan is "
                "derived from the image's own record table, never from a literal")
        plan_entries.append(emit_dialogue_plan(directory, image, profile))
        resources.update({entry.label: entry for entry in plan_entries})
    resources.update({entry.label: entry for entry in donor_entries})

    fixup_targets = [_fixup_payload(kind, name) for _, (kind, name, _s) in bound_fixups]
    reachable = ({item["target"] for item in seams.values()} | set(fixup_targets))
    selected = [item for item in payload_tables if item["label"] in reachable]
    not_composed = [item["label"] for item in payload_tables
                    if item["label"] not in reachable]

    code_labels = ({item["target"] for item in seams.values()}
                   | {_fixup_payload(kind, name)
                      for _, (kind, name, _s) in bound_fixups if kind == "payload"})
    code: list[Payload] = []
    blocks: dict[str, bytes] = {}
    for item in selected:
        label = item["label"]
        source_class = item.get("source_class", "new")
        donor_sha256 = item.get("donor_sha256")
        donor_span = item.get("donor_span")
        if source_class != "new" and not (donor_sha256 and donor_span):
            raise BackportCommandError(
                f"payload {label!r} is {source_class} but declares no donor fingerprint")
        origin = PRESENTATION_SOURCE / item["file"]
        if not origin.is_file():
            raise BackportCommandError(
                f"payload {label!r} is not assembled at {origin}; run assemble.ps1 there")
        data = origin.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if item.get("sha256") != actual:
            raise BackportCommandError(
                f"payload {label!r} assembles to {actual}, its declaration pins "
                f"{item.get('sha256')}")
        blocks[label] = data
        target = directory / "assets" / item["file"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        code.append(Payload(
            label=label, path=target, file=f"assets/{item['file']}",
            source_class=source_class,
            origin_note=item.get("origin_note") or f"{label} from {item['file']}",
            sha256=actual, size=len(data), alignment=int(item.get("alignment", 4)),
            code=label in code_labels, transform=item.get("transform") or "identity",
            donor_sha256=donor_sha256, donor_span=donor_span,
        ))


    relatives = [
        Relative(site=int(item["site"]), expect=bytes.fromhex(item["expect"]),
                 base=int(item["base"]), target=item["target"],
                 origin_note=item["note"])
        for item in seams.values() if item["kind"] == "relative"
    ]
    pointers = [
        Pointer(target=item["target"], state="thumb", origin_note=item["note"],
                site=int(item["site"]), expect=bytes.fromhex(item["expect"]))
        for item in seams.values() if item["kind"] == "absolute"
    ]
    hooks = [
        Hook(site=int(item["site"]), expect=bytes.fromhex(item["expect"]),
             target=item["target"], origin_note=item["note"])
        for item in seams.values() if item["kind"] == "hook"
    ]
    bound: list[dict] = []
    planned = {(entry["symbol"], entry["payload"], entry["offset"]): entry
               for entry in _plan_fixups(fixups, blocks)}
    for fixup, (kind, name, _slot) in bound_fixups:
        label = _fixup_payload(kind, name)
        resource = resources.get(label) or next(
            (payload for payload in code if payload.label == label), None)
        if resource is None:
            raise BackportCommandError(
                f"fixup {fixup.get('symbol')!r} needs payload {label!r}, which this "
                f"composition does not hold")
        declared = int(fixup["bytes"])
        if kind == "payload":
            if declared:
                raise BackportCommandError(
                    f"fixup {fixup.get('symbol')!r} declares {declared} bytes, {label!r} "
                    "is a code payload reached by that address; declare bytes = 0")
        elif resource.size != declared:
            raise BackportCommandError(
                f"fixup {fixup.get('symbol')!r} declares {declared} bytes, {label!r} is "
                f"{resource.size}; the payload does not read that extent")
        at = int(fixup["offset"])
        plan = planned[(fixup["symbol"], fixup["payload"], at)]
        pointers.append(Pointer(
            target=label, state="thumb" if kind == "payload" else "data",
            origin_note=f"{fixup['symbol']} fixup word, filled by the allocator",
            container=plan["payload"], at=plan["offset"],
        ))
        bound.append({"symbol": fixup["symbol"], "slot": at, "block": plan["payload"],
                      "resource": label, "resource_sha256": resource.sha256})

    ink_slot = None
    if PRESENTATION_PALETTE_LABEL in resources:
        bank = resources[PRESENTATION_PALETTE_LABEL]
        _require_shared_bank(bank)
        ink_slot = _bank_slot(bank.path.read_bytes(), 0x7FFF)
    write_patch_document(directory, PatchDocument(
        document.payloads + tuple(donor_entries) + tuple(plan_entries) + tuple(code),
        tuple(hooks), tuple(pointers), tuple(relatives),
    ))
    return {
        "declarations": [str(path) for path, _ in declarations],
        "donor_sha256": (load_donor(donor_path)[1] if wanted else None),
        "ink_white_slot": ink_slot,
        "payloads": [
            {"label": payload.label, "sha256": payload.sha256, "bytes": payload.size,
             "code": payload.code, "source_class": payload.source_class}
            for payload in (document.payloads + tuple(donor_entries)
                            + tuple(plan_entries) + tuple(code))
        ],
        "superseded": superseded,
        "not_composed": not_composed,
        "relative_sites": [f"0x{relative.site:06X}" for relative in relatives],
        "absolute_sites": [f"0x{pointer.site:06X}" for pointer in pointers
                          if pointer.site is not None],
        "fixups": bound,
    }


def _author_dialogue(directory: Path, image: bytes, profile: RomProfile, source) -> dict:
    """Author every node in a JSON dialogue file, capacity-checked against the image."""
    data = json.loads(Path(source).read_text(encoding="utf-8"))
    nodes = data.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise BackportCommandError(f"{source} declares no nodes")
    scene = read_scene(image, profile)
    texts: dict[int, str] = {}
    for item in nodes:
        index, text = item.get("node"), item.get("text")
        if type(index) is not int or not isinstance(text, str):
            raise BackportCommandError(
                f"{source}: every entry needs an integer 'node' and a string 'text'")
        node = scene.node(index)
        declared = item.get("capacity")
        if declared is not None and declared != node.capacity:
            raise BackportCommandError(
                f"{source}: node {index} declares capacity {declared}, the image's slot "
                f"is {node.capacity}; this is not that scene")
        texts[index] = text
    return _write_scene_text(directory, image, profile, texts)


def _write_scene_text(directory: Path, image: bytes, profile: RomProfile,
                      authored: dict[int, str]) -> dict:
    writes = plan_text_writes(image, profile, authored)
    existing = dict(read_raw_bytes(directory).bytes_by_offset)
    existing.update(writes)
    path = write_raw_bytes(directory, RawByteEdits(existing))
    scene = read_scene(image, profile)
    return {
        "raw_document": str(path),
        "slots": [
            {"node": index, "file_offset": f"0x{offset:06x}",
             "bytes": len(writes[offset]),
             "capacity": scene.node(index).capacity}
            for index, offset in ((index, scene.node(index).text_offset)
                                  for index in sorted(authored))
        ],
    }


def _size_of(rom) -> int:
    return Path(rom).stat().st_size


def scene_show(args) -> dict:
    profile, image, _digest = _profile(args)
    directory = _require_project_dir(args.project)
    scene = read_scene(image, profile)
    edits = read_raw_bytes(directory)
    return {
        "profile_id": profile.id,
        "record_file_offset": f"0x{scene.record_offset:06x}",
        "nodes": [
            {
                "node": node.index,
                "kind": f"0x{node.kind:02x}",
                "next": node.next_node,
                "capacity": node.capacity,
                "text": node.text,
                "authored": (
                    edits.bytes_by_offset[node.text_offset].decode("ascii", "replace")
                    if node.text_offset in edits.bytes_by_offset
                    else None
                ),
            }
            for node in scene.nodes
        ],
    }


def scene_set_text(args) -> dict:
    profile, image, _digest = _profile(args)
    directory = _require_project_dir(args.project)
    nodes = args.node or []
    texts = args.text or []
    if not nodes or len(nodes) != len(texts):
        raise BackportCommandError(
            "give one --node and one --text per line, with the same count"
        )
    authored = dict(zip(nodes, texts))
    result = _write_scene_text(directory, image, profile, authored)
    result["project"] = str(directory)
    return result


def patch_plan(args) -> dict:
    profile, image, _digest = _profile(args)
    directory = _require_project_dir(args.project)
    document = read_patch_document(directory)
    if not document:
        return {"project": str(directory), "payloads": [], "changes": []}
    materialization = materialize_patch(document, profile, image)
    return {
        "project": str(directory),
        "payloads": [
            {
                "label": placed.payload.label,
                "source_class": placed.payload.source_class,
                "transform": placed.payload.transform,
                "payload_sha256": placed.payload.sha256,
                "file_offset": f"0x{placed.allocation.range.start.value:06x}",
                "rom_address": f"0x{placed.allocation.rom_address:08x}",
                "expanded": placed.allocation.is_expanded,
                "owners": list(placed.owners),
            }
            for placed in materialization.payloads
        ],
        "changes": [
            {"file_offset": f"0x{change.offset:06x}", "size": change.size,
             "owner": change.owner, "reason": change.reason}
            for change in materialization.changes
        ],
    }


def donor_portrait(args) -> dict:
    data, donor_digest = load_donor(args.donor)
    extracted = portrait(data, args.name, slot=args.slot)
    directory = _require_project_dir(args.project)
    label = args.label or args.name.lower().replace(" ", "-")
    relative = Path("assets") / f"{label}.bin"
    target = directory / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(extracted.payload)
    document = read_patch_document(directory)
    others = tuple(payload for payload in document.payloads if payload.label != label)
    entry = Payload(
        label=label,
        path=target,
        file=relative.as_posix(),
        source_class="transferred",
        origin_note=f"{extracted.name} portrait slot {extracted.portrait_slot}",
        sha256=hashlib.sha256(extracted.payload).hexdigest(),
        size=len(extracted.payload),
        alignment=4,
        code=False,
        transform=extracted.transform,
        donor_sha256=donor_digest,
        donor_span=extracted.donor_span,
    )
    write_patch_document(
        directory, PatchDocument(others + (entry,), document.hooks,
                                 document.pointers, document.relatives)
    )
    return {
        "label": label,
        "file": relative.as_posix(),
        "portrait_slot": extracted.portrait_slot,
        "container_file_offset": f"0x{extracted.container_file_offset:06x}",
        "payload_sha256": entry.sha256,
        "donor_sha256": donor_digest,
        "donor_span": extracted.donor_span,
        "transform": extracted.transform,
    }


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not slug:
        raise BackportCommandError(f"{name!r} has no label-safe characters")
    return slug


def donor_convert(args) -> dict:
    """One shared low-half-bank palette for every named donor portrait.

    The bank is built over the UNION of the pieces, which is why this is one
    command and not a flag on `donor portrait`: two portraits converted
    separately would each bind donor index 1 to a different slot in the same
    on-screen bank.
    """
    names = list(args.name or [])
    if not names:
        raise BackportCommandError("donor convert needs at least one --name")
    slots = list(args.slot or [])
    if slots and len(slots) != len(names):
        raise BackportCommandError(
            f"{len(slots)} --slot values cannot be paired with {len(names)} --name values"
        )
    data, donor_digest = load_donor(args.donor)
    directory = _require_project_dir(args.project)
    document = read_patch_document(directory)
    extracted = {
        name: portrait(data, name, slot=slots[index] if slots else None)
        for index, name in enumerate(names)
    }

    labels = {name: _slug(name) for name in names}
    if len(set(labels.values())) != len(labels):
        raise BackportCommandError(f"two names share a label: {sorted(labels.values())}")
    box = dialogue_box(data) if args.box else None
    pieces = {labels[name]: extracted[name].payload for name in names}
    if box is not None:
        pieces["bf-box"] = box.payload
    bank, adapted = adapt_pieces(data, pieces)

    palette_label = args.palette_label
    assets = directory / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    entries: list[Payload] = []
    emitted: list[dict] = []

    palette_file = Path("assets") / f"{palette_label}.bin"
    (directory / palette_file).write_bytes(bank.palette)
    entries.append(Payload(
        label=palette_label,
        path=directory / palette_file,
        file=palette_file.as_posix(),
        source_class="adapted",
        origin_note=(
            "shared low OBJ bank for the converted portraits, emitted for the slots "
            "this bank uses only; slot 0 is the donor's only transparent index, every "
            "opaque donor colour takes slots 1.., and a copy of its own length never "
            "reaches bank 5..7 or 128..255"
        ),
        sha256=bank.sha256,
        size=len(bank.palette),
        alignment=4,
        code=False,
        transform=PALETTE_TRANSFORM,
        donor_sha256=donor_digest,
        donor_span=f"0x{PALETTE_FILE_OFFSET:06X}-0x{PALETTE_FILE_OFFSET + 512:06X}",
    ))
    emitted.append({"label": palette_label, "file": palette_file.as_posix(),
                    "payload_sha256": bank.sha256, "bytes": len(bank.palette),
                    "entries": len(bank.palette) // 2,
                    "opaque_slots_used": max(bank.remap.values()) if bank.remap else 0,
                    "opaque_capacity": OPAQUE_CAPACITY,
                    "transparent_index_only": bank.transparent,
                    "collapsed_opaque_colours": {
                        f"0x{colour:04X}": list(indices)
                        for colour, indices in bank.collapsed.items()}})

    for name in names:
        source = extracted[name]
        label = labels[name]
        file_value = Path("assets") / f"{label}-adapted.bin"
        payload = adapted[label]
        (directory / file_value).write_bytes(payload)
        entries.append(Payload(
            label=label,
            path=directory / file_value,
            file=file_value.as_posix(),
            source_class="adapted",
            origin_note=(
                f"{source.name} portrait slot {source.portrait_slot}, donor indices "
                "remapped into the shared low bank, row-major (the payload tiles at runtime)"
            ),
            sha256=hashlib.sha256(payload).hexdigest(),
            size=len(payload),
            alignment=4,
            code=False,
            transform=ADAPTED_TRANSFORM,
            donor_sha256=donor_digest,
            donor_span=source.donor_span,
        ))
        emitted.append({"label": label, "file": file_value.as_posix(),
                        "portrait_slot": source.portrait_slot,
                        "payload_sha256": entries[-1].sha256, "bytes": len(payload),
                        "donor_span": source.donor_span})

    if box is not None:
        file_value = Path("assets") / "bf-box-adapted.bin"
        payload = adapted["bf-box"]
        (directory / file_value).write_bytes(payload)
        entries.append(Payload(
            label="bf-box",
            path=directory / file_value,
            file=file_value.as_posix(),
            source_class="adapted",
            origin_note=(
                "primary BF dialogue box, donor indices remapped into the shared low "
                "bank; 160x64 row-major, layout record C measured at 0x071730"
            ),
            sha256=hashlib.sha256(payload).hexdigest(),
            size=len(payload),
            alignment=4,
            code=False,
            transform=BOX_TRANSFORM,
            donor_sha256=donor_digest,
            donor_span=box.donor_span,
        ))
        emitted.append({"label": "bf-box", "file": file_value.as_posix(),
                        "payload_sha256": entries[-1].sha256, "bytes": len(payload),
                        "donor_span": box.donor_span})

    fresh = {entry.label: entry for entry in entries}
    merged = [fresh.pop(payload.label, payload) for payload in document.payloads]
    write_patch_document(
        directory, PatchDocument(tuple(merged) + tuple(fresh.values()), document.hooks,
                                 document.pointers, document.relatives)
    )
    return {
        "project": str(directory),
        "donor_sha256": donor_digest,
        "payloads": emitted,
        "opaque_capacity": OPAQUE_CAPACITY,
    }


_COMMANDS = {
    ("scene", "init"): scene_init,
    ("scene", "show"): scene_show,
    ("scene", "set-text"): scene_set_text,
    ("payloads", "plan"): patch_plan,
    ("donor", "portrait"): donor_portrait,
    ("donor", "convert"): donor_convert,
}


def run(args) -> int:
    """Dispatch one authoring command; returns the process exit status."""
    key = (args.command, getattr(args, f"{args.command}_command", None))
    handler = _COMMANDS.get(key)
    if handler is None:
        print(json.dumps({"error": f"unknown command {key}"}))
        return 2
    try:
        result = handler(args)
    except (
        BackportCommandError,
        DonorResourceError,
        PatchDocumentError,
        SceneTextError,
    ) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0
