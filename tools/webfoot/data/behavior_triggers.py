"""Narrow, profile-bound authored behavior-trigger evidence contracts.

These declarations are validation data, not a scheduler implementation. The
engine relationship remains the ordinary placement-record descriptor pointer;
the contract states the one template family for which runtime evidence has
established when that relationship is consumed.

`on_defeat` is per placement: the binding is the descriptor field of one
placement record, so two placements of one type are linked or not each on its
own, and the type's own record is never written. It is established only for the
89 enemy types `enemy_types.donor_family` names, the one family seen to remove
the body on the kill frame. `placement_type` is the one template the scene
trigger is offered for, a member of that family, not the scope of the binding.
"""


BEHAVIOR_TRIGGER_CONTRACTS = {
    "buus_fury_usa_rev0_01c1707f": {
        "sha256": "940ad5f01db4465b8877dfe739510cbf34f4ea3d390f3df13519808bc36f059e",
        "on_defeat": {
            "placement_type": (
                "buus_fury_usa_rev0_01c1707f/placement_type:0086"
            ),
            "required_classification": "CONFIRMED_ENEMY_STAT_LINK",
            "binding": "placement_record_descriptor_pointer",
            "scope": "placement",
            "verified_family": (
                "the 89 enemy types enemy_types.donor_family names; the 55-type "
                "family sets the flag late and leaves the body, and the six types "
                "on the other callbacks were never run"
            ),
            "evidence": (
                "TOOLKIT-034 canonical Buu runtime evidence: defeating the "
                "type-0086 enemy runs the authored script bound through the "
                "record +0x14 descriptor pointer. Measured in the replacement "
                "trial tk034-trial-d-20260910-D2, a single capture holding "
                "both halves of the comparison. Negative half: across frames "
                "1440 to 8820 the authored actor was positively sampled as "
                "resident and alive 124 times, HP above zero and its +0x228 "
                "attachment re-validated on every sample, and started no "
                "authored behavior; one HP sample at frame 8820 showed the "
                "authored actor damaged but still alive. "
                "Positive half: at frame 8879 an HP-zero death callback for "
                "that same actor is followed within eight frames by the "
                "descriptor, the authored script cursor, native slot 0xB2 and "
                "its handler at args 1525/120/105. The descriptor is "
                "therefore not dispatched by ordinary actor ticking. The "
                "defeat chain reproduces from a separate load in "
                "tk034-trial-d-20260910-D1, which also carries the canonical "
                "death-channel control. WHAT IS MEASURED, in order: the "
                "actor reaches its defeat condition at HP zero; teardown "
                "traversal of the +0x14 binding occurs; the authored "
                "descriptor and script execute through that path. Defeat and "
                "teardown are CONFOUNDED in the captures, since the script is "
                "reached only through the destructor dispatch in both runs. "
                "Reading defeat as the author-facing gate on script execution "
                "is therefore an INFERENCE supported by that chain, not a "
                "measurement isolating defeat from teardown. This contract "
                "records an existing engine relationship; the trigger "
                "declaration emits no ROM bytes of its own."
            ),
        },
    },
}
