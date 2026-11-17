# CMake toolchain: cross-compile the runner for Windows from Linux/WSL with mingw-w64 GCC (no Visual Studio).
# MINGW_ROOT: the toolchain's usr/ dir (tools/windows/get_mingw.sh unpacks the distro packages to ~/opt/mingw-w64/usr).
set(CMAKE_SYSTEM_NAME Windows)
set(CMAKE_SYSTEM_PROCESSOR x86_64)

if(NOT MINGW_ROOT)
    set(MINGW_ROOT "$ENV{HOME}/opt/mingw-w64/usr")
endif()
set(MINGW_ROOT "${MINGW_ROOT}" CACHE PATH "mingw-w64 toolchain usr/ directory")
set(_triple x86_64-w64-mingw32)

set(CMAKE_C_COMPILER "${MINGW_ROOT}/bin/${_triple}-gcc-posix")
set(CMAKE_CXX_COMPILER "${MINGW_ROOT}/bin/${_triple}-g++-posix")
set(CMAKE_RC_COMPILER "${MINGW_ROOT}/bin/${_triple}-windres")
set(CMAKE_AR "${MINGW_ROOT}/bin/${_triple}-gcc-ar-posix" CACHE FILEPATH "")
set(CMAKE_RANLIB "${MINGW_ROOT}/bin/${_triple}-gcc-ranlib-posix" CACHE FILEPATH "")

set(CMAKE_FIND_ROOT_PATH "${MINGW_ROOT}/${_triple}")
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER) # host tools (glslangValidator, git)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)

# Unity-built game files exceed COFF's 32k section limit; ship without libgcc/libstdc++/winpthread DLLs.
set(CMAKE_C_FLAGS_INIT "-Wa,-mbig-obj")
set(CMAKE_CXX_FLAGS_INIT "-Wa,-mbig-obj")
set(CMAKE_EXE_LINKER_FLAGS_INIT "-static")
