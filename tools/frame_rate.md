# Frame rate: where it stands and how to reach 60 fps

Numbers: Windows mingw build, i9-9900K, RTX 4070 SUPER, `PS2X_GS_BACKEND=vulkan PS2X_VK_RASTER=1`, 2026-11-16.

## Terms

- **Game frame**: one pass of the game's main loop. The log line `[mhrs-fps]` counts **flips** (writes to
  DISPFB1 and DISPFB2), two per game frame: 60 flips/s = 30 fps.
- **Frame limiter**: `func_0015A080` waits until 2 vblanks have passed since the last frame, so the game runs at
  30 fps at most. PCSX2 shows a steady 30 fps in the mission-1 intro and in the first room. Since 2026-11-18 the
  recompiled game waits for only 1 vblank outside level loading (see "To 60 fps in gameplay").
- The game steps its logic by the vblanks that passed (`func_00271218`), so a lower frame rate does not slow the
  game down, and a higher one needs no logic patch.

## Where it stands

| Scene | flips/s before | flips/s now | Frames in the 30 fps slot |
|---|---|---|---|
| Mission-1 intro (in-engine) | 36 | 48 to 56 | about 70% |
| Mission 1, first room | 14.5 | 51 to 59 | 75% to 95% |
| Main menu (3D background) | not measured | 43 to 55 | not measured |

Played by hand, mission 1 held 30 fps up to the fire-extinguishing part. There the game halted: its draw
watchdog (`func_002CB720`, a counted busy loop) ran out during a slow frame. The count is patched to stand
still (`recomp/moh3rdvd.toml`), and the 465 microprograms that play session recorded are compiled in now.

The cutscene on arriving on deck then froze: the runtime walked at most 4096 tags of a DMA chain, and that
scene's VIF1 display list is longer, so its end and the VIF1 interrupt the game waits for were never processed
(`ps2recomp-dma-chain-length` lifts the limit). A cut-off chain leaves D1_CHCR with STR clear and a tag id
other than 7.

What changed on 2026-11-16 (new VU1 captures, PS2Recomp patches `ps2recomp-vu1-lean-values-only` and
`ps2recomp-worker-queue-spin`):

1. The first room ran its VU1 microprograms in the interpreter: 55 programs had never been captured, so no lean
   code existed for them. Capturing them took the room from 14.5 to 37 flips/s.
2. Lean programs no longer compute MAC/status flags that nothing reads, and copy PATH1 packets in bulk: with
   item 3, to 51 to 59 flips/s. The four VU1 recordings still replay with no mismatch (the sticky status bits,
   which no program of the game reads, are the one thing left out of the comparison).
3. The GIF/VU1 worker spins for its queue lock instead of sleeping on it: on Windows it lost a tenth of its time
   waiting there.

## What a frame costs

Four host threads share a frame, in this order:

| Thread | Work | Host time per game frame (first room) |
|---|---|---|
| EE (`GameThread`) | recompiled game code, VIF1 parsing, IOP | about 21 ms |
| GIF/VU1 worker | VIF1 unpacks, VU1 microprograms, XGKICK packets | about 27 ms |
| GS frontend | GIF packets to draw batches | a few ms |
| GS backend (Vulkan) | uploads, CLUT loads, draw dispatch | about 19 ms |

The game kicks the display list of frame N when it starts building frame N+1, and at the end of every frame it
waits for the drawing to finish (`func_002CADE8`, then a GS CSR read in `func_002CD5A0`: the runtime drains the
GIF/VU1 worker there). So a frame takes the longer of the EE's time and the worker's time, rounded up to whole
vblanks. With 21 ms and 27 ms most frames fit in 33.3 ms; the rest take 50 ms.

That end-of-frame wait cannot be skipped: when CSR reads stopped draining the worker, the game's watchdog
reported "Frame draw stalled" at the first heavy frame and halted.

## VU1 programs must be captured

The runtime runs VU1 microcode fast only where a lean program was compiled for it ahead of time
(`make vu1`, from `build/vu1/dumps`). Code that was never captured runs in the interpreter, about 4 times
slower (50 against 190 million VU cycles a second), and that scene drops to about 15 flips/s. A new area, weapon
or effect can bring new microprograms.

To capture while playing, start the game with `tools\windows\play_mingw.bat`, or set the variable yourself:

```bat
set PS2_VU1_DUMP_DIR=build\vu1\dumps
```

Only starts that have no lean program yet are recorded (`ps2recomp-vu1-dump-uncovered`), so a covered area
writes nothing. Before that the capture wrote every code image the game composes, tens of thousands for about
a thousand programs, and those file writes made new areas stutter. Afterwards run `make vu1`, copy `build/vu1/src/vu1_lean_*.cpp` into the
PS2Recomp tree's `ps2xRuntime/src/runner/` and rebuild. If the number of programs `ps2x_vu1_lean_gen` reports
did not grow, nothing new was captured. 1131 programs are known so far: 276 from the boot, the intro and the
first room of mission 1, 465 from a play session up to the fire-extinguishing part, and 390 from one that went
on to the deck (the Zero crashing into the AA gun).

On deck a frame needs 10 to 14 million VU1 cycles (the first room: 7). The lean code runs about 190 million
cycles a second, so those frames take 55 to 75 ms: 15 to 20 fps. A real VU1 runs 295 million cycles a second
and would need 35 to 47 ms, so the console probably drops to 20 fps there too (not checked in PCSX2).
Matching the console everywhere means lean code at 295 million cycles a second, 1.5 times today's.

## To a steady 30 fps

The worker's 27 ms is an average; frames above 33 ms miss the slot. About 20% less worker time would put nearly
all frames in it. What is left in the worker, by share of its time in the first room:

- lean program code, about 40%: no single hot spot any more. Measured on 2026-11-18 (Linux VU1 replay, line
  profile): FMACs and their operand clamps/normalization and flag checks take about 60% of VU time, the per-pair
  cycle bookkeeping only about 5%. A prototype that kept VU registers in host registers within a node and skipped
  the clamp on known-normal operands replayed without mismatch but was not faster: the loads and stores it
  removed are almost free (store forwarding); the cost is the work that makes results and flags exact.
  `ps2recomp-vu1-blend-stores` (single 16-byte stores for partial writes) gave 2 to 5%; an AVX2 build 2 to 4%.
- waiting for the EE, about 20%: not a cost, the worker is ahead.
- packet copies (`memmove`), about 8%: an XGKICK packet is copied from VU memory to the packet buffer, then into
  a pooled buffer for the GS frontend. Tried 2026-11-19: XGKICK copied straight into the pooled buffer, handed to
  the GS stage without the second copy. Mission 1 first room 63.3 flips/s with and without it, VU1 at the same
  190 million cycles a second; in a profile the worker's idle share rose only from 13% to 16%, so it was dropped
  (about 3% for 150 lines). Note that the first room no longer shows small gains in flips/s: nearly every frame
  takes 2 vblanks (31 fps), and only a frame under 16.7 ms takes 1. Measure worker idle share in a profile, or a
  heavier scene (the deck, 3 to 4 vblanks a frame), instead.

## To 60 fps in gameplay

Three things are needed together.

1. **The limiter: done (2026-11-18).** `func_0015A080` waited for 2 vblanks per frame. A limit of 1 everywhere
   starved level loading: the loader thread only runs while the main thread sleeps in the limiter, and with a
   limit of 1 it never sleeps there (4 of 10 boots were still loading after 60 s). Instruction patches in
   `recomp/moh3rdvd.toml` now make the limit `1 + (D_004BB870 < 5)`: 2 while the loader's state machine
   (`func_0026DC80`, started by `func_0026E688`, state 5 = done) runs, 1 otherwise. The patch reuses slots where
   the function loaded 0x360000 into a register that `$s4` already held. Before the first level load the
   state is 0, so the limit stays 2 until then.
   Measured 2026-11-19 (unattended run with `MHRS_SIO2_AUTOPRESS`, mission 1 first room, together with
   `ps2recomp-vu1-blend-stores`): 49 to 52 flips/s before, 62 to 63 after, so about 31 fps. The GIF/VU1 worker
   no longer idles while the main thread waits for a vblank: VU1 runs 190 instead of 149 million cycles a
   second, and at 3.05 million cycles a flip that is the whole frame rate. A level still loads in about 10 s.
   Regenerating the recompiled code for this also brought 96 functions up to patch 62 (64-bit
   BGEZ/BLTZ/BLEZ/BGTZ) and one up to patch 66 (SQRT.S): they had been regenerated with an older recompiler.
2. **The GIF/VU1 worker under about 14 ms a frame**, from 27 ms (32 ms at 31 fps; the VU1 microprograms alone
   need 3.05 million cycles a flip in the first room). Micro-optimizing the lean code will not give a
   factor of 2. Candidates, largest first:
   - Lean code without the cycle model: measured at about 5% of VU time (2026-11-18), so little to gain.
   - Wider host vectors (AVX2): measured 2 to 4%.
   - Host registers for VU registers within a node: prototyped, no gain (see above).
   - Splitting the worker: VIF1 unpacks on one thread, VU1 runs on another. Consecutive runs depend on each
     other (register state carries from one MSCNT to the next: measured, 97% of runs), so the runs themselves
     cannot be spread over threads.
3. **The EE under about 14 ms a frame**, from 21 ms. By share of its busy time: VIF1 parsing
   (`processVIF1Data`) about 20%, guest function lookup through a hash table about 5%, IOP interpreter a few
   percent, the rest is recompiled game code. Parsing VIF1 on the worker instead of the EE is the largest
   single step, but the game reads VIF1 registers about 800 times a second, so those reads must then wait for
   the worker.

The GS backend thread is busy about 55% of the time at 30 fps; at 60 fps texture uploads and CLUT loads, which
still run on the CPU, would saturate it. They need to move to the GPU as well.

## To 60 fps in the menus

The main menu is not a light 2D screen: it draws a 3D scene (the ship's bridge) behind the text and costs
about as much as gameplay, 2.9 million VU cycles a flip. Measured on 2026-11-16 once a profile existed on the
memory card (the unattended boot then stops at "Single Player Campaign"): 43 to 55 flips/s, so below its
30 fps cap. 60 fps in the menus therefore needs the same three steps as gameplay; the limiter change alone
does nothing there. Without a profile the unattended boot goes from the movies straight into mission 1.
