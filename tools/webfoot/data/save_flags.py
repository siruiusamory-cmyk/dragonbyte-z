"""Save flags a project may name, by profile.

DRAGONBYTE-Z-APP-005. A conversation's flag test and flag set take the flag
number as a one-byte push, so 0..255 is everything they can name. The ranges
below are the three longest runs of flags in that span that no decoded
base-game script names. The measurement decoded every script the conversation
table reaches: 1,129 plain script records, the script blocks of the
value-filled speech records and all 410 compressed script records, and added
the map event corpus. It read the flag from the constant pushed before native
slots 27, 28 and 29 (test, inverted test, set) and the base and count pushed
before slots 186 and 187 (range test, range write).

Not covered: two base-game scripts set a flag whose number is read from a
script variable at run time. Their values are not established, so the ranges
are free of every flag the game names by constant, not proven free of those two.
"""

FREE_SAVE_FLAGS = {
    "buus_fury_usa_rev0_01c1707f": ((157, 186), (216, 222), (224, 233)),
}
