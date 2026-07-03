#!/usr/bin/env python3
"""
cp1emu -- a small instruction-level emulator / tracer for the Kosmos CP1.

Runs a CP1 program (the same listings `cp1asm.py` assembles) with no hardware and
logs what it does: every `ANZ` (7-segment display), every port write, every port
read, and the final `HLT` -- or a diagnosed non-terminating loop. Handy for
checking a program's logic and its display output before keying/loading it onto a
real CP1, and for understanding the machine.

Semantics (matching `cp1asm.py`'s opcode table and the CP1 manual):
  * a memory cell's *value* is its operand byte; `ABS`/`AIS` overwrite it.
  * `AKO` loads an immediate; `LDA`/`ADD`/`SUB`/`VGL` use a cell's value.
  * `SPU` is an unconditional jump (used as a call); `SIU` is an indirect jump
    through a cell (used as a return); `LIA`/`AIS` are indirect load/store.
  * `VGL`/`VGR`/`VKL` set a compare flag (`==`,`>`,`<`) that `SPB` branches on.
  * arithmetic is 8-bit (wraps mod 256).

Port I/O: reads (`P1E`, `P3E`) return a constant you supply (default 0); writes
(`P1A`, `P2A`, `P4A`, `P5A`) are logged. Note a Port-2 pin write (`P2A`) latches
**1 for any non-zero accumulator** and 0 otherwise -- so it's shown as that bit.

Usage:
    python3 cp1emu.py examples/counter.txt
    python3 cp1emu.py prog.txt --trace
    python3 cp1emu.py prog.txt --p1e 1        # Port-1 reads return 1
"""
import sys, os, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)          # cp1asm.py lives beside this file
import cp1asm  # noqa: E402

MNEM = {1:'HLT', 2:'ANZ', 3:'VZG', 4:'AKO', 5:'LDA', 6:'ABS', 7:'ADD', 8:'SUB',
        9:'SPU', 10:'VGL', 11:'SPB', 12:'VGR', 13:'VKL', 14:'NEG', 15:'UND',
        16:'P1E', 17:'P1A', 18:'P2A', 19:'LIA', 20:'AIS', 21:'SIU', 22:'P3E',
        23:'P4A', 24:'P5A'}
OUT_PORTS = {17: 'P1A', 18: 'P2A', 23: 'P4A', 24: 'P5A'}


def load(path):
    img, maxaddr = cp1asm.assemble(open(path).read())
    code = [img[2 * i]     for i in range(len(img) // 2)]   # opcode per cell
    oper = [img[2 * i + 1] for i in range(len(img) // 2)]   # operand byte per cell
    while len(code) < 256:
        code.append(0); oper.append(0)
    return code, oper, maxaddr


def run(code, oper, p1e, p3e, max_steps, trace):
    mem = list(oper)                    # cell value = operand byte; ABS/AIS mutate
    pc = accu = 0
    flag = False
    steps = 0
    halted = False
    anz, writes, reads = [], 0, 0

    while steps < max_steps:
        steps += 1
        opc, opr = code[pc], oper[pc]
        if trace:
            print(f"  {pc:03d}: {MNEM.get(opc, '?'+str(opc))} .{opr:03d}"
                  f"   accu={accu} flag={int(flag)}")
        nxt = pc + 1

        if   opc == 1:  halted = True; break                   # HLT
        elif opc == 2:                                         # ANZ (display)
            anz.append(accu); print(f"[{steps:6d}] ANZ @{pc:03d}  display: {accu}")
        elif opc == 3:  pass                                   # VZG (delay)
        elif opc == 4:  accu = opr                             # AKO
        elif opc == 5:  accu = mem[opr]                        # LDA
        elif opc == 6:  mem[opr] = accu                        # ABS
        elif opc == 7:  accu = (accu + mem[opr]) & 0xFF        # ADD
        elif opc == 8:  accu = (accu - mem[opr]) & 0xFF        # SUB
        elif opc == 9:  nxt = opr                              # SPU (jump)
        elif opc == 10: flag = (accu == mem[opr])             # VGL  ==
        elif opc == 11: nxt = opr if flag else nxt            # SPB  (branch)
        elif opc == 12: flag = (accu > mem[opr])              # VGR  >
        elif opc == 13: flag = (accu < mem[opr])              # VKL  <
        elif opc == 14: accu = (-accu) & 0xFF                 # NEG
        elif opc == 15: accu = accu & mem[opr]                # UND  (and)
        elif opc == 16:                                       # P1E (read)
            reads += 1; accu = p1e
            print(f"[{steps:6d}] P1E @{pc:03d}  port 1 read -> {accu}")
        elif opc == 22:                                       # P3E (read)
            reads += 1; accu = p3e
            print(f"[{steps:6d}] P3E @{pc:03d}  port 3 read -> {accu}")
        elif opc in OUT_PORTS:                                # P1A/P2A/P4A/P5A
            writes += 1
            if opc == 18:      # P2A latches one pin: non-zero -> 1
                print(f"[{steps:6d}] P2A @{pc:03d}  pin {opr} <- "
                      f"{1 if accu else 0}  (accu={accu})")
            else:
                print(f"[{steps:6d}] {OUT_PORTS[opc]} @{pc:03d}  "
                      f"port {opr} <- accu={accu}")
        elif opc == 19: accu = mem[mem[opr]]                  # LIA (indirect load)
        elif opc == 20: mem[mem[opr]] = accu                  # AIS (indirect store)
        elif opc == 21: nxt = mem[opr]                        # SIU (indirect jump)
        # unknown opcodes fall through as no-ops
        pc = nxt

    return dict(halted=halted, steps=steps, pc=pc, anz=anz,
                writes=writes, reads=reads)


def main():
    ap = argparse.ArgumentParser(description="Kosmos CP1 emulator / tracer")
    ap.add_argument("listing")
    ap.add_argument("--p1e", type=int, default=0, help="value Port-1 reads return")
    ap.add_argument("--p3e", type=int, default=0, help="value Port-3 reads return")
    ap.add_argument("--max-steps", type=int, default=2_000_000)
    ap.add_argument("--trace", action="store_true", help="print every instruction")
    a = ap.parse_args()

    code, oper, maxaddr = load(a.listing)
    print(f"# {a.listing}: highest cell {maxaddr}")
    print("#" + "-" * 62)
    r = run(code, oper, a.p1e & 0xFF, a.p3e & 0xFF, a.max_steps, a.trace)
    print("#" + "-" * 62)
    shown = r['anz'] if len(r['anz']) <= 40 else r['anz'][:40] + ['...']
    print(f"display (ANZ) : {len(r['anz'])} values {shown}")
    print(f"port writes   : {r['writes']}")
    print(f"port reads    : {r['reads']}")
    print(f"steps         : {r['steps']}")
    if r['halted']:
        print(f"result        : HLT at pc={r['pc']}.")
    else:
        print(f"result        : no HLT after {r['steps']} steps (last pc={r['pc']}) "
              f"-- likely an infinite loop; try --trace.")


if __name__ == "__main__":
    main()
