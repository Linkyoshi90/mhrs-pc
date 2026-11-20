# leannode.py <lean .cpp> <program> <node>: prints a generated lean VU1 node compactly (pair words with their
# template flags, Q/P commits, kicks, exits), e.g. `leannode.py build/vu1/src/vu1_lean_116.cpp p1129 n7` to see
# which microcode loop a hot profile entry like (anonymous namespace)::p1129::n7 is.
import re, sys

path, program, node = sys.argv[1], sys.argv[2], sys.argv[3]
inside = printing = False
for line in open(path):
    if line.rstrip() == "namespace " + program:
        inside = True
    elif inside and line.startswith("namespace p"):
        break
    if inside and line.startswith("VU1_NO_STACK_PROTECTOR int " + node + "("):
        printing = True
    if printing:
        m = re.search(r"L::pair<(0x[0-9A-F]+)u, (0x[0-9A-F]+)u(.*)>\(vu\)", line)
        if m:
            print("  lower %s upper %s %s" % (m.group(1), m.group(2), m.group(3).strip(", ")))
        elif re.search(r"//\s*0x|L::commit|kickBusy|MUSTTAIL|leave\(", line):
            print(" ", line.strip())
        if line.startswith("}"):
            break
