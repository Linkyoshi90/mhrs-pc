"""Deswizzle a raw CT32 GS VRAM dump (fbp=140, 640x512) into a PNG."""
import sys
from PIL import Image

BLOCK32 = [
    [0, 1, 4, 5, 16, 17, 20, 21],
    [2, 3, 6, 7, 18, 19, 22, 23],
    [8, 9, 12, 13, 24, 25, 28, 29],
    [10, 11, 14, 15, 26, 27, 30, 31],
]
COL32 = [
    [0, 1, 4, 5, 8, 9, 12, 13],
    [2, 3, 6, 7, 10, 11, 14, 15],
    [16, 17, 20, 21, 24, 25, 28, 29],
    [18, 19, 22, 23, 26, 27, 30, 31],
    [32, 33, 36, 37, 40, 41, 44, 45],
    [34, 35, 38, 39, 42, 43, 46, 47],
    [48, 49, 52, 53, 56, 57, 60, 61],
    [50, 51, 54, 55, 58, 59, 62, 63],
]

src = sys.argv[1] if len(sys.argv) > 1 else 'build/asm_000.bin'
dst = sys.argv[2] if len(sys.argv) > 2 else 'build/asm_000.png'
dbp_word = 140 * 2048  # fbp=140 in words
bw = 10
W, H = 640, 512

data = open(src, 'rb').read()
im = Image.new('RGB', (W, H))
px = im.load()
for y in range(H):
    for x in range(W):
        page = dbp_word // 2048 + (y // 32) * bw + (x // 64)
        block = (dbp_word // 64) % 32 + BLOCK32[(y % 32 // 8) % 4][(x % 64 // 8) % 8]
        pix = page * 2048 + block * 64 + COL32[y % 8][x % 8]
        b = (pix - dbp_word) * 4
        r, g, b2, a = data[b], data[b+1], data[b+2], data[b+3]
        px[x, y] = (r, g, b2)
im.save(dst)
print('wrote', dst)
