# Native Windows build (MSVC)

Builds `ps2EntryRunner.exe` natively on Windows with the Vulkan GS backend
(runs on the real GPU, e.g. RTX 4070 SUPER — validated working).

## Prerequisites

- Visual Studio 2026 (Community is fine) with the C++ workload — uses the
  bundled CMake + Ninja.
- Git on PATH (CMake FetchContent clones raylib/imgui/rlImGui).
- The full PS2Recomp working tree **with all `tools/patches` applied and the
  generated runner sources** (`ps2xRuntime/src/runner/`, produced by the
  recompiler flow in WSL — the runner sources are not in git).
- Network access on first configure (raylib, imgui, ffmpeg MSVC prebuilt).

## One-time setup

1. Vulkan headers (no SDK needed — the driver already ships `vulkan-1.dll`):

   ```sh
   git clone --depth 1 https://github.com/KhronosGroup/Vulkan-Headers.git
   ```

2. Import library for the system Vulkan loader:

   ```bat
   dumpbin /exports C:\Windows\System32\vulkan-1.dll > exports.txt
   rem turn the names into a .def (LIBRARY vulkan-1 / EXPORTS / one per line)
   lib /def:vulkan-1.def /out:vulkan-1.lib /machine:x64
   ```

3. Prebuilt shader headers: generated once by glslangValidator (e.g. in WSL,
   they land in `out/linux/ps2xRuntime/shaders/*.h` after any Linux build).
   Copy `present_deswizzle.h`, `raster_sprite.h`, `raster_triangle.h` into a
   `shaders-prebuilt/` dir. Re-copy them whenever the `.comp`/`.glsl` sources
   change.

## Configure & build

See `tools/windows/configure_win.bat` / `build_win.bat` / `run_win.bat`
(adjust paths). Key CMake flags:

```
-G Ninja -DCMAKE_BUILD_TYPE=Release
-DPS2X_BUILD_RECOMP=OFF -DPS2X_BUILD_ANALYZER=OFF -DPS2X_BUILD_TEST=OFF -DPS2X_BUILD_STUDIO=OFF
-DPS2X_RUNNER_UNITY_BUILD_BATCH_SIZE=4
-DVulkan_INCLUDE_DIR=<Vulkan-Headers>/include
-DVulkan_LIBRARY=<path>/vulkan-1.lib
-DPS2X_VK_PREBUILT_SHADERS=<path>/shaders-prebuilt
cmake --build out/win --target ps2EntryRunner -j 12
```

Notes:

- `PS2X_RUNNER_UNITY_BUILD_BATCH_SIZE=4` keeps every Ninja edge short enough
  for incremental rebuilds; the default 32 produces multi-minute unity edges.
- MSVC builds compile `register_functions.cpp` with `/Od` (a single ~230k-line
  static initializer that the optimizer never finishes) and use `/fp:precise`
  everywhere — the GS rasterizer and EE float semantics require strict IEEE.
- Runtime env vars: `PS2X_GS_BACKEND=vulkan PS2X_VK_RASTER=1 PS2X_VK_PRESENT=1`
  (GPU raster + present), `MHRS_HUD=1`, `MHRS_WINDOW=1920x1080`,
  `MHRS_FILTER=point`, verify modes `PS2X_VK_RASTER_VERIFY=1` /
  `PS2X_VK_PRESENT_VERIFY=1`.
