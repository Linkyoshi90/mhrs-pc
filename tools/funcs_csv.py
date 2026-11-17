"""Turn splat's function boundaries into a PS2Recomp function map (Ghidra CSV format).
Usage: python tools/funcs_csv.py asm/main/000000.s build/analyzer.toml build/functions.csv
Names found as "name@0xADDR" in the analyzer TOML (SDK matches) replace splat's func_XXXXXXXX.
"""
import re
import sys

asm_path, toml_path, out_path = sys.argv[1:4]

sdk_names = {int(a, 16): n for n, a in re.findall(r'"([A-Za-z_]\w*)@0x([0-9A-Fa-f]+)"', open(toml_path).read())}

nonmatching = re.compile(r"^nonmatching (\S+), 0x([0-9A-Fa-f]+)")
insn = re.compile(r"^\s+/\* [0-9A-F]+ ([0-9A-F]{8}) ")
funcs, pending = [], None
for line in open(asm_path):
    if m := nonmatching.match(line):
        pending = (m.group(1), int(m.group(2), 16))
    elif pending and (m := insn.match(line)):
        name, size = pending
        start = int(m.group(1), 16)
        funcs.append((sdk_names.get(start, name), start, size))
        pending = None

# Self-check: sorted, non-overlapping, sane sizes.
for (_, a, sa), (n, b, _) in zip(funcs, funcs[1:]):
    assert a + sa <= b, f"overlap before {n} at 0x{b:08X}"
assert all(s > 0 and s % 4 == 0 for _, _, s in funcs)

with open(out_path, "w", newline="\n") as f:
    f.write("Name,Start,End,Size\n")
    for name, start, size in funcs:
        f.write(f"{name},0x{start:08X},0x{start + size:08X},{size}\n")

named = sum(1 for n, s, _ in funcs if sdk_names.get(s) == n)
print(f"{len(funcs)} functions, {named} with SDK names, {len(sdk_names) - named} SDK names unmatched")
