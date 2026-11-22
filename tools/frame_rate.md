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
a thousand programs, and those file writes made new areas stutter. Afterwards run `make vu1` with
`PS2RECOMP` set to the patched PS2Recomp tree (an older generator writes slower code), replace the
`vu1_lean_*.cpp` files in that tree's `ps2xRuntime/src/runner/` with those from `build/vu1/src` (remove the old
ones first: the build picks up every file of that name) and rebuild. If the number of programs
`ps2x_vu1_lean_gen` reports did not grow, nothing new was captured. 2186 programs are known so far (2026-11-19):
276 from the boot, the intro and the first room of mission 1, 465 from a play session up to the
fire-extinguishing part, 390 from one that went on to the deck (the Zero crashing into the AA gun), and the
rest from later play sessions.

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
   factor of 2.
   **Done 2026-11-19: relaxed VU1 floats** (`ps2recomp-vu1-relaxed-floats`, `PS2X_VU1_RELAXED` in
   `ps2_vu1.h`, 1 by default), the way PCSX2 runs VU code: operands are still clamped to finite values, but
   tiny results are flushed by the host (flush-to-zero) instead of per op, and the overflow/underflow edge
   cases no longer fall back to the exact path. Offline replay: 1.18x (play recording) and 1.26x (game
   recording) faster; the results differ from the exact ones in a few edge cases (2520 and 12560 mismatching
   calls). Dropping the operand clamp too gave only 4% more but 30 times the mismatches (Inf/NaN), so it stays.
   In the game: VU1 171 -> 214 million cycles a second, first room 57 -> 66 flips/s, frames looked right.
   Two unit tests that check exact overflow/underflow flags run only with `PS2X_VU1_RELAXED=0`.
   Other candidates, largest first:
   - **Native kernels for the hot VU1 loops** (analysed 2026-11-19, not built). In all four recordings about
     85% of the VU1 cycles are spent in short loops (5 to 40 pairs) that process one vertex per pass, and the
     same loop bodies recur across programs: one 30-pair transform/clip loop (at 0x04E0 in many programs) takes
     about 30% of all VU1 cycles alone, and the 8 largest loop bodies about 70%. These loops are software
     pipelined by the game's own code, but vertices do not depend on each other: values are handed from one pass to
     the next, and the only real link is the 3-vertex clip flag window (FCAND 0x3FFFF), with a per-vertex branch
     for clipped triangles. A hand-written native version of that loop (`~/vec/kbench.cpp`, synthetic data, same
     clamped float ops) takes 15 ns a vertex with SSE and 11 ns with AVX2 (2 vertices at once), against about
     60 to 80 ns in the lean code (Linux replay with `VUREPLAY_NOHASH=1`, 240 to 250 million cycles a second,
     15 to 20 cycles a pass). So most of the gain comes from running the loop natively (no per-pair
     bookkeeping), not from the wider vectors. Estimate: the top 5 to 6 loop bodies (about 65% of the cycles)
     at 4 times the speed would make VU1 about 1.9 times faster; 60 fps in the first room needs about 1.75. Not checked yet: bit-exact results, clip flag and Q timing,
     and the loop exit state.
     **Prototype 2026-11-19** (`ps2recomp-vu1-loop-kernel`; lean files must be regenerated with the patched
     generator for it to take effect: 624 kernel call sites in the 2229 programs known on 2026-11-19): `LeanAccess::transformClipLoop` in `ps2_vu1_lean.h` runs the loop natively; the generator calls
     it at the loop's head node when the node has exactly the expected words, issue cycles, Q commit and
     chain-start saves (46 nodes in the small replay set). It runs only unclipped passes and always leaves 2
     passes and their cycles to the lean code, then rebuilds the last two passes' MAC/status flag entries and
     chain starts, so the state matches the lean code's (only sticky status bits of earlier passes are left out).
     `PS2X_VU1_KERNELS=0` turns it off. Offline replay: every call of all four recordings gives the same state,
     VU memory and GIF packets with and without it; play 0.035 -> 0.029 s (1.21x), game 0.051 -> 0.043 s
     (1.19x). It takes about 22% of the VU1 cycles (clipped passes and the last two stay lean) at about 15 ns a
     pass instead of about 46. Replacing lane reads through memory by shuffles changed nothing measurable.
     In the game (Windows, unattended run into mission 1, same inputs): first room about 65 -> 72 flips/s
     (last 10 samples 62-70 -> 67-77), VU1 215 -> 229 million cycles a second; frames looked right.
     **Second kernel 2026-11-19** (`ps2recomp-vu1-light-kernel`, `LeanAccess::pointLightLoop`): the 26-pair
     point-light loop (second by VU1 cycles, about 15%). Bit-exact on all four recordings, but only about 2%
     faster in the replay: a third of its pairs are empty, so the lean code was already cheap there. **Lesson:
     rank loops by host time, not by VU1 cycles.** The game build does not call it yet (it needs regenerated
     lean files, which a full lean rebuild of ~2 hours compiles; do it with the next capture refresh).
   - **Host-time profile of mission 1's first room (2026-11-19, `prof_m1.sh`-style run: no memory card, auto
     press, tsample over 30 s)** showed both threads about 80% busy, so both bound the frame:
     - GIF/VU1 worker: loop kernel 7%, PATH1 copy (`progressXgkick*`) 6%, decoded-code cache rebuilds 3.4%
       plus binds 2.3% (`ps2recomp-vu1-code-cache`: the game swaps VU1 microcode ~10,000 times a second and the
       first room cycles through more than 64 code images, which caused up to 5,000 binds a second; now CRC32C
       content hash, SIMD compare, 256 images, unchanged MPG uploads skipped: rebuild 1.8%, binds 0),
       `fesetround` per run 2% (now MXCSR directly), copying unpacked data into VU memory 11-12% (inline SSE
       now, but the time stays: it is cross-core memory traffic), flag pipeline ~6%, lean nodes ~20%.
     - EE (GameThread): `processVIF1Data` 20.5% -> 14.4% (`ps2recomp-vif1-unpack-simd`: the `cl == wl` unpack
       loop decodes a vector at a time with SSE; a variable-size memcpy per vector had compiled to a slow
       `rep movsb`), plus a leftover debug scan over every VIF1 DMA chain (`[mhrs-zeromatrix]`, came in with
       `ps2recomp-sio2-dualshock`) removed.
     - Result, same unattended run: first room about 72 -> 74 flips/s on average, last samples 63-77, VU1
       ~236 million cycles a second, EE idle 27% and worker idle ~19%. Next: the unpack hand-off (EE writes
       unpacked vectors, worker copies them: maybe let the worker read packed data instead), PATH1 copy, and
       kernels for the loops that cost the most host time (p1129/p1373/p1537 nodes).
   - **2026-11-20, with GPU present (forced on by the internal resolution, faster than the CPU present anyway):**
     first room 78-86 flips/s. Profile (`~/mhrs-vurec/winprof/prof_m1.sh`): the GIF/VU1 worker is the
     bottleneck (85% busy) while the EE idles 32%. Worker: copying unpacked vectors into VU memory 10% (the copy
     loop waits on loads of data the EE core wrote: cross-core traffic, not instructions), transform/clip kernel
     8%, the point-light loop 7.5% (`p1129::n7`, `p1373::n7`: kernel 2 was not in the game build yet), PATH1 6.6%,
     the 6-pair copy loop at 0xE8 3.5% (`p1537::n3`, `p1128::n3`; `tools/leannode.py` prints a node).
     Kernel 3 `ps2recomp-vu1-copy-kernel` (`LeanAccess::scaleOffsetLoop`) runs that copy loop; with kernels 1-3
     the play replay is 23% faster than with none (19% with kernel 1 alone), bit-exact on all four recordings.
     `ps2recomp-vu1-path1-step`: progressXgkickTo jumps to the cycle of the next qword copy instead of stepping
     each cycle (same result). Frames are vblank-quantized: a frame the worker needs 17-33 ms for takes two
     vblanks, so every ms the worker saves moves frames from 30 to 60 fps.
     Built into the game together with the lean files regenerated from all captures (2418 programs, 977 kernel
     call sites) and `ps2recomp-gs-clut-reuse` (the GS backend thread spent 12% reloading the same palette before
     draws; a CSM1 load with the last load's parameters and unchanged source bytes is now skipped: 3%). Same
     unattended run, mean of the last 10 samples, two runs each (runs vary by ±4): first room 80.6 -> 88.2
     flips/s, VU1 237 -> 265 million cycles a second. Now three threads are at 75-85%: the VU1 worker, the GS backend thread (draw setup 30%, its first
     loads of each batch wait on the frontend core's cache; prefetching batches ahead only moved that time) and
     the EE.
   - **Window stalls (2026-11-20, `ps2recomp-gs-present-pipeline`):** the game ran at 85-90 flips/s, but the
     window dropped below 10 fps, because each window frame drained the whole GS queue first (about 155 ms at
     scale 3). Now the GPU present is queued behind the draws (at most 2 in flight). It deswizzles into one of 4
     output slots with a fence, the window shows the newest finished slot, and when nothing new has finished it
     keeps the last frame. The async queue limit went up to 65536 commands. Window, new frames a second: about 54
     at scale 1, about 45 at 2 (every game frame), and about 30 at 3 (limited by the GPU and backend thread).
     `play_mingw.bat` now defaults to 2.
   - **GS backend thread (2026-11-20, `ps2recomp-gs-backend-speedups`):** with the window fixed, the backend
     thread was the busiest (95%). Three fixes:
     - The window thread now copies the 2× frame itself (4.6 MB) from the GPU output slot. Before, the backend
       thread copied it, at ~8% of its time.
     - Image uploads write one row run inside a page at a time: one address calculation per run, then a table
       lookup per pixel (T8/T4 textures stream in every frame).
     - Each draw batch carries a state id from the frontend. Batches with the same id have the same state, so
       the backend reads only the vertex cache lines, not all five lines of each 320-byte batch the frontend
       core just wrote.

     Result: backend thread 95% → 72% busy, with uploads 12% → 6%. Tests cover both new paths (upload vs.
     per-pixel writes for all 13 formats across pages and split packets; state ids equal ⇔ state equal).
     Flips/s barely moved (83–85 at 2× in unattended runs) because the VU1 worker is now the busiest thread
     (95%: unpack copy 14.5%, transformClip 7.5%, XGKICK ~7%, GIF packet posts to the GS frontend). The EE, the
     VU1 worker and the GS backend each wait on one another for a large share of their time (EE ~26% waiting,
     backend ~30% idle). The "~8% of the EE in C++ exception unwinding" seen then was a profiler artifact:
     `tsample2` names the callers of samples outside the exe by scanning 1.3 KB of raw stack, and that
     found one stale return address inside `parse_lsda_header` while the EE waited in ntdll. No sample ever
     landed inside the unwinder.
   - **GS privileged register drains (2026-11-20, `ps2recomp-gs-display-writes-ordered`):** each game frame,
     the vblank handler reads CSR, acknowledges VSINT (CSR = 0x8), then writes PMODE, SMODE2, DISPFB1,
     DISPLAY1 and DISPFB2. Each access drained the GIF/VU worker and the GS stage completely, and the first one
     waited 150–250 ms per second (14–21% of the EE). The drain kept the EE from starting the next frame while
     the worker finished the last one. Now:
     - Display registers (PMODE..BGCOLOR) are written by a GS-stage job, in order after the GIF/VU work issued
       before them, so a present still sees DISPFB change only after the draws before the flip. The EE runs at
       most five such writes (one frame) ahead.
     - CSR reads, and CSR writes that don't clear SIGNAL/FINISH or request FLUSH/RESET, don't drain. A queued
       SIGNAL/FINISH shows up when the GS stage reaches it, as with a slower GS.
     - Reads of the other registers still drain, which also applies queued display writes first.

     A/B at 2×, two rounds: 92.6 → 95.8 flips/s. Frames dumped every ~2 s look complete. The VU1 worker is
     now at 100% (idle polling 16% → 10%): it is the bound. Its unpack copy (14–17%) is paid per byte, not
     per block. About 550k UNPACKs a second average 35 qwords, ~300 MB/s read from the EE core. Merging
     contiguous blocks (37% of them) and prefetching the next block made no difference (A/B 93.4 vs 92.6),
     so that was dropped. Writing the decoded words with streaming stores, so the worker reads DRAM instead of
     the EE core's cache, didn't help either (copy still 16%).
   - **GIF/VU worker heap and lock traffic (2026-11-20, `ps2recomp-gifvu-worker-pools`):** about 10% of the
     worker was in ntdll, not idle, from three per-job costs:
     - The unpack job captured a 72-byte struct, which `std::function` heap-allocated on the EE and freed on
       the worker. It now captures a pooled pointer, which `std::function` keeps inline.
     - The GIF arbiter allocated a vector per packet. Drained packet buffers are now reused through a
       per-thread free list.
     - The GIF packet and unpack pools used a `std::mutex` that the worker and the GS stage take per packet.
       They now use a spin lock.

     Measured while ComfyUI shared the GPU (8 GB of VRAM, generating now and then; runs ranged 57–94), so the
     size of the gain is uncertain. The new build won all three pairs: 64 vs 57, 82 vs 79, 88 vs 71.
     `ab2.sh` (scratchpad) logs GPU utilization per run to spot such load.

## Vulkan GS streams (2026-11-21, `ps2recomp-gs-vulkan-stream-halves`)

At 2× the game ran at 84–95 flips/s, against ~104 at 1×. The GS backend thread waited ~10% of its time on the GPU
(`PS2X_VK_STATS` waitMs ~450 per 400 presents at 2×, ~160 at 1×). The waits were full GPU drains to rewind the
batch streams, which are linear buffers reset only when the GPU is idle:
- Gameplay sends ~48k primitives and ~1.2M tile words per present. The geometry stream (131k) filled every
  ~2.7 presents, the tile stream (4M words) every ~3.6.
- The CLUT stream (2048 palettes) filled every ~4 presents.

First step: streams 4–8× larger, so they no longer filled in gameplay. Waits ~450 → ~110 ms per 400 presents.
A/B at 2×, three rounds: 93.9 / 94.6 / 93.1 → 97.6 / 97.2 / 97.7 flips/s, steadier (96–98.7).

Final version: the streams, the upload buffer and the command buffers are used in two halves with a fence each
(`switchHalf`). A full half waits only for the GPU work recorded in the other half, usually finished long ago.
Totals are back to 2× the original sizes (geometry 262144, tiles 8M words, CLUTs 8192, upload 32 MB, 256
command buffers): ~110 MB more than before instead of ~290 MB. GPU waits fell to ~0.4 ms per 400 presents. The
frame rate is unchanged against the larger buffers (97.7 vs 97.4): at 2× the VU1 worker is the bound again.
Upload overflow inside `closeBatch` and running out of command buffers without a draw still drain the GPU as
before (neither happens in gameplay). At 3× the GPU is the bound (94–96% busy, ~70–73 flips/s with or without
this change): faster 3× needs a cheaper raster shader.

## XGKICK at program end (2026-11-21, `ps2recomp-vu1-xgkick-flush-runs`)

All VU1 runs in mission 1 are lean programs, yet the worker made ~17M `progressXgkick` calls a second. They came
from `flushPipelines()` at the end of each program, which stepped `advanceOneCycle()` per cycle through the
program's last XGKICK, often hundreds of cycles. Once only PATH1 is left, it now finishes the packet with
`progressXgkickTo()`, which copies tag data in runs, and lands on the cycle the last qword is copied in. Nothing
writes VU memory after the program has ended, so the bytes are the same. cycles/flip unchanged (~3.05M). A/B at
2×, four rounds: 98.4 / 96.8 / 98.4 / 97.8 → 101.1 / 101.8 / 100.0 / 100.1 flips/s.

## EE UNPACK lane selectors (2026-11-21, `ps2recomp-vif1-unpack-selectors`)

About a fifth of `processVIF1Data` on the EE was a store-forwarding stall. Per UNPACK and mask cycle, three lane
selectors were written to stack arrays as four 32-bit values and loaded back as one vector. They are now built with
SSE compares from the MASK bits. EE share 18.9% → 17.8%. The frame rate is unchanged (the VU1 worker is the
bound), but the EE was ~87% busy.

## GS backend draw prefetch (2026-11-21, `ps2recomp-gs-vulkan-draw-prefetch`)

Once the VU1 worker was relieved, the GS backend thread was ~93% busy, and `VkState::draw()` was 44% of it. By
address, ~60% of `draw()`'s samples were on the first loads of each `GSPrimitiveBatch`: `vertexCount`, then the
vertices. The frontend builds the batches on another core, and a batch is ~312 bytes of which `draw()` reads the
first 128, so the hardware prefetcher doesn't follow them. `SubmitMany` now prefetches the vertex lines six draws
ahead. `draw()` went from 44% to 19% of the thread, which now waits ~31% of its time. A/B at 2×, three rounds:
90.1 / 90.1 / 89.5 → 94.5 / 95.3 / 93.8 flips/s. A remote-desktop session was running, so every run was ~10
flips/s below the earlier numbers; the runs were interleaved, so the difference holds.

Tried at the same time and dropped, no measurable gain:
- The VU1 decoded-image lookup hashes and compares all 16 KB of code on every code change: ~2900 a second, all
  hits, 2.5–2.9% of the worker. Two fixes were tried. Keeping the list most-recently-used first changed nothing.
  Finding the image from the previous image plus the MPG uploads skipped every full hash. Neither moved the frame
  rate: 94.7 vs 94.4 with the prefetch.
- `closeBatch` (8% of the backend thread) is its tile-binning counters, not misses.

## Loading screens (2026-11-21, `ps2recomp-skip-idle-loading` + `src/game/fast_load.cpp`)

Loads were paced by real time, not by the disc or the CPU. The emulated DVD has no speed model, so reads are
instant. The EE clock is held to host time, though: vblanks, `SetAlarm` alarms and EE timers wait for their
real-time deadline, and the IOP advances with EE cycles. Mission 1 from "Start Mission" to gameplay:
- About 7 s of disc reads with the main thread blocked and no frames: one 5.7 s stretch had the EE idle 89%.
- Then the loader state machine (func_0026DC80, state word D_004BB870 2..4, 5 when done): 7.8 s, EE idle 78%.
  Each of its steps takes ~200 ms of frame and alarm waits. Halving the IOP's speed changed nothing.

The fast-forward key doesn't help here: at 8× vblanks the main thread's loading-screen frame no longer fits in the
limiter's 2 vblanks, so it never sleeps, and the loader thread only runs while it sleeps (level load 7.8 → 21.5 s).

Now the scheduler skips idle time while a game-supplied predicate holds
(`EeScheduler::setSkipIdleWhile`):
- When every guest thread waits, it jumps straight to the next deadline.
- When the guest clock is ahead of host time, it doesn't stop the EE.
- Host deadlines are re-anchored to the guest clock, so nothing waits out the skipped time afterwards.

Every guest wait stays as long in guest time, so the loader keeps its share. Never while a movie plays
(`sceMpegGetPicture` within 200 ms): the game loads its front end under the opening movie, which ran too fast
before that guard.

The game's predicate: loader state 0..4, or no display-register write for 200 ms
(`EeScheduler::hostMsSinceDisplayWrite`). Movies, menus and gameplay flip every 17–40 ms. The game's own
frame counter doesn't work for this, because the movie player bypasses the main loop. State 0 lasts from boot
to the first load, which covers the "Checking for memory card" screen (4.5 s, EE idle ~85%). The THX and EA
logo movies still play at normal speed because of the movie guard.

| Phase | Before | After |
| --- | --- | --- |
| Mission 1 disc reads (no frames) | ~7 s | ~0.8 s |
| Mission 1 loader state machine | 7.8 s | 1.3 s |
| Launch to front end loaded, movies skipped | 17.1–17.3 s | 6.7–9.8 s |
| Launch to front end loaded, movies playing | 20.0 s | 13.4 s |
| Launch to front end loaded, movies skipped, memory cards present, with state 0 | 7.3–7.8 s (states 2..4 only) | 2.1–3.9 s |
| Launch to mission 1 loaded, auto-press, movies skipped | 140.6 s | 119.3–121.2 s |

(Auto-press taps buttons on a fixed schedule, so the launch-to-mission times also include its waits.)

`MHRS_FAST_LOAD=0` turns it off (real-time loads), e.g. if a loading screen's narration gets cut.

Audio during a skipped load: the IOP and SPU advance with the guest clock, so loading-screen sound plays
compressed or partly dropped for those 1–2 s. The SPU stream drops blocks once it runs more than ~170 ms ahead
(`SpuTimeStretch::kMaxQueue`), so sound can trail by at most that much after a load. Not checked by ear.
     Tools: `~/vec/vustats` (cycles per program),
     `~/vec/vuloops` (cycles per loop and loop body; needs a temporary pair hook in the interpreter, see
     `~/vec/mkloops.py`), `~/vec/vudis.py` (disassembler).
   - Lean code without the cycle model: measured at about 5% of VU time (2026-11-18), so little to gain.
   - Wider host vectors (AVX2): measured 2 to 4%.
   - Host registers for VU registers within a node: prototyped, no gain (see above).
   - Splitting the worker: VIF1 unpacks on one thread, VU1 runs on another. Consecutive runs depend on each
     other (register state carries from one MSCNT to the next: measured, 97% of runs), so the runs themselves
     cannot be spread over threads. Retried 2026-11-19 with prediction (`~/mhrs-vurec/vuspec2.cpp`): the
     register that breaks most runs is `vi14`, a pointer that steps each run, and predicting it by its last
     step is as good as knowing it; then 51% of runs could start early, but only the short ones (0.5% of the VU1
     cycles). Every heavy run still differs in two or three words of its first GIF packet (GS addresses that
     step by 0x40 a run, a double-buffer bit), even with all registers exact and memory the previous run wrote
     predicted. Running VU1 runs in parallel is not worth building.
3. **The EE under about 14 ms a frame**, from 21 ms. By share of its busy time: VIF1 parsing
   (`processVIF1Data`) about 20%, guest function lookup through a hash table about 5%, IOP interpreter a few
   percent, the rest is recompiled game code. Parsing VIF1 on the worker instead of the EE is the largest
   single step, but the game reads VIF1 registers about 800 times a second, so those reads must then wait for
   the worker. Tried 2026-11-19: a copy-only path for unpacks with no write mask and no ROW offset took
   `processVIF1Data` from 15.8% to 15.0% of the EE (most unpacks are not V4-32), dropped. With relaxed floats the
   EE still waits for the worker 41% of its time, so EE work does not limit the frame rate yet.

The GS backend thread is busy about 55% of the time at 30 fps; at 60 fps texture uploads and CLUT loads, which
still run on the CPU, would saturate it. They need to move to the GPU as well.

## Memory card screens (2026-11-21, `ps2recomp-mc-screen-fast-time` + `src/game/fast_load.cpp`)

The memory card stubs answer at once, but the game holds its messages for a fixed time: "Checking for memory
card" ~6 s, "Saving game data…" ~4 s, "Save complete." ~8 s. They draw the 3D menu behind them, so the EE never idles
and skipping idle time changes nothing. While one is up, guest time now runs 8× faster than host time, as with the
fast-forward key, but microprograms still run, so nothing disappears (`EeScheduler::setFastTimeWhile`). Such a
screen is detected by its polling: the game calls `sceMcSync` ~30 times a second while one is up, and never in
menus, on the profile name entry or in gameplay (`g_lastMcSyncNs`, 150 ms). Each screen now lasts about a second.
`MHRS_FAST_LOAD=0` turns this off too.

`PS2X_MC_ROOT=<dir>` (`ps2recomp-mc-root-env`) moves the memory card folder away from `<ELF folder>/mc0`. The
unattended test scripts use it, because their button presses create a new profile named PLAYER1 and save it over an
existing one on the real card.

## VU1 captures and dumping (2026-11-21, `ps2recomp-vu1-dump-async`)

In a play session, scenes ran at 20–35 flips/s with the VU1 at only 110–170 M cycles/s (vs ~290 M in mission 1). The
cause was microprograms seen for the first time, which run interpreted until they are compiled: 23 new programs
(12.6 k pairs) since the last regeneration, now in `vu1_lean_130.cpp`. The generator numbers programs in sequence,
so a full regeneration changes all 130 files. Generating only the new dumps into one more file avoids recompiling
the others. Use the generator in `out/linux-test`; the one in `out/linux` predates the loop kernels.

With `PS2_VU1_DUMP_DIR` set (`play_mingw.bat`), the GIF/VU worker also wrote each new dump file itself and hashed
the whole code image byte by byte at every code swap (~2900 a second). A background thread now writes the files,
and the hash is computed only for a start that is dumped.

## GIF packet batches (2026-11-21, `ps2recomp-gif-packet-batches`)

The GIF/VU worker (still the bound at 100%) posted one GS-stage job per GIF packet, ~150 k a second, each with a
queue lock, a `std::function` and a pooled buffer. It now hands them on in batches of up to 32 packets or 64 KB.
A batch is also handed on at the end of each batch of worker jobs (`OrderedWorker::s_flushHeld`, run before
`drain()` counts them done) and before any other GS-stage job the worker posts (`postGsAfterGifVu`), so order and
drains are unchanged. A/B at 1x, 2 rounds: 103.8/104.2 -> 105.8/107.2 flips/s.

Measured and dropped the same day:
- A larger unpack buffer pool (the EE runs thousands of flushes ahead and the pool of 8 runs dry): no change.
- Triangle Z in float instead of double for high-resolution samples (consumer NVIDIA GPUs run doubles at 1/64
  rate): GPU load 95% -> 88% at 2x but no fps change, +1 flip at 3x. Double Z is not what the GPU spends its time on.
- At 2x the frame rate was ~10 flips below 1x (95 vs 105) although the GPU was not the limit: see the next section.

## Window frames stay on the GPU (2026-11-21, `ps2recomp-gs-window-frames-on-gpu`)

At 2x and above each window frame went GPU -> host memory -> `UpdateTexture` (glTexSubImage2D, 4.6 MB at 2x, 10 MB
at 3x). The upload alone cost ~12% of the game's frame rate. Measured: dropping the upload gave 109.6 instead of 95;
copying without uploading 107; uploading straight from the mapped slot, as BGRA, or into two textures in turn changed
nothing. Now on Windows the high-resolution frame is written into device memory exported as an opaque NT handle
(`VK_KHR_external_memory_win32`, a second descriptor set with it as binding 1). The window's OpenGL context imports it
(`GL_EXT_memory_object_win32`, same GPU checked by device UUID) and copies a frame into its texture with a pixel
unpack buffer, on the GPU. If any step is missing, frames go through the CPU as before. `PS2X_VK_SHARE=0` forces that,
and `MHRS_HIRES_EVERY` dumps also use it. The log says which: `[window] high-resolution frames stay on the GPU`.

A/B in mission 1: 2x 94.7 -> 110.5 flips/s (and steadier), 3x 70.4 -> 89.9.

## What is left at ~115 flips/s (2026-11-22, nothing kept)

Mission 1 now runs about 115 flips/s at 1x and at 2x alike. The EE waits in `writeDisplayReg`'s one-frame-ahead
pacing, so the GIF/VU1 worker (~92% busy) sets the rate. Its largest item is copying the decoded unpack words into
VU1 memory (~18%), and ~80% of that is the load of words the EE just wrote on another core. A VIF1 DMA chain is
~2.5 MB and ~1600 tags per frame, and its copy on the EE (`chainBuf.insert`, ~10% of the EE thread) is the first read
of that cold guest memory. Tried, no gain (A/B flips/s at 1x):
- Only VIF1 chains reuse the spare chain buffer (GIF chains took it, so each VIF1 chain allocated fresh): 110 vs 115,
  slower.
- The interpreter copies the chain's spans lazily, 32 KB ahead of where it parses, instead of all up front: 113.6 vs
  115.6, slower. The cost is the cold reads, not the second pass.
- Software prefetch 2 KB ahead in the worker's unpack copy: 115.3 vs 116.2.

Not built: posting the unpack copy and the VU1 run as one worker job. The worker's job machinery is ~1% of it
(`OrderedWorker::loop` 0.4%, its spin lock 0.4%, no allocations), so that is all it could save.

## To 60 fps in the menus

The main menu is not a light 2D screen: it draws a 3D scene (the ship's bridge) behind the text and costs
about as much as gameplay, 2.9 million VU cycles a flip. Measured on 2026-11-16 once a profile existed on the
memory card (the unattended boot then stops at "Single Player Campaign"): 43 to 55 flips/s, so below its
30 fps cap. 60 fps in the menus therefore needs the same three steps as gameplay; the limiter change alone
does nothing there. Without a profile the unattended boot goes from the movies straight into mission 1.
