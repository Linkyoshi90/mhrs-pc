// Faster loading screens: while the level loader runs, the EE scheduler skips the host time it would only wait out.
//
// Two phases: the level's disc reads with the main thread blocked and no frames (see kNoFlipMs), then the loader
// state machine with the loading screen animating.
// A load (state machine func_0026DC80, state word D_004BB870: 2..4 while loading, 5 when done) is paced by the
// game's own frame and alarm waits, not by the disc or the CPU: the EE idled ~80% of a 7.8 s level load, and halving
// the IOP's speed did not change it. Speeding up guest time instead (the fast-forward key) starves the loader, which
// only runs while the main thread sleeps in the frame limiter. Skipping idle time keeps every guest wait as long in
// guest time and drops only the host time nothing runs in.
#include "game_overrides.h"
#include "ps2_runtime.h"
#include "runtime/ee_scheduler.h"

#include <cstdint>
#include <cstdlib>
#include <cstring>

namespace mhrs::fastload
{
    // D_004BB870: 0 from boot until the first load (the memory card check, EE idle ~85%) and for the moment
    // between a reset and 2; 2..4 while loading; 5 when done.
    constexpr uint32_t kLoaderState = 0x004BB870u;
    // Before the loader starts, the main thread blocks for seconds in the level's disc reads (5.7 s for mission 1,
    // EE idle 89%) and presents nothing. Movies, menus and gameplay flip every 17-40 ms.
    constexpr int64_t kNoFlipMs = 200;

    bool loading(const uint8_t *rdram)
    {
        uint32_t state = 0u;
        std::memcpy(&state, rdram + kLoaderState, sizeof(state));
        return state <= 4u || EeScheduler::hostMsSinceDisplayWrite() >= kNoFlipMs;
    }

    // MHRS_FAST_LOAD=0 keeps real-time loads (sound played during a load, such as narration, runs at its own pace).
    void apply(PS2Runtime &)
    {
        const char *setting = std::getenv("MHRS_FAST_LOAD");
        if (setting && std::strcmp(setting, "0") == 0)
            return;
        EeScheduler::setSkipIdleWhile(&loading);
    }
}

PS2_REGISTER_GAME_OVERRIDE("MOH Rising Sun: skip idle time on loading screens", "MOH3RDVD.ELF", 0x00135488u, 0u, mhrs::fastload::apply)
