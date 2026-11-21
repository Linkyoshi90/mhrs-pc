# Run inside WSL: make setup && make check
CROSS   := mips-linux-gnu-
AS      := $(CROSS)as
LD      := $(CROSS)ld
OBJCOPY := $(CROSS)objcopy
PYTHON  := .venv/bin/python

BASE    := moh3rdvd
CONFIG  := config/$(BASE).yaml
ORIG    := extracted/MOHRS/MOH3RDVD.ELF
ROM     := extracted/MOH3RDVD.rom
ELF     := build/$(BASE).elf
LDSCRIPT:= build/$(BASE).ld

ASFLAGS := -EL -march=r5900 -mabi=eabi -G0 -no-pad-sections -I include
LDFLAGS := -EL -T $(LDSCRIPT) -T config/linker_script_extra.ld \
           -T build/undefined_syms_auto.txt -T build/undefined_funcs_auto.txt \
           --no-check-sections -Map build/$(BASE).map

S_FILES = $(shell find asm -name '*.s' 2>/dev/null)
O_FILES = $(S_FILES:%.s=build/%.o)

.PHONY: setup split check clean

all: $(ELF)

# Raw image splat reads; derived from the original ELF.
$(ROM): $(ORIG)
	$(OBJCOPY) -O binary --gap-fill=0x00 $< $@

split: $(ROM)
	$(PYTHON) -m splat split $(CONFIG)

setup: split

build/%.o: %.s
	@mkdir -p $(dir $@)
	$(AS) $(ASFLAGS) -o $@ $<

$(ELF): $(O_FILES) $(LDSCRIPT)
	$(LD) $(LDFLAGS) -o $@

# Matching = our ELF flattens to the same bytes as the original.
check: $(ELF)
	$(OBJCOPY) -O binary --gap-fill=0x00 $(ELF) build/$(BASE).rom
	@sha1sum $(ROM) build/$(BASE).rom
	@cmp $(ROM) build/$(BASE).rom && echo "OK: $(BASE) matches"

# --- Static recomp (PS2Recomp, patched with tools/patches/*.patch) ---
PS2RECOMP  ?= $(HOME)/src/PS2Recomp
RECOMP_CFG := recomp/$(BASE).toml
RECOMP_BIN := $(PS2RECOMP)/out/linux

.PHONY: recomp runner vu1

# VU1 microcode the game uploads, compiled to C++ the runtime runs instead of interpreting: blocks (any pc)
# and lean programs (whole programs from their entries, see PS2Recomp's ps2xRuntime/tools/vu1_lean_gen.cpp).
# Record more with `PS2_VU1_DUMP_DIR=$(VU1_DUMPS) make boot` (code images + entry pcs); unrecorded code
# stays interpreted. Both are game code, so they live in build/.
VU1_DUMPS := build/vu1/dumps
VU1_OUT   := build/vu1/src
# Under 2 MB of lean source per file keeps one compile under 2 GB of memory (2186 programs: 130 files).
VU1_LEAN_FILES ?= 130
vu1:
	@mkdir -p $(VU1_DUMPS)
	python3 tools/vu1_compile.py $(VU1_OUT) $(VU1_DUMPS)
	test -f $(RECOMP_BIN)/build.ninja -o -f $(RECOMP_BIN)/Makefile || cmake -S $(PS2RECOMP) -B $(RECOMP_BIN)
	cmake --build $(RECOMP_BIN) --target ps2x_vu1_lean_gen
	$(RECOMP_BIN)/ps2xRuntime/ps2x_vu1_lean_gen --files $(VU1_LEAN_FILES) $(VU1_OUT) $(VU1_DUMPS)

# Function boundaries from splat, SDK names from the recomp config.
build/functions.csv: asm/main/000000.s $(RECOMP_CFG) tools/funcs_csv.py
	python3 tools/funcs_csv.py $< $(RECOMP_CFG) $@

recomp: build/functions.csv
	rm -rf build/recomp
	$(RECOMP_BIN)/ps2xRecomp/ps2_recomp $(RECOMP_CFG)

# The runtime compiles whatever sits in its runner/ and include/ dirs.
# rsync -c only touches files whose content changed, so rebuilds stay incremental.
# ponytail: --delete wipes runner/ extras (upstream only ships a placeholder there); revisit if upstream adds real runner sources.
# No LTO: Release IPO on ~170 MB of generated C++ is too slow.
runner: recomp vu1
	rsync -rc --delete --filter='P mhrs_*' --include='*.cpp' --exclude='*' build/recomp/ $(PS2RECOMP)/ps2xRuntime/src/runner/
	rsync -c build/recomp/*.h $(PS2RECOMP)/ps2xRuntime/include/
	# Our hand-written host code (game overrides, native IOP functions) builds into the same runner.
	for f in src/iop/*.cpp src/game/*.cpp; do rsync -c $$f $(PS2RECOMP)/ps2xRuntime/src/runner/mhrs_$$(basename $$f); done
	# VU1 microcode compiled into blocks (see vu1 above).
	for f in $(VU1_OUT)/*.cpp; do [ -e "$$f" ] && rsync -c $$f $(PS2RECOMP)/ps2xRuntime/src/runner/mhrs_$$(basename $$f); done
	cmake -S $(PS2RECOMP) -B $(RECOMP_BIN) -DCMAKE_BUILD_TYPE=RelWithDebInfo \
	  "-DCMAKE_CXX_FLAGS_RELWITHDEBINFO=-O2 -DNDEBUG" "-DCMAKE_C_FLAGS_RELWITHDEBINFO=-O2 -DNDEBUG"
	cmake --build $(RECOMP_BIN) --target ps2EntryRunner -j$$(nproc)

# The runtime maps cdrom0: to the ELF's folder, so boot a copy placed at the disc root.
# The game also reads raw sectors (it parses ISO9660 itself), so it needs the disc image too.
ISO ?= ISO/Medal of Honor - Rising Sun.iso
boot:
	@test -f "$(ISO)" || { echo "Missing disc image $(ISO): put your ISO there or pass ISO=path"; exit 1; }
	cp -u $(ORIG) extracted/
	$(RECOMP_BIN)/ps2xRuntime/ps2EntryRunner extracted/$(notdir $(ORIG)) "$(ISO)"

clean:
	rm -rf build asm
