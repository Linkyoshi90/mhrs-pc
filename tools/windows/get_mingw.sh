#!/bin/bash
# Fetch the mingw-w64 cross GCC from the distro's apt repo without root: download the .debs and unpack them
# into ~/opt/mingw-w64 (nothing is installed system-wide). Debian/Ubuntu hosts.
set -e
dest=${1:-$HOME/opt/mingw-w64}
dl=$(mktemp -d)
trap 'rm -rf "$dl"' EXIT
cd "$dl"
pkgs=$(apt-cache depends --recurse --no-recommends --no-suggests --no-conflicts --no-breaks --no-replaces \
        --no-enhances g++-mingw-w64-x86-64-posix | grep -E '^[a-z0-9]' | grep mingw | sort -u)
apt-get download $pkgs
mkdir -p "$dest"
for f in *.deb; do dpkg -x "$f" "$dest"; done
"$dest/usr/bin/x86_64-w64-mingw32-g++-posix" --version | head -1
