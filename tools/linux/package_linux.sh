#!/bin/bash
# Package a self-contained native Linux build of the MOH Rising Sun PC port.
# Usage: tools/linux/package_linux.sh [build-dir]   (run from the PS2Recomp tree)
set -euo pipefail

BUILD_DIR="${1:-out/linux}"
DIST="dist/mhrs-pc-linux"

cmake --build "$BUILD_DIR" --target ps2EntryRunner -j"$(nproc)"

rm -rf "$DIST"
mkdir -p "$DIST/bin"
cp "$BUILD_DIR/ps2xRuntime/ps2EntryRunner" "$DIST/bin/"

# Runtime deps are intentionally system-provided: Vulkan (ICD coupling) and
# ffmpeg (distro-matched). See Depends: in the README below.
cat > "$DIST/run.sh" <<'EOF'
#!/bin/bash
# Run from a directory containing extracted/MOH3RDVD.ELF and the game ISO.
cd "$(dirname "$(readlink -f "$0")")"
export PS2X_GS_BACKEND="${PS2X_GS_BACKEND:-vulkan}"
export PS2X_VK_RASTER="${PS2X_VK_RASTER:-1}"
export PS2X_VK_PRESENT="${PS2X_VK_PRESENT:-1}"
exec ./bin/ps2EntryRunner "${1:-extracted/MOH3RDVD.ELF}" "${2:-ISO/Medal of Honor - Rising Sun.iso}"
EOF
chmod +x "$DIST/run.sh"

cat > "$DIST/README.md" <<'EOF'
# Medal of Honor: Rising Sun — PC port (native Linux)

## Depends (Debian/Ubuntu package names)
    libavcodec60 libavutil60 libswscale9 libswresample6 libvulkan1
    plus a Vulkan driver for your GPU (e.g. nvidia-driver / mesa-vulkan-drivers)

## Run
    ./run.sh [path/to/MOH3RDVD.ELF] [path/to/game.iso]

The ELF and ISO are not included; dump them from your own disc.

## Environment options
    PS2X_GS_BACKEND=vulkan|cpu   GPU or CPU GS rasterization
    PS2X_VK_RASTER=1             GPU sprite/triangle rasterizer
    PS2X_VK_PRESENT=1            GPU present/deswizzle
    MHRS_WINDOW=1920x1080        initial window size
    MHRS_FILTER=point            crisp pixels (default: bilinear)
    MHRS_HUD=1                   FPS + vsync-rate overlay
EOF

tar -C dist -czf mhrs-pc-linux.tar.gz "$(basename "$DIST")"
echo "packaged: mhrs-pc-linux.tar.gz"
