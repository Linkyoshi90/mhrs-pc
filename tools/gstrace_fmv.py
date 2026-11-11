#!/usr/bin/env python3
"""Analyze an FMV-era gsrec trace: decode S (draw) batches to find the video
texture(s), then render those regions straight from the VRAM snapshot using
the runtime's own CT32 swizzle tables to check for strip seams."""
import struct, sys, os
from PIL import Image

PATH = sys.argv[1] if len(sys.argv) > 1 else "build/trace_fmv.bin"
OUT = sys.argv[2] if len(sys.argv) > 2 else "build/trace_fmv"
os.makedirs(OUT, exist_ok=True)

data = open(PATH, "rb").read()
magic, ver, batch_sz, vram_sz = struct.unpack_from("<4I", data, 0)
assert magic == 0x52545347
vram = data[16:16 + vram_sz]

# --- GS CT32 addressing (ported from ps2_gs_memory.*) ---
BLOCK32 = [[0,1,4,5,16,17,20,21],[2,3,6,7,18,19,22,23],[8,9,12,13,24,25,28,29],[10,11,14,15,26,27,30,31]]
COL32 = [[0,1,4,5,8,9,12,13],[2,3,6,7,10,11,14,15],[16,17,20,21,24,25,28,29],[18,19,22,23,26,27,30,31],
         [32,33,36,37,40,41,44,45],[34,35,38,39,42,43,46,47],[48,49,52,53,56,57,60,61],[50,51,54,55,58,59,62,63]]

def ct32_byte_addr(dbp, bw, x, y):
    page = dbp // 32 + (y // 32) * bw + (x // 64)
    b = dbp % 32
    yy, xx = y % 32, x % 64
    pix = page * 2048 + (b + BLOCK32[(yy // 8) % 4][(xx // 8) % 8]) * 64 + COL32[yy % 8][xx % 8]
    return (pix * 4) & (len(vram) - 4)

def dump_ct32(dbp, bw, w, h, name):
    img = Image.new("RGBA", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            a = ct32_byte_addr(dbp, bw, x, y)
            px[x, y] = (vram[a], vram[a+1], vram[a+2], vram[a+3])
    p = os.path.join(OUT, name)
    img.save(p)
    return p

# --- parse record stream, collect draws ---
off = 16 + vram_sz + 1024 + 8 + 36 + 32
draws = []
rec = 0
while off < len(data):
    tag = data[off:off+1]; off += 1
    if tag == b"S":
        b = data[off:off+batch_sz]; off += batch_sz
        n = b[120]
        st = 128
        prim_type = b[st+112]
        tex0 = st+24
        tbp, tbw, psm, tw, th = struct.unpack_from("<I4B", b, tex0)
        fbp, fbw, fpsm = struct.unpack_from("<IBxxxB", b, st)  # frame: fbp u32, fbw u8 @4, psm u8 @8
        verts = []
        for i in range(min(n, 3)):
            vb = i*40
            x, y = struct.unpack_from("<2f", b, vb)
            s, t = struct.unpack_from("<2f", b, vb+24)
            u, v = struct.unpack_from("<2H", b, vb+32)
            verts.append((x, y, s, t, u, v))
        draws.append(dict(prim=prim_type, n=n, tbp=tbp, tbw=tbw, psm=psm, tw=tw, th=th,
                          fbp=fbp, fbw=fbw, fpsm=fpsm, verts=verts))
    elif tag == b"B": off += 36; print(f"[{rec}] B!")
    elif tag == b"U":
        n = struct.unpack_from("<I", data, off)[0]; off += 4 + n; print(f"[{rec}] U {n} bytes!")
    elif tag in (b"R", b"F", b"P"): pass
    elif tag == b"C": off += 24
    elif tag == b"W": off += 24
    elif tag == b"K": off += 120
    else:
        print(f"[{rec}] unknown tag {tag!r} at {off-1}, stop"); break
    rec += 1

print(f"records={rec} draws={len(draws)}")
PRIM = {0:"point",1:"line",2:"linestrip",3:"tri",4:"tristrip",5:"trifan",6:"sprite"}

# group draws by texture
from collections import Counter
groups = Counter((d["tbp"], d["tbw"], d["psm"], d["tw"], d["th"], d["prim"]) for d in draws)
for k, c in groups.most_common(12):
    tbp, tbw, psm, tw, th, prim = k
    print(f"  {c:4d}x prim={PRIM.get(prim,prim)} tex tbp={tbp} tbw={tbw} psm={psm} {1<<tw}x{1<<th}")

# dump textures used by sprite draws
seen = set()
for d in draws:
    key = (d["tbp"], d["tbw"], d["psm"], d["tw"], d["th"])
    if d["prim"] == 6 and key not in seen and d["psm"] == 0:
        seen.add(key)
        w, h = min(1 << d["tw"], 2048), min(1 << d["th"], 2048)
        p = dump_ct32(d["tbp"], max(d["tbw"], 1), w, h, f"tex_tbp{d['tbp']}_bw{d['tbw']}_{w}x{h}.png")
        print("dumped", p)

# print a few sprite draws with geometry for strip analysis
print("--- first sprite draws:")
for d in [d for d in draws if d["prim"] == 6][:14]:
    vs = d["verts"]
    info = " ".join(f"({v[0]:.0f},{v[1]:.0f} uv={v[4]},{v[5]})" for v in vs)
    print(f"  tbp={d['tbp']} {1<<d['tw']}x{1<<d['th']} {info}")
