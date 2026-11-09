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
    .global ki_passive
ki_passive:
    push {r0}
    bl bf_ki_passive
    pop {r0}
    ldr r3,.Lki_passive_resume
    bx r3
    .align 2
.Lki_passive_resume:
    .word 0x08008049

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

    .thumb_func
    .global dialogue_open
dialogue_open:
    push {r0,r1,r4,r5,r6,lr}
    bl dialogue_yield
    ldr r0,[sp]
    ldr r1,[sp,#4]
    bl .Ldialogue_body
    movs r4,r0
    movs r5,r1
    bl dialogue_close
    movs r0,r4
    movs r1,r5
    add sp,#8
    pop {r4,r5,r6}
    pop {r3}
    bx r3
.Ldialogue_body:
    push {r0,r1,r4,r5,r6,r7,lr}
    ldr r2,.Ldialogue_records
    lsls r1,r0,#2
    ldr r1,[r2,r1]
    ldr r3,.Ldialogue_resume
    bx r3
    .align 2
.Ldialogue_records:
    .word 0x0815bf28
.Ldialogue_resume:
    .word 0x080051d9
