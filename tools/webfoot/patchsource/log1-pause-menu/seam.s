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
    strh r0, [r1]
    movs r0, #0xB0
    ldr  r1, .Lfade_left
    strh r0, [r1]
    pop  {r3, r4, r5, pc}

    .global fade_in
    .thumb_func
    .type fade_in, %function
fade_in:
    ldr  r3, .Lfade_left
    ldrh r2, [r3]
    cmp  r2, #0
    beq  .Lreplay
    cmp  r2, #0xA0
    bls  .Lclear
    cmp  r2, #0xB1
    bcs  .Lclear
    ldr  r1, .Lbldcnt
    subs r1, #0x50
    ldrh r1, [r1]
    movs r2, #0x7D
    lsls r2, r2, #6
    cmp  r1, r2
    bne  .Lclear
    ldrh r2, [r3]
    cmp  r2, #0xA1
    beq  .Lclear
    ldr  r1, .Lbldy
    subs r2, r2, #0xA0
    strh r2, [r1]
    ldr  r1, .Lbldcnt
    movs r3, #0xC0
    adds r3, #0x3F
    strh r3, [r1]
    ldr  r3, .Lfade_left
    adds r2, #0x9F
    strh r2, [r3]
    b    .Lreplay
.Lclear:
    movs r2, #0
    strh r2, [r3]
    ldr  r1, .Lbldcnt
    ldrh r2, [r1]
    cmp  r2, #0xFF
    bne  .Lreplay
    movs r2, #0
    strh r2, [r1]
    ldr  r1, .Lbldy
    strh r2, [r1]
    b    .Lreplay
.Lreplay:
    ldr  r3, .Lresume
    mov  r12, r3
    ldrb r1, [r0, #0]
    adds r2, r0, #0
    adds r2, #0x24
    ldr  r3, .Lmirror
    bx   r12

    .global page_push
    .thumb_func
    .type page_push, %function
page_push:
    push {r3, r4, r5, lr}
    ldr  r5, .Lpush_state
    adds r4, r0, #0
    ldr  r1, .Lfade_left
    ldrh r2, [r1]
    cmp  r2, #0
    beq  .Lpush_replay
    movs r2, #0
    strh r2, [r1]
    ldr  r1, .Lbldcnt
    ldrh r2, [r1]
    cmp  r2, #0xFF
    bne  .Lpush_replay
    movs r2, #0
    strh r2, [r1]
    ldr  r1, .Lbldy
    strh r2, [r1]
.Lpush_replay:
    ldrb r1, [r5, #0]
    ldr  r3, .Lpush_resume
    bx   r3

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
.Lflag:           .word 0x03006000
.Lfade_left:      .word 0x03006000
.Lretail:         .word 0x0800117D
.Ltail:           .word 0x0800119F
.Lafter_ptr:      .word .Lafter + 1
.Lresume:         .word 0x08008D1D
.Lpush_state:     .word 0x03003B60
.Lpush_resume:    .word 0x080097D1
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
