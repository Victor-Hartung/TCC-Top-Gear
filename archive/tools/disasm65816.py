#!/usr/bin/env python3
"""Small read-only 65C816 disassembler used for the Top Gear audit."""

from __future__ import annotations

import argparse
from pathlib import Path


ROWS = [
    "BRK:imm8 ORA:dpix COP:imm8 ORA:sr TSB:dp ORA:dp ASL:dp ORA:dpl PHP:imp ORA:immM ASL:acc PHD:imp TSB:abs ORA:abs ASL:abs ORA:long",
    "BPL:rel8 ORA:dpiy ORA:dpi ORA:sriy TRB:dp ORA:dpx ASL:dpx ORA:dply CLC:imp ORA:absy INC:acc TCS:imp TRB:abs ORA:absx ASL:absx ORA:longx",
    "JSR:abs AND:dpix JSL:long AND:sr BIT:dp AND:dp ROL:dp AND:dpl PLP:imp AND:immM ROL:acc PLD:imp BIT:abs AND:abs ROL:abs AND:long",
    "BMI:rel8 AND:dpiy AND:dpi AND:sriy BIT:dpx AND:dpx ROL:dpx AND:dply SEC:imp AND:absy DEC:acc TSC:imp BIT:absx AND:absx ROL:absx AND:longx",
    "RTI:imp EOR:dpix WDM:imm8 EOR:sr MVP:block EOR:dp LSR:dp EOR:dpl PHA:imp EOR:immM LSR:acc PHK:imp JMP:abs EOR:abs LSR:abs EOR:long",
    "BVC:rel8 EOR:dpiy EOR:dpi EOR:sriy MVN:block EOR:dpx LSR:dpx EOR:dply CLI:imp EOR:absy PHY:imp TCD:imp JMP:long EOR:absx LSR:absx EOR:longx",
    "RTS:imp ADC:dpix PER:rel16 ADC:sr STZ:dp ADC:dp ROR:dp ADC:dpl PLA:imp ADC:immM ROR:acc RTL:imp JMP:absi ADC:abs ROR:abs ADC:long",
    "BVS:rel8 ADC:dpiy ADC:dpi ADC:sriy STZ:dpx ADC:dpx ROR:dpx ADC:dply SEI:imp ADC:absy PLY:imp TDC:imp JMP:absxi ADC:absx ROR:absx ADC:longx",
    "BRA:rel8 STA:dpix BRL:rel16 STA:sr STY:dp STA:dp STX:dp STA:dpl DEY:imp BIT:immM TXA:imp PHB:imp STY:abs STA:abs STX:abs STA:long",
    "BCC:rel8 STA:dpiy STA:dpi STA:sriy STY:dpx STA:dpx STX:dpy STA:dply TYA:imp STA:absy TXS:imp TXY:imp STZ:abs STA:absx STZ:absx STA:longx",
    "LDY:immX LDA:dpix LDX:immX LDA:sr LDY:dp LDA:dp LDX:dp LDA:dpl TAY:imp LDA:immM TAX:imp PLB:imp LDY:abs LDA:abs LDX:abs LDA:long",
    "BCS:rel8 LDA:dpiy LDA:dpi LDA:sriy LDY:dpx LDA:dpx LDX:dpy LDA:dply CLV:imp LDA:absy TSX:imp TYX:imp LDY:absx LDA:absx LDX:absy LDA:longx",
    "CPY:immX CMP:dpix REP:imm8 CMP:sr CPY:dp CMP:dp DEC:dp CMP:dpl INY:imp CMP:immM DEX:imp WAI:imp CPY:abs CMP:abs DEC:abs CMP:long",
    "BNE:rel8 CMP:dpiy CMP:dpi CMP:sriy PEI:dp CMP:dpx DEC:dpx CMP:dply CLD:imp CMP:absy PHX:imp STP:imp JMP:abslind CMP:absx DEC:absx CMP:longx",
    "CPX:immX SBC:dpix SEP:imm8 SBC:sr CPX:dp SBC:dp INC:dp SBC:dpl INX:imp SBC:immM NOP:imp XBA:imp CPX:abs SBC:abs INC:abs SBC:long",
    "BEQ:rel8 SBC:dpiy SBC:dpi SBC:sriy PEA:abs SBC:dpx INC:dpx SBC:dply SED:imp SBC:absy PLX:imp XCE:imp JSR:absxi SBC:absx INC:absx SBC:longx",
]

OPS = []
for row in ROWS:
    OPS.extend(tuple(item.split(":", 1)) for item in row.split())

FIXED_LEN = {
    "imp": 1, "acc": 1,
    "imm8": 2, "dp": 2, "dpx": 2, "dpy": 2, "dpix": 2,
    "dpiy": 2, "dpi": 2, "dpl": 2, "dply": 2, "sr": 2,
    "sriy": 2, "rel8": 2,
    "abs": 3, "absx": 3, "absy": 3, "absi": 3, "absxi": 3,
    "abslind": 3, "rel16": 3, "block": 3,
    "long": 4, "longx": 4,
}


def cpu_to_offset(addr: int) -> int:
    bank = (addr >> 16) & 0xFF
    lo = addr & 0xFFFF
    if lo < 0x8000:
        raise ValueError("LoROM CPU address must be in $8000-$FFFF")
    return ((bank & 0x7F) * 0x8000) + (lo - 0x8000)


def fmt_operand(mode: str, raw: bytes, pc: int) -> str:
    v = int.from_bytes(raw, "little") if raw else 0
    if mode == "imp": return ""
    if mode == "acc": return "A"
    if mode.startswith("imm"): return f"#${v:0{len(raw)*2}X}"
    if mode == "rel8":
        d = v - 0x100 if v & 0x80 else v
        return f"${((pc & 0xFF0000) | ((pc + 2 + d) & 0xFFFF)):06X}"
    if mode == "rel16":
        d = v - 0x10000 if v & 0x8000 else v
        return f"${((pc & 0xFF0000) | ((pc + 3 + d) & 0xFFFF)):06X}"
    if mode == "dp": return f"${v:02X}"
    if mode == "dpx": return f"${v:02X},X"
    if mode == "dpy": return f"${v:02X},Y"
    if mode == "dpix": return f"(${v:02X},X)"
    if mode == "dpiy": return f"(${v:02X}),Y"
    if mode == "dpi": return f"(${v:02X})"
    if mode == "dpl": return f"[${v:02X}]"
    if mode == "dply": return f"[${v:02X}],Y"
    if mode == "sr": return f"${v:02X},S"
    if mode == "sriy": return f"(${v:02X},S),Y"
    if mode == "abs": return f"${v:04X}"
    if mode == "absx": return f"${v:04X},X"
    if mode == "absy": return f"${v:04X},Y"
    if mode == "absi": return f"(${v:04X})"
    if mode == "absxi": return f"(${v:04X},X)"
    if mode == "abslind": return f"[${v:04X}]"
    if mode == "long": return f"${v:06X}"
    if mode == "longx": return f"${v:06X},X"
    if mode == "block": return f"${raw[0]:02X},${raw[1]:02X}"
    return f"${v:X}"


def disassemble(data: bytes, start_cpu: int, count: int, m8: bool, x8: bool):
    off = cpu_to_offset(start_cpu)
    pc = start_cpu
    for _ in range(count):
        opcode = data[off]
        name, mode = OPS[opcode]
        if mode == "immM": size = 2 if m8 else 3
        elif mode == "immX": size = 2 if x8 else 3
        else: size = FIXED_LEN[mode]
        chunk = data[off:off + size]
        operand = fmt_operand(mode, chunk[1:], pc)
        flags = f"M{8 if m8 else 16} X{8 if x8 else 16}"
        print(f"{pc:06X}  {chunk.hex(' '):<11} {name:<4} {operand:<14} ; {flags}")
        if opcode == 0xC2 and len(chunk) == 2:  # REP clears status bits
            if chunk[1] & 0x20: m8 = False
            if chunk[1] & 0x10: x8 = False
        elif opcode == 0xE2 and len(chunk) == 2:  # SEP sets status bits
            if chunk[1] & 0x20: m8 = True
            if chunk[1] & 0x10: x8 = True
        off += size
        pc = (pc & 0xFF0000) | ((pc + size) & 0xFFFF)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom", type=Path)
    ap.add_argument("start", type=lambda s: int(s.replace(":", ""), 16))
    ap.add_argument("--count", type=int, default=100)
    ap.add_argument("--m8", action="store_true")
    ap.add_argument("--x8", action="store_true")
    ns = ap.parse_args()
    disassemble(ns.rom.read_bytes(), ns.start, ns.count, ns.m8, ns.x8)


if __name__ == "__main__":
    main()
