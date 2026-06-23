# Kosmos CP1 development toolchain

A small, modern toolchain for the **Kosmos CP1** ("Computer Praxis", 1983) — the
8049-based educational microcomputer sold in German-speaking Europe. It lets you:

- **write CP1 programs in real assembly** (mnemonics, labels, named data) — `cp1asm.py`
- **load them without typing them in** by rendering a program as a **cassette
  WAV** you play into the CP2 Kassetten-Modul — `cp1wav.py`
- **read real CP1 tapes back** into program images — `cp1decode.py`

Everything is plain Python 3 (only `numpy` for the audio tools). No hardware
mods, no hand-keying 256 cells on the keypad.

> The CP1/CP2 cassette format is documented nowhere numerically — the manual only
> *names* the two FSK tones, and no emulator implements the CP2. It was
> **reverse-engineered here from a digitized real CP2 save** and validated by a
> byte-exact round-trip. See [The cassette format](#the-cassette-format).

## Quick start

```sh
pip install numpy

# assemble an example program (counter that shows 0..99 on the display)
python3 cp1asm.py examples/counter.txt counter.bin

# turn it into a cassette tape you can play into the CP2
python3 cp1wav.py counter.bin counter.wav

# (optional) verify it decodes back byte-for-byte
python3 cp1decode.py counter.wav counter.bin     # -> 256/256 bytes match
```

Then on the CP1: select cassette-load (`CAL`) and play `counter.wav` into the
CP2's recorder input. Or just enter the listing by hand — `cp1asm` is useful on
its own to turn readable assembly into the cell numbers you key in.

## Writing programs — `cp1asm`

A real two-pass assembler: labels for jump targets, named `DATA` cells, `ORG`,
`EQU`, and case-insensitive mnemonics. The [`examples/counter.txt`](examples/counter.txt):

```asm
        ORG 0
start:  AKO 0          # Akku <- 0  (counter := 0)
loop:   ANZ            # show counter on the display
        VZG 250        #   for 250 ms
        ADD one        # counter := counter + 1
        VGL limit      # counter == 100 ?
        SPB start      #   yes -> wrap to 0
        SPU loop       #   no  -> next value
one:    DATA 1
limit:  DATA 100       # change this to count to a different value
```

Existing **hand-encoded numeric listings** (`000 AKO 04.000  # ...`) also
assemble unchanged, so old CP1 programs keep working.

### CP1 instruction set

The CP1 is a single-accumulator machine; a cell is `OP.operand` (opcode 01–24,
operand 0–255). `00.xxx` cells are *data*, not instructions.

| Mn. | OP | Meaning | | Mn. | OP | Meaning |
|-----|----|---------|-|-----|----|---------|
| `HLT` | 01 | halt | | `SPB` | 11 | branch if last compare true |
| `ANZ` | 02 | show Akku on display | | `VGR` | 12 | compare Akku > cell |
| `VZG` | 03 | delay *xxx* ms | | `VKL` | 13 | compare Akku < cell |
| `AKO` | 04 | Akku := constant *xxx* | | `NEG` | 14 | negate Akku (0/1) |
| `LDA` | 05 | Akku := cell *xxx* | | `UND` | 15 | Akku AND cell (0/1) |
| `ABS` | 06 | cell *xxx* := Akku | | `P1E` | 16 | read Port 1 (bit / byte) |
| `ADD` | 07 | Akku += cell *xxx* | | `P1A` | 17 | write Port 1 (bit / byte) |
| `SUB` | 08 | Akku -= cell *xxx* | | `P2A` | 18 | write Port 2 |
| `SPU` | 09 | jump to *xxx* | | `LIA` | 19 | load Akku indirect |
| `VGL` | 10 | compare Akku = cell | | `AIS` | 20 | store Akku indirect |
| | | | | `SIU` | 21 | jump indirect |

`P3E 22`, `P4A 23`, `P5A 24` need the CP3 memory expansion. Conditional jumps are
a compare (`VGL`/`VGR`/`VKL`) followed by `SPB`.

## The cassette format

Reverse-engineered from a real CP2 `CAS` save and validated by round-trip:

- **FSK**, two continuous-phase carriers: **f1 ≈ 984 Hz** (low) and **f2 ≈ 2250 Hz** (high).
- **Each bit = an f2 burst then an f1 burst** (~100 ms total); the *longer* burst
  encodes the value (the manual's 1/3 : 2/3 duty cycle, which also makes it
  tolerant of cassette speed wobble): bit **1** = 35 ms f2 + 65 ms f1, bit **0** =
  the reverse. **Bit boundary = the f1→f2 edge** → the decoder self-clocks.
- **LSB first**; ~10 baud, so a full 256-cell program is ~7 minutes of audio.
- **Lead-in:** ~16 s of steady f1; **trailing:** the line drops to 0 V (= f2).
- **Memory image:** each cell is `(opcode<<8)|operand`; stored opcode-then-operand,
  interleaved → 512 bytes = 256 cells. On tape, per 256-byte block the byte order
  is `0, 255, 254, … , 1`.

If your unit's tones differ, decode one of your own `CAS` saves with
`cp1decode.py`, read off f1/f2, and pass `--f1/--f2` to `cp1wav.py`.

(Bit timing and byte order match [asig/kosmos_tape_emulator](https://github.com/asig/kosmos_tape_emulator);
the image layout matches the [asig/kosmos-cp1](https://github.com/asig/kosmos-cp1) emulator/assembler,
which is a great companion for *running* `.bin` images and as a validation oracle.)

## Validation

- assemble → `cp1wav` → `cp1decode` reproduces the image **byte-exact**;
- a genuine CP2 recording decodes back to a valid CP1 program (init cells exactly).

## Credits

Reverse-engineering of the cassette format and these tools by **Claude
(Anthropic, Opus 4.8)**, directed by **Michael Wessel (LambdaMikel)**. Born out
of the [philips-mc6400-vector-graphics](https://github.com/lambdamikel/philips-mc6400-vector-graphics)
and [towers-of-hanoi](https://github.com/lambdamikel/towers-of-hanoi) projects.

MIT licensed — see [LICENSE](LICENSE).
