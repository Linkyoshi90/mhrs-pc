// Frame limit: 30 fps in the front end, the graphics menu's limit (30 to 144 fps) in missions.
//
// The limiter (recomp/moh3rdvd.toml, func_0015A080) waits for 1 + (state < 5) vblanks per frame. It used to
// read the level loader's state word D_004BB870 (2..4 while loading, 5 when done); it now reads kLimitState, which
// this wrapper around the frame tick func_00271218 fills before each frame: the loader state in a mission, 0 (so 2
// vblanks, 30 fps) while the front-end level is loaded. The menus step their cursor once per frame, so at 60 fps
// it moved twice as fast.
//
// Above 60 fps the vblank itself runs at the limit: the game flips only on a vblank (func_002CD3E0 waits for one,
// or its vblank handler func_002D1340 flips), so waiting for fewer than one per frame cannot show more frames. The
// frame tick steps the game by D_00359DDC per vblank (1.0 at 60 Hz; the PAL setup writes 1.2 for 50 Hz), so that
// step shrinks by the same factor and gameplay keeps its speed. Only in missions after loading: loading screens and
// the front end keep 60 Hz vblanks.
#include "game_overrides.h"
#include "ps2_runtime.h"
#include "runtime/ee_scheduler.h"
#include "runtime/ps2_menus.h"

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
    // Float: the frame tick stores it times the vblanks the limiter counted as the frame's time step (D_0035ED20).
    // It loads it before the limiter runs, so it must be set before the call.
    constexpr uint32_t kStepPerVBlank = 0x00359DDCu;

    PS2Runtime::RecompiledFunction g_frameTick = nullptr;
    float g_stepPerVBlank = 0.0f; // the game's own value, read at the first frame

    void frameTick(uint8_t *rdram, R5900Context *ctx, PS2Runtime *runtime)
    {
        uint32_t state = 0u, frontEnd = 0u;
        std::memcpy(&state, rdram + kLoaderState, sizeof(state));
        std::memcpy(&frontEnd, rdram + kFrontEnd, sizeof(frontEnd));
        const int fps = ps2GraphicsFrameRate(); // picked in the graphics menu (F4)
        if (frontEnd != 0u || fps <= 30)
            state = 0u;
        std::memcpy(rdram + kLimitState, &state, sizeof(state));

        // The vblanks this frame counts mostly come at the rate set here (a change applies from the next vblank, so
        // the frame that switches is off by part of one vblank).
        const int hz = runtime->eeScheduler().setVBlankHz(state >= 5u && fps > 60 ? fps : 60);
        if (g_stepPerVBlank == 0.0f)
            std::memcpy(&g_stepPerVBlank, rdram + kStepPerVBlank, sizeof(g_stepPerVBlank));
        const float step = g_stepPerVBlank * (static_cast<float>(EeScheduler::vblankPeriodUs(hz)) /
                                              static_cast<float>(EeScheduler::vblankPeriodUs(60)));
        std::memcpy(rdram + kStepPerVBlank, &step, sizeof(step));
        g_frameTick(rdram, ctx, runtime);
    }

    void apply(PS2Runtime &runtime)
    {
        g_frameTick = runtime.lookupFunction(kFrameTick);
        if (g_frameTick)
            runtime.registerFunction(kFrameTick, &frameTick);
    }
}

PS2_REGISTER_GAME_OVERRIDE("MOH Rising Sun: frame rate limit", "MOH3RDVD.ELF", 0x00135488u, 0u, mhrs::framelimit::apply)
