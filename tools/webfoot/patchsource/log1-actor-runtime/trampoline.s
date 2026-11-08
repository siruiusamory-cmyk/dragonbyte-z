    .syntax unified
    .thumb
    .text
    .thumb_func
    .global original_render
original_render:
    push {r4,r5,r6,r7,lr}
    movs r4,r0
    movs r5,r1
    sub sp,#404
    ldr r3, .Lbegin
    bl .Lcall
    ldr r3, .Lresume
    bx r3
.Lcall:
    bx r3
    .align 2
.Lbegin:
    .word 0x080098df
.Lresume:
    .word 0x08002563

    .thumb_func
    .global melee_probe
melee_probe:
    movs r0,r4
    mov r1,sp
    bl melee_contact
    cmp r0,#0
    beq .Lmelee_miss
    ldr r3,.Lmelee_hit_address
    bx r3
.Lmelee_miss:
    ldr r3,.Lmelee_miss_address
    bx r3
    .align 2
.Lmelee_hit_address:
    .word 0x0800565f
.Lmelee_miss_address:
    .word 0x08005711
