    .syntax unified
    .cpu arm7tdmi
    .thumb
    .text
    .global field_install
    .thumb_func
    .type field_install, %function

field_install:
    push {r3, r4, r5, lr}
    adds r5, r0, #0
    ldr  r3, .Lflag
    ldrh r2, [r3]
    cmp  r2, #1
    beq  .Lclosing
    movs r0, #0x80
    lsls r4, r0, #0x13
    ldr  r3, .Lretail
    bx   r3

.Lclosing:
    movs r2, #0
    strh r2, [r3]
    movs r0, #0x80
    lsls r4, r0, #0x13
    ldr  r3, .Lvram_reset
    bl   .Lveneer
    ldr  r0, .Lpalette_source
    ldr  r3, .Ldecompress
    bl   .Lveneer
    adds r2, r0, #0
    ldr  r3, .Lcopy
    mov  r12, r3
    movs r3, #0x49
    lsls r3, r3, #0x6
    movs r1, #0x3
    lsls r1, r1, #0x19
    ldr  r0, .Ldma3
    bl   .Lcopy_call
    adds r0, r5, #0
    movs r3, #0
    ldr  r3, .Lmap
    bl   .Lveneer
    movs r5, #0
    bl   .Lwait
    ldr  r0, .Lafter_ptr
    mov  lr, r0
    push {r3, r4, r5, lr}
    ldr  r3, .Ltail
    bx   r3

.Lafter:
    movs r0, #0xC0
    adds r0, #0x3F
    ldr  r1, .Lbldcnt
    strh r0, [r1]
    movs r0, #16
    ldr  r1, .Lbldy
.Lfade_in_loop:
    strh r0, [r1]
    bl   .Lwait
    subs r0, r0, #1
    bne  .Lfade_in_loop
    movs r0, #0
    strh r0, [r1]
    ldr  r1, .Lbldcnt
    strh r0, [r1]
    pop  {r3, r4, r5, pc}

.Lwait:
    ldr  r3, .Ldispstat
1:  ldrh r2, [r3]
    lsls r2, r2, #31
    bne  1b
2:  ldrh r2, [r3]
    lsls r2, r2, #31
    beq  2b
    bx   lr

.Lveneer:
    bx   r3

.Lcopy_call:
    bx   r12

    .align 2
.Lflag:           .word 0x02029DA8
.Lretail:         .word 0x0800117D
.Ltail:           .word 0x0800119F
.Lafter_ptr:      .word .Lafter + 1
.Lresume:         .word 0x08008D1D
.Lvram_reset:     .word 0x080098F9
.Ldecompress:     .word 0x080095DD
.Lcopy:           .word 0x080095FF
.Lmap:            .word 0x0800106D
.Lpalette_source: .word 0x085C31EC
.Ldma3:           .word 0x040000D4
.Lmirror:         .word 0x030047E8
.Lbldcnt:         .word 0x04000050
.Lbldy:           .word 0x04000054
.Ldispstat:       .word 0x04000004
