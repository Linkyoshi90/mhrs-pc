@echo off
rem Runs the mingw build with the GPU renderer and records the VU1 microprograms the game uploads into
rem build\vu1\dumps, so scenes that run slowly can be compiled into fast code afterwards: tools\frame_rate.md.
rem usage: play_mingw.bat [folder of ps2EntryRunner.exe, default build\mingw_play]
cd /d %~dp0..\..
set PS2X_GS_BACKEND=vulkan
set PS2X_VK_RASTER=1
rem Internal resolution: 1 = native 640x448, 2..4 = that many times sharper (2 = 1280x896, 3 = 1920x1344).
rem 2 shows every game frame; at 3 the GPU shows about 30 new frames a second. F2 changes it while playing.
if "%PS2X_VK_SCALE%"=="" set PS2X_VK_SCALE=2
set PS2_VU1_DUMP_DIR=build\vu1\dumps
rem FPS monitor in the top-left corner; F3 hides it.
set MHRS_HUD=1
rem Mouse aim (moves the right stick, captures the cursor; Alt+Tab to leave). controls.ini mouse_look overrides it.
set PS2X_MOUSE_LOOK=8
rem Loading and memory card screens go faster (tools\frame_rate.md). set MHRS_FAST_LOAD=0 for real-time ones.
rem In the game window: F2 rebinds the controls (saved to controls.ini), F5 opens the cheat menu (saved to cheats.ini).
set EXEDIR=%~1
if "%EXEDIR%"=="" set EXEDIR=build\mingw_play
"%EXEDIR%\ps2EntryRunner.exe" extracted\MOH3RDVD.ELF "ISO\Medal of Honor - Rising Sun.iso" > build\play.log 2>&1
