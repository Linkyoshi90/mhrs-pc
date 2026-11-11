"""Detect periodic vertical seam lines in a dumped frame.

Scans rows through the FMV area and reports columns whose brightness
dips sharply vs both neighbours, and the average column profile modulo 32.
"""
import sys
from PIL import Image

path = sys.argv[1] if len(sys.argv) > 1 else 'build/frame_019.png'
im = Image.open(path).convert('RGB')
w, h = im.size
px = im.load()

# brightness per column averaged over the vertical middle band
y0, y1 = int(h * 0.25), int(h * 0.75)
cols = []
for x in range(w):
    s = 0
    for y in range(y0, y1):
        r, g, b = px[x, y]
        s += r + g + b
    cols.append(s / (y1 - y0))

dips = []
for x in range(2, w - 2):
    loc = max(cols[x - 2], cols[x - 1], cols[x + 1], cols[x + 2])
    if loc > 60 and cols[x] < loc * 0.72:
        dips.append(x)
print('file:', path, 'size:', w, 'x', h)
print('dip columns:', dips)

# profile modulo 32 for columns with content
import statistics
buckets = [[] for _ in range(32)]
for x in range(w):
    if cols[x] > 40:
        buckets[x % 32].append(cols[x])
means = [statistics.mean(b) if b else 0 for b in buckets]
peak = max(means) if max(means) else 1
print('mod-32 column profile (normalized):')
print(' '.join(f'{m / peak:4.2f}' for m in means))
