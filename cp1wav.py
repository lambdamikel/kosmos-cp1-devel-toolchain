#!/usr/bin/env python3
"""
CP1 .bin -> cassette WAV, CALIBRATED against a real CP1/CP2 'CAS' recording.

Format (measured from hanoi-cp1.wav, a genuine CP2 save):
  - two continuous-phase carriers: f1 ~= 984 Hz (low), f2 ~= 2250 Hz (high)
  - each bit = an f2 burst followed by an f1 burst, total ~100 ms; the longer
    burst encodes the value (the 1/3:2/3 duty cycle):
        bit 1 -> 35 ms f2 + 65 ms f1     (f1 longer)
        bit 0 -> 65 ms f2 + 35 ms f1     (f2 longer)
  - LSB first; per 256-byte block, byte order 0,255,254,...,1
  - lead-in: a steady f1 tone (~16 s)
Validated by round-trip (cp1wav -> decode2 reproduces the bytes exactly).
"""
import sys, wave, struct, argparse
import numpy as np

SR = 44100

def tape_bits(img):
    for blk in range(max(1, len(img)//256)):
        pos = 0
        while True:
            b = img[blk*256 + pos]
            for j in range(8):                 # LSB first
                yield (b >> j) & 1
            pos = (pos - 1) & 0xff
            if pos == 0:
                break

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("binfile"); ap.add_argument("wavfile")
    ap.add_argument("--f1", type=float, default=984.0, help="low carrier (bit-1 / lead-in), Hz")
    ap.add_argument("--f2", type=float, default=2250.0, help="high carrier (bit-0), Hz")
    ap.add_argument("--lead", type=float, default=16.0, help="lead-in seconds")
    ap.add_argument("--bit", type=float, default=0.100, help="bit period, s")
    ap.add_argument("--amp", type=float, default=0.7)
    a = ap.parse_args()
    img = open(a.binfile, "rb").read()
    short, long = 0.35 * a.bit, 0.65 * a.bit

    segs = [(a.f1, a.lead)]                              # (freq, duration)
    for bit in tape_bits(img):
        if bit: segs += [(a.f2, short), (a.f1, long)]   # bit 1: f2 short, f1 long
        else:   segs += [(a.f2, long), (a.f1, short)]   # bit 0: f2 long,  f1 short
    segs.append((a.f2, 0.30))   # trailing tone (line drops to 0 V -> f2): closes the last bit

    freqs = np.concatenate([np.full(max(1, int(SR*d)), f) for f, d in segs])
    phase = 2*np.pi*np.cumsum(freqs)/SR                  # continuous phase -> no clicks
    sig = (a.amp*np.sin(phase)*32767).astype(np.int16)

    w = wave.open(a.wavfile, "wb")
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(sig.tobytes()); w.close()
    print(f"{len(img)} bytes -> {a.wavfile}: {len(sig)/SR:.1f}s, f1={a.f1} f2={a.f2} lead={a.lead}s")

if __name__ == "__main__":
    main()
