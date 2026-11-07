
    .syntax unified
    .thumb
    .text
    .align  2

    .equ    PAGE,        0x02029D94
    .equ    P_TILE,      0x0E
    .equ    P_PTR,       0x14
    .equ    P_COUNT,     0x1C
    .equ    P_DONE,      0x20
    .equ    CTX,         0x03000794
    .equ    CTX_TILE,    0x02
    .equ    CTX_BASE,    0x0A
    .equ    STAGE,       0x0200B024
    .equ    EDGE,        0x03003D14
    .equ    LATCH,       0x03003D10
    .equ    ROM_LO,      0x08000000
    .equ    ROM_HI,      0x08800000
    .equ    NATIVE,      0x08009329
    .equ    NATIVE_CB,   0x080051B5
    .equ    BOX_BYTES,   10240
    .equ    BOX_UNITS,   320
    .equ    LINES,       4
    .equ    LIMIT,       144
    .equ    PITCH,       14
    .equ    TOPY,        3
    .equ    ORIGIN_X,    8
    .equ    INK,         77
    .equ    WIDE_ADV,    12

    .equ    S_BASE,      0
    .equ    S_PTR,       4
    .equ    S_TGT,       8
    .equ    S_IDX,       12
    .equ    S_LINE,      16
    .equ    S_PEN,       20
    .equ    S_INK,       24
    .equ    S_LINK,      28
    .equ    S_LASTSP,    32
    .equ    S_LASTC,     36
    .equ    S_LSTART,    40
    .equ    S_LEND,      44
    .equ    S_NEXT,      48
    .equ    S_ENDED,     52
    .equ    S_TABLE,     56
    .equ    S_COUNT,     60
    .equ    S_RASTER,    64
    .equ    S_FRAME,     76

    .globl  bf_text_update
    .thumb_func
    .type   bf_text_update, %function
bf_text_update:
    push    {r4, r5, r6, r7, lr}
    sub     sp, #S_FRAME
    mov     r6, sp

    bl      xfix
    ldr     r5, [r3, #0]
    cmp     r5, #1
    bhi     40f
    b       Lnative
40:
    str     r5, [r6, #S_RASTER]
    ldr     r5, [r3, #4]
    cmp     r5, #1
    bhi     41f
    b       Lnative
41:
    str     r5, [r6, #S_TABLE]

    ldr     r4, =PAGE
    ldrh    r5, [r4, #P_TILE]
    cmp     r5, #2
    bhs     42f
    b       Lnative
42: ldr     r3, =CTX
    ldrh    r0, [r3, #CTX_BASE]
    cmp     r0, #0
    bne     43f
    b       Lnative
43: cmp     r0, r5
    blo     44f
    b       Lnative
44:
    ldrh    r1, [r3, #CTX_TILE]
    ldr     r2, =BOX_UNITS
    adds    r2, r5, r2
    cmp     r2, r1
    bls     45f
    b       Lnative
45:
    subs    r5, r5, r0
    lsls    r5, r5, #5
    ldr     r2, =STAGE
    adds    r5, r2
    str     r5, [r6, #S_BASE]

    ldr     r5, [r4, #P_PTR]
    cmp     r5, #0
    beq     Lwait
    ldr     r2, =ROM_LO
    cmp     r5, r2
    bhs     46f
    b       Lnative
46: ldr     r2, =ROM_HI
    cmp     r5, r2
    blo     47f
    b       Lnative
47:
    str     r5, [r6, #S_PTR]
    ldr     r2, [r4, #P_DONE]
    cmp     r2, #0
    bne     Lwait

    ldrb    r0, [r4, #P_COUNT]
    cmp     r0, #0
    bne     3f
    bl      reset_surface
    movs    r0, #0
3:  adds    r0, #1
    strb    r0, [r4, #P_COUNT]
    subs    r0, #1
    str     r0, [r6, #S_TGT]
    ldr     r0, [r6, #S_PTR]
    str     r0, [r6, #S_LSTART]
    movs    r0, #0
    str     r0, [r6, #S_IDX]
    str     r0, [r6, #S_LINE]
    movs    r0, #INK
    str     r0, [r6, #S_INK]

Lline:
    ldr     r0, [r6, #S_INK]
    str     r0, [r6, #S_LINK]
    bl      linescan
    ldr     r0, [r6, #S_IDX]
    ldr     r1, [r6, #S_TGT]
    subs    r2, r1, r0
    bcc     Lnextline
    ldr     r3, [r6, #S_COUNT]
    cmp     r2, r3
    bhs     Lnextline
    bl      drawline
    movs    r0, #0
    b       Lout

Lnextline:
    ldr     r0, [r6, #S_IDX]
    ldr     r1, [r6, #S_COUNT]
    adds    r0, r0, r1
    str     r0, [r6, #S_IDX]
    ldr     r0, [r6, #S_NEXT]
    str     r0, [r6, #S_LSTART]
    ldr     r0, [r6, #S_ENDED]
    cmp     r0, #0
    beq     Ladvline
    cmp     r0, #1
    beq     Ladvline
    b       Lpageend
Ladvline:
    ldr     r0, [r6, #S_LINE]
    adds    r0, #1
    str     r0, [r6, #S_LINE]
    cmp     r0, #LINES
    bhs     Lpageend
    b       Lline

Lpageend:
    ldr     r4, =PAGE
    movs    r0, #1
    str     r0, [r4, #P_DONE]
    ldr     r0, [r6, #S_NEXT]
    str     r0, [r4, #P_PTR]
    movs    r0, #0
    b       Lout

Lwait:
    ldr     r4, =PAGE
    ldr     r3, [r4, #P_DONE]
    lsrs    r3, r3, #8
    cmp     r3, #0
    bne     Lclose
    ldr     r3, =EDGE
    ldrh    r3, [r3]
    movs    r0, #3
    ands    r0, r3
    beq     Lzero
    ldr     r5, [r4, #P_PTR]
    cmp     r5, #0
    beq     Lfinish
    ldrb    r0, [r5]
    cmp     r0, #0
    beq     Llast
    movs    r0, #0
    strb    r0, [r4, #P_COUNT]
    str     r0, [r4, #P_DONE]
    b       Lzero

Llast:
    movs    r1, r5
    bl      stage_final
    cmp     r0, #0
    beq     Lfinish
    movs    r0, #1
    movs    r3, #1
    lsls    r3, r3, #8
    orrs    r0, r3
    str     r0, [r4, #P_DONE]
    movs    r0, #0
    b       Lout

Lclose:
    cmp     r3, #8
    bhs     Lfinish
    adds    r3, #1
    lsls    r3, r3, #8
    adds    r3, #1
    str     r3, [r4, #P_DONE]
    movs    r0, #0
    b       Lout
Lfinish:
    movs    r0, #0
    str     r0, [r4, #P_PTR]
    ldr     r3, =EDGE
    strh    r0, [r3]
    ldr     r3, =LATCH
    strb    r0, [r3]
    movs    r0, #1
    b       Lout
Lzero:
    movs    r0, #0
Lout:
    add     sp, #S_FRAME
    pop     {r4, r5, r6, r7, pc}

Lnative:
    ldr     r0, =PAGE
    ldr     r1, =NATIVE_CB
    adr     r2, 4f
    adds    r2, #1
    mov     lr, r2
    ldr     r3, =NATIVE
    bx      r3
    .balign 4
4:  ldr     r4, =PAGE
    ldr     r0, [r4, #P_PTR]
    cmp     r0, #0
    bne     5f
    movs    r0, #1
    b       6f
5:  movs    r0, #0
6:  add     sp, #S_FRAME
    pop     {r4, r5, r6, r7, pc}

reset_surface:
    push    {r4, r5, r7, lr}
    sub     sp, #8
    movs    r2, #0
rs_strip:
    ldr     r1, [r6, #S_BASE]
    ldr     r0, [r6, #S_RASTER]
    lsls    r3, r2, #12
    adds    r1, r1, r3
    lsls    r3, r2, #6
    adds    r0, r0, r3
    movs    r3, #8
    str     r3, [sp, #0]
    str     r0, [sp, #4]
rs_row:
    ldr     r7, [sp, #4]
    movs    r5, #8
    cmp     r2, #2
    bne     rs_tiles
    movs    r5, #4
rs_tiles:
    movs    r3, r7
    .rept   8
    ldmia   r3!, {r0, r4}
    adds    r3, #152
    stmia   r1!, {r0, r4}
    .endr
    adds    r7, #8
    subs    r5, #1
    bne     rs_tiles
    ldr     r3, [sp, #4]
    ldr     r0, =1280
    adds    r3, r3, r0
    str     r3, [sp, #4]
    ldr     r3, [sp, #0]
    subs    r3, #1
    str     r3, [sp, #0]
    bne     rs_row
    adds    r2, #1
    cmp     r2, #3
    bne     rs_strip
    add     sp, #8
    pop     {r4, r5, r7, pc}

linescan:
    push    {r4, r5, r7, lr}
    ldr     r4, [r6, #S_LSTART]
    movs    r0, #0
    str     r0, [r6, #S_PEN]
    str     r0, [r6, #S_COUNT]
    str     r0, [r6, #S_LASTSP]
    str     r0, [r6, #S_LASTC]
    str     r4, [r6, #S_LEND]
    str     r4, [r6, #S_NEXT]
ls1:
    ldrb    r7, [r4]
    cmp     r7, #0
    beq     ls_end0
    cmp     r7, #0x0A
    beq     ls_endA
    cmp     r7, #0x0B
    beq     ls_endB
    cmp     r7, #0x08
    bne     ls2
    ldrh    r0, [r4, #2]
    str     r0, [r6, #S_INK]
    adds    r4, #4
    str     r4, [r6, #S_LEND]
    str     r4, [r6, #S_NEXT]
    b       ls1
ls2:
    movs    r0, r7
    bl      gw_adv
    ldr     r1, [r6, #S_PEN]
    adds    r2, r1, r0
    cmp     r2, #LIMIT
    bhi     ls_wrap
    str     r2, [r6, #S_PEN]
    ldr     r2, [r6, #S_COUNT]
    adds    r2, #1
    str     r2, [r6, #S_COUNT]
    cmp     r7, #0x20
    bne     ls3
    adds    r2, r4, #1
    str     r2, [r6, #S_LASTSP]
    ldr     r2, [r6, #S_COUNT]
    str     r2, [r6, #S_LASTC]
ls3:
    adds    r4, #1
    str     r4, [r6, #S_LEND]
    b       ls1
ls_wrap:
    cmp     r7, #0x20
    beq     ls_wrap_space
    ldr     r2, [r6, #S_LASTSP]
    cmp     r2, #0
    beq     ls_hard
    str     r2, [r6, #S_NEXT]
    subs    r2, #1
    str     r2, [r6, #S_LEND]
    ldr     r2, [r6, #S_LASTC]
    subs    r2, #1
    str     r2, [r6, #S_COUNT]
    movs    r0, #0
    b       ls_set
ls_wrap_space:
    movs    r2, r4
    str     r2, [r6, #S_LEND]
    adds    r2, r4, #1
    str     r2, [r6, #S_NEXT]
    movs    r0, #0
    b       ls_set
ls_hard:
    movs    r2, r4
    str     r2, [r6, #S_LEND]
    str     r2, [r6, #S_NEXT]
    movs    r0, #0
    b       ls_set
ls_end0:
    str     r4, [r6, #S_LEND]
    str     r4, [r6, #S_NEXT]
    movs    r0, #3
    b       ls_set
ls_endA:
    movs    r0, #1
    b       ls_endx
ls_endB:
    movs    r0, #2
ls_endx:
    str     r4, [r6, #S_LEND]
    adds    r2, r4, #1
    str     r2, [r6, #S_NEXT]
ls_set:
    str     r0, [r6, #S_ENDED]
    pop     {r4, r5, r7, pc}

drawline:
    push    {r4, r5, r7, lr}
    ldr     r4, [r6, #S_LSTART]
    movs    r0, #0
    str     r0, [r6, #S_PEN]
    ldr     r0, [r6, #S_LINK]
    str     r0, [r6, #S_INK]
dl1:
    ldr     r2, [r6, #S_LEND]
    cmp     r4, r2
    bhs     dl9
    ldrb    r7, [r4]
    cmp     r7, #0x08
    bne     dl2
    ldrh    r0, [r4, #2]
    str     r0, [r6, #S_INK]
    adds    r4, #4
    b       dl1
dl2:
    movs    r0, r7
    bl      gw_rec
    movs    r5, r1
    ldr     r3, [r6, #S_IDX]
    ldr     r2, [r6, #S_TGT]
    cmp     r3, r2
    beq     dl3
    ldr     r2, [r6, #S_PEN]
    adds    r2, r2, r0
    str     r2, [r6, #S_PEN]
    adds    r3, #1
    str     r3, [r6, #S_IDX]
    adds    r4, #1
    b       dl1
dl3:
    movs    r1, r5
    bl      plot_glyph
dl9:
    pop     {r4, r5, r7, pc}

gw_adv:
    cmp     r0, #0xFF
    bhs     gwa_wide
    ldr     r3, [r6, #S_TABLE]
    lsls    r2, r0, #1
    ldrh    r2, [r3, r2]
    cmp     r2, #0
    beq     gwa_none
    lsls    r2, r2, #1
    adds    r3, r2, r3
    ldrh    r0, [r3, #0]
    adds    r0, #1
    bx      lr
gwa_none:
    movs    r0, #1
    bx      lr
gwa_wide:
    movs    r0, #WIDE_ADV
    bx      lr

gw_rec:
    cmp     r0, #0xFF
    bhs     gwr_wide
    ldr     r3, [r6, #S_TABLE]
    lsls    r2, r0, #1
    ldrh    r2, [r3, r2]
    cmp     r2, #0
    beq     gwr_none
    lsls    r2, r2, #1
    adds    r3, r2, r3
    ldrh    r0, [r3, #0]
    adds    r1, r3, #2
    adds    r0, #1
    bx      lr
gwr_none:
    movs    r0, #1
    movs    r1, #0
    bx      lr
gwr_wide:
    movs    r0, #WIDE_ADV
    movs    r1, #0
    bx      lr

plot_glyph:
    push    {r0, r1, r2, r3, r4, r5, r7, lr}
    subs    r0, #1
    beq     pg9
    movs    r7, r0
    movs    r4, r1
    ldr     r1, [r6, #S_PEN]
    adds    r1, #ORIGIN_X
pg_col:
    ldrh    r3, [r4, #0]
    adds    r4, #2
    ldr     r5, [r6, #S_LINE]
    movs    r2, #PITCH
    muls    r5, r2, r5
    adds    r5, #TOPY
    movs    r2, #16
pg_row:
    lsrs    r3, r3, #1
    bcc     pg_next
    push    {r2, r3}
    bl      pix_addr
    ldr     r3, [r6, #S_INK]
    strb    r3, [r0]
    pop     {r2, r3}
pg_next:
    adds    r5, #1
    subs    r2, #1
    bne     pg_row
    adds    r1, #1
    subs    r7, #1
    bne     pg_col
pg9:
    pop     {r0, r1, r2, r3, r4, r5, r7, pc}

pix_addr:
    ldr     r0, [r6, #S_BASE]
    movs    r3, r1
    cmp     r1, #128
    bhs     pa_hi
    movs    r2, #0x40
    cmp     r1, r2
    blo     pa_lo
    movs    r2, #0x10
    lsls    r2, r2, #8
    adds    r0, r0, r2
pa_lo:
    movs    r2, #63
    ands    r3, r2
    movs    r2, r5
    lsrs    r2, r2, #3
    lsls    r2, r2, #9
    adds    r0, r0, r2
    lsrs    r2, r3, #3
    lsls    r2, r2, #6
    adds    r0, r0, r2
    b       pa_tail
pa_hi:
    movs    r2, #31
    ands    r3, r2
    movs    r2, #0x20
    lsls    r2, r2, #8
    adds    r0, r0, r2
    movs    r2, r5
    lsrs    r2, r2, #3
    lsls    r2, r2, #8
    adds    r0, r0, r2
    lsrs    r2, r3, #3
    lsls    r2, r2, #6
    adds    r0, r0, r2
pa_tail:
    movs    r2, #7
    ands    r2, r5
    lsls    r2, r2, #3
    adds    r0, r0, r2
    movs    r2, #7
    ands    r2, r3
    adds    r0, r0, r2
    bx      lr

stage_final:
    push    {r4, lr}
    movs    r0, #0
    adr     r3, text_fixups
    ldr     r3, [r3, #8]
    cmp     r3, #0
    beq     sf_out
    cmp     r5, #0
    beq     sf_out
    movs    r1, r5
    movs    r0, r3
    bl      life_lookup
    cmp     r0, #0
    beq     sf_out
    ldrb    r1, [r0, #8]
    movs    r0, #2
    ands    r0, r1
    beq     sf_out
    movs    r0, #1
sf_out:
    pop     {r4, pc}

xfix:
    adr     r3, text_fixups
    bx      lr

life_lookup:
    push    {r4, r5, lr}
    ldrh    r4, [r0, #0]
    cmp     r4, #0
    beq     ll_none
    cmp     r4, #64
    bhi     ll_none
    adds    r0, #4
    movs    r5, #0
ll_loop:
    ldr     r2, [r0, #0]
    cmp     r1, r2
    blo     ll_next
    ldr     r3, [r0, #4]
    cmp     r1, r3
    bhi     ll_next
    cmp     r5, #0
    bne     ll_dup
    movs    r5, r0
ll_next:
    adds    r0, #12
    subs    r4, #1
    bne     ll_loop
    movs    r0, r5
    pop     {r4, r5, pc}
ll_dup:
    movs    r0, #0
    pop     {r4, r5, pc}
ll_none:
    movs    r0, #0
    pop     {r4, r5, pc}

    .ltorg
    .align  2
text_fixups:
    .word   0
    .word   0
    .word   0
    .size   bf_text_update, . - bf_text_update
