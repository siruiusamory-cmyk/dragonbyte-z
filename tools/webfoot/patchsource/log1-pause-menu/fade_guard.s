    .syntax unified
    .cpu arm7tdmi
    .thumb
    .text
    .include "generated_fade_target.inc"

    .global fade_guard
    .thumb_func
    .type fade_guard, %function
fade_guard:
    push {r3, r4, r5, lr}
    adds r4, r0, #0
    adds r5, r1, #0
    ldr  r3, .Ltag
    ldrh r2, [r3]
    subs r2, #0xA1
    cmp  r2, #0x0F
    bhi  .Ldone
    movs r0, #0
    ldr  r1, .Lbldcnt
    strh r0, [r1]
    ldr  r1, .Lbldalpha
    ldr  r0, .Lrestalpha
    strh r0, [r1]
    ldr  r1, .Lbldy
    ldr  r0, .Lrestbldy
    strh r0, [r1]
    movs r0, #0
    strh r0, [r3]
.Ldone:
    adds r0, r4, #0
    adds r1, r5, #0
    pop  {r3, r4, r5}
    add  sp, #4
    ldr  r3, .Lretail
    bx   r3

    .align 2
.Ltag:        .word 0x03006000
.Lbldcnt:     .word 0x04000050
.Lbldalpha:   .word 0x04000052
.Lbldy:       .word 0x04000054
.Lrestalpha:  .word 0x0C10
.Lrestbldy:   .word 1
.Lretail:     .word FADE_TARGET
    .size fade_guard, . - fade_guard
