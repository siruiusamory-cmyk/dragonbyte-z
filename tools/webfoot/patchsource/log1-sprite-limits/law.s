    .syntax unified
    .thumb
    .text
    .thumb_func
    .global sprite_frame_law_entry
sprite_frame_law_entry:
    subs    r0, #1                /* the hook follows retail's tick increment */
    movs    r1, #37
    muls    r1, r0, r1
    lsrs    r1, r1, #8
    cmp     r1, #10
    bls     .Lsprite_law_keep
    movs    r1, #10
.Lsprite_law_keep:
    adds    r0, #1
    lsls    r0, r0, #24
    lsrs    r0, r0, #24
    bx      lr
    .align 2
