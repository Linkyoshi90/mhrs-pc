# Native Linux build

The whole project is developed on Linux (WSL); a native desktop Linux build is
the same flow. Only distro-provided deps differ.

## Prereqs (Debian/Ubuntu)

```sh
sudo apt install build-essential cmake ninja-build git \
    libavcodec-dev libavformat-dev libavutil-dev libswscale-dev libswresample-dev \
    libvulkan-dev glslang-tools
```

Plus a Vulkan driver (nvidia-driver / mesa-vulkan-drivers). glslang-tools
provides `glslangValidator` for the GS compute shaders; without it the Vulkan
backend builds as CPU passthrough.

## Build

```sh
git clone https://github.com/ran-j/PS2Recomp.git
cd PS2Recomp && git checkout e563698
while read -r p; do case "$p" in ''|\#*) continue;; esac; git apply "<mhrs-pc>/tools/patches/$p"; done < "<mhrs-pc>/tools/patches/series"
# generate the runner sources with the recompiler (see the main README / Makefile
# in the mhrs-pc repo), then:
cmake -S . -B out/linux -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build out/linux --target ps2EntryRunner -j"$(nproc)"
```

## Package

```sh
bash <mhrs-pc>/tools/linux/package_linux.sh out/linux
# produces dist/mhrs-pc-linux/ and mhrs-pc-linux.tar.gz
```

The package keeps Vulkan + ffmpeg as system dependencies on purpose: the Vulkan
loader must match the installed GPU driver, and distro ffmpeg avoids bundling a
dozen transitive codec libs.
