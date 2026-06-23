#!/usr/bin/env python3
"""
cp1asm -- a real assembler for the Kosmos CP1.

Write programs with mnemonics, labels and named data instead of raw cell
numbers. Two-phase: collect labels, then resolve & emit (so forward jumps work).
Output is the CP1 memory image (256 bytes if the highest cell <= 127, else 512),
2 bytes per cell: opcode then operand.

Syntax
------
  # or ;            comment to end of line
  label:           define a label = the current cell address
  ORG  n           set the assembly address (default 0)
  name EQU n       define a constant symbol (a value, not a cell)
  MNEMONIC [op]    an instruction; op is a number or a label/EQU name (default 0)
  DATA n           a data cell holding value n  (assembled as 00.n)

Legacy numeric listings -- '<addr> [mnemonic] <OP>.<operand>  # comment' -- are
also accepted unchanged, so existing hand-encoded CP1 programs still assemble.

Mnemonics (CP1 Kurzform):
  HLT ANZ VZG AKO LDA ABS ADD SUB SPU VGL SPB VGR VKL NEG UND
  P1E(=PIE) P1A(=PIA) P2A LIA AIS SIU P3E P4A P5A
"""
import re, sys

OPS = {'HLT':1, 'ANZ':2, 'VZG':3, 'AKO':4, 'LDA':5, 'ABS':6, 'ADD':7, 'SUB':8,
       'SPU':9, 'VGL':10, 'SPB':11, 'VGR':12, 'VKL':13, 'NEG':14, 'UND':15,
       'P1E':16, 'PIE':16, 'P1A':17, 'PIA':17, 'P2A':18, 'LIA':19, 'AIS':20,
       'SIU':21, 'P3E':22, 'P4A':23, 'P5A':24}

class AsmError(Exception):
    pass

def assemble(text):
    items = []          # (addr, opcode, operand)  operand: int or symbol str
    labels = {}
    pc = 0
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = re.split(r'[#;]', raw, 1)[0].strip()
        if not line:
            continue
        toks = line.split()
        # --- legacy numeric listing line:  addr [mnem] OP.operand [junk] ---
        if re.fullmatch(r'\d+', toks[0]) and re.search(r'\d+\.\d+', line):
            m = re.search(r'(\d+)\.(\d+)', line)
            items.append((int(toks[0]), int(m.group(1)), int(m.group(2))))
            continue
        # --- leading label(s):  name: ---
        while True:
            lm = re.match(r'([A-Za-z_]\w*)\s*:\s*(.*)$', line)
            if not lm:
                break
            name = lm.group(1).upper()
            if name in labels:
                raise AsmError(f"line {lineno}: symbol '{name}' redefined")
            labels[name] = pc
            line = lm.group(2).strip()
        if not line:
            continue
        toks = line.split()
        head = toks[0].upper()
        if head == 'ORG':
            pc = _num(toks[1], lineno); continue
        if len(toks) >= 3 and toks[1].upper() == 'EQU':
            labels[toks[0].upper()] = _num(toks[2], lineno); continue
        if head in ('DATA', 'DB'):
            items.append((pc, 0, toks[1])); pc += 1; continue
        if head in OPS:
            items.append((pc, OPS[head], toks[1] if len(toks) > 1 else 0)); pc += 1; continue
        raise AsmError(f"line {lineno}: unknown mnemonic/directive '{toks[0]}'")

    def resolve(tok):
        if isinstance(tok, int):
            return tok
        if re.fullmatch(r'\d+', tok):
            return int(tok)
        if tok.upper() in labels:
            return labels[tok.upper()]
        raise AsmError(f"undefined symbol '{tok}'")

    mem = [(0, 0)] * 256
    maxaddr = -1
    for addr, op, operand in items:
        val = resolve(operand)
        if not 0 <= addr < 256:
            raise AsmError(f"address {addr} out of range (0..255)")
        if not (0 <= op < 256 and 0 <= val < 256):
            raise AsmError(f"cell {addr}: {op}.{val} out of byte range")
        mem[addr] = (op, val); maxaddr = max(maxaddr, addr)
    ncells = 256 if maxaddr > 127 else 128
    out = bytearray()
    for i in range(ncells):
        out += bytes(mem[i])
    return bytes(out), maxaddr

def _num(s, lineno):
    try:
        return int(s, 0)
    except ValueError:
        raise AsmError(f"line {lineno}: '{s}' is not a number")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: cp1asm.py program.txt out.bin")
    try:
        img, maxaddr = assemble(open(sys.argv[1]).read())
    except AsmError as e:
        sys.exit(f"error: {e}")
    open(sys.argv[2], "wb").write(img)
    print(f"highest cell = {maxaddr}; wrote {len(img)} bytes ({len(img)//2} cells) -> {sys.argv[2]}")
