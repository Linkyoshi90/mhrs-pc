@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >NUL
set CMAKE="C:\Program Files\Microsoft Visual Studio\18\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
cd /d D:\docs\GitHub\mhrs-pc\build\win\PS2Recomp
%CMAKE% --build out/win --target ps2EntryRunner -j 12
