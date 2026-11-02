"""Build the O1 relocation derivative.

The object at 0x081D4EE0 is 12 bytes of read-only data that the boot path
dereferences at +0x0, +0x4 and +0x8 through a pointer held in exactly one
literal word, at 0x08000204. This copies those 12 bytes verbatim into the
expanded region and rewrites that single literal to the new address.

Changed bytes: the 12 copied into previously-0xFF padding, plus the 4-byte
literal. The canonical 8 MiB prefix is otherwise byte-identical, so the object's
original bytes remain in place and unreferenced.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
import sys
from pathlib import Path

ROM_BASE = 0x08000000
CANONICAL_SIZE = 0x00800000
OBJECT_ADDRESS = 0x081D4EE0
OBJECT_SIZE = 12
LITERAL_ADDRESS = 0x08000204
RELOCATED_ADDRESS = 0x08800000


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    data = bytearray(args.source.read_bytes())
    if len(data) != 0x01000000:
        print(f"REFUSED: source is {len(data)} bytes, expected 16777216")
        return 2

    src_off = OBJECT_ADDRESS - ROM_BASE
    lit_off = LITERAL_ADDRESS - ROM_BASE
    dst_off = RELOCATED_ADDRESS - ROM_BASE

    obj = bytes(data[src_off:src_off + OBJECT_SIZE])
    held = struct.unpack_from("<I", data, lit_off)[0]
    if held != OBJECT_ADDRESS:
        print(f"REFUSED: literal holds 0x{held:08X}, expected 0x{OBJECT_ADDRESS:08X}")
        return 2

    target = data[dst_off:dst_off + OBJECT_SIZE]
    if any(b != 0xFF for b in target):
        print(f"REFUSED: destination is not 0xFF padding: {target.hex()}")
        return 2

    original = bytes(data)
    before_prefix = sha256(original[:CANONICAL_SIZE])

    data[dst_off:dst_off + OBJECT_SIZE] = obj
    struct.pack_into("<I", data, lit_off, RELOCATED_ADDRESS)

    prefix_changes = sum(
        1 for i in range(CANONICAL_SIZE) if data[i] != original[i]
    )
    tail_changes = sum(
        1 for i in range(CANONICAL_SIZE, len(data)) if data[i] != original[i]
    )

    changed_offsets = [i for i in range(CANONICAL_SIZE) if data[i] != original[i]]
    if not all(lit_off <= i < lit_off + 4 for i in changed_offsets):
        print(f"REFUSED: prefix changes outside the literal word: {changed_offsets[:8]}")
        return 2
    if tail_changes != OBJECT_SIZE:
        print(f"REFUSED: changed {tail_changes} tail bytes, expected {OBJECT_SIZE}")
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(bytes(data))

    print(f"source              : {args.source}")
    print(f"output              : {args.output}")
    print(f"object address      : 0x{OBJECT_ADDRESS:08X}")
    print(f"object size         : {OBJECT_SIZE} bytes")
    print(f"object bytes        : {obj.hex().upper()}")
    print(f"literal address     : 0x{LITERAL_ADDRESS:08X}")
    print(f"literal was         : 0x{held:08X}")
    print(f"literal now         : 0x{RELOCATED_ADDRESS:08X}")
    print(f"relocated to        : 0x{RELOCATED_ADDRESS:08X} (file 0x{dst_off:08X})")
    print(f"canonical prefix sha: {before_prefix}")
    print(f"output size         : {len(data)}")
    print(f"output sha256       : {sha256(bytes(data))}")
    print(f"bytes changed in prefix : {prefix_changes}")
    print(f"bytes changed in tail   : {tail_changes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
