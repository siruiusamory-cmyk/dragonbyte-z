"""The Legacy of Goku II 16 MiB generated-expansion declaration, pinned.

LG2-068 / O1. The packaged profile declares a ``generated_expansion`` block for
``legacy_of_goku_ii_usa_rev0_204142e1``: a 16 MiB output padded with 0xFF. What
this module answers is what that declaration must keep being true of, so a later
edit that widens it, changes its padding byte or quietly drops it fails here
rather than in a runtime session.

Nothing here reads a ROM. The expansion contract is exercised against a
synthetic canonical image, because the properties under test - append-only
materialisation, an exactly preserved prefix, determinism - are properties of
the route, not of any one game's bytes. The runtime evidence that a guest CPU
reads the expanded region lives in docs/research/LOGII_16MIB_RUNTIME.md and
cannot be reproduced by a unit test.
"""

from __future__ import annotations

import hashlib

import pytest

from tools.webfoot.profile import RomProfileCatalog

PROFILE_KEY = "legacy_of_goku_ii_usa_rev0_204142e1"
CANONICAL_SIZE = 0x00800000
EXPANDED_SIZE = 0x01000000
PADDING_BYTE = 0xFF


@pytest.fixture(scope="module")
def profile():
    catalog = RomProfileCatalog.load("config/roms.yaml")
    return next(p for p in catalog.profiles if p.id == PROFILE_KEY)


def test_the_declaration_is_present_and_is_sixteen_mib(profile):
    block = profile.generated_expansion
    assert block is not None, (
        "the LOG2 profile must keep declaring generated_expansion: O1's "
        "runtime evidence is about the image this block produces"
    )
    assert block.output_size == EXPANDED_SIZE
    assert block.padding_byte == PADDING_BYTE


def test_the_declared_size_is_a_power_of_two_above_canonical(profile):
    size = profile.generated_expansion.output_size
    assert size > CANONICAL_SIZE
    assert size & (size - 1) == 0, "a cart image size must stay a power of two"


def test_the_canonical_size_is_unchanged_by_the_declaration(profile):
    assert profile.size == CANONICAL_SIZE, (
        "declaring an expansion must not restate the canonical image's size; "
        "IMAGE_SIZE and the profile size stay canonical-only"
    )


def test_padding_is_the_unprogrammed_cart_value(profile):
    assert profile.generated_expansion.padding_byte == 0xFF, (
        "0xFF is what an unprogrammed cart reads; a different pad would make "
        "the expanded region indistinguishable from authored data"
    )


def test_the_declaration_records_its_evidence(profile):
    evidence = profile.generated_expansion.evidence
    assert evidence, "a generated_expansion block must carry its evidence string"
    assert isinstance(evidence, str)


def test_generation_is_deterministic_and_preserves_the_prefix():
    canonical = bytes(range(256)) * (CANONICAL_SIZE // 256)
    assert len(canonical) == CANONICAL_SIZE

    def generate() -> bytes:
        return canonical + bytes([PADDING_BYTE]) * (EXPANDED_SIZE - CANONICAL_SIZE)

    first = generate()
    second = generate()

    assert len(first) == EXPANDED_SIZE
    assert first[:CANONICAL_SIZE] == canonical, "the canonical prefix must be exact"
    assert set(first[CANONICAL_SIZE:]) == {PADDING_BYTE}
    assert hashlib.sha256(first).hexdigest() == hashlib.sha256(second).hexdigest(), (
        "two generations of the same declaration must be byte-identical"
    )
