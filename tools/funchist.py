# funchist.py <nm.txt> <samples> <thread id> <function name prefix> [bucket]: where inside one function a tsample
# profile's samples of one thread fall (offsets from the function start), to read with objdump next to them.
import bisect, collections, sys

nmf, samf, tid, name = sys.argv[1:5]
bucket = int(sys.argv[5]) if len(sys.argv) > 5 else 16
syms = []
for line in open(nmf, errors="replace"):
    p = line.rstrip("\n").split(" ", 2)
    if len(p) == 3 and p[0] and p[1] in "tTwW":
        syms.append((int(p[0], 16) - 0x140000000, p[2]))
syms.sort()
starts = [a for a, _ in syms]
lines = [l.split() for l in open(samf) if l.strip()]
exe = next(int(p[2], 16) for p in lines if p[0] == "M" and p[1].lower().endswith(".exe"))
start = next(a for a, n in syms if n.startswith(name))
end = starts[bisect.bisect_right(starts, start)]
hist = collections.Counter()
for p in lines:
    if p[0] == "S" and p[1] == tid:
        a = int(p[2], 16) - exe
        if start <= a < end:
            hist[(a - start) // bucket * bucket] += int(p[3])
total = sum(hist.values())
print("function at 0x%x, size 0x%x, %d samples" % (start + 0x140000000, end - start, total))
for off, n in sorted(hist.items(), key=lambda kv: -kv[1])[:16]:
    print("  +0x%04x  %5d  %4.1f%%" % (off, n, 100.0 * n / total))
