// Frame limit: 30 fps in the front end, 60 fps in missions.
//
// The 60 fps limiter (recomp/moh3rdvd.toml, func_0015A080) waits for 1 + (state < 5) vblanks per frame. It used to
// read the level loader's state word D_004BB870 (2..4 while loading, 5 when done); it now reads kLimitState, which
// this wrapper around the frame tick func_00271218 fills before each frame: the loader state in a mission, 0 (so 2
// vblanks, 30 fps) while the front-end level is loaded. The menus step their cursor once per frame, so at 60 fps
// it moved twice as fast.
#include "game_overrides.h"
#include "ps2_runtime.h"

#include <cstdint>
#include <cstring>

namespace mhrs::framelimit
{
    constexpr uint32_t kFrameTick = 0x00271218u;
    constexpr uint32_t kLoaderState = 0x004BB870u; // func_0026DC80's state, 5 = done
    // 1 while the front-end level is loaded: func_002721E0 (level init) stores func_00274D38's result, which tests
    // the level id bytes (1, 0x10).
    constexpr uint32_t kFrontEnd = 0x003CBDF4u;
    // Read by the patched limiter (lui $s0, 0xE / lw $s0, 0($s0)). Unused kernel-area RAM: always zero in RAM dumps
    // from boot, menus and missions (0x75330..0xFFCF0).
    constexpr uint32_t kLimitState = 0x000E0000u;

    PS2Runtime::RecompiledFunction g_frameTick = nullptr;

    void frameTick(uint8_t *rdram, R5900Context *ctx, PS2Runtime *runtime)
    {
        uint32_t state = 0u, frontEnd = 0u;
        std::memcpy(&state, rdram + kLoaderState, sizeof(state));
        std::memcpy(&frontEnd, rdram + kFrontEnd, sizeof(frontEnd));
        if (frontEnd != 0u)
            state = 0u;
        std::memcpy(rdram + kLimitState, &state, sizeof(state));
        g_frameTick(rdram, ctx, runtime);
    }

    void apply(PS2Runtime &runtime)
    {
        g_frameTick = runtime.lookupFunction(kFrameTick);
        if (g_frameTick)
            runtime.registerFunction(kFrameTick, &frameTick);
    }
}

PS2_REGISTER_GAME_OVERRIDE("MOH Rising Sun: 30 fps front end", "MOH3RDVD.ELF", 0x00135488u, 0u, mhrs::framelimit::apply)
