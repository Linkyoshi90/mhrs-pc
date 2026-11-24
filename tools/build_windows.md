# Windows build

`ps2EntryRunner.exe` is cross-compiled **from Linux/WSL with mingw-w64 GCC**. No Visual Studio or other
installed SDK is needed: the compiler, raylib/imgui, ffmpeg and the Vulkan headers are all downloaded.
Players need only a GPU driver (it ships `vulkan-1.dll`) and the DLLs packed next to the exe.

Same compiler family as the Linux build, so the generated VU1 code is optimized the same way and keeps
`-frounding-math` (VU float rounding).

## One-time setup (WSL / Debian / Ubuntu)

```sh
bash <mhrs-pc>/tools/windows/get_mingw.sh       # apt-get download + unpack into ~/opt/mingw-w64, no root
```

Also needed: `cmake`, `ninja`, `git`, `glslangValidator` (same as the Linux build).

## Build

Prepare a PS2Recomp tree exactly as for Linux (`tools/build_linux.md`: e563698 + `tools/patches/series` +
the recompiler's output: `ps2xRuntime/src/runner/*` and `ps2xRuntime/include/ps2_recompiled_{functions,stubs}.h`),
then:

```sh
bash <mhrs-pc>/tools/windows/cross_build.sh <PS2Recomp tree> [jobs]
# -> <tree>/out/mingw/ps2xRuntime/ps2EntryRunner.exe
```

The script clones Vulkan-Headers to `~/opt/Vulkan-Headers` if missing and links against the driver's
`vulkan-1.dll` (`VULKAN_DLL`, default `/mnt/c/Windows/System32/vulkan-1.dll`; read at link time only).
The toolchain file is `tools/windows/mingw-w64.cmake` (`-static`: no libstdc++/winpthread DLLs to ship;
`-Wa,-mbig-obj` for the unity-built game files).

## Run

Run from the mhrs-pc repo root (paths are relative), with the ffmpeg DLLs next to the exe:

```bat
set PS2X_GS_BACKEND=vulkan
set PS2X_VK_PRESENT=1
set PS2X_VK_RASTER=1
ps2EntryRunner.exe extracted\MOH3RDVD.ELF "ISO\Medal of Honor - Rising Sun.iso"
```

Env vars: `PS2X_SKIP_MOVIES=60` (end every movie after 60 pictures; Esc/Backspace skips one by hand),
`PS2X_VBLANK_CLOCK=cycles` (old guest-cycle vblank clock: slow-motion gameplay), `PS2X_VK_RASTER=1` (sprites and triangles rasterized on the GPU; without it the Vulkan backend draws on the CPU),
`PS2X_VK_STATS=<n>` (batch/readback counters every n presents), `MHRS_HUD=1` (start with the FPS monitor on),
`MHRS_WINDOW=1920x1080`, `MHRS_FILTER=point`.

Internal resolution (`ps2recomp-gs-internal-resolution`): `PS2X_VK_SCALE=2..4` (with `PS2X_VK_RASTER=1`) draws every
32-bit frame and depth buffer at that many times the native resolution as well, and shows the display at that
size (3 = 1920x1344). It is a copy of GS memory with scale x scale samples per pixel next to the native one, which
stays exactly as before, so everything the game reads back is unchanged; 32-bit textures drawn earlier (the frame
a full-screen pass copies or filters) are sampled from the copy. 16-bit buffers stay native. `play_mingw.bat` sets
2 unless `PS2X_VK_SCALE` is already set; the controls menu (F2, row "Internal resolution", Left/Right) changes it
while the game runs (not saved). With `PS2X_VK_RASTER=1` the display is always copied out on the GPU (formerly
`PS2X_VK_PRESENT=1`), which is also faster than the CPU copy. Costs GPU time only: mission 1's first room runs as fast at 3 as at 1;
the mission-1 intro (heavy overdraw) drops from about 76 to 62 flips/s at 3 (72 at 2). The present runs
behind the GS queue (`ps2recomp-gs-present-pipeline`), so the window never waits for drawing to finish. It shows
every game frame at 2 and about 30 new frames a second at 3.

In the game window: **F2** opens the controls menu (rebind keys, mouse and gamepad, mouse look settings; saved to
`controls.ini`), **F5** the cheat menu (the game's 12 bonus cheats; saved to `cheats.ini`).

FPS monitor (`ps2recomp-fps-monitor`): **F3** shows or hides it; `play_mingw.bat` starts with it on. The large
number is game frames a second (the game writes DISPFB1 once a frame; green at 55+, yellow at 28+, red below).
Below it: the slowest frame in the last half second, the emulated vsync rate (60/s when the game runs at full
speed) and how often the window redraws.

Controls: copy `tools/controls.example.ini` to `controls.ini` in the folder you start from (or set `PS2X_CONTROLS`)
to rebind keys, mouse buttons and gamepad buttons/axes, and to set mouse look, dead zone, sensitivity and invert-Y.
A second player (pad port 2, for split screen) uses the same names with a `p2_` prefix and the second gamepad by
default (`p2_gamepad`; `-1` = no gamepad); in the F2 menu the first row, "Player", switches the rows to player 2.

`tools/windows/pack_mingw.sh <tree> <dest>` copies the exe plus every DLL it imports from the build tree
(ffmpeg and its codec libs); everything else is a Windows system DLL or the driver's `vulkan-1.dll`.

`tools\windows\play_mingw.bat` starts `build\mingw_play` with the GPU renderer and records the VU1 microprograms
the game uploads (`PS2_VU1_DUMP_DIR`), which is how slow scenes get fast code: see `tools/frame_rate.md`.
`PS2X_FAST_FORWARD=1` holds the `fast_forward` input down (default key F: the game runs several times faster
without 3D drawing, to get through in-engine cutscenes).

Frame rate (RTX 4070 SUPER, i9-9900K, Vulkan GPU raster, 2026-11-16; 60 flips/s = the game's 30 fps): mission-1
intro 48 to 56 flips/s, first room of mission 1 51 to 59. Details and the way to 60 fps: `tools/frame_rate.md`.

## MSVC (not supported)

Patch `ps2recomp-windows-msvc-port.patch` and `tools/windows/*.bat` build with Visual Studio. Not the project
route: it needs a VS install, and MSVC cannot fold the lean VU1 programs (gameplay ~12 flips/s vs ~17.8 with
mingw GCC; forcing the inlining needs >14 GB per file).
