#!/usr/bin/env python3
"""
CP1 cassette WAV -> bytes  (decoder / verifier).

Self-clocking FSK decoder for the Kosmos CP1 / CP2 cassette format:
each bit is an f2 burst (~2250 Hz) followed by an f1 burst (~980 Hz); the
longer burst wins (1-run > 0-run -> bit 1).  Bit boundaries are the f1->f2
falling edges, so wow/flutter is tolerated.  LSB first; per 256-byte block the
byte order on tape is 0,255,254,...,1; a long f1 tone is the lead-in.

usage: cp1decode.py recording.wav [expected.bin]
Writes <recording>.decoded.bin (the 256/512-byte memory image) and, if an
expected image is given, reports the byte match.
"""
import wave, numpy as np, sys, os

THR = 1500; HOP_S = 0.002; WIN_S = 0.008

def decode(wavfile):
    w = wave.open(wavfile, 'rb'); sr = w.getframerate(); n = w.getnframes()
    a = np.frombuffer(w.readframes(n), dtype=np.int16).astype(float); a /= np.abs(a).max()
    hop, win = int(HOP_S*sr), int(WIN_S*sr)
    nb = (len(a)-win)//hop
    s = np.empty(nb, dtype=np.int8)
    for k in range(nb):
        seg = a[k*hop:k*hop+win]; seg = seg - seg.mean()
        zc = np.sum(np.abs(np.diff(np.sign(seg))))/2.0
        s[k] = 1 if (zc*sr/(2.0*win)) < THR else 0      # 1 = f1 (low), 0 = f2 (high)
    # clean transition glitches shorter than ~12 ms
    runs = []; v = s[0]; c = 1
    for x in s[1:]:
        if x == v: c += 1
        else: runs.append([v, c]); v = x; c = 1
    runs.append([v, c])
    for i in range(1, len(runs)-1):
        if runs[i][1] < int(0.012/HOP_S): runs[i][0] = runs[i-1][0]
    sc = np.array([val for val, cnt in runs for _ in range(cnt)], dtype=np.int8)
    fall = np.where((sc[:-1] == 1) & (sc[1:] == 0))[0]
    rise = np.where((sc[:-1] == 0) & (sc[1:] == 1))[0]
    # data starts at the falling edge ending the first >3 s f1 lead-in
    start = None; i = 0
    while i < len(sc):
        if sc[i] == 1:
            j = i
            while j < len(sc) and sc[j] == 1: j += 1
            if j - i > int(3.0/HOP_S): start = j - 1; break
            i = j
        else: i += 1
    fall = fall[fall >= start]
    bits = []
    for i in range(len(fall)-1):
        f0, f1 = fall[i], fall[i+1]
        r = rise[(rise > f0) & (rise < f1)]
        if len(r) == 0: continue
        bits.append(1 if (f1 - r[0]) > (r[0] - f0) else 0)
    by = [sum(bits[8*k+j] << j for j in range(8)) for k in range(len(bits)//8)]
    return by

def untape(by):
    img = bytearray((len(by)//256)*256)
    idx = 0
    for blk in range(len(by)//256):
        pos = 0
        while True:
            img[blk*256+pos] = by[idx]; idx += 1; pos = (pos-1) & 0xff
            if pos == 0: break
    return bytes(img)

if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit("usage: cp1decode.py recording.wav [expected.bin]")
    by = decode(sys.argv[1])
    mem = untape(by)
    out = os.path.splitext(sys.argv[1])[0] + ".decoded.bin"
    open(out, "wb").write(mem)
    print(f"decoded {len(by)} bytes -> {out}")
    print("cells 0..9:", [f"{mem[2*i]:02d}.{mem[2*i+1]:03d}" for i in range(10)])
    if len(sys.argv) > 2:
        e = open(sys.argv[2], "rb").read()
        print(f"match vs {sys.argv[2]}: {sum(x==y for x,y in zip(mem,e))}/{min(len(mem),len(e))} bytes")
