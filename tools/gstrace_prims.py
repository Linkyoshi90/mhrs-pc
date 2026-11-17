"""Parse a gsrec trace: list 'S' (GSPrimitiveBatch) records with geometry detail.

Layout (verified via offsetof):
  record: tag byte + payload
  'S' payload: 312B GSPrimitiveBatch
    vertices @0   : 3 x GSVertex (40B): x f32@0, y f32@4, q f32@20, s f32@24, t f32@28, u u16@32, v u16@34
    vertexCount   @120 (u8)
    state         @128: prim @+112 (type u8@0, tme u8@2, fst u8@6)
                        texW @+44? -> use 172-128=44 (u16), linearFilter @176-128=48 (u8)
    state.context @128+? : frame fbp u32 @0, fbw u8 @4, psm u8 @8
                           tex0 @24: tbp0 u32, tbw/psm/tw/th u8 @4..7
"""
import struct, sys

path = sys.argv[1] if len(sys.argv) > 1 else 'build/trace_strip.bin'
data = open(path, 'rb').read()

magic, ver, batchsz, vram = struct.unpack_from('<IIII', data, 0)
print(f'magic={magic:#x} ver={ver} batchSize={batchsz} vram={vram}')
off = 16 + vram + 1024 + 8 + 36 + 32  # header + VRAM + CLUT + clutCbp + GSTransferCommand + snapshot

n = 0
while off < len(data):
    tag = data[off:off+1]
    off += 1
    if tag == b'B':
        (sbp, sbw, spsm, dbp, dbw, dpsm, dsax, dsay, rrw, rrh, direction) = struct.unpack_from('<IBBxxIBBxxHHxxHHxxI', data, off)
        print(f'B dbp={dbp} dbw={dbw} dpsm={dpsm} rrw={rrw} rrh={rrh} dir={direction}')
        off += 36
    elif tag == b'U':
        (size,) = struct.unpack_from('<I', data, off)
        print(f'U size={size}')
        off += 4 + size
    elif tag == b'S':
        vc = data[off + 120]
        st = off + 128
        fbp, = struct.unpack_from('<I', data, st + 0)
        fbw = data[st + 4]
        fpsm = data[st + 8]
        tbp0, = struct.unpack_from('<I', data, st + 24)
        tbw, tpsm, tw, th = data[st+28], data[st+29], data[st+30], data[st+31]
        prim = st + 112
        ptype, tme, fst = data[prim], data[prim+2], data[prim+6]
        texW, = struct.unpack_from('<H', data, st + 44)
        lin = data[st + 48]
        vs = []
        for i in range(vc):
            x, y = struct.unpack_from('<ff', data, off + i*40)
            q, s, t = struct.unpack_from('<fff', data, off + i*40 + 20)
            u, v = struct.unpack_from('<HH', data, off + i*40 + 32)
            vs.append(f'({x:.1f},{y:.1f} s={s:.4f} t={t:.4f} q={q:.2f} u={u} v={v})')
        print(f'S prim={ptype} vc={vc} tme={tme} fst={fst} lin={lin} fbp={fbp} fbw={fbw} fpsm={fpsm} tbp={tbp0} tbw={tbw} tpsm={tpsm} tw={tw} th={th} texW={texW}')
        for v in vs:
            print('   ', v)
        off += batchsz
        n += 1
        if n > 60:
            print('... (truncated)')
            break
    elif tag == b'C':
        off += 24
    elif tag == b'K':
        off += 120
    elif tag == b'W':
        off += 24
    elif tag in (b'R', b'F', b'P'):
        if tag == b'P':
            print('--- present ---')
    else:
        print('unknown tag', tag, 'at', off - 1)
        break
