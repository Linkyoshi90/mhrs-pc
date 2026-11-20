# ppm2png.py <in.ppm> <out.png> [x0 y0 x1 y1]: binary PPM (P6, maxval 255) to PNG with the standard library only,
# optionally cropped. Used to look at build/frame_NNN.ppm and build/hires_NNN.ppm dumps.
import struct, sys, zlib

def read_ppm(path):
    data = open(path, "rb").read()
    fields, pos = [], 0
    while len(fields) < 4:
        while data[pos:pos + 1].isspace():
            pos += 1
        end = pos
        while not data[end:end + 1].isspace():
            end += 1
        fields.append(data[pos:end])
        pos = end
    w, h = int(fields[1]), int(fields[2])
    return w, h, data[pos + 1:pos + 1 + w * h * 3]

def write_png(path, w, h, rows):
    raw = b"".join(b"\0" + r for r in rows)
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    open(path, "wb").write(png + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))

w, h, rgb = read_ppm(sys.argv[1])
x0, y0, x1, y1 = (int(v) for v in sys.argv[3:7]) if len(sys.argv) >= 7 else (0, 0, w, h)
rows = [rgb[(y * w + x0) * 3:(y * w + x1) * 3] for y in range(y0, y1)]
write_png(sys.argv[2], x1 - x0, y1 - y0, rows)
