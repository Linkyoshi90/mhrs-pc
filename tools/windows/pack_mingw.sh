#!/bin/bash
# Copy the cross-built runner plus the DLLs it imports from the build tree (ffmpeg) into <dest>.
# usage: pack_mingw.sh <PS2Recomp tree> <dest dir>
set -e
tree=$(cd "${1:?PS2Recomp tree}" && pwd); dest=${2:?dest dir}
bin=$tree/out/mingw/ps2xRuntime
objdump=${OBJDUMP:-$HOME/opt/mingw-w64/usr/bin/x86_64-w64-mingw32-objdump}
mkdir -p "$dest"
cp "$bin/ps2EntryRunner.exe" "$dest/"
# Imports, then the imports of every DLL we ship (ffmpeg libs import each other).
todo=("$bin/ps2EntryRunner.exe"); declare -A seen
while [ ${#todo[@]} -gt 0 ]; do
  f=${todo[0]}; todo=("${todo[@]:1}")
  for dll in $("$objdump" -p "$f" | awk '/DLL Name:/ {print $3}'); do
    [ -n "${seen[$dll]}" ] && continue; seen[$dll]=1
    src=$(find "$tree/out/mingw" -iname "$dll" -print -quit)
    [ -n "$src" ] || continue # system DLL (kernel32, vulkan-1, ...)
    cp "$src" "$dest/"; todo+=("$src"); echo "  + $dll"
  done
done
