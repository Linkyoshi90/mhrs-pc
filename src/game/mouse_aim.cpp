// Mouse aim: the mouse turns the player's view directly instead of acting as a right stick.
//
// func_001B3F58(player, dt) is the player's per-frame look update: it adds turn rate * dt (rates from the right
// stick, func_001B70B0) to yaw (player +0x274, radians, wrapped to +-pi there) and pitch (+0x278, clamped to
// +-1.45 there, negative = up). This wrapper adds the mouse movement to both before calling it, so the game's own
// wrap and clamp still apply. While the wrapper takes the mouse, the pad leaves the right stick centred
// (ps2PadTakeMouseAim). It skips players with bit 0 of +0xD46 set, as the original does (its look code does not
// run then), so there the pad's mouse-as-stick mapping comes back.
#include "game_overrides.h"
#include "ps2_runtime.h"
#include "ps2_runtime_macros.h"
#include "runtime/ps2_pad_keys.h"

#include <cstdint>
#include <cstring>

namespace mhrs::mouseaim
{
    constexpr uint32_t kLookUpdate = 0x001B3F58u;
    // Radians per pixel at mouse_look = 1 (mouse_look 8, the default, is ~0.046 degrees per pixel).
    constexpr float kRadiansPerPixel = 0.0001f;

    PS2Runtime::RecompiledFunction g_lookUpdate = nullptr;

    void addFloat(uint8_t *rdram, uint32_t address, float delta)
    {
        float value;
        std::memcpy(&value, rdram + address, sizeof(value));
        value += delta;
        std::memcpy(rdram + address, &value, sizeof(value));
    }

    void lookUpdate(uint8_t *rdram, R5900Context *ctx, PS2Runtime *runtime)
    {
        const uint32_t player = GPR_U32(ctx, 4) & 0x01FFFFFFu;
        uint16_t flags = 0;
        std::memcpy(&flags, rdram + player + 0xD46u, sizeof(flags));
        float dx = 0.0f, dy = 0.0f;
        if ((flags & 1u) == 0u && ps2PadTakeMouseAim(dx, dy))
        {
            addFloat(rdram, player + 0x274u, -dx * kRadiansPerPixel); // yaw: turning right lowers it
            addFloat(rdram, player + 0x278u, dy * kRadiansPerPixel);
        }
        g_lookUpdate(rdram, ctx, runtime);
    }

    void apply(PS2Runtime &runtime)
    {
        g_lookUpdate = runtime.lookupFunction(kLookUpdate);
        if (g_lookUpdate)
            runtime.registerFunction(kLookUpdate, &lookUpdate);
    }
}

PS2_REGISTER_GAME_OVERRIDE("MOH Rising Sun: mouse aim", "MOH3RDVD.ELF", 0x00135488u, 0u, mhrs::mouseaim::apply)
