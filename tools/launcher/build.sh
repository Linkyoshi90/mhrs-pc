#!/bin/bash
# Launcher back end: everything between "extracted/ exists" and "a game binary sits in dist/".
# Runs on Linux, or inside WSL when the launcher runs on Windows (launcher.py calls it either way).
# usage: build.sh check <linux|windows>     list missing build tools (exit 1 if a required one is missing)
#        build.sh build <linux|windows>     dist/MOHRS-x86_64.AppImage  or  dist/windows/ps2EntryRunner.exe
# Every step is skipped when its output is already there, so a rerun continues where the last one stopped.
# MHRS_WORK: PS2Recomp checkout + build trees (default ~/.cache/mhrs-pc); MHRS_JOBS: compile jobs (default 4,
# the generated files need a few GB each).
set -euo pipefail
cd "$(dirname "$0")/../.."
cmd=${1:?check|build}; target=${2:-linux}
WORK=${MHRS_WORK:-$HOME/.cache/mhrs-pc}
TREE=$WORK/PS2Recomp
JOBS=${MHRS_JOBS:-4}
PS2RECOMP_REV=e563698
MINGW=$HOME/opt/mingw-w64
export PATH="$HOME/bin:$HOME/.local/bin:$PATH" # non-login shells (wsl bash script) skip ~/.profile

check() {
    local missing=()
    for t in git cmake ninja g++ make rsync python3 curl mips-linux-gnu-as mips-linux-gnu-objcopy; do
        command -v "$t" >/dev/null || missing+=("$t")
    done
    python3 -c 'import venv, ensurepip' 2>/dev/null || missing+=(python3-venv)
    if [ "$target" = windows ]; then
        [ -x "$MINGW/usr/bin/x86_64-w64-mingw32-g++-posix" ] || command -v apt-get >/dev/null || missing+=("apt-get (to fetch mingw-w64)")
        [ -f "${VULKAN_DLL:-/mnt/c/Windows/System32/vulkan-1.dll}" ] || missing+=("vulkan-1.dll (install a GPU driver)")
    fi
    command -v glslangValidator >/dev/null || echo "note: no glslangValidator (glslang-tools): the GPU renderer would be built as CPU passthrough"
    if [ ${#missing[@]} -gt 0 ]; then
        echo "missing: ${missing[*]}"
        echo "Debian/Ubuntu: sudo apt install build-essential cmake ninja-build git rsync curl python3-venv binutils-mips-linux-gnu glslang-tools \\"
        echo "    libavcodec-dev libavformat-dev libavutil-dev libswscale-dev libswresample-dev libvulkan-dev"
        return 1
    fi
    echo "build tools: ok"
}

step() { echo; echo "=== $*"; }

build() {
    check
    [ -f extracted/MOHRS/MOH3RDVD.ELF ] || { echo "extracted/MOHRS/MOH3RDVD.ELF missing: load the ISO first"; exit 1; }

    if [ ! -f asm/main/000000.s ]; then
        step "Disassembling the game (splat)"
        [ -x .venv/bin/python ] || python3 -m venv .venv
        .venv/bin/python -c 'import splat' 2>/dev/null || .venv/bin/python -m pip install 'splat64[mips]==0.50.1'
        make split
    fi

    # Patched PS2Recomp; redone from scratch when tools/patches changes.
    local want; want=$(cat tools/patches/series tools/patches/*.patch | sha1sum | cut -d' ' -f1)
    if [ "$(cat "$TREE/.mhrs_patches" 2>/dev/null)" != "$want" ]; then
        step "Preparing PS2Recomp $PS2RECOMP_REV + tools/patches"
        mkdir -p "$WORK"
        [ -d "$TREE/.git" ] || git clone https://github.com/ran-j/PS2Recomp.git "$TREE"
        git -C "$TREE" checkout -qf "$PS2RECOMP_REV"
        git -C "$TREE" clean -fdq -e out -e .mhrs_patches
        while read -r p; do
            case "$p" in ''|\#*) continue ;; esac
            git -C "$TREE" apply "$PWD/tools/patches/$p"
        done < tools/patches/series
        echo "$want" > "$TREE/.mhrs_patches"
    fi

    step "Building the recompiler"
    cmake -S "$TREE" -B "$TREE/out/linux" -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo \
        "-DCMAKE_CXX_FLAGS_RELWITHDEBINFO=-O2 -DNDEBUG" "-DCMAKE_C_FLAGS_RELWITHDEBINFO=-O2 -DNDEBUG"
    cmake --build "$TREE/out/linux" --target ps2_recomp -j"$JOBS"

    if [ ! build/recomp/ps2_recompiled_functions.h -nt recomp/moh3rdvd.toml ]; then
        step "Recompiling the game code to C++"
        make recomp PS2RECOMP="$TREE"
    fi

    # ponytail: lean VU1 code is generated once; after recording new programs (build/vu1/dumps) run
    # `rm build/vu1/src/vu1_lean_*.cpp` and build again. No dumps (fresh setup): VU1 stays interpreted, slower.
    if [ -n "$(ls build/vu1/dumps 2>/dev/null | head -1)" ] && ! ls build/vu1/src/vu1_lean_*.cpp >/dev/null 2>&1; then
        step "Compiling recorded VU1 programs"
        make vu1 PS2RECOMP="$TREE"
    fi

    step "Copying generated sources into the runtime"
    make -o recomp -o vu1 runner-src PS2RECOMP="$TREE"

    if [ "$target" = windows ]; then
        if [ ! -x "$MINGW/usr/bin/x86_64-w64-mingw32-g++-posix" ]; then
            step "Fetching mingw-w64"
            bash tools/windows/get_mingw.sh "$MINGW"
        fi
        step "Building ps2EntryRunner.exe (takes a long time the first time)"
        bash tools/windows/cross_build.sh "$TREE" "$JOBS"
        bash tools/windows/pack_mingw.sh "$TREE" dist/windows
        echo "built dist/windows/ps2EntryRunner.exe"
    else
        step "Building ps2EntryRunner (takes a long time the first time)"
        cmake --build "$TREE/out/linux" --target ps2EntryRunner -j"$JOBS"
        if ! command -v appimagetool >/dev/null && [ -z "${APPIMAGETOOL:-}" ]; then
            export APPIMAGETOOL=$WORK/appimagetool-x86_64.AppImage
            [ -x "$APPIMAGETOOL" ] || { curl -fL -o "$APPIMAGETOOL" \
                https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
                chmod +x "$APPIMAGETOOL"; }
        fi
        # appimagetool is an AppImage itself: run it without FUSE
        APPIMAGE_EXTRACT_AND_RUN=1 bash tools/linux/make_appimage.sh "$TREE/out/linux/ps2xRuntime/ps2EntryRunner" dist
    fi
}

case "$cmd" in
    check) check ;;
    build) build ;;
    *) echo "usage: $0 check|build <linux|windows>"; exit 2 ;;
esac
