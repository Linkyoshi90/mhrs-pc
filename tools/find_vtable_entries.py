#!/usr/bin/env python3
"""List code addresses that GCC 2.x vtables point at but splat did not recognise as functions.

A vtable entry is a (delta/index word, function pointer) pair, so a raw `.word` that points into
.text and follows a 0x00000000 word inside a data label (not a jump table) is a hidden entry
point. Prints `codeptr_XXXXXXXX = 0x...; // type:func` lines for config/symbol_addrs.txt.

usage: find_vtable_entries.py asm/data/main/*.s [--text-start 0x135480 --text-end 0x359B30]
"""
import argparse
import re

WORD = re.compile(r"/\* \w+ ([0-9A-F]{8}) [0-9A-F]{8} \*/ \.word (0x[0-9A-Fa-f]{8}|\w+)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--text-start", type=lambda v: int(v, 0), default=0x135480)
    ap.add_argument("--text-end", type=lambda v: int(v, 0), default=0x359B30)
    args = ap.parse_args()

    found = {}
    for path in args.files:
        label, prev = None, None
        for line in open(path):
            line = line.strip()
            if line.startswith("dlabel "):
                label, prev = line.split()[1], None
                continue
            m = WORD.search(line)
            if not m:
                prev = None
                continue
            vram, value = int(m.group(1), 16), m.group(2)
            raw = int(value, 16) if value.startswith("0x") else None
            in_jump_table = label is not None and label.startswith("jtbl_")
            if (raw is not None and not in_jump_table and prev == 0 and raw % 4 == 0
                    and args.text_start <= raw < args.text_end):
                found.setdefault(raw, vram)
            prev = raw if raw is not None else -1
    for target in sorted(found):
        print(f"codeptr_{target:08X} = 0x{target:08X}; // type:func  (vtable entry at 0x{found[target]:08X})")


if __name__ == "__main__":
    main()
