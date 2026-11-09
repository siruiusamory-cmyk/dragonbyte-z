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

    .thumb_func
    .global ki_request
ki_request:
    movs r0,r4
    bl bf_ki_request
    cmp r0,#0
    bne .Lki_done
    ldrb r0,[r5,#5]
    cmp r0,#2
    bne .Lki_original
    ldr r1,[r6]
    ldr r2,[r5,#56]
    cmp r1,r2
    blt .Lki_done
.Lki_original:
    ldr r3,.Lki_original_address
    bx r3
.Lki_done:
    ldr r3,.Lki_done_address
    bx r3
    .align 2
.Lki_original_address:
    .word 0x08002f2d
.Lki_done_address:
    .word 0x08002f01

    .thumb_func
    .global hit_apply
hit_apply:
    add r3,sp,#20
    adds r1,r4,#0
    adds r0,r7,#0
    ldm r3,{r2,r3}
    bl bf_hit_apply
    ldr r3,.Lhit_resume_address
    bx r3
    .align 2
.Lhit_resume_address:
    .word 0x080074cb
