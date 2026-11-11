"""One evidence-backed authored Buu script effect; not a native-handler census.

The text-table bound this effect's `text` argument is checked against is the
profile's own declared `text_strings.count`, read by the consumers that hold a
loaded text domain (`scene.visible_text_options`, the specialized placement
editor). It is deliberately NOT restated here: a second copy of a per-game count
inside a contract is exactly the duplicate-authority defect CQA-15 closed.

`set_save_flag` carries its own two bounds for the same reason. `flag_range` is
the width the encoder can express, not a guess at the save block: `push_byte`
takes one unsigned byte, so 0..255 is the whole range of flags a straight-line
body can name. `stack` is what the native handler does to the VM stack, measured
from the handler and not inferred from the operand position.
"""


SCRIPT_EFFECTS = {
    'buus_fury_usa_rev0_01c1707f': {
        'show_centered_sprite_text': {
            'native_opcode': 'native_stack',
            'native_slot': 178,
            'native_handler_raw': 0x08003031,
            'arguments': ('text', 'x', 'y'),
            'coordinate_ranges': {'x': (0, 239), 'y': (0, 159)},
            'evidence': (
                'docs/research/BUU_DIALOG_RUNTIME.md:115-230; handler 0x08003030 '
                'pops three values, passes the deepest as an index into text table '
                '0x0806BCE8, passes the other two as coordinates, and builds centred '
                'OAM sprite text'
            ),
        },
        'set_save_flag': {
            'native_opcode': 'native_stack',
            'native_slot': 29,
            'native_handler_raw': 0x080007E6,
            'arguments': ('flag',),
            'flag_range': (0, 255),
            'stack': {'pops': 1, 'pushes': 0},
            'evidence': (
                'docs/research/BUU_MAP_EVENT_REFERENCES.md; slot 29 handler '
                '0x080007E6 pops one value and calls 0x08004380 (orrs) on the save '
                'bitfield. The handler forms the byte as save object + 0x55 + '
                '(flag >> 3) with bit (flag & 7), not from the pool base at object + '
                '0x50: flag 228 is 0x03001068 + 0x55 + 28 = 0x030010D9, five bytes '
                'above the pool base word. docs/research/BUU_SCRIPT_VM.md fixes the '
                "opcode set, and `push_byte` is the set's one-byte push, so the "
                'expressible flags are 0..255'
            ),
        },
    },
}
