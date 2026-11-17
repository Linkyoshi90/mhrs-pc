@echo off
rem Runs the mingw build with the GPU renderer and records the VU1 microprograms the game uploads into
rem build\vu1\dumps, so scenes that run slowly can be compiled into fast code afterwards: tools\frame_rate.md.
rem usage: play_mingw.bat [folder of ps2EntryRunner.exe, default build\mingw_play]
cd /d %~dp0..\..
set PS2X_GS_BACKEND=vulkan
set PS2X_VK_RASTER=1
set PS2_VU1_DUMP_DIR=build\vu1\dumps
rem TEMP-DEBUG(mhrs): sound-chip register trace into build\play.log (~30 MB per hour) to find missing sound effects
set MHRS_SPU2_LOG=1
set EXEDIR=%~1
if "%EXEDIR%"=="" set EXEDIR=build\mingw_play
"%EXEDIR%\ps2EntryRunner.exe" extracted\MOH3RDVD.ELF "ISO\Medal of Honor - Rising Sun.iso" > build\play.log 2>&1
