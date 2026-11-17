#!/bin/bash
# Cross-build ps2EntryRunner.exe for Windows from Linux/WSL (mingw-w64 GCC, no Visual Studio).
# usage: cross_build.sh <PS2Recomp tree with tools/patches/series applied + runner sources> [jobs]
# Needs: tools/windows/get_mingw.sh run once, Vulkan-Headers checkout (VULKAN_HEADERS), a vulkan-1.dll to link
# against (VULKAN_DLL; the GPU driver's copy, only read at link time), cmake, ninja, glslangValidator.
set -e
here=$(cd "$(dirname "$0")" && pwd)
tree=$(cd "${1:?PS2Recomp tree}" && pwd)
jobs=${2:-6}
VULKAN_HEADERS=${VULKAN_HEADERS:-$HOME/opt/Vulkan-Headers}
VULKAN_DLL=${VULKAN_DLL:-/mnt/c/Windows/System32/vulkan-1.dll}
[ -d "$VULKAN_HEADERS" ] || git clone --depth 1 https://github.com/KhronosGroup/Vulkan-Headers.git "$VULKAN_HEADERS"

cd "$tree"
cmake -S . -B out/mingw -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_TOOLCHAIN_FILE="$here/mingw-w64.cmake" \
    -DPS2X_BUILD_RECOMP=OFF -DPS2X_BUILD_ANALYZER=OFF -DPS2X_BUILD_TEST=OFF -DPS2X_BUILD_STUDIO=OFF \
    -DVulkan_INCLUDE_DIR="$VULKAN_HEADERS/include" -DVulkan_LIBRARY="$VULKAN_DLL"
# Generated VU1 files need ~4.5 GB per compiler: build them two at a time first.
vu1=$(ninja -C out/mingw -t targets all | grep -oE '^[^:]*vu1_(lean|blocks)_[^:]*\.obj' || true)
[ -n "$vu1" ] && ninja -C out/mingw -j2 $vu1
ninja -C out/mingw -j"$jobs" ps2EntryRunner
