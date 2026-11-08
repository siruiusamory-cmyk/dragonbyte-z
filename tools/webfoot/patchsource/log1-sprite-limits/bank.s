/* LOG1 per-piece palette bank: the bank selector reached from the retail body.
 *
 * LOG1-BUU-SPRITE-BACKPORT-001 phase 3 (DBZ-033) SC3.
 *
 * Retail reads one bank per actor: 0x0800B09A `ldrb r6,[r0,#0xD]`, then shifts
 * the low nibble into OAM attribute 2 bits 12..15. Verified from the bytes at
 * 0x0800B09A..0x0800B0A6: `ldrb r6,[r0,#0xd] / lsls r7,r7,#0xc / bics r5,r7 /
 * lsls r6,r6,#0x1c / lsrs r6,r6,#0x10 / orrs r5,r6 / str r5,[r2,#4]`.
 *
 * The cell record is sixteen bytes and every byte is used, so the per-piece bank
 * lives in attribute bits the renderer never reads: bits 6..7 of record byte
 * +0x0A are a mode, bits 2..5 of the same byte are the bank. Measured across the
 * canonical image - 84 arts, 1121 distinct cell records - bits 2..7 of +0x0A are
 * ZERO in every retail cell, so mode 0 is retail and nothing else can occur by
 * accident.
 *
 *   mode 0b00  -> the retail path: bank = actor +0x0D low nibble
 *   otherwise  -> bank = cell +0x0A bits 2..5
 *
 * Entered by a BL that replaces the two instructions 0x0800B09A and 0x0800B09C;
 * returns with `bx lr` to 0x0800B09E, having performed the displaced
 * `lsls r7,r7,#0xc`. Only r6 and r7 are written, which are the retail body's own
 * outputs at that point; r0 (object), r2 (OAM entry), r3 (cell) and r5
 * (attribute 2 under construction) are untouched.
 */
    .syntax unified
    .thumb
    .text
    .thumb_func
    .global sprite_bank_entry
sprite_bank_entry:
    ldrb    r6, [r3, #0x0A]
    lsls    r6, r6, #0x18
    lsrs    r6, r6, #0x1E          /* r6 = mode, bits 6..7 */
    beq     .Lsprite_bank_retail
    ldrb    r6, [r3, #0x0A]
    lsls    r6, r6, #0x1A
    lsrs    r6, r6, #0x10          /* r6 = (bits 2..5) << 12 */
    b       .Lsprite_bank_done
.Lsprite_bank_retail:
    ldrb    r6, [r0, #0x0D]
    lsls    r6, r6, #0x1C
    lsrs    r6, r6, #0x10          /* r6 = (actor bank) << 12 */
.Lsprite_bank_done:
    lsls    r7, r7, #0x0C          /* the displaced retail instruction */
    bx      lr
    .align 2
