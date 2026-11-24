#!/bin/bash
# Packs launcher.py into dist/MOHRS-Launcher-x86_64.AppImage (no Python needed to run it).
# The AppImage must stay in the repo folder or its dist/ (it finds tools/launcher/build.sh from there).
# Distro Pythons often lack tkinter, so this uses uv's standalone CPython (ships Tcl/Tk); uv, the Python and
# PyInstaller go into ~/.cache/mhrs-pc/launcher. appimagetool: PATH, APPIMAGETOOL, or downloaded.
set -euo pipefail
cd "$(dirname "$0")/../.."
W=$HOME/.cache/mhrs-pc/launcher
mkdir -p "$W"
UV=$(command -v uv || echo "$W/uv")
if [ ! -x "$UV" ]; then
    curl -fL https://github.com/astral-sh/uv/releases/download/0.9.5/uv-x86_64-unknown-linux-gnu.tar.gz \
        | tar -xz -C "$W" --strip-components=1 uv-x86_64-unknown-linux-gnu/uv
fi
export UV_PYTHON_INSTALL_DIR=$W/python
[ -x "$W/venv/bin/python" ] || "$UV" venv -q --python 3.12 "$W/venv"
"$UV" pip install -q --python "$W/venv/bin/python" pyinstaller
"$W/venv/bin/python" -c 'import tkinter'  # fail here, not in the player's hands
# PyInstaller misses the Tcl/Tk libraries _tkinter links against in uv's Python: add them by hand.
PYLIB=$("$W/venv/bin/python" -c 'import sys; print(sys.base_prefix)')/lib

APPDIR=$W/MOHRS-Launcher.AppDir
rm -rf "$APPDIR"
"$W/venv/bin/python" -m PyInstaller --noconfirm --onedir --name mohrs-launcher \
    --add-binary "$PYLIB/libtcl8.6.so:." --add-binary "$PYLIB/libtk8.6.so:." \
    --distpath "$APPDIR/usr/lib" --workpath "$W/pyi" --specpath "$W/pyi" launcher.py
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/bash
exec "$(dirname "$(readlink -f "$0")")/usr/lib/mohrs-launcher/mohrs-launcher" "$@"
EOF
chmod +x "$APPDIR/AppRun"
cat > "$APPDIR/mohrs-launcher.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=MOH Rising Sun launcher
Exec=AppRun
Icon=mohrs-launcher
Categories=Game;
EOF
cp tools/linux/mohrs.png "$APPDIR/mohrs-launcher.png"

TOOL=${APPIMAGETOOL:-$(command -v appimagetool || echo "$W/appimagetool")}
if [ ! -x "$TOOL" ]; then
    curl -fL -o "$TOOL" https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x "$TOOL"
fi
mkdir -p dist
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" --no-appstream "$APPDIR" dist/MOHRS-Launcher-x86_64.AppImage
echo "built dist/MOHRS-Launcher-x86_64.AppImage"
