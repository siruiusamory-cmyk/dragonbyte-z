/* LOG1 actor draw budget: the guard prologue that runs before the retail body.
 *
 * LOG1-BUU-SPRITE-BACKPORT-001 phase 3 (DBZ-033) SC2.
 *
 * The retail append method at 0x0800B01E appends one OAM entry and stages that
 * piece's tiles with no bound test at all (110 straight-line instructions, zero
 * compare, zero conditional branch, re-derived from the bytes). This prologue
 * runs FIRST with the method's own arguments (r0 = object, r1 = render context
 * 0x03000794) and either falls into the body exactly as retail does, or returns
 * having written nothing.
 *
 * A refusal is side-effect free: no OAM cursor change, no tile cursor change, no
 * staging, no OAM entry. Nothing is clamped, so a piece is never laid over
 * another actor's tiles and the tile field is never wrapped onto tile 0.
 *
 * Registers: r0 and r1 reach the body untouched; r4-r7 and lr are saved and
 * restored on both paths; the body saves them again, exactly as retail does.
 *
 * The final instruction is a 16-bit branch into the copied retail body; the
 * generator fills its offset because the body is not an assembler symbol.
 */
    .syntax unified
    .thumb
    .text
    .thumb_func
    .global sprite_append_entry
sprite_append_entry:
    push    {r4, r5, r6, r7}
    ldrb    r3, [r0, #0x13]        /* facing index */
    ldr     r2, [r0, #8]           /* state row: four facing cell pointers */
    lsls    r4, r3, #2
    ldr     r4, [r2, r4]           /* this piece's cell record */
    ldrb    r5, [r4, #8]           /* tiles this piece stages */
    ldrh    r2, [r1]               /* OAM entry cursor */
    cmp     r2, #128
    bhs     .Lsprite_skip
    ldrh    r6, [r1, #2]           /* tile cursor */
    adds    r6, r6, r5
    movs    r4, #0x80
    lsls    r4, r4, #3             /* r4 = 1024, the 10-bit OBJ tile field */
    cmp     r6, r4
    bhi     .Lsprite_skip
    ldr     r2, [r1, #4]           /* EWRAM staging cursor */
    movs    r4, #0x02
    lsls    r4, r4, #0x18
    movs    r6, #0xB0
    lsls    r6, r6, #8
    adds    r4, r4, r6
    adds    r4, #0x24              /* r4 = 0x0200B024, the staging base */
    subs    r2, r2, r4
    lsls    r6, r5, #5             /* bytes this piece stages */
    adds    r2, r2, r6
    ldrh    r4, [r1, #0x0A]        /* VRAM base tile of the flush block */
    lsls    r4, r4, #5
    movs    r6, #0x80
    lsls    r6, r6, #8             /* r6 = 0x8000, the OBJ window in bytes */
    subs    r6, r6, r4
    cmp     r2, r6
    bls     .Lsprite_fits
.Lsprite_skip:
    pop     {r4, r5, r6, r7, pc}
.Lsprite_fits:
    pop     {r4, r5, r6, r7}
    b       .

