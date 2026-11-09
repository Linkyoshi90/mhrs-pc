"""Dump PS2 ELF basics: header, segments, sections, symbols, compiler/SDK strings.
Usage: python tools/elfinfo.py extracted/SLUS_207.53
"""
import re
import struct
import sys

data = open(sys.argv[1], "rb").read()
assert data[:4] == b"\x7fELF" and data[4] == 1 and data[5] == 1, "not a 32-bit little-endian ELF"

(e_type, e_machine, _, e_entry, e_phoff, e_shoff, e_flags, _, e_phentsize, e_phnum,
 e_shentsize, e_shnum, e_shstrndx) = struct.unpack_from("<HHIIIIIHHHHHH", data, 16)
print(f"type={e_type} machine={e_machine} (8=MIPS) entry=0x{e_entry:08X} flags=0x{e_flags:08X}")

print("\nSegments:")
for i in range(e_phnum):
    p_type, off, vaddr, _, filesz, memsz, flags, _ = struct.unpack_from("<8I", data, e_phoff + i * e_phentsize)
    print(f"  type={p_type} off=0x{off:06X} vaddr=0x{vaddr:08X} filesz=0x{filesz:06X} memsz=0x{memsz:06X} flags={flags}")

sections = [struct.unpack_from("<10I", data, e_shoff + i * e_shentsize) for i in range(e_shnum)]
if sections:
    strtab_off = sections[e_shstrndx][4]
    name = lambda n: data[strtab_off + n:data.index(b"\0", strtab_off + n)].decode(errors="replace")
    print("\nSections:")
    for sh in sections:
        sh_name, sh_type, _, addr, off, size = sh[:6]
        print(f"  {name(sh_name):<20} type={sh_type:<10} addr=0x{addr:08X} off=0x{off:06X} size=0x{size:06X}")
    names = {name(sh[0]) for sh in sections}
    for s in (".symtab", ".mdebug", ".debug", ".debug_info"):
        print(f"  has {s}: {s in names}")
    for sh in sections:
        if sh[1] == 2:  # SHT_SYMTAB
            print(f"  symbol count: {sh[5] // 16}")
else:
    print("\nNo section headers (stripped).")

print("\nCompiler / SDK strings:")
pat = re.compile(rb"(GCC: \([^\0]{0,80}|ProDG[^\0]{0,60}|SN Systems[^\0]{0,60}|Metrowerks[^\0]{0,60}"
                 rb"|CodeWarrior[^\0]{0,60}|PsIIlib\w*\s+\d+|Sony Computer Entertainment[^\0]{0,60})")
for s in sorted({m.group(0) for m in pat.finditer(data)}):
    print("  ", s.decode(errors="replace"))
