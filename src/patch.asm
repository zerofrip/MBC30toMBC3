; RGBDS 0.3.4. Standard MBC3, four SRAM banks and hardware RTC.
; The Japanese stock OpenSRAM/CloseSRAM calling convention preserves AF.
SECTION "Guarded SRAM entry", ROM0[$2f9d]
    jp MBC3OpenSRAM

SECTION "Guarded SRAM implementation", ROM0[$3f7f]
MBC3OpenSRAM:
    push af
    cp 4
    jr c, .valid
    cp 8
    jr c, .invalid
    cp 13
    jr nc, .invalid
.valid:
    ld a, 1
    ld [$6000], a
    ld a, $0a
    ld [$0000], a
    pop af
    ld [$4000], a
    ret
.invalid:
    pop af
    jp $2fad
MBC3OpenSRAMEnd:

; Nine bytes formerly in bank 4 now follow the bank 3 backup save.
SECTION "Save Crystal data", ROMX[$5068], BANK[5]
    ld a, 3
    call $2f9d
    ld hl, $d463
    ld de, $bf20
    ld bc, 7
    call $2ff2
    ld hl, $d46a
    ld a, [hli]
    ld [$bf27], a
    ld a, [hli]
    ld [$bf28], a
    jp $2fad

SECTION "Load Crystal data", ROMX[$5087], BANK[5]
    ld a, 3
    call $2f9d
    ld hl, $bf20
    ld de, $d463
    ld bc, 7
    call $2ff2
    ld hl, $d46a
    xor a
    ld [hli], a
    ld [hli], a
    jp $2fad

; Always report no configured Mobile Adapter (A=C=0, carry clear).
SECTION "Offline Mobile Adapter status", ROMX[$6397], BANK[$41]
    xor a
    ld c, a
    ret

; PCC entry must not use an unreadable SRAM value as a jump-table index.
; No Mobile Trade Corner transaction is pending in the offline edition.
SECTION "Offline Trade Corner status", ROMX[$4918], BANK[$5c]
    xor a
    ld [$c2dd], a
    ret

; SRAM $05:a000 is an online distribution flag. $ff must not grant a GS Ball.
SECTION "Offline distribution event", ROMX[$4816], BANK[$5c]
    xor a
    ld [$c2dd], a
    ret
