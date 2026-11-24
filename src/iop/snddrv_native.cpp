// Native replacements for hot functions in SNDDRV.IRX (EA sound driver, MOH: Rising Sun NTSC-U).
//
// The IOP interpreter is far too slow for SNDDRV's software audio path, and the game's frame clock is
// driven by SNDDRV, so these run natively via ps2x::iop::NativeFunction. Each one is installed only when
// the loaded code hashes to the expected value (tools/irx_native_sig.py), and can be checked against the
// interpreted original with PS2X_IOP_NATIVE_VERIFY=1.
//
// SNDIOP_ee48_iop48 (+0x5824): mixes four blocks of 256 samples; for block k = inner + 2*outer:
//   src = a0 + tableA[k]*2, acc = ptrTable[tableB[k]] + outer*1024, dst = a1 + k*512
//   dst[i] = clamp16(src[i] + (acc[i] >> 7)); acc[i] = 0
//   tableA/tableB (int16[4]) and ptrTable live in SNDDRV's data; their addresses are read from the
//   relocated lui/addiu and lui/lw pairs in the function itself, so no load address is assumed.
// SNDI_memcpy (+0x4600): hand-written memmove(a0 = dst, a1 = src, a2 = n); n <= 0 copies nothing.
// mixiop (+0x36d0): acc[i] += src[i] * (a1 >> 8) for a0 int32 samples (a2 = src, a3 = acc); the hot loop of
//   SNDDRV's software voices, so scenes with many sounds (explosions) ran the IOP interpreter flat out.
// SFILTERI_rs16linear (+0x3120) and decxa16c (+0x9ba0): the software voices' linear resampler and ADPCM
//   decoder, the next hottest IOP code once mixiop was native.
#include "game_overrides.h"
#include "ps2_runtime.h"
#include "ps2x/iop/iop_subsystem.h"

#include <algorithm>
#include <cstring>
#include <initializer_list>

// Named (not anonymous): the runner is a unity build, so helpers must not clash with other files.
namespace mhrs::snddrv
{
    constexpr uint32_t kRamSize = 0x00200000u;

    uint32_t phys(uint32_t address) { return address & (kRamSize - 1u); }

    uint32_t read32(std::span<uint8_t> ram, uint32_t address)
    {
        uint32_t value;
        std::memcpy(&value, ram.data() + phys(address), sizeof(value));
        return value;
    }

    int16_t read16(std::span<uint8_t> ram, uint32_t address)
    {
        int16_t value;
        std::memcpy(&value, ram.data() + phys(address), sizeof(value));
        return value;
    }

    // Address built by `lui rX, hi` at `hiAt` and a 16-bit signed low part at `loAt` (addiu or lw offset).
    uint32_t hiLo(std::span<uint8_t> ram, uint32_t hiAt, uint32_t loAt)
    {
        return (read32(ram, hiAt) << 16u) + static_cast<uint32_t>(static_cast<int16_t>(read32(ram, loAt)));
    }

    uint32_t mixEe48Iop48(uint32_t entry, uint32_t *gpr, std::span<uint8_t> ram)
    {
        const uint32_t tableA = hiLo(ram, entry + 0x18u, entry + 0x1Cu);
        const uint32_t tableB = hiLo(ram, entry + 0x40u, entry + 0x44u);
        const uint32_t ptrTable = hiLo(ram, entry + 0x98u, entry + 0xA0u);
        const uint32_t src = gpr[4];
        const uint32_t dst = gpr[5];

        for (uint32_t outer = 0; outer < 2; ++outer)
        {
            for (uint32_t inner = 0; inner < 2; ++inner)
            {
                const uint32_t k = inner + 2u * outer;
                const uint32_t in = src + static_cast<uint32_t>(read16(ram, tableA + 2u * k)) * 2u;
                const uint32_t acc = read32(ram, ptrTable + static_cast<uint32_t>(read16(ram, tableB + 2u * k)) * 4u) + outer * 1024u;
                const uint32_t out = dst + k * 512u;
                for (uint32_t i = 0; i < 256; ++i)
                {
                    int32_t accValue;
                    std::memcpy(&accValue, ram.data() + phys(acc + 4u * i), sizeof(accValue));
                    const int32_t mixed = std::clamp<int32_t>(read16(ram, in + 2u * i) + (accValue >> 7), -32768, 32767);
                    const int16_t sample = static_cast<int16_t>(mixed);
                    std::memcpy(ram.data() + phys(out + 2u * i), &sample, sizeof(sample));
                    std::memset(ram.data() + phys(acc + 4u * i), 0, sizeof(int32_t));
                }
            }
        }
        // Caller-saved registers are clobbered in the original too; v0 is not a result.
        return 14817u; // guest instructions of the original, measured in verify mode ("guestInsns")
    }

    uint32_t memmoveNative(uint32_t, uint32_t *gpr, std::span<uint8_t> ram)
    {
        const uint32_t dst = phys(gpr[4]);
        const uint32_t src = phys(gpr[5]);
        const int32_t n = static_cast<int32_t>(gpr[6]);
        if (n <= 0)
            return 12u;
        const uint32_t size = static_cast<uint32_t>(n);
        // Out-of-RAM copies would hit hardware registers in the original; never seen, so just refuse.
        if (dst + size > kRamSize || src + size > kRamSize)
            return 12u;
        std::memmove(ram.data() + dst, ram.data() + src, size);
        return 20u + size * 35u / 64u; // the original moves 64 bytes per ~35 instructions
    }

    uint32_t mixIop(uint32_t, uint32_t *gpr, std::span<uint8_t> ram)
    {
        const uint32_t count = gpr[4];
        const int32_t gain = static_cast<int32_t>(gpr[5]) >> 8;
        const uint32_t src = gpr[6];
        const uint32_t acc = gpr[7];
        // The original never ends for a count of 0 (its pair loop runs at least once); never seen, so do nothing.
        if (count == 0u || count > kRamSize / 4u)
            return 4u;
        for (uint32_t i = 0; i < count; ++i)
        {
            int32_t s, a;
            std::memcpy(&s, ram.data() + phys(src + 4u * i), sizeof(s));
            std::memcpy(&a, ram.data() + phys(acc + 4u * i), sizeof(a));
            a = static_cast<int32_t>(static_cast<uint32_t>(a) + static_cast<uint32_t>(s) * static_cast<uint32_t>(gain)); // mult/mflo + add, wrapping
            std::memcpy(ram.data() + phys(acc + 4u * i), &a, sizeof(a));
        }
        return 20u + (count & 3u) * 9u + (count & ~3u) * 7u;
    }

    int32_t readS32(std::span<uint8_t> ram, uint32_t address) { return static_cast<int32_t>(read32(ram, address)); }

    void write32(std::span<uint8_t> ram, uint32_t address, uint32_t value)
    {
        std::memcpy(ram.data() + phys(address), &value, sizeof(value));
    }

    // Low 32 bits of a signed mult, as mflo gives them.
    int32_t mulLo(int32_t a, int32_t b) { return static_cast<int32_t>(static_cast<uint32_t>(a) * static_cast<uint32_t>(b)); }

    uint32_t rs16Linear(uint32_t, uint32_t *gpr, std::span<uint8_t> ram)
    {
        const uint32_t state = gpr[4];
        const int32_t count = static_cast<int32_t>(gpr[5]);
        const uint32_t src = gpr[6];
        uint32_t dst = gpr[7];
        if (count <= 0)
            return 7u;
        if (static_cast<uint32_t>(count) > kRamSize / 4u) // never seen; the original would write past IOP RAM
            return 7u;
        // Four outputs per pass, at pos + {0, step1, step2, step3}; pos += step4 (16.16 fixed point).
        const uint32_t passes = (static_cast<uint32_t>(count) + 3u) / 4u;
        for (uint32_t p = 0; p < passes; ++p, dst += 16u)
        {
            const uint32_t pos = read32(ram, state + 48u);
            const uint32_t at[4] = {pos, pos + read32(ram, state + 32u), pos + read32(ram, state + 36u), pos + read32(ram, state + 40u)};
            for (uint32_t k = 0; k < 4; ++k)
            {
                const uint32_t sample = src + (at[k] >> 16u) * 4u;
                const int32_t s0 = readS32(ram, sample);
                const int32_t diff = static_cast<int32_t>(read32(ram, sample + 4u) - static_cast<uint32_t>(s0));
                write32(ram, dst + 4u * k, static_cast<uint32_t>((mulLo(diff, static_cast<int32_t>(at[k] & 0xFFFFu)) >> 16) + s0));
            }
            write32(ram, state + 48u, pos + read32(ram, state + 44u));
        }
        return 8u + passes * 72u;
    }

    // XA-style ADPCM: groups of 15 bytes (header: filter index << 4 | shift, then 14 bytes of two nibbles)
    // -> 28 int32 samples. State: +0 bytes left (-28 per group, runs while > 0), +4/+8 history, +12 src, +16 dst.
    uint32_t decXa16c(uint32_t entry, uint32_t *gpr, std::span<uint8_t> ram)
    {
        const uint32_t s = gpr[4];
        const uint32_t coefA = hiLo(ram, entry + 0x40u, entry + 0x48u);
        const uint32_t coefB = hiLo(ram, entry + 0x4Cu, entry + 0x54u);
        uint32_t insns = 7u;
        for (uint32_t groups = 0; readS32(ram, s) > 0; ++groups)
        {
            if (groups > kRamSize / 15u) // never seen: a group count no RAM could hold
                break;
            write32(ram, s, read32(ram, s) - 28u);
            uint32_t in = read32(ram, s + 12u);
            uint32_t out = read32(ram, s + 16u);
            const uint32_t header = ram[phys(in++)];
            const uint32_t shift = (header & 0xFu) + 8u;
            const int32_t c0 = read16(ram, coefA + (header >> 4u) * 4u);
            const int32_t c1 = read16(ram, coefB + (header >> 4u) * 4u);
            int32_t newest = readS32(ram, s + 4u);
            int32_t older = readS32(ram, s + 8u);
            for (uint32_t i = 0; i < 14; ++i, ++in, out += 8u)
            {
                const uint32_t byte = ram[phys(in)];
                const int32_t hi = static_cast<int32_t>((byte >> 4u) << 28u) >> shift;
                const int32_t first = static_cast<int32_t>(static_cast<uint32_t>(hi) + static_cast<uint32_t>(mulLo(newest, c0)) + static_cast<uint32_t>(mulLo(older, c1))) >> 8;
                write32(ram, out, static_cast<uint32_t>(first));
                const int32_t lo = static_cast<int32_t>(byte << 28u) >> shift;
                const int32_t second = static_cast<int32_t>(static_cast<uint32_t>(lo) + static_cast<uint32_t>(mulLo(first, c0)) + static_cast<uint32_t>(mulLo(newest, c1))) >> 8;
                write32(ram, out + 4u, static_cast<uint32_t>(second));
                older = first;
                newest = second;
            }
            write32(ram, s + 4u, static_cast<uint32_t>(newest));
            write32(ram, s + 8u, static_cast<uint32_t>(older));
            write32(ram, s + 12u, in);
            write32(ram, s + 16u, out);
            insns += 698u;
        }
        return insns;
    }

    // Masks: all bits checked except relocated fields at the given word indices.
    std::vector<uint32_t> masks(uint32_t words, std::initializer_list<uint32_t> hiLoWords, std::initializer_list<uint32_t> jumpWords)
    {
        std::vector<uint32_t> m(words, 0xFFFFFFFFu);
        for (uint32_t i : hiLoWords) // R_MIPS_HI16/LO16
            m[i] = 0xFFFF0000u;
        for (uint32_t i : jumpWords) // R_MIPS_26
            m[i] = 0xFC000000u;
        return m;
    }

    void add(PS2Runtime &runtime, uint32_t offset, std::vector<uint32_t> masks, uint32_t hash,
             uint32_t (*call)(uint32_t, uint32_t *, std::span<uint8_t>))
    {
        ps2x::iop::NativeFunction function;
        function.module = "SNDDRV.IRX";
        function.offset = offset;
        function.masks = std::move(masks);
        function.maskedHash = hash;
        function.call = call;
        runtime.iopSubsystem().registerNativeFunction(std::move(function));
    }

    void apply(PS2Runtime &runtime)
    {
        // Hashes from tools/irx_native_sig.py extracted/MOHRS/IOP/SNDDRV.IRX <start> <end>.
        add(runtime, 0x5824u, masks(122u, {6, 7, 16, 17, 38, 40}, {51, 55, 66, 70, 81, 85, 96, 100}), 0x0AA430FEu, mixEe48Iop48);
        add(runtime, 0x4600u, masks(201u, {}, {153}), 0x5674C270u, memmoveNative);
        add(runtime, 0x36D0u, masks(49u, {}, {}), 0x6A1CFBD3u, mixIop);
        add(runtime, 0x3120u, masks(80u, {}, {}), 0x9E068FEFu, rs16Linear);
        add(runtime, 0x9BA0u, masks(77u, {16, 18, 19, 21}, {73}), 0xBA2AEBE3u, decXa16c);
    }
}

PS2_REGISTER_GAME_OVERRIDE("MOH Rising Sun: native SNDDRV hot functions", "MOH3RDVD.ELF", 0x00135488u, 0u, mhrs::snddrv::apply)
