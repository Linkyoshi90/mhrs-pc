#!/bin/bash
# Build MOHRS-x86_64.AppImage from a native Linux build of ps2EntryRunner.
# Usage: tools/linux/make_appimage.sh <path/to/ps2EntryRunner> [out-dir]
# Needs appimagetool on PATH (or APPIMAGETOOL=/path); without it only the AppDir is produced.
# The AppImage bundles ffmpeg and the other user-space libraries the runner links, but NOT glibc,
# the Vulkan loader, or the X11/DRM/VA graphics stack: those must come from the target system, so
# the target needs a glibc at least as new as the build machine's (see `ldd --version`).
#
# Run it from the folder that holds the game files:
#   ./MOHRS-x86_64.AppImage [MOH3RDVD.ELF] [disc.iso]
# defaults: extracted/MOH3RDVD.ELF and "ISO/Medal of Honor - Rising Sun.iso", memory cards in mc0/ mc1/.
set -euo pipefail

RUNNER=$(readlink -f "$1")
OUT=$(readlink -f "${2:-dist}")
HERE=$(cd "$(dirname "$0")" && pwd)
APPDIR="$OUT/MOHRS.AppDir"

rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/lib"
cp "$RUNNER" "$APPDIR/usr/bin/ps2EntryRunner"
strip --strip-debug "$APPDIR/usr/bin/ps2EntryRunner" 2>/dev/null || true

# System-coupled libraries stay on the host: glibc, the Vulkan loader (matches the GPU driver) and the
# window-system / GPU stack.
SKIP='^(linux-vdso|ld-linux|libc\.|libm\.|libmvec|libpthread|libdl\.|librt\.|libresolv|libvulkan|libX|libxcb|libdrm|libGL|libEGL|libgbm|libva|libvdpau|libOpenCL|libwayland|libasound|libpulse|libfontconfig|libfreetype|libexpat|libz\.)'
ldd "$RUNNER" | awk '/=> \//{print $1, $3}' | while read -r name path; do
    [[ "$name" =~ $SKIP ]] && continue
    cp -L "$path" "$APPDIR/usr/lib/"
done

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/bash
HERE=$(dirname "$(readlink -f "$0")")
export LD_LIBRARY_PATH="$HERE/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
# Game files are looked up relative to where the AppImage was started (or MHRS_DATA).
cd "${MHRS_DATA:-${OWD:-$PWD}}"
export PS2X_GS_BACKEND="${PS2X_GS_BACKEND:-vulkan}"
export PS2X_VK_RASTER="${PS2X_VK_RASTER:-1}"
# Record VU1 programs that have no compiled version yet (see tools/frame_rate.md) when the folder exists.
[ -d build/vu1/dumps ] && export PS2_VU1_DUMP_DIR="${PS2_VU1_DUMP_DIR:-build/vu1/dumps}"
exec "$HERE/usr/bin/ps2EntryRunner" "${1:-extracted/MOH3RDVD.ELF}" "${2:-ISO/Medal of Honor - Rising Sun.iso}"
EOF
chmod +x "$APPDIR/AppRun"

cat > "$APPDIR/mohrs.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=MOH Rising Sun (recomp)
Exec=AppRun
Icon=mohrs
Categories=Game;
Terminal=true
EOF
cp "$HERE/mohrs.png" "$APPDIR/mohrs.png"

TOOL=${APPIMAGETOOL:-$(command -v appimagetool || true)}
if [ -z "$TOOL" ]; then
    echo "AppDir ready at $APPDIR (no appimagetool: run it from there with ./AppRun)"
    exit 0
fi
ARCH=x86_64 "$TOOL" --no-appstream "$APPDIR" "$OUT/MOHRS-x86_64.AppImage"
echo "built $OUT/MOHRS-x86_64.AppImage"
