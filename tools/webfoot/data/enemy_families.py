"""Enemy type table facts a project type is built against, by profile.

The spare rows are the ones no map placement, loader or constructor in the base
game names: the census walked every map's object array, every table loader and
every constructor call, and the union of what they select leaves these rows out.
"Not named" is a measured negative, not proof of disuse, which is why the list
is short and fixed rather than computed at build time.

The donor callback is the third word of the type record's +0x14 descriptor. A
type on this callback is one whose defeat was observed to remove the body on the
kill frame; the other callbacks in the table are not offered as donors yet.

The unlinked placement selectors are the ones the census that proved a placement
selector indexes the stat table did not cover: it read rows 0..140, and the enemy
randomizer states its eligibility in terms of that link. Linking a further row is
a separate measurement, not a consequence of the table's extent.
"""

SPARE_ROWS = {
    "buus_fury_usa_rev0_01c1707f": (
        30, 31, 34, 42, 73, 81, 83, 87, 92, 95, 114, 126, 134, 135, 139, 144,
    ),
}

DONOR_CALLBACK_WORDS = {
    "buus_fury_usa_rev0_01c1707f": (0x08018951,),
}

UNLINKED_PLACEMENT_SELECTORS = {
    "buus_fury_usa_rev0_01c1707f": (141, 142, 145, 146, 147, 148, 149),
}
