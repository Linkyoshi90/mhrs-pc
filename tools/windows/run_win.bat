@echo off
cd /d D:\docs\GitHub\mhrs-pc
set PS2X_GS_BACKEND=vulkan
set PS2X_VK_RASTER=1
set PS2X_VK_PRESENT=1
set MHRS_HUD=1
D:\docs\GitHub\mhrs-pc\build\win\PS2Recomp\out\win\ps2xRuntime\ps2EntryRunner.exe extracted\MOH3RDVD.ELF "ISO\Medal of Honor - Rising Sun.iso" > build\win_run.log 2>&1
