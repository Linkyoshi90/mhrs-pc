"""Print the masks + masked FNV-1a hash that ps2x::iop::NativeFunction uses to recognise an IRX function.
Masks clear the fields the IRX loader relocates, so the hash matches the code as loaded in IOP RAM.
Usage: python tools/irx_native_sig.py extracted/MOHRS/IOP/SNDDRV.IRX 0x5824 0x5a0c
"""
import struct
import sys

path, start, end = sys.argv[1], int(sys.argv[2], 0), int(sys.argv[3], 0)
data = open(path, "rb").read()
assert data[:4] == b"\x7fELF" and data[4] == 1 and data[5] == 1, "expected a 32-bit little-endian ELF"
shoff, = struct.unpack_from("<I", data, 0x20)
shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 0x2E)
sections = [struct.unpack_from("<10I", data, shoff + i * shentsize) for i in range(shnum)]
strtab = sections[shstrndx][4]
name = lambda s: data[strtab + s[0]:data.index(b"\0", strtab + s[0])].decode()
text_index = next(i for i, s in enumerate(sections) if name(s) == ".text")
text = sections[text_index]

R_MIPS_26, R_MIPS_HI16, R_MIPS_LO16 = 4, 5, 6
field = {R_MIPS_26: 0xFC000000, R_MIPS_HI16: 0xFFFF0000, R_MIPS_LO16: 0xFFFF0000}
masks = {}
for s in sections:
    if s[1] == 9 and s[7] == text_index:  # SHT_REL targeting .text
        for off in range(s[4], s[4] + s[5], 8):
            r_offset, r_info = struct.unpack_from("<II", data, off)
            if start <= r_offset < end:
                masks[r_offset] = field.get(r_info & 0xFF, 0)

words, mask_list = [], []
for addr in range(start, end, 4):
    words.append(struct.unpack_from("<I", data, text[4] + addr)[0])
    mask_list.append(masks.get(addr, 0xFFFFFFFF))

h = 2166136261
for w, m in zip(words, mask_list):
    v = w & m
    for b in range(4):
        h = ((h ^ ((v >> (8 * b)) & 0xFF)) * 16777619) & 0xFFFFFFFF

print(f"// {len(words)} words, {len(masks)} relocated")
print("masks = {")
for i in range(0, len(mask_list), 6):
    print("    " + ", ".join(f"0x{m:08X}u" for m in mask_list[i:i + 6]) + ",")
print("}")
print(f"maskedHash = 0x{h:08X}u")
