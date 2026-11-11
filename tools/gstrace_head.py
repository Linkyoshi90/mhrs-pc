#!/usr/bin/env python3
"""Parse the head of a gsrec trace.bin: header, VRAM snapshot, then the
leading record stream (B = BeginTransfer, U = raw upload bytes).
Renders each upload's raw source data as a linear image so we can see
whether strip seams already exist before GS VRAM addressing is involved."""
import struct, sys, os
from PIL import Image

PATH = sys.argv[1] if len(sys.argv) > 1 else "build/trace.bin"
OUT = sys.argv[2] if len(sys.argv) > 2 else "build/trace_uploads"
os.makedirs(OUT, exist_ok=True)

data = open(PATH, "rb").read()
magic, ver, batch_sz, vram_sz = struct.unpack_from("<4I", data, 0)
print(f"magic={magic:#x} ver={ver} batchSize={batch_sz} vramSize={vram_sz}")
assert magic == 0x52545347

off = 16 + vram_sz + 1024 + 8 + 36  # vram + clut + clutCbp + GSTransferCommand
# GSTransferSnapshot: probe 28 vs 32
for probe in (32, 28):
    tag = data[off + probe:off + probe + 1]
    print(f"probe transferState size {probe}: next tag {tag!r}")

# pick the one whose tag is a known record char
KNOWN0 = {b"B", b"U", b"S", b"R", b"F", b"P", b"W", b"C", b"K"}
ts_size = None
for probe in (32, 28):
    if data[off + probe:off + probe + 1] in KNOWN0:
        ts_size = probe
        break
assert ts_size is not None
off += ts_size
print(f"transferState size = {ts_size}, stream starts at {off}")

PSM = {0: "CT32", 1: "CT24", 2: "CT16", 10: "CT16S", 19: "T8", 20: "T4", 27: "T8H", 36: "T4HL", 44: "T4HH", 48: "Z32", 50: "Z16"}

rec = 0
last_b = None
uploads = 0
while off < len(data) and rec < 400:
    tag = data[off:off + 1]
    off += 1
    if tag == b"B":
        (sbp, sbw, spsm, dbp, dbw, dpsm) = struct.unpack_from("<IBBxxIBBxx", data, off)
        ssax, ssay, dsax, dsay, ddir = struct.unpack_from("<HHHHB", data, off + 16)
        rrw, rrh = struct.unpack_from("<HH", data, off + 26)
        direction = struct.unpack_from("<I", data, off + 32)[0]
        off += 36
        last_b = dict(sbp=sbp, sbw=sbw, spsm=spsm, dbp=dbp, dbw=dbw, dpsm=dpsm,
                      dsax=dsax, dsay=dsay, rrw=rrw, rrh=rrh, dir=direction)
        print(f"[{rec:3d}] B dir={direction} dpsm={PSM.get(dpsm, dpsm)} dbp={dbp} dbw={dbw} dst=({dsax},{dsay}) rrw={rrw} rrh={rrh}")
    elif tag == b"U":
        n = struct.unpack_from("<I", data, off)[0]
        off += 4
        payload = data[off:off + n]
        off += n
        info = last_b or {}
        print(f"[{rec:3d}] U {n} bytes  (rrw={info.get('rrw')} rrh={info.get('rrh')} dpsm={PSM.get(info.get('dpsm'), info.get('dpsm'))})")
        if info and n and uploads < 30:
            rrw, rrh, dpsm = info["rrw"], info["rrh"], info["dpsm"]
            img = None
            if dpsm in (0, 48) and rrw * rrh * 4 == n:
                img = Image.frombytes("RGBA", (rrw, rrh), payload)
            elif dpsm in (2, 10, 50) and rrw * rrh * 2 == n:
                raw = struct.unpack(f"<{rrw * rrh}H", payload)
                px = [((v & 0x1F) << 3, ((v >> 5) & 0x1F) << 3, ((v >> 10) & 0x1F) << 3, 255) for v in raw]
                img = Image.new("RGBA", (rrw, rrh)); img.putdata(px)
            if img:
                p = os.path.join(OUT, f"upload_{uploads:02d}_{rrw}x{rrh}_{PSM.get(dpsm, dpsm)}_dst{info.get('dsax')},{info.get('dsay')}.png")
                img.save(p)
                print(f"        -> {p}")
            uploads += 1
    elif tag in (b"R", b"F", b"P"):
        print(f"[{rec:3d}] {tag.decode()}")
    elif tag == b"S":
        off += batch_sz
        print(f"[{rec:3d}] S batch({batch_sz})")
    elif tag == b"W":
        off += 24
        print(f"[{rec:3d}] W")
    elif tag == b"C":
        off += 24
        print(f"[{rec:3d}] C texload")
    elif tag == b"K":
        off += 120
        print(f"[{rec:3d}] K clear")
    else:
        print(f"[{rec:3d}] unknown tag {tag!r} at {off - 1}, stopping")
        break
    rec += 1
print(f"parsed {rec} records, {uploads} uploads dumped")
