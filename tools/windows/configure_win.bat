@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >NUL
set CMAKE="C:\Program Files\Microsoft Visual Studio\18\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
cd /d D:\docs\GitHub\mhrs-pc\build\win\PS2Recomp
%CMAKE% -S . -B out/win -G "Ninja" -DCMAKE_BUILD_TYPE=Release -DPS2X_BUILD_RECOMP=OFF -DPS2X_BUILD_ANALYZER=OFF -DPS2X_BUILD_TEST=OFF -DPS2X_BUILD_STUDIO=OFF -DPS2X_RUNNER_UNITY_BUILD_BATCH_SIZE=4 -DVulkan_INCLUDE_DIR=D:/docs/GitHub/mhrs-pc/build/win/Vulkan-Headers/include -DVulkan_LIBRARY=D:/docs/GitHub/mhrs-pc/build/win/vulkan-1.lib -DPS2X_VK_PREBUILT_SHADERS=D:/docs/GitHub/mhrs-pc/build/win/shaders-prebuilt
