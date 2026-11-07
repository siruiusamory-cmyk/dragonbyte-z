
    .syntax unified
    .thumb
    .text
    .align  2

    .globl  bf_presentation
    .thumb_func
    .type   bf_presentation, %function
bf_presentation:
    push    {r4, lr}
    adds    r4, r0, #0

    ldr     r3, =0x08005381
    adr     r2, 2f
    adds    r2, #1
    mov     lr, r2
    bx      r3

    .balign 4
2:
    adds    r0, r4, #0
    pop     {r4, pc}

    .ltorg
    .size   bf_presentation, . - bf_presentation
