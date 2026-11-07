
    .syntax unified
    .thumb
    .text
    .align  2

    .equ    STAGING_BASE, 0x0200B024
    .equ    OAM_STAGING,  0x0202BE24
    .equ    OBJ_PALETTE,  0x05000200
    .equ    ATTR0_8BPP,   0x2000
    .equ    ATTR1_64PX,   0xC000
    .equ    ATTR0_AFF,   0x0100
    .equ    TILE_LIMIT,   896
    .equ    VRAM_LIMIT,   0x8000
    .equ    IMAGE_BYTES,  4096

    .macro  CMP15 rom, hit
    adds    r0, r5, #2
    ldr     r1, =\rom
    adds    r1, #2
    movs    r2, #15
91: ldrh    r3, [r0]
    ldrh    r4, [r1]
    ands    r3, r6
    ands    r4, r6
    cmp     r3, r4
    bne     92f
    adds    r0, #2
    adds    r1, #2
    subs    r2, #1
    bne     91b
    b       \hit
92:
    .endm

    .globl  bf_portrait
    .thumb_func
    .type   bf_portrait, %function
bf_portrait:
    push    {r4, r5, r6, r7, lr}
    sub     sp, #32
    str     r0, [sp, #0]
    str     r1, [sp, #4]

    adr     r2, resource_words
    ldr     r3, [r2, #0]
    cmp     r3, #0
    bne     11f
    b       retail
11: ldr     r3, [r2, #4]
    cmp     r3, #0
    bne     12f
    b       retail
12: ldr     r3, [r2, #8]
    cmp     r3, #0
    bne     13f
    b       retail
13: str     r2, [sp, #16]

    ldr     r5, [r0, #0x34]
    ldr     r3, =0x08011480
    cmp     r5, r3
    beq     14f
    b       retail
14:
    ldrb    r5, [r0, #0x0D]
    movs    r3, #0x0F
    ands    r5, r3
    lsls    r5, r5, #5
    ldr     r3, =OBJ_PALETTE
    adds    r5, r3
    ldr     r6, =0x7FFF
    CMP15   0x08541748, match_roshi
    CMP15   0x0853E4E8, match_goku
    b       retail

match_roshi:
    movs    r7, #0
    str     r7, [sp, #8]
    movs    r7, #8
    str     r7, [sp, #20]
    b       guards
match_goku:
    movs    r7, #1
    str     r7, [sp, #8]
    movs    r7, #8
    str     r7, [sp, #20]

guards:
    ldr     r5, [sp, #4]
    ldrh    r0, [r5, #0]
    cmp     r0, #0x80
    blo     31f
    b       retail
31: ldrh    r1, [r5, #2]
    movs    r3, #1
    ands    r3, r1
    adds    r2, r1, r3
    ldr     r7, =TILE_LIMIT
    cmp     r2, r7
    bls     32f
    b       retail
32: str     r2, [sp, #24]
    lsls    r7, r3, #5
    str     r7, [sp, #28]
    ldr     r4, [r5, #4]
    ldr     r6, =STAGING_BASE
    subs    r4, r4, r6
    adds    r4, r4, r7
    ldr     r6, =IMAGE_BYTES
    adds    r4, r4, r6
    ldrh    r6, [r5, #0x0A]
    lsls    r6, r6, #5
    ldr     r7, =VRAM_LIMIT
    subs    r7, r7, r6
    cmp     r4, r7
    bls     33f
    b       retail
33:
    ldr     r2, [sp, #16]
    ldr     r1, [r2, #8]
    ldr     r2, =OBJ_PALETTE
    movs    r3, #19
41: ldmia   r1!, {r4, r5}
    stmia   r2!, {r4, r5}
    subs    r3, #1
    bne     41b
    ldmia   r1!, {r4}
    stmia   r2!, {r4}

    ldr     r2, [sp, #16]
    ldr     r3, [sp, #8]
    lsls    r3, r3, #2
    adds    r2, r2, r3
    ldr     r0, [r2, #0]
    str     r0, [sp, #12]

    ldr     r5, [sp, #4]
    ldr     r6, [r5, #4]
    ldr     r3, [sp, #28]
    cmp     r3, #0
    beq     51f
    movs    r0, #0
    movs    r2, #4
52: str     r0, [r6]
    adds    r6, #4
    str     r0, [r6]
    adds    r6, #4
    subs    r2, #1
    bne     52b
51:
    ldr     r0, [sp, #12]
    movs    r7, #56
    movs    r4, #0
61: lsrs    r2, r4, #3
    lsls    r2, r2, #9
    movs    r3, #7
    ands    r3, r4
    lsls    r3, r3, #3
    adds    r2, r3
    adds    r2, r0
    .rept   8
    ldmia   r2!, {r1, r3}
    stmia   r6!, {r1, r3}
    adds    r2, r7
    .endr
    adds    r4, #1
    cmp     r4, #64
    bne     61b

    ldr     r5, [sp, #4]
    ldrh    r0, [r5, #0]
    lsls    r1, r0, #3
    ldr     r2, =OAM_STAGING
    adds    r1, r2, r1
    adds    r0, #1
    strh    r0, [r5, #0]

    ldr     r0, [sp, #0]
    ldrh    r2, [r0, #2]
    lsls    r2, r2, #0x18
    lsrs    r2, r2, #0x18
    ldr     r0, =ATTR0_8BPP
    orrs    r2, r0
    movs    r0, #0x80
    lsls    r0, r0, #1
    orrs    r2, r0
    ldr     r0, [sp, #20]
    ldr     r3, =ATTR1_64PX
    orrs    r0, r3
    lsls    r0, r0, #16
    orrs    r2, r0
    str     r2, [r1, #0]
    ldr     r3, [sp, #24]
    str     r3, [r1, #4]

    str     r6, [r5, #4]
    ldr     r3, [sp, #24]
    adds    r3, #128
    strh    r3, [r5, #2]

    add     sp, #32
    pop     {r4, r5, r6, r7, pc}

retail:
    ldr     r0, [sp, #0]
    ldr     r1, [sp, #4]
    add     sp, #32
    pop     {r4, r5, r6, r7}
    pop     {r3}
    mov     lr, r3
    ldr     r3, =0x08005119
    bx      r3

    .ltorg
    .align  2
resource_words:
    .word   0
    .word   0
    .word   0

    .size   bf_portrait, . - bf_portrait
