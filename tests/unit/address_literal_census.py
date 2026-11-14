"""The measured hard-coded address surface of ``tools/``.

This module holds the pins and the exemption table for the census guard in
``tests/unit/test_hardcoded_address_census.py``. It measures nothing by itself:
every function here reads the tracked tree and returns a count, and the guard
compares that count against a pin.

The census set is every path from ``tools.quality.architecture.tracked_files()``
starting with ``tools/``. The enforcement set is that set minus the four
instrument directories named in ``INSTRUMENT_DIRECTORIES``. Three units are
counted, always per line and never per match, so a line carrying eleven
addresses counts once:

* ``HEX5`` - a hexadecimal literal token of five or more digits. The metric was
  widened once, after a review found two spellings that evaded it, an uppercase
  prefix and a digit separator; it measures 2882 lines in 272 files.
* ``ROM_HEX`` - a hexadecimal token whose parsed integer lands in
  ``[0x08000000, 0x0A000000)``. Deciding by value rather than by the ``0[89]``
  digit shape is what makes a seven-digit spelling such as ``0x82ed222`` count.
* ``DECIMAL`` - an integer token whose value lands in
  ``[0x08000000, 0x0A000000)``. The decimal spelling is invisible to every
  hexadecimal pattern, which is the falsifier the migration order names; the
  value is range-checked as an integer, never by a pattern.

``INVENTORY.md`` section 4 publishes the parent pair 2884 lines in 272 files for
its ``0x[0-9A-Fa-f]{5,}`` count. That pattern and the token measured here differ
by exactly one line, ``tools/runtime/rom008_query_probe.py:105``, which spells
its literal with a digit separator. Both pairs are pinned and the difference was
asserted to be exactly one line and no files, so the reconciliation with section
4 was machine-checked rather than discarded. PINMAP-04 then moved the tree itself
and the published pair was not re-measured with it, so that pinned difference is
the one thing this module cannot restate from inside its own write surface; see
the ``CENSUS_HEX5`` note below for the arithmetic, which is stated so a reader can
reproduce it line by line.

Named limits: ``0o`` and ``0b`` spellings are not detected at all, and no such
spelling exists in the tracked tree today. The two hex boundary rules differ on
purpose: the historical lowercase form keeps the historical boundary so a Java
suffix such as ``0x080126D4L`` still counts and no tracked line lost a count
(measured), while the widened form must also exclude identifier characters, or the
name ``byte_at_0x10_census`` reads as the literal ``0x10ce``.

What this module does NOT cover, stated so a reader does not expect more:

* it does not decide whether a hit is a real address. A file is counted by what
  it spells, and a counted file is a row with a reason, which is why the one
  row whose hit is a Windows creation flag rather than an address says so.
* it counts literals per file, so it detects a change in how many literals a
  file carries and not a swap of one address for another at constant count.
* it governs the index, not the disk. A path that exists only on disk is not in
  the set, so the guard never fires on a bytecode cache, an editor backup or
  generated output, and it never sees a file that was not added to the index.
* it says nothing about the four instrument directories, deliberately.

ponytail: a row pins three counts, not the literal values. A swap of one address
for another at the same count is invisible. The one-line upgrade, when a swap
starts to matter, is a digest over the sorted distinct literals of the row; the
stated aim is that this surface does not grow, so the digest is not built.
"""

from __future__ import annotations

import re
from typing import Iterable, Mapping, NamedTuple, Sequence

from tools.quality.architecture import REPOSITORY_ROOT, tracked_files

#: A hex literal token, two spellings of boundary on purpose. The first
#: alternative is the historical spelling and keeps the historical boundary, so
#: a Java suffix such as 0x080126D4L still counts, and no tracked line lost a count
#: (measured). The second adds the upper-case prefix and the digit separator;
#: its boundary must also exclude identifier characters, or the name
#: byte_at_0x10_census reads as the literal 0x10ce.
HEX_TOKEN = re.compile(
    r"(?<![0-9A-Fa-f])0x[0-9A-Fa-f]{5,}(?![0-9A-Fa-f])"
    r"|(?<![0-9A-Za-z_.])0[xX][0-9A-Fa-f_]*[0-9A-Fa-f](?![0-9A-Za-z_])"
)

#: A decimal integer token of eight digits or more, underscores allowed.
DECIMAL = re.compile(r"(?<![\w.])\d[\d_]{7,}\d(?![\w.])")

#: ROM space, as the Game Pak window the readers subtract a base from.
ROM_START = 0x08000000
ROM_END = 0x0A000000

#: ``INVENTORY.md`` section 4's published parent pair, quoted as published: its
#: ``0x[0-9A-Fa-f]{5,}`` count, per line, over the 560 tracked ``tools/`` files.
#: The per-file rows that document reports are lane-reported and are not
#: reproducible under any single unit, so only this pair is quoted.
#: PINMAP-04 moved the measured pair and left this one at the published value on
#: purpose: it is a quotation of an external document, not a restatement of the
#: tree, and rewriting it to keep a pinned difference true would make it lie about
#: what section 4 says. The consequence is stated where a reader meets it, in the
#: ``CENSUS_HEX5`` note here and in the reconciliation node's own failure message.
CENSUS_INVENTORY_S4 = (2884, 272)

#: The whole-tree measurement under this module's widened token. PINMAP-04 moved
#: it by -3 lines and 0 files, and the arithmetic is one line, not three: FOUR
#: counted lines left ``tools/webfoot/sprite_swap.py`` and ONE counted line
#: arrived in the profile catalogue pair.
#:
#: Left, each a counted hex5 and rom_hex line: the constant
#: ``REGISTRY_TABLE_ADDRESS = 0x086B6BDC`` at sprite_swap.py:61, the constant
#: ``OBJECT_PALETTE_ADDRESS = 0x0805652C`` at :63, the comment
#: ``#: The portrait pointer array (accessor 0x08011F20).`` at :67, and the
#: constant ``PORTRAIT_ARRAY_ADDRESS = 0x086F393C`` at :68.
#: Arrived: ``portrait_table_address: 0x086f393c`` at
#: ``tools/webfoot/data/roms.yaml:21``, and the byte-identical copy of the same
#: line at ``config/roms.yaml:21``, which is outside the ``tools/`` census set.
#: Measured 2885 -> 2882 lines, 272 -> 272 files.
#: PINMAP-05 moved 2882 -> 2879; the entry it appended names all nineteen lines.
#: PINMAP-06 moved 2879 -> 2877; the entry it appended names both lines.
#: PINMAP-07a moved 2877 -> 2887; the entry it appended names all ten lines.
#: PINMAP-07b moved 2887 -> 2875; the entry it appended names all twelve lines.
#: PINMAP-09 moved 2875 -> 2866; the entry it appended names all eleven lines.
#: APPEARANCE-OFFSET-KEYS-001 moved 2866 -> 2868; its ledger entry names both lines.
CENSUS_HEX5 = (3777, 308)

#: The enforcement set: conventional hex, ROM-space hex, and the decimal
#: ROM-range corpus, each as (lines, files). All three moved at PINMAP-04, by the
#: same four removals and the one added key the ``CENSUS_HEX5`` note lists; the
#: enforcement set is the whole-tree set minus the four instrument directories, so
#: the three move together. PINMAP-07a then moved the first two, ten lines each.
#: PINMAP-07b moved them back down by the twelve hex lines it removed.
#: APPEARANCE-OFFSET-KEYS-001 added one line to each, on the profile catalogue pair.
ENFORCEMENT_HEX5 = (1410, 100)
ENFORCEMENT_ROM_HEX = (941, 81)
ENFORCEMENT_DECIMAL = (404, 1)

#: Directories the migration order leaves out of scope deliberately: they hold
#: evidence instruments whose addresses are inputs to a mapping effort rather
#: than consumers of the pinned map, and migrating them would put the probe
#: corpus at risk for no product gain. This is a scan-set definition and not an
#: exemption row, and a directory not named here is inside the enforcement set
#: by construction, so a new directory under ``tools/`` is covered as soon as it
#: is tracked.
INSTRUMENT_DIRECTORIES: tuple[tuple[str, str], ...] = (
    (
        "tools/runtime/",
        "runtime capture instruments; the migration order leaves them out of "
        "scope because their addresses are evidence inputs, not consumers",
    ),
    (
        "tools/research/",
        "read-only archaeology instruments; the migration order leaves them out "
        "of scope for the same reason",
    ),
    (
        "tools/ghidra/",
        "Ghidra analysis scripts; their addresses are analysis inputs for the "
        "same mapping effort and are not read by a shipping module",
    ),
    (
        "tools/mgba_probe/",
        "the emulator probe harness and its patch; its addresses belong to its "
        "own probes and are not read by a shipping module",
    ),
)


class CensusError(RuntimeError):
    """A measurement that cannot be trusted, raised instead of counting zero."""


class Row(NamedTuple):
    """One enforced file: its per-line counts and the reason it is exempt."""

    path: str
    hex5: int
    rom_hex: int
    decimal: int
    reason: str


#: One row per enforced file that carries a ROM-space or decimal literal, keyed
#: by path and generated by re-running the scan, never typed from memory. A row
#: asserts equality in both directions, and a row whose file stops carrying a
#: literal, whose count moves either way, or that names a path which is not
#: tracked fails the guard by name.
EXEMPTIONS: tuple[Row, ...] = (
    Row(
        "tools/buufury_text/preview.py", 19, 11, 0,
        "the preview's portrait-index selectors, the layout and art containers "
        "they select, and a module base constant: 0x08012012, 0x08012104, "
        "0x0801210A, 0x08071720..0x08071A6C, 0x08000000, cited in the docstring "
        "as measured portrait-record layout. No ticket covers this file yet: "
        "recorded debt.",
    ),
    Row(
        "tools/dragonbyte/textsurface.py", 9, 1, 0,
        "one docstring range naming the packed-dialogue container span "
        "0x0877C5A4..0x0879B704, quoted while counting those containers. No "
        "ticket covers this file yet: recorded debt.",
    ),
    Row(
        "tools/export/buu_resource_export.py", 6, 6, 0,
        "comments and docstrings citing engine sites: the decompressing "
        "constructor 0x08007B63, the marker installer 0x0800897B, the occupancy "
        "test 0x08008076, the default container 0x08070808 and the 24-byte-record "
        "table 0x086B82EC. No ticket covers this file yet: recorded debt.",
    ),
    Row(
        "tools/export/canonical.py", 9, 9, 0,
        "the literals PINMAP-06 leaves, each named with its role at its line in "
        "this file after those removals: the bank container table 0x08179764 at "
        ":150, the absent-layer placeholder container 0x08070808 at :154, the "
        "engine code sites 0x08000158 and 0x0801713C at :170-171, the party-alias "
        "index table 0x086B82EC at :172, the portrait pointer array 0x086F393C at "
        ":232, which PINMAP-04 declared as actor_sprites.portrait_table_address, "
        "and the terrain-field handler word 0x080088BD cited at :308, :321 and "
        ":330, which is PINMAP-07's surface. The two this row used to spell, the "
        "sprite-definition run 0x086B6BDC and the appearance table 0x0874D380, now "
        "resolve from the profile through the module's existing accessor pattern.",
    ),
    Row(
        "tools/export/render.py", 2, 1, 0,
        "one docstring citation of the payload-streaming constructor "
        "0x080088BD, quoted to explain what its bytes mean. No ticket covers "
        "this file yet: recorded debt.",
    ),
    Row(
        "tools/export/webfoot_strict.py", 5, 3, 0,
        "the engine dispatcher 0x0803D940 cited in comments and in the dispatch "
        "comment, plus the two form words 0x087B7CCC and 0x087B7CD0 read from "
        "its literal pool. No ticket covers this file yet: recorded debt.",
    ),
    Row(
        "tools/quality/readability.py", 1, 1, 0,
        "the single hit is the ROM base used as an example inside the comment "
        "that documents this scanner's own combined-hex rule. It is prose about "
        "a spelling, not a target address; no ticket covers it yet: recorded "
        "debt.",
    ),
    Row(
        "tools/save_catalogue/geometry.py", 13, 4, 0,
        "comments citing the record access sites 0x0800493C..0x08004942 and the "
        "header read and write routines 0x08006B88, 0x08006B7E, 0x08006B5E, "
        "0x08006AF0 and 0x08006B0C. No ticket covers this file yet: recorded "
        "debt.",
    ),
    Row(
        "tools/webfoot/allocation.py", 6, 6, 0,
        "comments citing the engine key lookup 0x080089FC, the count reader "
        "0x080125E0 and the Game Pak window bounds 0x08000000, 0x08800000 and "
        "0x09FFFFFF. No ticket covers this file yet: recorded debt.",
    ),
    Row(
        "tools/webfoot/appearance_authoring.py", 14, 14, 0,
        "comments citing the two-loop appearance search 0x08027948..0x080279CE, "
        "the sibling factory words 0x086AED8C and 0x086AEBF0, and the accessor "
        "and write sites 0x0802794E, 0x08010312 and 0x0800FB72. No ticket covers "
        "this file yet: recorded debt.",
    ),
    Row(
        "tools/webfoot/atlas_producers/code_functions.py", 17, 14, 0,
        "the ARM entry point 0x080000C0 and the table of function addresses the "
        "atlas producer emits, 0x080728AC and 0x087B6904 with their per-family "
        "runs 0x080123E8..0x08012464 and 0x0803E4E4..0x0803EC5A. No ticket "
        "covers this file yet: recorded debt.",
    ),
    Row(
        "tools/webfoot/atlas_producers/seed.py", 214, 177, 0,
        "168 distinct ROM words: the seed's function anchors, dispatch tables "
        "and per-row evidence strings. PINMAP-09 reads the TEN rows that "
        "duplicated a profile key from the profile instead of restating it; "
        "nine counted lines left this file and two arrived in the rewritten "
        "conflict note and its guard, so the pair is -9 lines and no files. "
        "The seed's one reported conflict is recorded as one named row.",
    ),
    Row(
        "tools/webfoot/authored_placements.py", 2, 2, 0,
        "two comments citing the map entry byte read at 0x08008CA2 and "
        "0x08008CD2 and the loader 0x08008C9E. No ticket covers this file yet: "
        "recorded debt.",
    ),
    Row(
        "tools/webfoot/binary.py", 2, 1, 0,
        "GBA_ROM_BASE, the image base every reader here subtracts to reach a "
        "file offset. It names the address space, not a location in it; no "
        "ticket covers this file yet: recorded debt.",
    ),
    Row(
        "tools/webfoot/compressed_dialogue.py", 5, 3, 0,
        "two comments and one note citing the record loop 0x08012552 that "
        "branches on the record word and the compressed-dialogue consumer "
        "0x08012230. No ticket covers this file yet: recorded debt.",
    ),
    Row(
        "tools/webfoot/data/enemy_families.py", 1, 1, 0,
        "the donor family's defeat callback 0x08018951, the third word of a type "
        "record's +0x14 descriptor: the family a project enemy type may be copied "
        "from. The family is computed from the image rather than typed as a row "
        "list, so this is the only address the file needs.",
    ),
    Row(
        "tools/webfoot/data/pause_menu_sites.yaml", 26, 17, 0,
        "the two pause method-table seams and their evidence: the draw and update "
        "entries of the table at 0x0800EF84, the dispatcher that adds the base and "
        "branches, and the runtime register state that identifies the page.",
    ),
    Row(
        "tools/webfoot/data/placement_contracts.py", 40, 40, 404,
        "the placement and event corpus itself: 404 decimal ROM addresses in 347 "
        "distinct values, plus 40 hex lines naming the VM roots, handlers and "
        "record tables those entries hang from. PINMAP-10 gives the corpus a "
        "map-shaped home and is the largest row; it waits on an owner decision "
        "about that shape.",
    ),
    Row(
        "tools/webfoot/data/roms.yaml", 377, 255, 0,
        "the profile's own declared table addresses: character table, object and "
        "background palettes, the portrait pointer array, factory raw, constructor, "
        "and the per-title rows the shipping tools resolve against, in both hex "
        "spellings. This file is the destination the PINMAP-04 to PINMAP-09 removals "
        "read from rather than a removal target; no ticket removes the profile's own "
        "rows. PINMAP-05 added eight of them, the optional keys the text-edit row now "
        "reads, seven as full GBA addresses: :86, :89, :90, :91 and :93-96. PINMAP-07a "
        "added the ten declared code anchors at :152-188, which is what moved this row "
        "51 -> 61 and its ROM-space count 45 -> 55. APPEARANCE-OFFSET-KEYS-001 added "
        "the appearance offset declarations at :151-152, which is what moved this row "
        "61 -> 63; only :151 counts, because the count offsets at :152 are five-digit "
        "file offsets rather than ROM addresses. O1 added the LOG2 generated-expansion "
        "declaration, which moved this row 69 -> 77 and its ROM-space count 55 -> 60; "
        "the LG2-068 ledger entry names those lines. O2b added the LOG2 enemy stat "
        "declaration and its evidence, which moved this row 77 -> 89 and its ROM-space "
        "count 60 -> 68; the O2b ledger entry names those twelve lines. DBZ-008 added the "
        "eighteen LOG1 script families, which moved this row 89 -> 179 and its ROM-space "
        "count 68 -> 158: each family declares its word-table address and its first record "
        "start, and three lines of its evidence cite that table address, its selector table "
        "address and the pool address; its ledger entry names all ninety catalogue lines. "
        "Recorded debt.",
    ),
    Row(
        "tools/webfoot/data/script_effects.py", 6, 5, 0,
        "the dialogue effect's native handler word 0x08003031 and docstring "
        "citations of the handler 0x08003030 and the routine 0x0806BCE8, plus "
        "DBZ-051's set_save_flag declaration: its handler word 0x080007E6, the "
        "handler citation 0x08004380 it calls, and the flag-byte derivation "
        "0x030010D9. The three added lines are named in the DBZ-051 ledger entry.",
    ),
    Row(
        "tools/webfoot/data/script_specs.py", 9, 9, 0,
        "the per-script handler run 0x08003C75..0x08003FEF held in the script "
        "spec table as the words the VM dispatches on, plus DBZ-008's module "
        "docstring line naming the 16-byte operand-width table's ROM address "
        "0x08142386, which is what moved this row 8 -> 9. No ticket removes the "
        "handler run: recorded debt.",
    ),
    Row(
        "tools/webfoot/dialogue_edit.py", 3, 1, 0,
        "one ROM base constant, used to convert a record address to a file "
        "offset. No ticket covers this file yet: recorded debt.",
    ),
    Row(
        "tools/webfoot/dialogue_repack.py", 2, 1, 0,
        "one ROM base constant, used to convert a record address to a file "
        "offset. No ticket covers this file yet: recorded debt.",
    ),
    Row(
        "tools/webfoot/donor_resources.py", 6, 1, 0,
        "the donor's appearance table 0x074D380 and its word stride, the text pointer table 0x06BCE8, the portrait-array pool word 0x08012194, the global OBJ palette bank 0x05652C, the primary dialogue box container 0x071758, and the raw font span 0x06E05C with the digest that guards it. Every one is a measured donor offset this ticket's extraction is derived from; no donor byte is copied into the module.",
    ),
    Row(
        "tools/webfoot/enemy_randomizer/compatibility.py", 3, 3, 0,
        "comments citing the shared placement table 0x080555A0 and the one "
        "factory and constructor pair 0x0800FD55 and 0x0800F68C that serve the "
        "whole corpus. No ticket covers this file yet: recorded debt.",
    ),
    Row(
        "tools/webfoot/enemy_randomizer/config.py", 1, 1, 0,
        "one comment citing the level-cap comparison site 0x08013A00 where the "
        "cap of 200 was read. No ticket covers this file yet: recorded debt.",
    ),
    Row(
        "tools/webfoot/enemy_randomizer/eligibility.py", 1, 1, 0,
        "one comment citing the verified script handler 0x0800421F that a "
        "candidate record dispatches through. No ticket covers this file yet: "
        "recorded debt.",
    ),
    Row(
        "tools/webfoot/enemy_randomizer/enemy_type.py", 1, 1, 0,
        "one comment citing the actor character pointer table 0x086B6BDC that "
        "the randomizer indexes. PINMAP-06 removes the same address from the "
        "export path only; this file is not named by any ticket yet, so it is "
        "recorded debt.",
    ),
    Row(
        "tools/webfoot/events.py", 8, 5, 0,
        "the event compiler's region class and activation handler words written into "
        "an authored region record, and the two interpreter breakpoints of the trace "
        "script it writes; the other three lines are a 28-bit item bound, the "
        "appears-rule condition words and the save flag byte base. No ticket moves "
        "them to the profile catalogue yet: recorded debt.",
    ),
    Row(
        "tools/webfoot/formats/map_entry.py", 1, 1, 0,
        "one comment citing the loader 0x08008C9E whose byte read bounds the "
        "entry count. No ticket covers this file yet: recorded debt.",
    ),
    Row(
        "tools/webfoot/formats/map_graphics.py", 17, 14, 0,
        "the layer-handler words DOMINANT_LAYER_HANDLER, "
        "ABSENT_LAYER_HANDLER and ABSENT_LAYER_RECORD, "
        "plus citations of the container constructors 0x08007B63, 0x0800897B and "
        "the descriptor reads 0x080088E6, 0x08008924. PINMAP-07b resolved the two "
        "handler words by name through the profile's code anchors; the record "
        "address and the constructor citations stay because they are citations "
        "rather than consumers.",
    ),
    Row(
        "tools/webfoot/formats/map_placements.py", 6, 3, 0,
        "the record tail 0x080555A0 and 0x080716EC plus citations of the layout "
        "and loader sites 0x08008C9E and 0x08017DA3. PINMAP-07b read FACTORY_RAW "
        "from placement_types.factory_raw and the handler and sibling words from "
        "their named anchors, which removed three hex lines.",
    ),
    Row(
        "tools/webfoot/formats/map_slots.py", 3, 1, 0,
        "one comment citing the slot source 0x080755C0 and the halfwords at its "
        "header. No ticket covers this file yet: recorded debt.",
    ),
    Row(
        "tools/webfoot/formats/map_transitions.py", 20, 14, 0,
        "TRANSITION_CLASS_A_RAW and TRANSITION_CLASS_B_RAW, 0x08007675 and "
        "0x080072CD, plus comments citing the class methods 0x080075AC and "
        "0x080071F8, the record layouts 0x08008d44, 0x0800CEF4 and the pool "
        "words 0x080159B0, 0x0800A890 and 0x080707D8. No ticket names this file "
        "yet: recorded debt.",
    ),
    Row(
        "tools/webfoot/formats/placement_links.py", 3, 3, 0,
        "comments citing the byte-branch sites 0x080040BA..0x080040C2, the "
        "dialog block 0x080040EA and the handler 0x08003030 that routes into "
        "0x0802BFBC. No ticket covers this file yet: recorded debt.",
    ),
    Row(
        "tools/webfoot/formats/script_vm.py", 4, 2, 0,
        "DBZ-008's record grammar names the interpreter sites it rests on in two "
        "docstring lines: the per-activation counter at 0x0800A3EA-0x0800A3F2 tested "
        "at 0x0800A3F4-0x0800A3FA, and the step gate at 0x0800A4CC-0x0800A4D8 "
        "reloading from 0x0800A608. The other two counted lines predate DBZ-008: the "
        "signed-magnitude encoder's range guards 0x7fffffff and 0x3fffffff, which are "
        "integer bounds rather than addresses. Only the two docstring lines are "
        "ROM-space, which is what moved the ROM-space file count.",
    ),
    Row(
        "tools/webfoot/formats/sprite_graphics.py", 6, 6, 0,
        "comments citing the frame arithmetic sites 0x0800F3C0..0x0800F3CE and "
        "the attribute reads 0x0800F204, 0x0800F22A, 0x0800F206, 0x0800F22E, "
        "0x0800F1C2 and 0x0800F24C. No ticket covers this file yet: recorded "
        "debt.",
    ),
    Row(
        "tools/webfoot/formats/stat_tables.py", 9, 4, 0,
        "one comment quoting the toolkit's ROM offset convention with the base "
        "0x08000000, plus the LOG2 record's provenance cited in the docstring that "
        "declares it: the enemy constructor 0x0800E280, its load 0x0800E2E6 and store "
        "0x0800E2EA, and the runtime entity 0x0203BC28 whose cached pointer proved the "
        "HP field. One more is the ROM window's 0x02000000 width in the LOG2 "
        "recognisability predicate, which is how a descriptor pointer at +0x14 is told "
        "from a stat byte, and is one of the three positive checks that predicate makes "
        "instead of deferring to Buu's, which accepts LOG2 records. O2b added all five; "
        "its ledger entry names them. Recorded debt.",
    ),
    Row(
        "tools/webfoot/formats/webfoot_lz.py", 6, 2, 0,
        "one docstring citation of the retail packed decoder 0x087B79E4 and the "
        "Thumb-to-ARM veneer 0x08049120 it is reached through. No ticket covers "
        "this file yet: recorded debt.",
    ),
    Row(
        "tools/webfoot/graphics.py", 6, 5, 0,
        "comments citing the sprite-id accessor 0x08000158 and its literal site "
        "0x0800015E, the party re-entry path 0x0801713C and its site 0x0801713E, "
        "and the character pointer table 0x086B6BDC. No ticket covers this file "
        "yet: recorded debt.",
    ),
    Row(
        "tools/webfoot/graphics_authoring.py", 1, 1, 0,
        "one comment citing the declared expansion window 0x08800000 that the "
        "profile maps a file offset into. No ticket covers this file yet: "
        "recorded debt.",
    ),
    Row(
        "tools/webfoot/handles.py", 3, 2, 0,
        "comments citing the handle pack and unpack sites 0x08012240, 0x08012244 "
        "and 0x08012246. No ticket covers this file yet: recorded debt.",
    ),
    Row(
        "tools/webfoot/layout.py", 10, 8, 0,
        "comments citing the character pointer table 0x086B6BDC, the accessor "
        "and re-entry words 0x08000158, 0x0800015E, 0x0801713C and 0x0801713E, "
        "the map entry table 0x0808E2E0, the key lookup 0x08008A0A and "
        "0x080089FC and the count reader 0x080125E0. No ticket covers this file "
        "yet: recorded debt.",
    ),
    Row(
        "tools/webfoot/map_authoring.py", 11, 10, 0,
        "comments and one subtraction citing the key lookup 0x080089FC, the "
        "count reader 0x080125E0, the literal pool site 0x08008A0A and the ROM "
        "base 0x08000000. No ticket covers this file yet: recorded debt.",
    ),
    Row(
        "tools/webfoot/map_chunk.py", 1, 1, 0,
        "one line subtracting the ROM base 0x08000000 from a resolved template "
        "address to get a file offset. No ticket covers this file yet: recorded "
        "debt.",
    ),
    Row(
        "tools/webfoot/map_render.py", 3, 3, 0,
        "the background palette address "
        "0x080701B0 repeated in two provenance strings, and a comment citing the "
        "engine loop 0x08009C02..0x08009C12. PINMAP-07b resolved "
        "SUPPORTED_LAYER_HANDLER by name; the palette strings stay because they "
        "are provenance text that shadows a profile key rather than code words.",
    ),
    Row(
        "tools/webfoot/map_resize.py", 3, 3, 0,
        "comments citing the camera clamp 0x080094F0 and the camera update "
        "0x08009744, plus one ROM base subtraction 0x08000000. No ticket covers "
        "this file yet: recorded debt.",
    ),
    Row(
        "tools/webfoot/map_transitions.py", 5, 4, 0,
        "comments citing the pair loader 0x08009676, the registry walk "
        "0x08012664 and the key-scan sites 0x08008A0E, 0x08008A14 and "
        "0x080089FC. No ticket covers this file yet: recorded debt.",
    ),
    Row(
        "tools/webfoot/maps.py", 7, 3, 0,
        "comments citing map entry 39's slot word 0x080755C0, the factory word "
        "0x0800FD55 in a slot and the engine loop bounds 0x08008CA2 and "
        "0x08008CD2. No ticket covers this file yet: recorded debt.",
    ),

    Row(
        'tools/webfoot/patchsource/log1-actor-runtime/combat.c', 45, 33, 0,
        'Pinned original LOG1 projectile methods, player-object bounds, native charge and damage dispatch, plus donor melee rectangles through generated extern data; scope is checked by canonical-image fingerprints and the runtime builder.',
    ),
    Row(
        'tools/webfoot/patchsource/log1-actor-runtime/renderer.c', 41, 9, 0,
        'Pinned LOG1 actor list, native palette registry, OAM staging buffer, hardware palette window, damage wrapper and culling method; these are the target ABI consumed by the lossless renderer. The pending palette queue lives in the EWRAM gap between the bounded staging window end 0x02013024 and the retail stats heap base 0x02013224.',
    ),
    Row(
        'tools/webfoot/patchsource/log1-actor-runtime/trampoline.s', 10, 10, 0,
        'Native renderer continuation, melee success/miss addresses and the dialogue entry prologue (record table and resume address); the builder checks their original entry bytes and independent review verifies the calling contexts.',
    ),
    Row(
        'tools/webfoot/patchsource/log1-actor-runtime/transform.c', 12, 6, 0,
        'Pinned LOG1 state-nine dispatch, native object bitmap and palette registry, appearance transition and native rebind methods; no donor artwork is embedded in this source.',
    ),
    Row(
        "tools/webfoot/patchsource/log1-bf-presentation/BOX_SOURCE.md", 25, 11, 0,
        "lane A's provenance note for the box payloads: the LOG1 page object 0x02029D94 with its inline cell map, the fill and publish sites 0x08008D14 and 0x08008D8A, the retail nine-slice tile run 0x64..0x68, the EWRAM staging cursor 0x0200B024, the shadow-OAM base 0x0202BE24 and the VRAM flush bound 0x06018000. The addresses are the evidence for the seams, not an input to a build.",
    ),
    Row(
        "tools/webfoot/patchsource/log1-bf-presentation/SOURCE.md", 24, 14, 0,
        "lane B's provenance note for the two payload blocks: the method table base 0x0800EF28 and its entries, the consumer instructions 0x08009828..0x08009830, the retained retail routines 0x08005380 and 0x080097F8, the vtable 0x08011480 and the two palette-blob constants. The addresses are the evidence for the seam, not an input to a build.",
    ),
    Row(
        "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md", 30, 27, 0,
        "lane A's provenance note for the donor text rules and the target seam: the "
        "method table 0x0800EF28 with the retail wrapper 0x08005392 and its callback "
        "0x080051B5, the retail body 0x08009328 and its entry 0x08009329, the donor "
        "rasteriser 0x0803F444 and composer 0x0800AED0, the column-mask table "
        "0x080116B4, and the EWRAM staging span 0x0200B024. The addresses are the "
        "evidence for the seam, not an input to a build.",
    ),
    Row(
        "tools/webfoot/patchsource/log1-bf-presentation/box-sites.toml", 11, 6, 0,
        "lane A's declaration of the three box seams and their expected words: the vtable word at file 0x0011480 carrying 0x08005109, the vtable word at 0x0011490 carrying 0x08005119, and file 0x0000EF30 carrying 0xFFFF6459 under base 0x0800EF28. The expect values are the guards the build checks.",
    ),
    Row(
        "tools/webfoot/patchsource/log1-bf-presentation/box.s", 7, 2, 0,
        "lane A's payload source: the page object 0x02029D94 and its inline map, the retail publish 0x08008D8A, the nine-slice tiles 0x64..0x68, the EWRAM staging cursor 0x0200B024, the shadow-OAM base 0x0202BE24 and the retained per-frame box draw 0x08005381. A payload cannot reach a retail routine without naming it.",
    ),
    Row(
        "tools/webfoot/patchsource/log1-bf-presentation/portrait.s", 7, 4, 0,
        "lane B's payload source: the cache array 0x03000994, the two palette-blob constants 0x08541748 and 0x0853E4E8, the palette window 0x05000200, the OBJ VRAM base 0x06010000, the shadow-OAM base 0x0202BE24 and the retail renderer 0x08005119. A payload cannot reach a retail routine without naming it.",
    ),
    Row(
        "tools/webfoot/patchsource/log1-bf-presentation/presentation.s", 1, 1, 0,
        "lane B's stage-1 payload source: the NPC method table base 0x0800EF28 and the retained per-frame box draw 0x08005381 it calls. The wrapper is a branch to a retail address, so the address has to appear in it.",
    ),
    Row(
        "tools/webfoot/patchsource/log1-bf-presentation/sites.toml", 7, 3, 0,
        "lane B's declaration of the two seams and their expected words: file 0x0000EF30 with 0xFFFF6459 under base 0x0800EF28, and the absolute vtable word at 0x0011490 carrying 0x08005119. The expect values are the guards the build checks.",
    ),
    Row(
        "tools/webfoot/patchsource/log1-bf-presentation/text-sites.toml", 5, 3, 0,
        "lane A's declaration of the text seam: entry 0x0000EF44 under base 0x0800EF28, canonical 0xFFFF646B resolving to 0x08005393, and the donor span 0x03DEA6-0x03DEF0 the font table is read from. The expect value and the span are the guards the build checks.",
    ),
    Row(
        "tools/webfoot/patchsource/log1-bf-presentation/text.s", 9, 4, 0,
        "lane A's text-controller payload source: the page object 0x02029D94, the render context 0x03000794, the EWRAM staging span 0x0200B024, the input-poll words 0x03003D14 and 0x03003D10, the retail update body 0x08009329 with its callback 0x080051B5, the retail composer and rasteriser 0x0800AED0 / 0x0803F444, and the ROM window bounds. A payload cannot reach a retail routine without naming it.",
    ),
    Row(
        "tools/webfoot/patchsource/log1-pause-menu/menu.c", 44, 12, 0,
        "the pause page's memory-mapped targets: the display, BG and blend registers, "
        "the key word, the level, experience, HP, Ki, option and quest words the page "
        "reads, the level table it subtracts from, and the two retail routines it calls "
        "to leave the page the way retail does.",
    ),
    Row(
        "tools/webfoot/patchsource/log1-pause-menu/seam.s", 17, 9, 0,
        "the close seam's retail targets: the field install entry it displaces, the "
        "three retail routines it calls in its place, the tail it re-enters, the palette "
        "source it copies, the DMA register block, the DISPSTAT wait register and the "
        "close flag it reads and clears. The addresses are the seam's evidence, not an "
        "input to a build.",
    ),
    Row(
        "tools/webfoot/patchsource/log1-sprite-limits/bank.s", 4, 4, 0,
        "the per-piece palette bank selector: the retail bank read at 0x0800B09A, "
        "the two displaced instructions it replaces, and the actor and cell field "
        "offsets its header comment names. Every literal is a retail site the "
        "selector stands in for, and sprite_limits.py asserts the same addresses.",
    ),
    Row(
        "tools/webfoot/patchsource/log1-sprite-limits/budget.s", 3, 1, 0,
        "the draw guard prologue: the object tile and OAM cursor fields it reads at "
        "0x0202BE24 and the staging window base it subtracts, all named in its header "
        "comment. The guard adds no address of its own.",
    ),
    Row(
        "tools/webfoot/pause_menu.py", 34, 33, 0,
        "the donor resource addresses the build-time extractor reads (panel container, "
        "BG palette, font and string tables), the pause method-table base and its two "
        "seam offsets, the dialogue's per-frame entry and its own relative base, and the "
        "payload's nominal expansion address.",
    ),
    Row(
        "tools/webfoot/placement_events.py", 2, 2, 0,
        "the two script dispatch handler words 0x0800424F and 0x0800421F, cited "
        "in comments over the counts the codec already verifies. PINMAP-07b did "
        "not need a line here: the module already reads HANDLERS and "
        "SCRIPT_DISPATCH_HANDLER from map_placements by name.",
    ),
    Row(
        "tools/webfoot/project/model.py", 6, 3, 0,
        "comments citing the unresolved byte 0x08007282, the count reader "
        "0x080125E0 and the key lookup 0x080089FC. No ticket covers this file "
        "yet: recorded debt.",
    ),
    Row(
        "tools/webfoot/project/patchdoc.py", 7, 3, 0,
        "the encoders' own constants and the cited retail facts: the ROM window, the ARMv4T branch range, the method-table consumer at 0x0800982c and the relative-base discussion. The encoders refuse an out-of-range value, so the bound they check is named beside the check.",
    ),
    Row(
        "tools/webfoot/release_identity.py", 1, 1, 0,
        "the one hit is a Windows process creation-flag fallback spelled "
        "0x08000000, not a ROM address. It is a pattern coincidence kept visible "
        "as a row; no ticket covers it and none is needed. Recorded debt.",
    ),
    Row(
        "tools/webfoot/relocation_proof.py", 1, 1, 0,
        "the one hit writes the Game Pak entry point 0x08000100 into the image "
        "header at 0xC0 while proving a relocation. No ticket covers this file "
        "yet: recorded debt.",
    ),
    Row(
        "tools/webfoot/sprite_attachment.py", 7, 5, 0,
        "the object factory word 0x08017DA3 and the other sibling factory "
        "0x080111A9 in the module docstring, the entry class 0x0800A7A1, the "
        "placement family 0x0800FD55 and the record run the comment measures "
        "from 0x0807831C. PINMAP-07b resolved the two live words by name; the "
        "docstring and comment citations stay.",
    ),
    Row(
        "tools/webfoot/sprite_limits.py", 13, 11, 0,
        "the LOG1 actor draw payload module: the retail draw method 0x0800B01E, its "
        "body and literal-pool extents, the bank read 0x0800B09A it displaces, the "
        "staging base and object window, the art table 0x085C0C80 and the state "
        "window bound. Every literal is read from the pinned image or asserted by "
        "the module's own check.",
    ),
    Row(
        'tools/webfoot/sprite_runtime.py', 21, 15, 0,
        'Canonical LOG1 runtime patch seams, entry-byte expectations, projectile method pointers, visibility census and first-pass expansion link addresses; the second pass reuses the shared allocator and validated writer.',
    ),
    Row(
        'tools/webfoot/sprite_runtime_assets.py', 16, 14, 0,
        'Approved canonical donor definitions, player body and melee-rectangle tables, projectile records and source palettes; asset bytes are derived from verified private inputs at build time.',
    ),
    Row(
        "tools/webfoot/sprite_swap.py", 6, 6, 0,
        "the ROM base 0x08000000, used at six sites to convert an offset to the "
        "address a reference word holds and back. No target address is spelled "
        "here: PINMAP-04 removed the three that shadowed live profile keys, and "
        "the character table, the object palette and the portrait pointer array "
        "now resolve from the actor-sprite layout the caller hands in. The "
        "animation pointer offset 0x54 is still a local constant shadowing the "
        "live key animation_pointer_offset; recorded debt.",
    ),
    Row(
        "tools/webfoot/stats.py", 1, 1, 0,
        "one comment citing the level-cap comparison site 0x08013A00 where the "
        "cap was read. No ticket covers this file yet: recorded debt.",
    ),
    Row(
        "tools/webfoot/textedit/engine.py", 6, 1, 0,
        "the text tool's private per-title row at engine.py:178-199 is gone: its nine "
        "already-carried values read from the packaged profile and its twelve "
        "carrierless ones arrive through new optional catalogue keys, so no number in "
        "that range is spelled here and a profile edit moves the tool. What remains is "
        "the RETAIL container-table offset 0x7B5B64 at :135, a dataclass default with "
        "no profile key; the comments at :155-156, :1087, :1652 and :1690-1691 cite it "
        "and the 0x6F393C art array as evidence; and :253-256 keeps the proven-reference "
        "range, whose evidence is the in-pool 11-of-2,639 against the out-of-pool "
        "281-of-907 measured on the Release 4A image. Debt: the retail offset should "
        "become a profile key so the row has no defaulted address.",
    ),
    Row(
        "tools/webfoot/workbench/map_browser_tab.py", 2, 2, 0,
        "two comments, one naming the address space base 0x08000000 while "
        "explaining why -1 cannot be a pointer, one quoting the key lookup "
        "0x080089FC as the engine's map identity. No ticket covers this file "
        "yet: recorded debt.",
    ),

)


def census_paths() -> list[str]:
    """Every tracked path under ``tools/``.

    The index is the only source. Nothing here walks the disk, so a path that
    exists on disk but was never added is invisible by construction.
    """
    return [path for path in tracked_files() if path.startswith("tools/")]


def enforcement_paths() -> list[str]:
    """The census set minus the instrument directories."""
    excluded = tuple(directory for directory, _ in INSTRUMENT_DIRECTORIES)
    return [path for path in census_paths() if not path.startswith(excluded)]


def decimal_in_rom_space(line: str) -> bool:
    """Whether ``line`` carries a decimal integer token inside ROM space."""
    for match in DECIMAL.finditer(line):
        try:
            value = int(match.group().replace("_", ""))
        except ValueError:
            continue
        if ROM_START <= value < ROM_END:
            return True
    return False


def count_line(line: str) -> tuple[int, int, int]:
    """``(hex5, rom_hex, decimal)`` for one line, each 0 or 1.

    The whole parser lives here, so a spelling is exercised at the level the
    patterns live and ``scan`` stays a file-reading wrapper.
    """
    hex5 = rom_hex = 0
    for match in HEX_TOKEN.finditer(line):
        token = match.group()
        if len(token[2:].replace("_", "")) >= 5:
            hex5 = 1
        try:
            value = int(token, 16)  # accepts 0x / 0X and the digit separators
        except ValueError:
            continue  # a token that will not parse counts by length, not as address
        if ROM_START <= value < ROM_END:
            rom_hex = 1
    return hex5, rom_hex, 1 if decimal_in_rom_space(line) else 0


def count_lines(lines: Iterable[str]) -> tuple[int, int, int]:
    """The three per-line counts summed over ``lines``."""
    total = [0, 0, 0]
    for line in lines:
        for index, value in enumerate(count_line(line)):
            total[index] += value
    return total[0], total[1], total[2]


def scan(paths: Sequence[str]) -> dict[str, tuple[int, int, int]]:
    """Per-line counts for every path that carries a literal.

    Returns only the paths with at least one hit. An empty path list, or a path
    that cannot be read, is a ``CensusError``: a measurement nobody can trust is
    never reported as a count of zero. An absolute path is read where it points,
    which is what lets a caller measure a file outside the worktree.
    """
    if not paths:
        raise CensusError("the scan was handed no path to read")
    counted: dict[str, tuple[int, int, int]] = {}
    for path in paths:
        try:
            text = (REPOSITORY_ROOT / path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise CensusError(f"{path}: cannot be read ({error})") from error
        counts = count_lines(text.splitlines())
        if any(counts):
            counted[path] = counts
    return counted


def totals(
    per_file: Mapping[str, tuple[int, int, int]],
) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    """``((hex5 lines, files), (rom hex lines, files), (decimal lines, files))``."""
    columns: list[tuple[int, int]] = []
    for index in range(3):
        values = [counts[index] for counts in per_file.values()]
        columns.append((sum(values), sum(1 for value in values if value)))
    return columns[0], columns[1], columns[2]


def carrying_paths(per_file: Mapping[str, tuple[int, int, int]]) -> list[str]:
    """The sorted paths that carry a ROM-space hex or decimal literal."""
    return sorted(
        path for path, counts in per_file.items() if counts[1] or counts[2]
    )


PIN_NAMES: tuple[str, ...] = (
    "CENSUS_INVENTORY_S4",
    "CENSUS_HEX5",
    "ENFORCEMENT_HEX5",
    "ENFORCEMENT_ROM_HEX",
    "ENFORCEMENT_DECIMAL",
)


def pinned() -> dict[str, tuple[int, int]]:
    """Every pin by name, read from this module, so a caller cannot pick a subset."""
    return {name: globals()[name] for name in PIN_NAMES}


def coupled(paths: Sequence[str]) -> dict:
    """The measurements a change to ``paths`` can move, and this module's rows.

    ``pins`` is every pin, never a subset: the whole-tree pair and the
    enforcement pair are measured over the same set, so a change inside the set
    moves both and a change listed under one name alone is an incomplete
    declaration. ``rows`` carries the per-file counts of any changed path that
    already has an exemption row, which is the number that moves with it.
    """
    measured = sorted(path for path in paths if path.startswith("tools/"))
    wanted = set(measured)
    return {
        "pins": pinned(),
        "rows": {
            row.path: (row.hex5, row.rom_hex, row.decimal)
            for row in EXEMPTIONS
            if row.path in wanted
        },
        "measured_paths": measured,
        "unmeasured_paths": sorted(path for path in paths if path not in wanted),
    }


class LedgerEntry(NamedTuple):
    """One ticket's declared move of the whole-tree pair, against the publication.

    ``lines`` and ``files`` are signed deltas of that tree measurement, and ``named``
    is the evidence: every ``path:line`` that left or arrived, so the arithmetic can be
    re-measured line by line instead of taken on trust. A move that is not here fails
    the reconciliation guard by name.
    """

    ticket: str
    lines: int
    files: int
    named: tuple[str, ...]
    reason: str


#: Every declared move of the ``HEX5`` tree pair since ``INVENTORY.md`` section 4 was
#: published. Append-only: a ticket that moves the measured pair appends its own entry
#: in its own commit, and no entry is rewritten in place.
RECONCILIATION_LEDGER: tuple[LedgerEntry, ...] = (
    LedgerEntry(
        "PINMAP-02", 1, 0,
        ("tools/runtime/rom008_query_probe.py:105",),
        "the widened token found one line section 4's pattern cannot see: the literal "
        "is spelled with a digit separator",
    ),
    LedgerEntry(
        "PINMAP-04", -3, 0,
        (
            "tools/webfoot/sprite_swap.py:61",
            "tools/webfoot/sprite_swap.py:63",
            "tools/webfoot/sprite_swap.py:67",
            "tools/webfoot/sprite_swap.py:68",
            "tools/webfoot/data/roms.yaml:21",
        ),
        "four counted lines left the sprite swap planner - the character-table and "
        "object-palette constants at :61 and :63, the comment citing the portrait "
        "accessor at :67, and the portrait-array constant at :68 - and one arrived in "
        "the profile catalogue, which is a net -3",
    ),
    LedgerEntry(
        "PINMAP-05", -3, 0,
        (
            "tools/webfoot/textedit/engine.py:155",
            "tools/webfoot/textedit/engine.py:156",
            "tools/webfoot/textedit/engine.py:158",
            "tools/webfoot/textedit/engine.py:179",
            "tools/webfoot/textedit/engine.py:186",
            "tools/webfoot/textedit/engine.py:187",
            "tools/webfoot/textedit/engine.py:189",
            "tools/webfoot/textedit/engine.py:191",
            "tools/webfoot/textedit/engine.py:194",
            "tools/webfoot/textedit/engine.py:195",
            "tools/webfoot/textedit/engine.py:197",
            "tools/webfoot/data/roms.yaml:86",
            "tools/webfoot/data/roms.yaml:89",
            "tools/webfoot/data/roms.yaml:90",
            "tools/webfoot/data/roms.yaml:91",
            "tools/webfoot/data/roms.yaml:93",
            "tools/webfoot/data/roms.yaml:94",
            "tools/webfoot/data/roms.yaml:95",
            "tools/webfoot/data/roms.yaml:96",
        ),
        "eleven counted lines left the text-edit engine - the comments at :155-156 and "
        ":186 and the row's literals at :158, :179, :187, :189, :191, :194, :195 and "
        ":197 - and eight arrived in the profile catalogue, the new optional keys at "
        ":86, :89, :90, :91 and :93-96, which is a net -3. The engine row fell 17 -> 6 "
        "lines and its ROM-space count 5 -> 1; the catalogue row rose 43 -> 51 and its "
        "ROM-space count 37 -> 45 because seven of the new keys are full GBA addresses",
    ),
    LedgerEntry(
        "PINMAP-06", -2, 0,
        (
            "tools/export/canonical.py:164",
            "tools/export/canonical.py:228",
        ),
        "two counted lines left the export reader: the sprite-definition run constant "
        "at :164 and the appearance-table constant at :228, both replaced by a read of "
        "the profile keys tables.actor_sprites.character_table_address and "
        "tables.appearances.address, which is a net -2 and no files. The canonical.py "
        "row fell 11 -> 9 lines and its ROM-space count 11 -> 9, and the enforcement "
        "pair fell by the same two lines because that file is in the enforcement set",
    ),
    LedgerEntry(
        "PINMAP-07a", 10, 0,
        (
            "tools/webfoot/data/roms.yaml:152",
            "tools/webfoot/data/roms.yaml:156",
            "tools/webfoot/data/roms.yaml:160",
            "tools/webfoot/data/roms.yaml:164",
            "tools/webfoot/data/roms.yaml:168",
            "tools/webfoot/data/roms.yaml:172",
            "tools/webfoot/data/roms.yaml:176",
            "tools/webfoot/data/roms.yaml:180",
            "tools/webfoot/data/roms.yaml:184",
            "tools/webfoot/data/roms.yaml:188",
        ),
        "ten counted lines arrived in the profile catalogue: the ten declared code "
        "anchor addresses, the placement factory raw word, the three placement "
        "handlers, the two sibling factories, the three layer handlers and the entry "
        "class, which the profile's resolver now reads by name. No line left and no "
        "file arrived, so the tree pair is +10 lines and the enforcement pair moved "
        "with it; the catalogue row rose 51 -> 61 and its ROM-space count 45 -> 55",
    ),
    LedgerEntry(
        "PINMAP-07b", -12, 0,
        (
            "tools/webfoot/formats/map_placements.py:8",
            "tools/webfoot/formats/map_placements.py:13",
            "tools/webfoot/formats/map_placements.py:14",
            "tools/webfoot/formats/map_placements.py:15",
            "tools/webfoot/formats/map_placements.py:16",
            "tools/webfoot/formats/map_placements.py:176",
            "tools/webfoot/formats/map_graphics.py:133",
            "tools/webfoot/formats/map_graphics.py:134",
            "tools/webfoot/formats/map_graphics.py:166",
            "tools/webfoot/map_render.py:73",
            "tools/webfoot/sprite_attachment.py:218",
            "tools/webfoot/sprite_attachment.py:228",
        ),
        "twelve counted lines left the three consuming modules and none arrived, so the "
        "tree pair is -12 lines and no files and the enforcement pair fell with it. "
        "map_placements.py lines 8, 13, 14, 15, 16 and 176 held FACTORY_RAW, the three "
        "handler keys, SCRIPT_DISPATCH_HANDLER and SIBLING_FACTORIES; map_graphics.py "
        "lines 133, 134 and 166 held DOMINANT_LAYER_HANDLER, ABSENT_LAYER_HANDLER and "
        "TERRAIN_FIELD_LAYER_HANDLER; map_render.py line 73 held SUPPORTED_LAYER_HANDLER; "
        "sprite_attachment.py lines 218 and 228 held the family factory and the entry "
        "class. Those are pre-move line numbers, because the lines no longer exist: each "
        "word now reads its declared anchor by name. placement_events.py keeps its two "
        "citations and is not in the census set",
    ),
    LedgerEntry(
        "PINMAP-09", -9, 0,
        (
            "tools/webfoot/atlas_producers/seed.py:132",
            "tools/webfoot/atlas_producers/seed.py:140",
            "tools/webfoot/atlas_producers/seed.py:254",
            "tools/webfoot/atlas_producers/seed.py:267",
            "tools/webfoot/atlas_producers/seed.py:293",
            "tools/webfoot/atlas_producers/seed.py:425",
            "tools/webfoot/atlas_producers/seed.py:464",
            "tools/webfoot/atlas_producers/seed.py:483",
            "tools/webfoot/atlas_producers/seed.py:511",
            "tools/webfoot/atlas_producers/seed.py:507",
            "tools/webfoot/atlas_producers/seed.py:533",
        ),
        "nine counted lines left tools/webfoot/atlas_producers/seed.py and two arrived, "
        "so the tree pair is -9 lines and no files. The nine held a value the seed now "
        "reads from the profile instead: the placement-type constructor and factory raw "
        "at :132 and :140, the text pool base and its pointer table at :254 and :267, the "
        "MapEntry table base and the character table base at :293 and :425, the "
        "base-stat and enemy-stat table bases at :464 and :483, and the free-window file "
        "offset at :511. The two arrived inside the rewrite that RECORDS the seed's one "
        "conflict as one named row: the consolidated note states the raw base the two "
        "declarations share at :507, and the guard that refuses a moved free window "
        "states the window it requires at :533. Each of the ten rows that restated a "
        "profile key now reads its own declaring key. Those two are current line "
        "numbers because those lines exist; the nine are pre-move line numbers, "
        "because those lines no longer exist",
    ),
    LedgerEntry(
        "APPEARANCE-OFFSET-KEYS-001", 2, 0,
        (
            "tools/webfoot/data/roms.yaml:151",
            "tools/webfoot/data/roms.yaml:152",
        ),
        "two counted lines arrived in the profile catalogue, which is a net +2 and no "
        "files: the new optional key family declaring the appearance table's own "
        "citation offsets at :151-152, which tools/webfoot/appearances.py now reads "
        "instead of carrying the census result as its only statement. The catalogue row "
        "rose 61 -> 63 and its ROM-space count stayed 55, because these are five-digit "
        "file offsets and not ROM addresses. Only data/roms.yaml is in the tree census: "
        "config/roms.yaml is the byte-identical second copy outside tools/",
    ),
    LedgerEntry(
        "LG2-068", 74, 3,
        (
            "tools/research/free_space_audit.py:192",
            "tools/research/free_space_audit.py:218",
            "tools/research/free_space_audit.py:219",
            "tools/research/free_space_audit.py:228",
            "tools/research/free_space_audit.py:232",
            "tools/research/free_space_audit.py:234",
            "tools/research/free_space_audit.py:236",
            "tools/research/free_space_audit.py:244",
            "tools/research/free_space_audit.py:247",
            "tools/research/free_space_audit.py:251",
            "tools/research/free_space_audit.py:277",
            "tools/research/free_space_audit.py:309",
            "tools/research/free_space_audit.py:311",
            "tools/research/free_space_audit.py:313",
            "tools/research/free_space_audit.py:316",
            "tools/research/free_space_audit.py:317",
            "tools/research/free_space_audit.py:318",
            "tools/research/free_space_audit.py:322",
            "tools/research/free_space_audit.py:325",
            "tools/research/free_space_audit.py:411",
            "tools/research/free_space_audit.py:412",
            "tools/research/free_space_audit.py:413",
            "tools/research/free_space_audit.py:417",
            "tools/research/free_space_audit.py:418",
            "tools/research/free_space_audit.py:436",
            "tools/research/free_space_audit.py:437",
            "tools/research/free_space_audit.py:444",
            "tools/research/free_space_audit.py:489",
            "tools/research/free_space_audit.py:492",
            "tools/research/free_space_audit.py:494",
            "tools/research/free_space_audit.py:580",
            "tools/research/free_space_audit.py:581",
            "tools/research/free_space_audit.py:582",
            "tools/research/free_space_audit.py:583",
            "tools/research/free_space_audit.py:586",
            "tools/research/free_space_audit.py:587",
            "tools/webfoot/data/roms.yaml:223",
            "tools/webfoot/data/roms.yaml:1493",
            "tools/webfoot/data/roms.yaml:1502",
            "tools/webfoot/data/roms.yaml:1524",
            "tools/webfoot/data/roms.yaml:1525",
            "tools/webfoot/data/roms.yaml:1541",
            "tools/webfoot/data/roms.yaml:1545",
            "tools/webfoot/data/roms.yaml:1559",
            "tools/webfoot/data/roms.yaml:1560",
            "tools/webfoot/data/roms.yaml:1571",
            "tools/webfoot/data/roms.yaml:1572",
            "tools/webfoot/data/roms.yaml:1574",
            "tools/webfoot/data/roms.yaml:1575",
            "tools/webfoot/data/roms.yaml:1579",
            "tools/runtime/o1_build_relocation.py:3",
            "tools/runtime/o1_build_relocation.py:5",
            "tools/runtime/o1_build_relocation.py:21",
            "tools/runtime/o1_build_relocation.py:22",
            "tools/runtime/o1_build_relocation.py:23",
            "tools/runtime/o1_build_relocation.py:25",
            "tools/runtime/o1_build_relocation.py:26",
            "tools/runtime/o1_build_relocation.py:40",
            "tools/runtime/o1_clean_gameplay_route.lua:29",
            "tools/runtime/o1_clean_gameplay_route.lua:30",
            "tools/runtime/o1_clean_gameplay_route.lua:31",
            "tools/runtime/o1_clean_gameplay_route.lua:32",
            "tools/runtime/o1_clean_gameplay_route.lua:33",
            "tools/runtime/o1_clean_gameplay_route.lua:34",
            "tools/runtime/o1_clean_gameplay_route.lua:35",
            "tools/runtime/o1_clean_gameplay_route.lua:38",
            "tools/runtime/o1_expanded_read_probe.py:6",
            "tools/runtime/o1_expanded_read_probe.py:7",
            "tools/runtime/o1_expanded_read_probe.py:40",
            "tools/runtime/o1_expanded_read_probe.py:41",
            "tools/runtime/o1_expanded_read_probe.py:42",
            "tools/runtime/o1_expanded_read_probe.py:44",
            "tools/runtime/o1_expanded_read_probe.py:45",
            "tools/runtime/o1_expanded_read_probe.py:46",
            "tools/runtime/o1_expanded_read_probe.py:47",
        ),
        "seventy-four counted lines arrived and none left, which is a net +74 and three "
        "files, in three places. Thirty-five arrived in the capacity audit when its model became "
        "per-profile and gained a Legacy of Goku II model: the file carried 1 counted "
        "line at 0fc3d92f and carries 36 now, and every one of the thirty-six is a table "
        "base, stride, extent or reader address cited beside the structure it decodes, "
        "which is what makes the model auditable line by line. Six arrived in the profile "
        "catalogue with the reviewed free-region declaration: the declared file offset at "
        ":641, the two nearest candidate targets at :650, the highest modelled owned end "
        "and highest reference target at :672-673, the branch-target argument's address "
        "at :689, and the undeclared 897-byte window named at :693. The catalogue row "
        "rose 63 -> 69 and its ROM-space count stayed 55, because these are five-digit "
        "file offsets and not ROM addresses. Eight more arrived with O1's generated "
        "expansion declaration: the declared output size at :707 and the addresses its "
        "evidence cites at :708 and :719-727, plus the Buu's Fury output size at :223, "
        "which the matcher pairs by text because O1's own size line is spelled "
        "identically. That moved the row 69 -> 77 and its ROM-space count 55 -> 60. "
        "Twenty-five more arrived with O1's three new runtime tools, which are the "
        "three files this entry adds: the relocation builder names the object, its "
        "literal and the addresses it refuses to write outside, the route script names "
        "the hardware registers it samples, and the probe names the boot literal and "
        "sentinel its controls depend on. Each is the address the tool acts on, cited "
        "beside the code that uses it. Only data/roms.yaml is in the tree census: "
        "config/roms.yaml is the byte-identical second copy outside tools/",
    ),
    LedgerEntry(
        "O2b", 17, 0,
        (
            "tools/webfoot/data/roms.yaml:1441",
            "tools/webfoot/data/roms.yaml:1446",
            "tools/webfoot/data/roms.yaml:1447",
            "tools/webfoot/data/roms.yaml:1448",
            "tools/webfoot/data/roms.yaml:1449",
            "tools/webfoot/data/roms.yaml:1450",
            "tools/webfoot/data/roms.yaml:1451",
            "tools/webfoot/data/roms.yaml:1452",
            "tools/webfoot/data/roms.yaml:1455",
            "tools/webfoot/data/roms.yaml:1456",
            "tools/webfoot/data/roms.yaml:1459",
            "tools/webfoot/data/roms.yaml:1460",
            "tools/webfoot/formats/stat_tables.py:76",
            "tools/webfoot/formats/stat_tables.py:77",
            "tools/webfoot/formats/stat_tables.py:78",
            "tools/webfoot/formats/stat_tables.py:79",
            "tools/webfoot/formats/stat_tables.py:216",
        ),
        "seventeen counted lines arrived and none left, which is a net +17 and no new "
        "file, in two places. Twelve arrived in the profile catalogue with the Legacy "
        "of Goku II enemy stat declaration: the declared table address at :589, and its "
        "evidence citing the constructor and its load and store at :594-596, the two "
        "readers and the three base references at :597-599, the indexing directory and "
        "the table's own extent arithmetic at :600 and :603, the EWRAM class that "
        "follows the table at :604, and the runtime entity and its cached record "
        "pointer at :607-608. That moved the catalogue row 77 -> 89 and its ROM-space "
        "count 60 -> 68; the four non-ROM lines are five-digit file offsets and EWRAM "
        "addresses rather than cartridge addresses. Five more arrived in the stat "
        "codec: four in the LOG2 record's docstring, which cites the constructor, its "
        "load and store, and the runtime entity that proved which word is HP, and one "
        "in the recognisability predicate, where the ROM window's width is how a "
        "descriptor pointer at +0x14 is told from a stat byte. Each is the address the "
        "declaration rests on, cited beside the structure it describes. Only "
        "data/roms.yaml is in the tree census: config/roms.yaml is the byte-identical "
        "second copy outside tools/",
    ),
    LedgerEntry(
        "DBZ-008", 93, 0,
        (
            "tools/webfoot/data/roms.yaml:271",
            "tools/webfoot/data/roms.yaml:275",
            "tools/webfoot/data/roms.yaml:279",
            "tools/webfoot/data/roms.yaml:280",
            "tools/webfoot/data/roms.yaml:281",
            "tools/webfoot/data/roms.yaml:286",
            "tools/webfoot/data/roms.yaml:290",
            "tools/webfoot/data/roms.yaml:294",
            "tools/webfoot/data/roms.yaml:295",
            "tools/webfoot/data/roms.yaml:296",
            "tools/webfoot/data/roms.yaml:301",
            "tools/webfoot/data/roms.yaml:305",
            "tools/webfoot/data/roms.yaml:309",
            "tools/webfoot/data/roms.yaml:310",
            "tools/webfoot/data/roms.yaml:311",
            "tools/webfoot/data/roms.yaml:316",
            "tools/webfoot/data/roms.yaml:320",
            "tools/webfoot/data/roms.yaml:324",
            "tools/webfoot/data/roms.yaml:325",
            "tools/webfoot/data/roms.yaml:326",
            "tools/webfoot/data/roms.yaml:331",
            "tools/webfoot/data/roms.yaml:335",
            "tools/webfoot/data/roms.yaml:339",
            "tools/webfoot/data/roms.yaml:340",
            "tools/webfoot/data/roms.yaml:341",
            "tools/webfoot/data/roms.yaml:346",
            "tools/webfoot/data/roms.yaml:350",
            "tools/webfoot/data/roms.yaml:354",
            "tools/webfoot/data/roms.yaml:355",
            "tools/webfoot/data/roms.yaml:356",
            "tools/webfoot/data/roms.yaml:361",
            "tools/webfoot/data/roms.yaml:365",
            "tools/webfoot/data/roms.yaml:369",
            "tools/webfoot/data/roms.yaml:370",
            "tools/webfoot/data/roms.yaml:371",
            "tools/webfoot/data/roms.yaml:376",
            "tools/webfoot/data/roms.yaml:380",
            "tools/webfoot/data/roms.yaml:384",
            "tools/webfoot/data/roms.yaml:385",
            "tools/webfoot/data/roms.yaml:386",
            "tools/webfoot/data/roms.yaml:391",
            "tools/webfoot/data/roms.yaml:395",
            "tools/webfoot/data/roms.yaml:399",
            "tools/webfoot/data/roms.yaml:400",
            "tools/webfoot/data/roms.yaml:401",
            "tools/webfoot/data/roms.yaml:406",
            "tools/webfoot/data/roms.yaml:410",
            "tools/webfoot/data/roms.yaml:414",
            "tools/webfoot/data/roms.yaml:415",
            "tools/webfoot/data/roms.yaml:416",
            "tools/webfoot/data/roms.yaml:421",
            "tools/webfoot/data/roms.yaml:425",
            "tools/webfoot/data/roms.yaml:429",
            "tools/webfoot/data/roms.yaml:430",
            "tools/webfoot/data/roms.yaml:431",
            "tools/webfoot/data/roms.yaml:436",
            "tools/webfoot/data/roms.yaml:440",
            "tools/webfoot/data/roms.yaml:444",
            "tools/webfoot/data/roms.yaml:445",
            "tools/webfoot/data/roms.yaml:446",
            "tools/webfoot/data/roms.yaml:451",
            "tools/webfoot/data/roms.yaml:455",
            "tools/webfoot/data/roms.yaml:459",
            "tools/webfoot/data/roms.yaml:460",
            "tools/webfoot/data/roms.yaml:461",
            "tools/webfoot/data/roms.yaml:466",
            "tools/webfoot/data/roms.yaml:470",
            "tools/webfoot/data/roms.yaml:474",
            "tools/webfoot/data/roms.yaml:475",
            "tools/webfoot/data/roms.yaml:476",
            "tools/webfoot/data/roms.yaml:481",
            "tools/webfoot/data/roms.yaml:485",
            "tools/webfoot/data/roms.yaml:489",
            "tools/webfoot/data/roms.yaml:490",
            "tools/webfoot/data/roms.yaml:491",
            "tools/webfoot/data/roms.yaml:496",
            "tools/webfoot/data/roms.yaml:500",
            "tools/webfoot/data/roms.yaml:504",
            "tools/webfoot/data/roms.yaml:505",
            "tools/webfoot/data/roms.yaml:506",
            "tools/webfoot/data/roms.yaml:511",
            "tools/webfoot/data/roms.yaml:515",
            "tools/webfoot/data/roms.yaml:519",
            "tools/webfoot/data/roms.yaml:520",
            "tools/webfoot/data/roms.yaml:521",
            "tools/webfoot/data/roms.yaml:526",
            "tools/webfoot/data/roms.yaml:530",
            "tools/webfoot/data/roms.yaml:534",
            "tools/webfoot/data/roms.yaml:535",
            "tools/webfoot/data/roms.yaml:536",
            "tools/webfoot/data/script_specs.py:4",
            "tools/webfoot/formats/script_vm.py:71",
            "tools/webfoot/formats/script_vm.py:75",
        ),
        "ninety-three counted lines arrived and none left, which is a net +93 and no new "
        "file under the HEX5 unit: ninety in the profile catalogue and three in the script "
        "codec. The catalogue's ninety are the eighteen declared LOG1 script families, five "
        "counted lines each: the family's word-table address and its first record start, "
        "plus the three evidence lines that cite that table address, its selector table "
        "address and the pool address. That moved the catalogue row 89 -> 179 and its "
        "ROM-space count 68 -> 158. The other three are each the address the declaration "
        "rests on: the module docstring in script_specs.py naming the 16-byte operand-width "
        "table's ROM address 0x08142386, and two Record docstring lines in "
        "tools/webfoot/formats/script_vm.py naming the interpreter's activation counter and "
        "its step gate. Only data/roms.yaml is in the tree census: config/roms.yaml is the "
        "byte-identical second copy outside tools/. Both arriving codec lines are ROM-space, "
        "which is why the ROM-space pair's file count moved 53 -> 54 while the HEX5 pair's "
        "275 census and 70 enforcement file counts did not move",
    ),
    LedgerEntry(
        "LOG1-BUU-DIALOGUE-BACKPORT-001", 179, 13,
        (
            "tools/webfoot/commands/backport.py:784",
            "tools/webfoot/donor_resources.py:187",
            "tools/webfoot/donor_resources.py:289",
            "tools/webfoot/donor_resources.py:320",
            "tools/webfoot/donor_resources.py:35",
            "tools/webfoot/donor_resources.py:39",
            "tools/webfoot/donor_resources.py:41",
            "tools/webfoot/patchsource/log1-bf-presentation/BOX_SOURCE.md:100",
            "tools/webfoot/patchsource/log1-bf-presentation/BOX_SOURCE.md:102",
            "tools/webfoot/patchsource/log1-bf-presentation/BOX_SOURCE.md:103",
            "tools/webfoot/patchsource/log1-bf-presentation/BOX_SOURCE.md:107",
            "tools/webfoot/patchsource/log1-bf-presentation/BOX_SOURCE.md:119",
            "tools/webfoot/patchsource/log1-bf-presentation/BOX_SOURCE.md:120",
            "tools/webfoot/patchsource/log1-bf-presentation/BOX_SOURCE.md:122",
            "tools/webfoot/patchsource/log1-bf-presentation/BOX_SOURCE.md:137",
            "tools/webfoot/patchsource/log1-bf-presentation/BOX_SOURCE.md:167",
            "tools/webfoot/patchsource/log1-bf-presentation/BOX_SOURCE.md:173",
            "tools/webfoot/patchsource/log1-bf-presentation/BOX_SOURCE.md:179",
            "tools/webfoot/patchsource/log1-bf-presentation/BOX_SOURCE.md:180",
            "tools/webfoot/patchsource/log1-bf-presentation/BOX_SOURCE.md:188",
            "tools/webfoot/patchsource/log1-bf-presentation/BOX_SOURCE.md:27",
            "tools/webfoot/patchsource/log1-bf-presentation/BOX_SOURCE.md:29",
            "tools/webfoot/patchsource/log1-bf-presentation/BOX_SOURCE.md:34",
            "tools/webfoot/patchsource/log1-bf-presentation/BOX_SOURCE.md:48",
            "tools/webfoot/patchsource/log1-bf-presentation/BOX_SOURCE.md:52",
            "tools/webfoot/patchsource/log1-bf-presentation/BOX_SOURCE.md:53",
            "tools/webfoot/patchsource/log1-bf-presentation/BOX_SOURCE.md:54",
            "tools/webfoot/patchsource/log1-bf-presentation/BOX_SOURCE.md:58",
            "tools/webfoot/patchsource/log1-bf-presentation/BOX_SOURCE.md:60",
            "tools/webfoot/patchsource/log1-bf-presentation/BOX_SOURCE.md:61",
            "tools/webfoot/patchsource/log1-bf-presentation/BOX_SOURCE.md:62",
            "tools/webfoot/patchsource/log1-bf-presentation/BOX_SOURCE.md:71",
            "tools/webfoot/patchsource/log1-bf-presentation/SOURCE.md:123",
            "tools/webfoot/patchsource/log1-bf-presentation/SOURCE.md:126",
            "tools/webfoot/patchsource/log1-bf-presentation/SOURCE.md:16",
            "tools/webfoot/patchsource/log1-bf-presentation/SOURCE.md:17",
            "tools/webfoot/patchsource/log1-bf-presentation/SOURCE.md:18",
            "tools/webfoot/patchsource/log1-bf-presentation/SOURCE.md:19",
            "tools/webfoot/patchsource/log1-bf-presentation/SOURCE.md:24",
            "tools/webfoot/patchsource/log1-bf-presentation/SOURCE.md:25",
            "tools/webfoot/patchsource/log1-bf-presentation/SOURCE.md:26",
            "tools/webfoot/patchsource/log1-bf-presentation/SOURCE.md:32",
            "tools/webfoot/patchsource/log1-bf-presentation/SOURCE.md:33",
            "tools/webfoot/patchsource/log1-bf-presentation/SOURCE.md:34",
            "tools/webfoot/patchsource/log1-bf-presentation/SOURCE.md:35",
            "tools/webfoot/patchsource/log1-bf-presentation/SOURCE.md:42",
            "tools/webfoot/patchsource/log1-bf-presentation/SOURCE.md:44",
            "tools/webfoot/patchsource/log1-bf-presentation/SOURCE.md:45",
            "tools/webfoot/patchsource/log1-bf-presentation/SOURCE.md:46",
            "tools/webfoot/patchsource/log1-bf-presentation/SOURCE.md:52",
            "tools/webfoot/patchsource/log1-bf-presentation/SOURCE.md:53",
            "tools/webfoot/patchsource/log1-bf-presentation/SOURCE.md:55",
            "tools/webfoot/patchsource/log1-bf-presentation/SOURCE.md:57",
            "tools/webfoot/patchsource/log1-bf-presentation/SOURCE.md:61",
            "tools/webfoot/patchsource/log1-bf-presentation/SOURCE.md:63",
            "tools/webfoot/patchsource/log1-bf-presentation/SOURCE.md:73",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:106",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:122",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:133",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:148",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:159",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:170",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:171",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:189",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:193",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:194",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:209",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:22",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:23",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:230",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:252",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:30",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:31",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:35",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:36",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:37",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:42",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:43",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:45",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:53",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:54",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:60",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:76",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:79",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:9",
            "tools/webfoot/patchsource/log1-bf-presentation/TEXT_SOURCE.md:97",
            "tools/webfoot/patchsource/log1-bf-presentation/box-sites.toml:12",
            "tools/webfoot/patchsource/log1-bf-presentation/box-sites.toml:18",
            "tools/webfoot/patchsource/log1-bf-presentation/box-sites.toml:24",
            "tools/webfoot/patchsource/log1-bf-presentation/box-sites.toml:29",
            "tools/webfoot/patchsource/log1-bf-presentation/box-sites.toml:6",
            "tools/webfoot/patchsource/log1-bf-presentation/box-sites.toml:60",
            "tools/webfoot/patchsource/log1-bf-presentation/box-sites.toml:66",
            "tools/webfoot/patchsource/log1-bf-presentation/box-sites.toml:72",
            "tools/webfoot/patchsource/log1-bf-presentation/box-sites.toml:78",
            "tools/webfoot/patchsource/log1-bf-presentation/box-sites.toml:80",
            "tools/webfoot/patchsource/log1-bf-presentation/box-sites.toml:85",
            "tools/webfoot/patchsource/log1-bf-presentation/box.s:12",
            "tools/webfoot/patchsource/log1-bf-presentation/box.s:13",
            "tools/webfoot/patchsource/log1-bf-presentation/box.s:14",
            "tools/webfoot/patchsource/log1-bf-presentation/box.s:241",
            "tools/webfoot/patchsource/log1-bf-presentation/box.s:470",
            "tools/webfoot/patchsource/log1-bf-presentation/box.s:7",
            "tools/webfoot/patchsource/log1-bf-presentation/box.s:8",
            "tools/webfoot/patchsource/log1-bf-presentation/portrait.s:212",
            "tools/webfoot/patchsource/log1-bf-presentation/portrait.s:61",
            "tools/webfoot/patchsource/log1-bf-presentation/portrait.s:7",
            "tools/webfoot/patchsource/log1-bf-presentation/portrait.s:73",
            "tools/webfoot/patchsource/log1-bf-presentation/portrait.s:74",
            "tools/webfoot/patchsource/log1-bf-presentation/portrait.s:8",
            "tools/webfoot/patchsource/log1-bf-presentation/portrait.s:9",
            "tools/webfoot/patchsource/log1-bf-presentation/presentation.s:14",
            "tools/webfoot/patchsource/log1-bf-presentation/sites.toml:12",
            "tools/webfoot/patchsource/log1-bf-presentation/sites.toml:14",
            "tools/webfoot/patchsource/log1-bf-presentation/sites.toml:19",
            "tools/webfoot/patchsource/log1-bf-presentation/sites.toml:25",
            "tools/webfoot/patchsource/log1-bf-presentation/sites.toml:49",
            "tools/webfoot/patchsource/log1-bf-presentation/sites.toml:52",
            "tools/webfoot/patchsource/log1-bf-presentation/sites.toml:58",
            "tools/webfoot/patchsource/log1-bf-presentation/text-sites.toml:11",
            "tools/webfoot/patchsource/log1-bf-presentation/text-sites.toml:35",
            "tools/webfoot/patchsource/log1-bf-presentation/text-sites.toml:37",
            "tools/webfoot/patchsource/log1-bf-presentation/text-sites.toml:42",
            "tools/webfoot/patchsource/log1-bf-presentation/text-sites.toml:6",
            "tools/webfoot/patchsource/log1-bf-presentation/text.s:12",
            "tools/webfoot/patchsource/log1-bf-presentation/text.s:15",
            "tools/webfoot/patchsource/log1-bf-presentation/text.s:16",
            "tools/webfoot/patchsource/log1-bf-presentation/text.s:17",
            "tools/webfoot/patchsource/log1-bf-presentation/text.s:18",
            "tools/webfoot/patchsource/log1-bf-presentation/text.s:19",
            "tools/webfoot/patchsource/log1-bf-presentation/text.s:20",
            "tools/webfoot/patchsource/log1-bf-presentation/text.s:21",
            "tools/webfoot/patchsource/log1-bf-presentation/text.s:7",
            "tools/webfoot/project/patchdoc.py:125",
            "tools/webfoot/project/patchdoc.py:126",
            "tools/webfoot/project/patchdoc.py:153",
            "tools/webfoot/project/patchdoc.py:254",
            "tools/webfoot/project/patchdoc.py:255",
            "tools/webfoot/project/patchdoc.py:293",
            "tools/webfoot/project/patchdoc.py:58",
            "tools/webfoot/data/roms.yaml:541",
            "tools/webfoot/data/roms.yaml:552",
            "tools/webfoot/data/roms.yaml:553",
            "tools/webfoot/data/roms.yaml:556",
            "tools/webfoot/data/roms.yaml:558",
            "tools/webfoot/data/roms.yaml:560",
            "tools/webfoot/data/roms.yaml:562",
            "tools/webfoot/data/roms.yaml:563",
            "tools/webfoot/data/roms.yaml:565",
            "tools/webfoot/data/roms.yaml:566",
            "tools/webfoot/data/roms.yaml:567",
            "tools/webfoot/data/roms.yaml:568",
            "tools/webfoot/data/roms.yaml:569",
            "tools/webfoot/data/roms.yaml:570",
            "tools/webfoot/data/roms.yaml:571",
            "tools/webfoot/data/roms.yaml:576",
            "tools/webfoot/data/roms.yaml:578",
            "tools/webfoot/data/roms.yaml:579",
            "tools/webfoot/data/roms.yaml:581",
            "tools/webfoot/data/roms.yaml:584",
            "tools/webfoot/data/roms.yaml:586",
            "tools/webfoot/data/roms.yaml:588",
            "tools/webfoot/data/roms.yaml:591",
            "tools/webfoot/data/roms.yaml:1304",
            "tools/webfoot/data/roms.yaml:1312",
            "tools/webfoot/data/roms.yaml:1315",
            "tools/webfoot/data/roms.yaml:1323",
            "tools/webfoot/data/roms.yaml:1326",
            "tools/webfoot/data/roms.yaml:1334",
            "tools/webfoot/data/roms.yaml:1337",
            "tools/webfoot/data/roms.yaml:1345",
            "tools/webfoot/data/roms.yaml:1348",
            "tools/webfoot/data/roms.yaml:1356",
            "tools/webfoot/data/roms.yaml:1359",
            "tools/webfoot/data/roms.yaml:1367",
            "tools/webfoot/data/roms.yaml:1370",
            "tools/webfoot/data/roms.yaml:1378",
            "tools/webfoot/data/roms.yaml:1381",
            "tools/webfoot/data/roms.yaml:1389",
        ),
        "179 counted hex5 lines arrived across 13 files and none left, so this ticket's declared move is +179 lines / +13 files, of which the arrival-by-text derivation names 38 and the thirty-ninth is the shared output_size text explained at the end of this entry: lane B's portrait and presentation sources plus their declaration, lane A's box and text sources plus their declarations (the page object and its inline cell map, the retail publish and fill sites, the nine-slice tile run, the EWRAM staging cursor, the shadow-OAM base and the ink slot a compiled payload has to name), the shipped SDK's donor extraction including the donor font span's own digest-pinned offset, the patch-document encoder, the lifecycle-table derivation and the authoring command that cites the box layout record. Every pointer was re-derived from the current tree by diffing counted-line text against HEAD, not by shifting an earlier number. The packaged catalogue copy tools/webfoot/data/roms.yaml then received the same declared-scene and patch-site block the development copy carries, because webfoot.capability always reads the packaged copy and the two must stay byte-identical; that brought 39 further counted lines into the census set, 17 of them in ROM space, which is what moved this entry 140 -> 179 lines and the catalogue row 179 -> 218 and its ROM-space count 158 -> 175. config/roms.yaml is outside the tools/ census set, so the development copy's own lines were never counted. The LG2-068 and O2b pointers into the catalogue were re-derived by matching each named line's text in the synchronised file, not by shifting a number. The thirty-ninth counted line is the Legacy of Goku II profile's own generated_expansion output_size at :848: its text already existed at the merge base in the Buu's Fury profile at :223, so the arrival-by-text derivation assigns that one slot to LG2-068 and this entry names the thirty-eight whose text is new, while the tree pair counts all thirty-nine lines.",
    ),
    LedgerEntry(
        "LOG1-BUU-SPRITE-BACKPORT-001", 20, 3,
        (
            "tools/webfoot/patchsource/log1-sprite-limits/bank.s:20",
            "tools/webfoot/patchsource/log1-sprite-limits/bank.s:21",
            "tools/webfoot/patchsource/log1-sprite-limits/bank.s:5",
            "tools/webfoot/patchsource/log1-sprite-limits/bank.s:7",
            "tools/webfoot/patchsource/log1-sprite-limits/budget.s:49",
            "tools/webfoot/patchsource/log1-sprite-limits/budget.s:5",
            "tools/webfoot/patchsource/log1-sprite-limits/budget.s:9",
            "tools/webfoot/sprite_limits.py:169",
            "tools/webfoot/sprite_limits.py:245",
            "tools/webfoot/sprite_limits.py:33",
            "tools/webfoot/sprite_limits.py:34",
            "tools/webfoot/sprite_limits.py:35",
            "tools/webfoot/sprite_limits.py:36",
            "tools/webfoot/sprite_limits.py:39",
            "tools/webfoot/sprite_limits.py:40",
            "tools/webfoot/sprite_limits.py:43",
            "tools/webfoot/sprite_limits.py:48",
            "tools/webfoot/sprite_limits.py:50",
            "tools/webfoot/sprite_limits.py:6",
            "tools/webfoot/sprite_limits.py:9",
        ),
        "phase 3 wave 1 added the LOG1 per-frame actor draw payload: two assembled "
        "assembly sources and the module that composes them. The literals are the "
        "retail draw method 0x0800B01E and its extents, the bank read 0x0800B09A it "
        "displaces, the staging base and object window, the art table and the state "
        "window bound. The assembled payload binaries were never meant to be tracked "
        "and are untracked in this same commit, so only the sources move the census. "
        "HEX5 moves 3231/288 -> 3251/291 and ROM-space 679/66 -> 695/69; nothing was "
        "removed.",
    ),
    LedgerEntry(
        "DBZ-033-RUNTIME", 306, 7,
        (
            'tools/webfoot/data/roms.yaml:597',
            'tools/webfoot/data/roms.yaml:600',
            'tools/webfoot/data/roms.yaml:606',
            'tools/webfoot/data/roms.yaml:608',
            'tools/webfoot/data/roms.yaml:609',
            'tools/webfoot/data/roms.yaml:614',
            'tools/webfoot/data/roms.yaml:617',
            'tools/webfoot/data/roms.yaml:620',
            'tools/webfoot/data/roms.yaml:623',
            'tools/webfoot/data/roms.yaml:629',
            'tools/webfoot/data/roms.yaml:632',
            'tools/webfoot/data/roms.yaml:638',
            'tools/webfoot/data/roms.yaml:641',
            'tools/webfoot/data/roms.yaml:647',
            'tools/webfoot/data/roms.yaml:650',
            'tools/webfoot/data/roms.yaml:656',
            'tools/webfoot/data/roms.yaml:659',
            'tools/webfoot/data/roms.yaml:665',
            'tools/webfoot/data/roms.yaml:668',
            'tools/webfoot/data/roms.yaml:674',
            'tools/webfoot/data/roms.yaml:677',
            'tools/webfoot/data/roms.yaml:683',
            'tools/webfoot/data/roms.yaml:686',
            'tools/webfoot/data/roms.yaml:692',
            'tools/webfoot/data/roms.yaml:695',
            'tools/webfoot/data/roms.yaml:701',
            'tools/webfoot/data/roms.yaml:704',
            'tools/webfoot/data/roms.yaml:710',
            'tools/webfoot/data/roms.yaml:713',
            'tools/webfoot/data/roms.yaml:719',
            'tools/webfoot/data/roms.yaml:722',
            'tools/webfoot/data/roms.yaml:728',
            'tools/webfoot/data/roms.yaml:731',
            'tools/webfoot/data/roms.yaml:737',
            'tools/webfoot/data/roms.yaml:740',
            'tools/webfoot/data/roms.yaml:746',
            'tools/webfoot/data/roms.yaml:749',
            'tools/webfoot/data/roms.yaml:755',
            'tools/webfoot/data/roms.yaml:758',
            'tools/webfoot/data/roms.yaml:764',
            'tools/webfoot/data/roms.yaml:767',
            'tools/webfoot/data/roms.yaml:773',
            'tools/webfoot/data/roms.yaml:776',
            'tools/webfoot/data/roms.yaml:782',
            'tools/webfoot/data/roms.yaml:785',
            'tools/webfoot/data/roms.yaml:791',
            'tools/webfoot/data/roms.yaml:794',
            'tools/webfoot/data/roms.yaml:800',
            'tools/webfoot/data/roms.yaml:803',
            'tools/webfoot/data/roms.yaml:809',
            'tools/webfoot/data/roms.yaml:812',
            'tools/webfoot/data/roms.yaml:818',
            'tools/webfoot/data/roms.yaml:821',
            'tools/webfoot/data/roms.yaml:827',
            'tools/webfoot/data/roms.yaml:830',
            'tools/webfoot/data/roms.yaml:836',
            'tools/webfoot/data/roms.yaml:839',
            'tools/webfoot/data/roms.yaml:845',
            'tools/webfoot/data/roms.yaml:848',
            'tools/webfoot/data/roms.yaml:854',
            'tools/webfoot/data/roms.yaml:857',
            'tools/webfoot/data/roms.yaml:863',
            'tools/webfoot/data/roms.yaml:866',
            'tools/webfoot/data/roms.yaml:872',
            'tools/webfoot/data/roms.yaml:875',
            'tools/webfoot/data/roms.yaml:881',
            'tools/webfoot/data/roms.yaml:884',
            'tools/webfoot/data/roms.yaml:890',
            'tools/webfoot/data/roms.yaml:893',
            'tools/webfoot/data/roms.yaml:899',
            'tools/webfoot/data/roms.yaml:902',
            'tools/webfoot/data/roms.yaml:908',
            'tools/webfoot/data/roms.yaml:911',
            'tools/webfoot/data/roms.yaml:917',
            'tools/webfoot/data/roms.yaml:920',
            'tools/webfoot/data/roms.yaml:926',
            'tools/webfoot/data/roms.yaml:929',
            'tools/webfoot/data/roms.yaml:935',
            'tools/webfoot/data/roms.yaml:938',
            'tools/webfoot/data/roms.yaml:944',
            'tools/webfoot/data/roms.yaml:947',
            'tools/webfoot/data/roms.yaml:953',
            'tools/webfoot/data/roms.yaml:956',
            'tools/webfoot/data/roms.yaml:962',
            'tools/webfoot/data/roms.yaml:965',
            'tools/webfoot/data/roms.yaml:971',
            'tools/webfoot/data/roms.yaml:974',
            'tools/webfoot/data/roms.yaml:980',
            'tools/webfoot/data/roms.yaml:983',
            'tools/webfoot/data/roms.yaml:989',
            'tools/webfoot/data/roms.yaml:992',
            'tools/webfoot/data/roms.yaml:998',
            'tools/webfoot/data/roms.yaml:1001',
            'tools/webfoot/data/roms.yaml:1007',
            'tools/webfoot/data/roms.yaml:1010',
            'tools/webfoot/data/roms.yaml:1016',
            'tools/webfoot/data/roms.yaml:1019',
            'tools/webfoot/data/roms.yaml:1025',
            'tools/webfoot/data/roms.yaml:1028',
            'tools/webfoot/data/roms.yaml:1034',
            'tools/webfoot/data/roms.yaml:1037',
            'tools/webfoot/data/roms.yaml:1043',
            'tools/webfoot/data/roms.yaml:1046',
            'tools/webfoot/data/roms.yaml:1052',
            'tools/webfoot/data/roms.yaml:1055',
            'tools/webfoot/data/roms.yaml:1061',
            'tools/webfoot/data/roms.yaml:1064',
            'tools/webfoot/data/roms.yaml:1070',
            'tools/webfoot/data/roms.yaml:1073',
            'tools/webfoot/data/roms.yaml:1079',
            'tools/webfoot/data/roms.yaml:1082',
            'tools/webfoot/data/roms.yaml:1088',
            'tools/webfoot/data/roms.yaml:1091',
            'tools/webfoot/data/roms.yaml:1097',
            'tools/webfoot/data/roms.yaml:1100',
            'tools/webfoot/data/roms.yaml:1106',
            'tools/webfoot/data/roms.yaml:1109',
            'tools/webfoot/data/roms.yaml:1115',
            'tools/webfoot/data/roms.yaml:1118',
            'tools/webfoot/data/roms.yaml:1124',
            'tools/webfoot/data/roms.yaml:1127',
            'tools/webfoot/data/roms.yaml:1133',
            'tools/webfoot/data/roms.yaml:1136',
            'tools/webfoot/data/roms.yaml:1142',
            'tools/webfoot/data/roms.yaml:1145',
            'tools/webfoot/data/roms.yaml:1151',
            'tools/webfoot/data/roms.yaml:1154',
            'tools/webfoot/data/roms.yaml:1160',
            'tools/webfoot/data/roms.yaml:1163',
            'tools/webfoot/data/roms.yaml:1169',
            'tools/webfoot/data/roms.yaml:1172',
            'tools/webfoot/data/roms.yaml:1178',
            'tools/webfoot/data/roms.yaml:1181',
            'tools/webfoot/data/roms.yaml:1187',
            'tools/webfoot/data/roms.yaml:1190',
            'tools/webfoot/data/roms.yaml:1196',
            'tools/webfoot/data/roms.yaml:1199',
            'tools/webfoot/data/roms.yaml:1205',
            'tools/webfoot/data/roms.yaml:1208',
            'tools/webfoot/data/roms.yaml:1214',
            'tools/webfoot/data/roms.yaml:1217',
            'tools/webfoot/data/roms.yaml:1223',
            'tools/webfoot/data/roms.yaml:1226',
            'tools/webfoot/data/roms.yaml:1232',
            'tools/webfoot/data/roms.yaml:1235',
            'tools/webfoot/data/roms.yaml:1241',
            'tools/webfoot/data/roms.yaml:1244',
            'tools/webfoot/data/roms.yaml:1250',
            'tools/webfoot/data/roms.yaml:1253',
            'tools/webfoot/data/roms.yaml:1259',
            'tools/webfoot/data/roms.yaml:1262',
            'tools/webfoot/data/roms.yaml:1268',
            'tools/webfoot/data/roms.yaml:1271',
            'tools/webfoot/data/roms.yaml:1277',
            'tools/webfoot/data/roms.yaml:1280',
            'tools/webfoot/data/roms.yaml:1286',
            'tools/webfoot/data/roms.yaml:1289',
            'tools/webfoot/data/roms.yaml:1295',
            'tools/webfoot/data/roms.yaml:1298',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:1',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:2',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:9',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:18',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:23',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:26',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:31',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:34',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:38',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:40',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:45',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:47',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:51',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:56',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:60',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:66',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:70',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:71',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:72',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:74',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:78',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:84',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:94',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:109',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:120',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:125',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:131',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:132',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:133',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:137',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:141',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:142',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:146',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:147',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:153',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:190',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:194',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:195',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:200',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:208',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:212',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:217',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:259',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:261',
            'tools/webfoot/patchsource/log1-actor-runtime/combat.c:262',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:16',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:41',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:59',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:67',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:68',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:69',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:87',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:92',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:95',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:99',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:100',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:101',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:119',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:144',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:152',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:179',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:205',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:211',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:212',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:219',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:315',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:318',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:330',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:336',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:350',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:365',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:368',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:384',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:445',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:453',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:457',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:459',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:467',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:468',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:484',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:522',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:524',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:534',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:539',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:593',
            'tools/webfoot/patchsource/log1-actor-runtime/renderer.c:609',
            'tools/webfoot/patchsource/log1-actor-runtime/trampoline.s:19',
            'tools/webfoot/patchsource/log1-actor-runtime/trampoline.s:21',
            'tools/webfoot/patchsource/log1-actor-runtime/trampoline.s:48',
            'tools/webfoot/patchsource/log1-actor-runtime/trampoline.s:50',
            'tools/webfoot/patchsource/log1-actor-runtime/trampoline.s:74',
            'tools/webfoot/patchsource/log1-actor-runtime/trampoline.s:76',
            'tools/webfoot/patchsource/log1-actor-runtime/trampoline.s:88',
            'tools/webfoot/patchsource/log1-actor-runtime/trampoline.s:102',
            'tools/webfoot/patchsource/log1-actor-runtime/trampoline.s:130',
            'tools/webfoot/patchsource/log1-actor-runtime/trampoline.s:132',
            'tools/webfoot/patchsource/log1-actor-runtime/transform.c:11',
            'tools/webfoot/patchsource/log1-actor-runtime/transform.c:12',
            'tools/webfoot/patchsource/log1-actor-runtime/transform.c:16',
            'tools/webfoot/patchsource/log1-actor-runtime/transform.c:17',
            'tools/webfoot/patchsource/log1-actor-runtime/transform.c:18',
            'tools/webfoot/patchsource/log1-actor-runtime/transform.c:19',
            'tools/webfoot/patchsource/log1-actor-runtime/transform.c:30',
            'tools/webfoot/patchsource/log1-actor-runtime/transform.c:45',
            'tools/webfoot/patchsource/log1-actor-runtime/transform.c:51',
            'tools/webfoot/patchsource/log1-actor-runtime/transform.c:57',
            'tools/webfoot/patchsource/log1-actor-runtime/transform.c:61',
            'tools/webfoot/patchsource/log1-actor-runtime/transform.c:64',
            'tools/webfoot/sprite_runtime.py:175',
            'tools/webfoot/sprite_runtime.py:196',
            'tools/webfoot/sprite_runtime.py:198',
            'tools/webfoot/sprite_runtime.py:199',
            'tools/webfoot/sprite_runtime.py:200',
            'tools/webfoot/sprite_runtime.py:263',
            'tools/webfoot/sprite_runtime.py:264',
            'tools/webfoot/sprite_runtime.py:265',
            'tools/webfoot/sprite_runtime.py:266',
            'tools/webfoot/sprite_runtime.py:316',
            'tools/webfoot/sprite_runtime.py:317',
            'tools/webfoot/sprite_runtime.py:318',
            'tools/webfoot/sprite_runtime.py:319',
            'tools/webfoot/sprite_runtime.py:320',
            'tools/webfoot/sprite_runtime.py:321',
            'tools/webfoot/sprite_runtime.py:322',
            'tools/webfoot/sprite_runtime.py:323',
            'tools/webfoot/sprite_runtime.py:324',
            'tools/webfoot/sprite_runtime.py:325',
            'tools/webfoot/sprite_runtime.py:326',
            'tools/webfoot/sprite_runtime.py:339',
            'tools/webfoot/patchsource/log1-actor-runtime/bf_math.c:15',
            'tools/webfoot/patchsource/log1-actor-runtime/bf_math.c:16',
            'tools/webfoot/sprite_runtime_assets.py:25',
            'tools/webfoot/sprite_runtime_assets.py:26',
            'tools/webfoot/sprite_runtime_assets.py:27',
            'tools/webfoot/sprite_runtime_assets.py:28',
            'tools/webfoot/sprite_runtime_assets.py:29',
            'tools/webfoot/sprite_runtime_assets.py:43',
            'tools/webfoot/sprite_runtime_assets.py:45',
            'tools/webfoot/sprite_runtime_assets.py:49',
            'tools/webfoot/sprite_runtime_assets.py:65',
            'tools/webfoot/sprite_runtime_assets.py:114',
            'tools/webfoot/sprite_runtime_assets.py:121',
            'tools/webfoot/sprite_runtime_assets.py:122',
            'tools/webfoot/sprite_runtime_assets.py:132',
            'tools/webfoot/sprite_runtime_assets.py:180',
            'tools/webfoot/sprite_runtime_assets.py:196',
            'tools/webfoot/sprite_runtime_assets.py:338',
        ),
        "Existing catalogue anchor coordinates follow their unchanged text after the inserted seams; historical deltas and reasons are retained. Six new runtime/compiler sources declare the measured target ABI and canonical donor readers. The packaged profile gains the same 77 draw-method and two state-nine method seams already declared by the development profile. The new literals are source identities, target dispatch and resource addresses, donor metadata readers and expansion placement placeholders; none is an extracted asset. HEX5 moves 3251/291 to 3504/297; enforcement moves 967/86 to 1220/92 and ROM-space 695/69 to 843/75. The dialogue palette lifecycle then relocated the pending queue base in renderer.c to 0x02013024 and added the dialogue record table and resume address to trampoline.s, moving HEX5 3539/298 to 3542/298, enforcement 1255/93 to 1258/93 and ROM-space 860/75 to 862/75. The dialogue colour split then added the palette RAM, OBJ VRAM, OAM, OAM shadow and DISPCNT accesses in renderer.c that recolour a piece whose bank has no free target, moving HEX5 3542/298 to 3557/298 and enforcement 1258/93 to 1273/93; ROM-space is unchanged.",
    ),
    LedgerEntry(
        "DBZ-044", 178, 5,
        (
            "tools/runtime/pause001_probe.lua:8",
            "tools/runtime/pause001_probe.lua:9",
            "tools/runtime/pause001_probe.lua:47",
            "tools/runtime/pause001_probe.lua:48",
            "tools/runtime/pause001_probe.lua:84",
            "tools/runtime/pause001_probe.lua:110",
            "tools/runtime/pause001_probe.lua:111",
            "tools/runtime/pause001_probe.lua:112",
            "tools/runtime/pause001_probe.lua:113",
            "tools/runtime/pause001_probe.lua:114",
            "tools/runtime/pause001_probe.lua:134",
            "tools/runtime/pause001_probe.lua:135",
            "tools/runtime/pause001_probe.lua:136",
            "tools/runtime/pause001_probe.lua:137",
            "tools/runtime/pause001_probe.lua:138",
            "tools/runtime/pause001_probe.lua:139",
            "tools/runtime/pause001_probe.lua:140",
            "tools/runtime/pause001_probe.lua:141",
            "tools/runtime/pause001_probe.lua:142",
            "tools/runtime/pause001_probe.lua:144",
            "tools/runtime/pause001_probe.lua:231",
            "tools/runtime/pause001_probe.lua:253",
            "tools/runtime/pause001_probe.lua:260",
            "tools/runtime/pause001_probe.lua:261",
            "tools/runtime/pause001_probe.lua:262",
            "tools/runtime/pause001_probe.lua:263",
            "tools/runtime/pause001_probe.lua:264",
            "tools/runtime/pause001_probe.lua:265",
            "tools/runtime/pause001_probe.lua:266",
            "tools/runtime/pause001_probe.lua:267",
            "tools/runtime/pause001_probe.lua:268",
            "tools/runtime/pause001_probe.lua:269",
            "tools/runtime/pause001_probe.lua:270",
            "tools/runtime/pause001_probe.lua:271",
            "tools/runtime/pause001_probe.lua:272",
            "tools/runtime/pause001_probe.lua:273",
            "tools/runtime/pause001_probe.lua:274",
            "tools/runtime/pause001_probe.lua:291",
            "tools/runtime/pause001_probe.lua:292",
            "tools/runtime/pause001_probe.lua:293",
            "tools/runtime/pause001_probe.lua:294",
            "tools/runtime/pause001_probe.lua:299",
            "tools/runtime/pause001_probe.lua:300",
            "tools/runtime/pause001_probe.lua:301",
            "tools/runtime/pause001_probe.lua:353",
            "tools/runtime/pause001_probe.lua:355",
            "tools/runtime/pause001_probe.lua:356",
            "tools/runtime/pause001_probe.lua:357",
            "tools/runtime/pause001_probe.lua:365",
            "tools/runtime/pause001_probe.lua:366",
            "tools/runtime/pause001_probe.lua:367",
            "tools/runtime/pause001_probe.lua:409",
            "tools/runtime/pause001_probe.lua:415",
            "tools/runtime/pause001_probe.lua:418",
            "tools/runtime/pause001_probe.lua:420",
            "tools/runtime/pause001_probe.lua:421",
            "tools/runtime/pause001_probe.lua:422",
            "tools/runtime/pause001_probe.lua:423",
            "tools/runtime/pause001_probe.lua:424",
            "tools/runtime/pause001_probe.lua:466",
            "tools/webfoot/data/pause_menu_sites.yaml:3",
            "tools/webfoot/data/pause_menu_sites.yaml:4",
            "tools/webfoot/data/pause_menu_sites.yaml:6",
            "tools/webfoot/data/pause_menu_sites.yaml:7",
            "tools/webfoot/data/pause_menu_sites.yaml:13",
            "tools/webfoot/data/pause_menu_sites.yaml:14",
            "tools/webfoot/data/pause_menu_sites.yaml:16",
            "tools/webfoot/data/pause_menu_sites.yaml:17",
            "tools/webfoot/data/pause_menu_sites.yaml:18",
            "tools/webfoot/data/pause_menu_sites.yaml:19",
            "tools/webfoot/data/pause_menu_sites.yaml:22",
            "tools/webfoot/data/pause_menu_sites.yaml:27",
            "tools/webfoot/data/pause_menu_sites.yaml:28",
            "tools/webfoot/data/pause_menu_sites.yaml:30",
            "tools/webfoot/data/pause_menu_sites.yaml:32",
            "tools/webfoot/data/pause_menu_sites.yaml:34",
            "tools/webfoot/data/pause_menu_sites.yaml:38",
            "tools/webfoot/data/pause_menu_sites.yaml:41",
            "tools/webfoot/data/pause_menu_sites.yaml:48",
            "tools/webfoot/data/pause_menu_sites.yaml:49",
            "tools/webfoot/data/pause_menu_sites.yaml:52",
            "tools/webfoot/data/pause_menu_sites.yaml:56",
            "tools/webfoot/data/pause_menu_sites.yaml:57",
            "tools/webfoot/data/pause_menu_sites.yaml:61",
            "tools/webfoot/data/pause_menu_sites.yaml:64",
            "tools/webfoot/data/pause_menu_sites.yaml:67",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:6",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:7",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:8",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:9",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:10",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:11",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:12",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:13",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:14",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:15",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:16",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:17",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:18",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:19",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:21",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:22",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:23",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:24",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:25",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:26",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:27",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:28",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:29",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:30",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:31",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:33",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:35",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:42",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:46",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:47",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:48",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:49",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:50",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:51",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:52",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:109",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:110",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:111",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:112",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:113",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:114",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:115",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:116",
            "tools/webfoot/patchsource/log1-pause-menu/menu.c:117",
            "tools/webfoot/patchsource/log1-pause-menu/seam.s:162",
            "tools/webfoot/patchsource/log1-pause-menu/seam.s:163",
            "tools/webfoot/patchsource/log1-pause-menu/seam.s:164",
            "tools/webfoot/patchsource/log1-pause-menu/seam.s:165",
            "tools/webfoot/patchsource/log1-pause-menu/seam.s:167",
            "tools/webfoot/patchsource/log1-pause-menu/seam.s:168",
            "tools/webfoot/patchsource/log1-pause-menu/seam.s:169",
            "tools/webfoot/patchsource/log1-pause-menu/seam.s:170",
            "tools/webfoot/patchsource/log1-pause-menu/seam.s:171",
            "tools/webfoot/patchsource/log1-pause-menu/seam.s:172",
            "tools/webfoot/patchsource/log1-pause-menu/seam.s:173",
            "tools/webfoot/patchsource/log1-pause-menu/seam.s:174",
            "tools/webfoot/patchsource/log1-pause-menu/seam.s:175",
            "tools/webfoot/patchsource/log1-pause-menu/seam.s:176",
            "tools/webfoot/patchsource/log1-pause-menu/seam.s:177",
            "tools/webfoot/patchsource/log1-pause-menu/seam.s:178",
            "tools/webfoot/patchsource/log1-pause-menu/seam.s:179",
            "tools/webfoot/pause_menu.py:13",
            "tools/webfoot/pause_menu.py:15",
            "tools/webfoot/pause_menu.py:55",
            "tools/webfoot/pause_menu.py:59",
            "tools/webfoot/pause_menu.py:64",
            "tools/webfoot/pause_menu.py:65",
            "tools/webfoot/pause_menu.py:67",
            "tools/webfoot/pause_menu.py:69",
            "tools/webfoot/pause_menu.py:71",
            "tools/webfoot/pause_menu.py:72",
            "tools/webfoot/pause_menu.py:74",
            "tools/webfoot/pause_menu.py:75",
            "tools/webfoot/pause_menu.py:76",
            "tools/webfoot/pause_menu.py:79",
            "tools/webfoot/pause_menu.py:80",
            "tools/webfoot/pause_menu.py:81",
            "tools/webfoot/pause_menu.py:82",
            "tools/webfoot/pause_menu.py:83",
            "tools/webfoot/pause_menu.py:84",
            "tools/webfoot/pause_menu.py:85",
            "tools/webfoot/pause_menu.py:86",
            "tools/webfoot/pause_menu.py:87",
            "tools/webfoot/pause_menu.py:88",
            "tools/webfoot/pause_menu.py:90",
            "tools/webfoot/pause_menu.py:94",
            "tools/webfoot/pause_menu.py:97",
            "tools/webfoot/pause_menu.py:130",
            "tools/webfoot/pause_menu.py:137",
            "tools/webfoot/pause_menu.py:139",
            "tools/webfoot/pause_menu.py:141",
            "tools/webfoot/pause_menu.py:169",
        ),
        "The four-tab pause page adds its payload, its build-time extractor, its seam "
        "declaration and its runtime observer. Every literal named here is in a file the "
        "same commit adds, so no existing line moved: the extractor reads the donor's "
        "starfield, frame, arrow, slider, panel and portrait art, its palette, font and string tables, the payload names the display "
        "and game-state addresses it reads, and the observer samples the registers and "
        "memory a pause frame is proved with.",
    ),
    LedgerEntry(
        "DBZ-044", 7, 1,
        (
            "tools/webfoot/pause_menu.py:170",
            "tools/webfoot/pause_menu.py:171",
            "tools/webfoot/pause_menu.py:601",
            "tools/webfoot/patchsource/log1-pause-menu/fade_guard.s:39",
            "tools/webfoot/patchsource/log1-pause-menu/fade_guard.s:40",
            "tools/webfoot/patchsource/log1-pause-menu/fade_guard.s:41",
            "tools/webfoot/patchsource/log1-pause-menu/fade_guard.s:42",
        ),
        "The second DBZ-044 entry: the close fade's guard chains the dialogue's per-frame "
        "method through a new assembly source, which names the fade word and the three "
        "blend registers, and the build names the entry word, its own relative base and "
        "the generated constant's format. Every line is new: the constants added after "
        "the first entry's last pointer moved nothing it names.",
    ),
    LedgerEntry(
        "DBZ-051", 17, 1,
        (
            "tools/runtime/dbz002b_entry_watch.lua:1",
            "tools/runtime/dbz002b_entry_watch.lua:3",
            "tools/runtime/dbz002b_entry_watch.lua:4",
            "tools/runtime/dbz002b_entry_watch.lua:8",
            "tools/runtime/dbz002b_entry_watch.lua:9",
            "tools/runtime/dbz002b_entry_watch.lua:11",
            "tools/runtime/dbz002b_entry_watch.lua:12",
            "tools/runtime/dbz002b_entry_watch.lua:13",
            "tools/runtime/dbz002b_entry_watch.lua:14",
            "tools/runtime/dbz002b_entry_watch.lua:15",
            "tools/runtime/dbz002b_entry_watch.lua:17",
            "tools/runtime/dbz002b_entry_watch.lua:140",
            "tools/runtime/dbz002b_entry_watch.lua:179",
            "tools/runtime/dbz002b_entry_watch.lua:189",
            "tools/webfoot/data/script_effects.py:35",
            "tools/webfoot/data/script_effects.py:41",
            "tools/webfoot/data/script_effects.py:44",
        ),
        "The scene's entry watcher is a new instrument whose addresses are the map "
        "lookup, dialogue constructor and pool, VM entry and save-flag handler it reads, "
        "and the declared set_save_flag effect adds its handler word 0x080007E6, the "
        "0x08004380 handler it calls and the 0x030010D9 flag-byte derivation. Every "
        "named line is new in this branch, so no existing line moved.",
    ),
    LedgerEntry(
        "DRAGONBYTE-Z-APP-006", 8, 1,
        (
            "tools/webfoot/events.py:63",
            "tools/webfoot/events.py:75",
            "tools/webfoot/events.py:76",
            "tools/webfoot/events.py:77",
            "tools/webfoot/events.py:724",
            "tools/webfoot/events.py:774",
            "tools/webfoot/events.py:775",
            "tools/webfoot/events.py:789",
        ),
        "The event compiler is a new module: it names the two region class words and "
        "the three activation handlers an authored region record carries, the two "
        "interpreter breakpoints of the trace script, the item bound, the appears-rule "
        "condition words and the save flag byte base. Adding the character steps above "
        "them moved every line below the module constants, so each pointer here was "
        "re-measured against the file rather than taken from the earlier entry.",
    ),
    LedgerEntry(
        "DRAGONBYTE-Z-APP-008", 1, 1,
        ("tools/webfoot/data/enemy_families.py:26",),
        "A new data module states the donor family's defeat callback, the third word "
        "of a type record's +0x14 descriptor. The family is computed from the image "
        "rather than typed as a row list, so this is the only address the module "
        "needs.",
    ),
    LedgerEntry(
        "DRAGONBYTE-Z-APP-008 P2", 8, 1,
        (
            "tools/runtime/combat001_trace.lua:30",
            "tools/runtime/combat001_trace.lua:31",
            "tools/runtime/combat001_trace.lua:32",
            "tools/runtime/combat001_trace.lua:33",
            "tools/runtime/combat001_trace.lua:35",
            "tools/runtime/combat001_trace.lua:36",
            "tools/runtime/combat001_trace.lua:66",
            "tools/runtime/combat001_trace.lua:124",
        ),
        "The product combat trace is a new instrument. It names the map loader's "
        "construct call site, the map-load liveness channel, the story-flag handler, "
        "the EWRAM bounds it scans, the save block and its zeni field, the experience "
        "word, and the two constants its signed conversion and record check compare "
        "against. Every named line is new in this branch.",
    ),
    LedgerEntry(
        "DRAGONBYTE-Z-APP-008 P2b", 1, 0,
        ("tools/runtime/combat001_trace.lua:39",),
        "The combat trace derives the tracked type row from the stat record address "
        "it follows, so its construct channel attributes the placement under test "
        "rather than the first record the loader builds. One new table-base "
        "constant; the two pointers above it were re-measured after the shift.",
    ),
)

LEDGER_ARRIVAL_BAR_EXEMPT: dict[str, str] = {
    "PINMAP-07a": "An arriving entry written before the guard required each named line "
    "to carry a counted literal. Nine of its ten pointers at data/roms.yaml:152-188 "
    "drifted under later edits and now land on 'kind: thumb' rows, the tenth at :152 "
    "still carrying one, so the move it records "
    "cannot be re-measured line by line; its totals still reconcile, which is why the "
    "census pairs are unaffected. Repair belongs to the PINMAP track, which owns the "
    "anchors, and the entry leaves this set when that ticket re-derives its pointers "
    "from the current tree. Nothing is added here to make a new entry pass.",
}


def expected_census_hex5() -> tuple[int, int]:
    """Section 4's published pair plus every declared move, as the tree pair to expect.

    The publication is quoted, never restated: a ticket that moves the tree declares
    its move here rather than rewriting what section 4 says.
    """
    lines = CENSUS_INVENTORY_S4[0] + sum(entry.lines for entry in RECONCILIATION_LEDGER)
    files = CENSUS_INVENTORY_S4[1] + sum(entry.files for entry in RECONCILIATION_LEDGER)
    return lines, files
