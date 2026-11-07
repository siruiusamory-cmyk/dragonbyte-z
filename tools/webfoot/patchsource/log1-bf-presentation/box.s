
    .syntax unified
    .thumb
    .text
    .align  2

    .equ    PAGE,          0x02029D94
    .equ    PAGE_MAP,      0x02029DB8
    .equ    PAGE_BOX_TILE, 0x0E
    .equ    P_PTR,         0x14
    .equ    P_DONE,        0x20
    .equ    STAGING_BASE,  0x0200B024
    .equ    OBJ_PALETTE,   0x05000200
    .equ    OAM_STAGING,   0x0202BE24
    .equ    ATTR0_8BPP,    0x2000
    .equ    ATTR0_AFF,     0x0100
    .equ    ATTR0_V,       0x8000
    .equ    SIZE_SQ3,      0xC000
    .equ    SIZE_V3,       0xC000
    .equ    MATRIX_PA,     0x06
    .equ    MATRIX_PD,     0x1E
    .equ    OPEN_SCALE,    0x800
    .equ    REST_SCALE,    0x100
    .equ    RAMP_ROW,      10
    .equ    BOX_X,         72
    .equ    BOX_Y,         88
    .equ    TEXT_X,        80
    .equ    TEXT_Y,        91
    .equ    BOX_BYTES,     10240
    .equ    BOX_UNITS,     320
    .equ    TILE_LIMIT,    704
    .equ    VRAM_LIMIT,    0x8000
    .equ    WINDOW_TILE,   0x64

    .globl  bf_box_geometry
    .thumb_func
    .type   bf_box_geometry, %function
bf_box_geometry:
    movs    r1, #8
    strh    r1, [r0, #0]
    movs    r1, #BOX_Y
    strh    r1, [r0, #2]
    bx      lr
    .size   bf_box_geometry, . - bf_box_geometry

    .balign 4
    .globl  bf_box_strips
    .thumb_func
    .type   bf_box_strips, %function
bf_box_strips:
    push    {r4, r5, r6, r7, lr}
    sub     sp, #28
    str     r0, [sp, #0]
    str     r1, [sp, #4]

    adr     r2, resource_words
    ldr     r3, [r2, #0]
    cmp     r3, #0
    bne     21f
    b       fail
21: ldr     r3, [r2, #4]
    cmp     r3, #0
    bne     22f
    b       fail
22: str     r2, [sp, #8]

    ldrh    r0, [r1, #0]
    cmp     r0, #0x7C
    bls     23f
    b       fail
23:
    ldrh    r1, [r1, #2]
    movs    r3, #1
    ands    r3, r1
    adds    r2, r1, r3
    ldr     r7, =TILE_LIMIT
    cmp     r2, r7
    bls     24f
    b       fail
24: str     r2, [sp, #12]
    lsls    r3, r3, #5
    str     r3, [sp, #16]

    ldr     r5, [sp, #4]
    ldr     r4, [r5, #4]
    ldr     r6, =STAGING_BASE
    subs    r4, r4, r6
    adds    r4, r4, r3
    ldr     r6, =BOX_BYTES
    adds    r4, r4, r6
    ldrh    r6, [r5, #0x0A]
    lsls    r6, r6, #5
    ldr     r7, =VRAM_LIMIT
    subs    r7, r7, r6
    cmp     r4, r7
    bls     25f
    b       fail
25:
    ldr     r2, [sp, #8]
    ldr     r1, [r2, #12]
    cmp     r1, #0
    beq     26f
    ldr     r2, =OBJ_PALETTE
    movs    r3, #19
27: ldmia   r1!, {r4, r5}
    stmia   r2!, {r4, r5}
    subs    r3, #1
    bne     27b
    ldmia   r1!, {r4}
    stmia   r2!, {r4}
26:
    ldr     r5, [sp, #4]
    ldr     r4, [r5, #4]
    ldr     r3, [sp, #16]
    cmp     r3, #0
    beq     3f
    movs    r0, #0
    movs    r2, #4
4:  str     r0, [r4]
    adds    r4, #4
    str     r0, [r4]
    adds    r4, #4
    subs    r2, #1
    bne     4b
3:
    ldr     r0, [sp, #8]
    ldr     r0, [r0, #0]
    str     r0, [sp, #16]
    movs    r3, #0
    str     r3, [sp, #20]
strip:
    ldr     r0, [sp, #16]
    ldr     r3, [sp, #20]
    lsls    r3, r3, #6
    adds    r7, r0, r3
    movs    r6, #8
rowloop:
    movs    r2, r7
    movs    r5, #8
    ldr     r3, [sp, #20]
    cmp     r3, #2
    bne     6f
    movs    r5, #4
6:
tileloop:
    movs    r1, r2
    .rept   8
    ldmia   r1!, {r0, r3}
    adds    r1, #152
    stmia   r4!, {r0, r3}
    .endr
    adds    r2, #8
    subs    r5, #1
    bne     tileloop
    ldr     r3, =1280
    adds    r7, r7, r3
    subs    r6, #1
    bne     rowloop
    ldr     r3, [sp, #20]
    adds    r3, #1
    str     r3, [sp, #20]
    cmp     r3, #3
    bne     strip
    str     r4, [sp, #24]

    ldr     r5, [sp, #4]
    ldrh    r0, [r5, #0]
    lsls    r1, r0, #3
    ldr     r2, =OAM_STAGING
    adds    r1, r2, r1
    adds    r0, #3
    strh    r0, [r5, #0]
    ldr     r6, [sp, #12]
    adr     r5, oam_table
    movs    r4, #3
10: ldrh    r0, [r5, #0]
    ldrh    r2, [r5, #6]
    orrs    r0, r2
    ldrh    r2, [r5, #2]
    ldrh    r3, [r5, #4]
    orrs    r2, r3
    lsls    r2, r2, #16
    orrs    r0, r2
    str     r0, [r1, #0]
    ldrh    r2, [r5, #8]
    adds    r2, r6
    str     r2, [r1, #4]
    adds    r1, #8
    adds    r5, #10
    subs    r4, #1
    bne     10b

    ldr     r5, [sp, #4]
    ldr     r0, [sp, #24]
    str     r0, [r5, #4]
    ldr     r3, [sp, #12]
    ldr     r2, =BOX_UNITS
    adds    r2, r3, r2
    strh    r2, [r5, #2]
    ldr     r1, =PAGE
    strh    r3, [r1, #PAGE_BOX_TILE]

    ldr     r0, =OPEN_SCALE
    ldr     r2, [sp, #8]
    ldr     r3, [r2, #8]
    cmp     r3, #0
    beq     30f
    ldr     r1, =PAGE
    ldr     r1, [r1, #P_PTR]
    movs    r0, r3
    bl      life_lookup
    cmp     r0, #0
    beq     31f
    ldrb    r2, [r0, #8]
    movs    r3, #1
    ands    r2, r3
    beq     31f
    ldr     r0, =OPEN_SCALE
    b       30f
31: ldr     r0, =REST_SCALE
30: ldr     r1, =OAM_STAGING
    strh    r0, [r1, #MATRIX_PA]
    strh    r0, [r1, #MATRIX_PD]

chain:
    ldr     r0, [sp, #0]
    ldr     r1, [sp, #4]
    add     sp, #28
    pop     {r4, r5, r6, r7}
    pop     {r3}
    mov     lr, r3
    adr     r2, resource_words
    ldr     r3, [r2, #4]
    cmp     r3, #0
    beq     retail
    bx      r3
fail:
    b       chain

retail:
    ldr     r3, =0x08005119
    bx      r3

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
oam_table:
    .hword  ATTR0_8BPP | ATTR0_AFF, SIZE_SQ3,              BOX_X,       BOX_Y, 0
    .hword  ATTR0_8BPP | ATTR0_AFF, SIZE_SQ3,              BOX_X + 64,  BOX_Y, 128
    .hword  ATTR0_8BPP | ATTR0_AFF | ATTR0_V, SIZE_V3,     BOX_X + 128, BOX_Y, 256
    .align  2
    .balign 4
resource_words:
    .word   0
    .word   0
    .word   0
    .word   0
    .size   bf_box_strips, . - bf_box_strips

    .balign 4
    .globl  bf_box_window
    .thumb_func
    .type   bf_box_window, %function
bf_box_window:
    push    {r4, r5, r6, r7, lr}
    sub     sp, #28
    adds    r6, r0, #0

    ldr     r2, =PAGE
    ldr     r3, [r2, #P_DONE]
    lsrs    r3, r3, #8
    cmp     r3, #0
    bne     bw_close

    ldr     r4, =OAM_STAGING
    ldrh    r3, [r4, #MATRIX_PA]
    cmp     r3, #0
    beq     bw_end
    adr     r2, affine_ramp
    movs    r1, #8
bw_find:
    ldrh    r0, [r2]
    cmp     r0, r3
    beq     bw_row
    adds    r2, #RAMP_ROW
    subs    r1, #1
    bne     bw_find
    b       bw_end
bw_row:
    cmp     r1, #1
    beq     bw_rest
    adds    r2, #RAMP_ROW
    str     r2, [sp, #16]
    b       bw_own
bw_rest:
    str     r2, [sp, #16]
    b       bw_own

bw_close:
    cmp     r3, #8
    bhs     bw_end
    movs    r1, #7
    subs    r1, r1, r3
    lsls    r2, r1, #3
    lsls    r1, r1, #1
    adds    r2, r2, r1
    adr     r3, affine_ramp
    adds    r3, r3, r2
    str     r3, [sp, #16]
    ldr     r4, =OAM_STAGING

bw_own:
    ldr     r2, =PAGE
    ldrh    r2, [r2, #PAGE_BOX_TILE]
    str     r2, [sp, #20]
    movs    r7, #0
    movs    r1, #0
    movs    r5, #128
    movs    r2, #0
    str     r2, [sp, #0]
    str     r2, [sp, #4]
    str     r2, [sp, #8]
    str     r2, [sp, #12]
bw_scan:
    ldr     r2, [r4, #0]
    lsrs    r3, r2, #16
    lsls    r2, r2, #16
    lsrs    r2, r2, #16
    lsls    r2, r2, #23
    bpl     bw_next
    lsrs    r2, r3, #9
    movs    r0, #0x1F
    ands    r2, r0
    bne     bw_next
    ldr     r2, [r4, #4]
    movs    r0, #0xFF
    lsls    r0, r0, #2
    adds    r0, #3
    ands    r2, r0
    ldr     r0, [sp, #20]
    cmp     r2, r0
    beq     bw_ours
    adds    r0, #128
    cmp     r2, r0
    beq     bw_ours
    adds    r0, #128
    cmp     r2, r0
    beq     bw_ours
    adds    r0, #64
    cmp     r2, r0
    beq     bw_fourth
    adds    r7, #1
    b       bw_next
bw_fourth:
    ldr     r2, [sp, #12]
    cmp     r2, #0
    bne     bw_next
    str     r4, [sp, #12]
    b       bw_next
bw_ours:
    cmp     r1, #3
    bhs     bw_next
    mov     r0, sp
    lsls    r2, r1, #2
    adds    r0, r0, r2
    str     r4, [r0, #0]
    adds    r1, #1
bw_next:
    adds    r4, #8
    subs    r5, #1
    bne     bw_scan
    cmp     r1, #3
    bne     bw_clamp
    cmp     r7, #0
    bne     bw_clamp

    ldr     r4, =OAM_STAGING
    ldr     r2, [sp, #16]
    ldrh    r0, [r2, #0]
    strh    r0, [r4, #MATRIX_PA]
    strh    r0, [r4, #MATRIX_PD]
    movs    r3, #0xC0
    lsls    r3, r3, #8
    ldr     r4, [sp, #0]
    ldrh    r5, [r2, #2]
    orrs    r5, r3
    strh    r5, [r4, #2]
    ldr     r4, [sp, #4]
    ldrh    r5, [r2, #4]
    orrs    r5, r3
    strh    r5, [r4, #2]
    ldr     r4, [sp, #8]
    ldrh    r5, [r2, #6]
    orrs    r5, r3
    strh    r5, [r4, #2]
    ldr     r4, [sp, #12]
    cmp     r4, #0
    beq     bw_end
    ldrh    r5, [r2, #8]
    orrs    r5, r3
    strh    r5, [r4, #2]
    b       bw_end

bw_clamp:
    mov     r0, sp
    movs    r1, #4
bw_cl_loop:
    ldr     r4, [r0, #0]
    cmp     r4, #0
    beq     bw_end
    ldrh    r5, [r4, #0]
    movs    r3, #0x80
    lsls    r3, r3, #1
    bics    r5, r3
    strh    r5, [r4, #0]
    adds    r0, #4
    subs    r1, #1
    bne     bw_cl_loop

bw_end:
    ldr     r4, =PAGE_MAP
    movs    r5, #0x80
    lsls    r5, r5, #2
    movs    r2, #0x64
    movs    r1, #0x3F
    lsls    r1, r1, #4
    adds    r1, #0x0F
7:  ldrh    r3, [r4]
    movs    r0, r3
    ands    r0, r1
    cmp     r0, r2
    blo     8f
    movs    r0, #0
    strh    r0, [r4]
8:  adds    r4, #2
    subs    r5, #1
    bne     7b

    ldr     r3, =0x08005381
    adr     r2, 9f
    adds    r2, #1
    mov     lr, r2
    bx      r3
    .balign 4
9:  adds    r0, r6, #0
    add     sp, #28
    pop     {r4, r5, r6, r7, pc}
    .ltorg

    .align  2
affine_ramp:
    .hword  2048,  86,  94, 116, 78
    .hword  1024,  84, 100, 128, 68
    .hword   682,  82, 106, 140, 58
    .hword   512,  80, 112, 152, 48
    .hword   409,  78, 118, 164, 38
    .hword   341,  76, 124, 176, 28
    .hword   292,  74, 130, 188, 18
    .hword   256,  72, 136, 200,  8
    .size   bf_box_window, . - bf_box_window
