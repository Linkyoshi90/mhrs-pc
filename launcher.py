#!/usr/bin/env python3
"""MOH Rising Sun launcher: shows what is still missing, unpacks your ISO, builds the game and starts it.

    python launcher.py                  window (needs tkinter)
    python launcher.py status           what is done / missing
    python launcher.py load <game.iso>  unpack the ISO, then build
    python launcher.py build            generate the code and build the game for this OS
    python launcher.py play
    python launcher.py selftest

On Windows the build runs inside WSL (tools/launcher/build.sh) and produces dist\\windows\\ps2EntryRunner.exe;
on Linux it produces dist/MOHRS-x86_64.AppImage.
"""
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

def find_root():
    """The repo folder. A packaged launcher (tools/launcher/package.*) sits in it or in its dist/."""
    if not getattr(sys, "frozen", False):
        return Path(__file__).resolve().parent
    start = Path(os.environ.get("APPIMAGE") or sys.executable).resolve().parent
    for d in (start, *start.parents):
        if (d / "tools/launcher/build.sh").is_file():
            return d
    return Path.cwd()


ROOT = find_root()
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # no console windows popping up from the windowed exe
CFG = ROOT / "launcher.json"
WIN = os.name == "nt"
TARGET = "windows" if WIN else "linux"
EXTRACTED = ROOT / "extracted"
ELF_IN_ISO = "MOHRS/MOH3RDVD.ELF"
ELF_SHA1 = "2d524fe5a0c9c452da60635e906670d30c556d63"  # NTSC-U SLUS-20753, the build the patches are made for
DEFAULT_ISO = ROOT / "ISO" / "Medal of Honor - Rising Sun.iso"
SECTOR = 2048


# --- ISO9660 ---------------------------------------------------------------------------------------------

def iso_files(f):
    """Yield (path, lba, size) for every file in an ISO9660 image.
    ponytail: single-extent files only (none on this disc is over 4 GB)."""
    f.seek(16 * SECTOR)
    pvd = f.read(SECTOR)
    if pvd[:6] != b"\x01CD001":
        raise ValueError("not an ISO9660 disc image")

    def walk(lba, size, prefix, depth=0):
        if depth > 8:
            raise ValueError("ISO directory tree too deep")
        f.seek(lba * SECTOR)
        data = f.read(size)
        i = 0
        while i < len(data):
            n = data[i]
            if n == 0:  # records never cross a sector: the rest of this one is padding
                i = (i // SECTOR + 1) * SECTOR
                continue
            rec = data[i:i + n]
            i += n
            raw = rec[33:33 + rec[32]]
            if raw in (b"\x00", b"\x01"):  # self / parent
                continue
            name = raw.decode("ascii", "replace").split(";")[0].rstrip(".")
            if not name or name == ".." or "/" in name or "\\" in name:  # names come from the image: no escaping dest
                raise ValueError(f"bad file name in ISO: {raw!r}")
            elba, esize = struct.unpack_from("<I4xI", rec, 2)
            if rec[25] & 2:
                yield from walk(elba, esize, prefix + name + "/", depth + 1)
            else:
                yield prefix + name, elba, esize

    yield from walk(*struct.unpack_from("<I4xI", pvd, 158), "")


def copy_out(f, lba, size, sink):
    f.seek(lba * SECTOR)
    while size > 0:
        chunk = f.read(min(size, 1 << 20))
        if not chunk:
            raise ValueError("ISO is truncated")
        sink(chunk)
        size -= len(chunk)


def load_iso(iso, log=print, dest=EXTRACTED, sha1=ELF_SHA1):
    """Check that `iso` is the right disc and unpack it into dest."""
    iso = Path(iso)
    with open(iso, "rb") as f:
        files = list(iso_files(f))
        elf = next((e for e in files if e[0] == ELF_IN_ISO), None)
        if not elf:
            raise ValueError(f"{iso.name}: no {ELF_IN_ISO} on this disc, not Medal of Honor: Rising Sun (NTSC-U)")
        h = hashlib.sha1()
        copy_out(f, elf[1], elf[2], h.update)
        if sha1 and h.hexdigest() != sha1:
            raise ValueError(f"{iso.name}: different game version (need NTSC-U SLUS-20753), {ELF_IN_ISO} sha1 {h.hexdigest()}")
        # ponytail: unpacks the whole disc (~4.3 GB), the layout the runner is known to work with. MOHRS/DATA is
        # probably only read from the ISO itself; skip it here once that is confirmed.
        total = sum(s for _, _, s in files) or 1
        done = 0
        for path, lba, size in files:
            out = dest / path
            if not (out.is_file() and out.stat().st_size == size):
                out.parent.mkdir(parents=True, exist_ok=True)
                tmp = out.with_name(out.name + ".part")  # a cancelled copy never looks complete
                with open(tmp, "wb") as o:
                    copy_out(f, lba, size, o.write)
                tmp.replace(out)
            before, done = done, done + size
            if done * 20 // total != before * 20 // total:
                log(f"unpacking {done * 100 // total}%")
    # The runtime maps cdrom0: to the ELF's folder, so it boots a copy at the disc root (see Makefile `boot`).
    shutil.copyfile(dest / ELF_IN_ISO, dest / "MOH3RDVD.ELF")
    CFG.write_text(json.dumps({"iso": str(iso.resolve())}))
    log(f"unpacked {len(files)} files into {dest}")


# --- state -----------------------------------------------------------------------------------------------

def iso_path():
    try:
        p = Path(json.loads(CFG.read_text())["iso"])
        if p.is_file():
            return p
    except (OSError, ValueError, KeyError):
        pass
    return DEFAULT_ISO if DEFAULT_ISO.is_file() else None


def game_binary():
    names = ["dist/windows/ps2EntryRunner.exe"] if WIN else ["dist/MOHRS-x86_64.AppImage", "dist/MOHRS.AppDir/AppRun"]
    return next((ROOT / n for n in names if (ROOT / n).is_file()), None)


def backend(*args):
    """Start tools/launcher/build.sh (inside WSL on Windows); returns the process, output on stdout."""
    cmd = ["bash", "tools/launcher/build.sh", *args]
    if WIN:
        cmd = ["wsl", "--cd", str(ROOT), *cmd]
    return subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace",
                            creationflags=NO_WINDOW)


def tools_status():
    try:
        p = backend("check", TARGET)
        out = p.communicate(timeout=120)[0].replace("\0", "").strip()  # wsl.exe's own errors are UTF-16
        return p.returncode == 0, out
    except FileNotFoundError:
        return False, "WSL is not installed: run `wsl --install` in an admin terminal, reboot, then start the launcher again" if WIN else "bash not found"
    except subprocess.TimeoutExpired:
        p.kill()
        return False, "build tool check timed out"


def status():
    """[(label, ok, detail)] for every preliminary task, in the order they have to be done."""
    iso, binary = iso_path(), game_binary()
    unpacked = (EXTRACTED / ELF_IN_ISO).is_file() and (EXTRACTED / "MOH3RDVD.ELF").is_file()
    tools_ok, tools = tools_status()
    return [
        ("Disc image", bool(iso), str(iso) if iso else "not set: load your ISO"),
        ("Game files unpacked", unpacked, str(EXTRACTED) if unpacked else "load your ISO"),
        ("Build tools" + (" (WSL)" if WIN else ""), tools_ok, tools),
        ("Game built", bool(binary), str(binary) if binary else "press Build"),
    ]


def build(log=print):
    p = backend("build", TARGET)
    for line in p.stdout:
        log(line.rstrip())
    if p.wait() != 0:
        raise RuntimeError(f"build failed (exit {p.returncode}); fix the error above and press Build again, it continues where it stopped")


def play():
    iso, binary = iso_path(), game_binary()
    if not (iso and binary):
        raise RuntimeError("not ready: " + ", ".join(label for label, ok, _ in status() if not ok))
    env = dict(os.environ)
    if WIN:  # the AppImage's AppRun sets the same defaults on Linux
        for k, v in {"PS2X_GS_BACKEND": "vulkan", "PS2X_VK_RASTER": "1", "PS2X_VK_SCALE": "2", "PS2X_MOUSE_LOOK": "8"}.items():
            env.setdefault(k, v)
        if (ROOT / "build/vu1/dumps").is_dir():
            env.setdefault("PS2_VU1_DUMP_DIR", r"build\vu1\dumps")
    (ROOT / "build").mkdir(exist_ok=True)
    with open(ROOT / "build" / "play.log", "wb") as out:  # same log as play_mingw.bat
        return subprocess.Popen([str(binary), str(Path("extracted") / "MOH3RDVD.ELF"), str(iso)], cwd=ROOT, env=env,
                                stdout=out, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)


# --- window ----------------------------------------------------------------------------------------------

def gui():
    import queue
    import threading
    import tkinter as tk
    from tkinter import filedialog, scrolledtext

    win = tk.Tk()
    win.title("Medal of Honor: Rising Sun - launcher")
    rows = tk.Frame(win)
    rows.pack(fill="x", padx=8, pady=8)
    bar = tk.Frame(win)
    bar.pack(fill="x", padx=8)
    text = scrolledtext.ScrolledText(win, height=18, width=100, state="disabled")
    text.pack(fill="both", expand=True, padx=8, pady=8)
    q = queue.Queue()  # worker threads -> window: log lines and ("status", rows)
    buttons = {}

    def log(line):
        q.put(line)

    def run(*jobs):
        """Run jobs one after the other off the UI thread, then refresh the status rows."""
        for b in buttons.values():
            b["state"] = "disabled"

        def work():
            try:
                for job in jobs:
                    job()
            except Exception as e:  # shown to the user, the window stays usable
                log(f"ERROR: {e}")
            q.put(("status", status()))
        threading.Thread(target=work, daemon=True).start()

    def show(state):
        for w in rows.winfo_children():
            w.destroy()
        for r, (label, ok, detail) in enumerate(state):
            tk.Label(rows, text="OK" if ok else "--", fg="green" if ok else "red", width=3).grid(row=r, column=0)
            tk.Label(rows, text=label, anchor="w", width=22).grid(row=r, column=1, sticky="w")
            tk.Label(rows, text=detail.splitlines()[0] if detail else "", anchor="w", fg="gray30").grid(row=r, column=2, sticky="w")
            if not ok and "\n" in detail:
                log(detail)
        _, unpacked, tools, built = (ok for _, ok, _ in state)
        buttons["load"]["state"] = "normal"
        buttons["build"]["state"] = "normal" if unpacked and tools else "disabled"
        buttons["play"]["state"] = "normal" if built and state[0][1] and unpacked else "disabled"

    def pump():
        try:
            while True:
                item = q.get_nowait()
                if isinstance(item, tuple):
                    show(item[1])
                else:
                    text["state"] = "normal"
                    text.insert("end", item + "\n")
                    text.see("end")
                    text["state"] = "disabled"
        except queue.Empty:
            pass
        win.after(100, pump)

    def on_load():
        path = filedialog.askopenfilename(title="Medal of Honor: Rising Sun disc image", filetypes=[("Disc image", "*.iso"), ("All files", "*")])
        if path:
            run(lambda: load_iso(path, log), lambda: build(log))

    buttons["load"] = tk.Button(bar, text="Load ISO...", command=on_load)
    buttons["build"] = tk.Button(bar, text="Build", command=lambda: run(lambda: build(log)))
    buttons["play"] = tk.Button(bar, text="Play", command=lambda: run(play))
    for b in buttons.values():
        b.pack(side="left", padx=(0, 8))
    run()  # first status check
    pump()
    win.mainloop()


# --- self-check --------------------------------------------------------------------------------------------

def selftest():
    import io
    import tempfile

    def rec(name, lba, size, is_dir=False):
        r = bytearray(33 + len(name) + (len(name) + 1) % 2)
        r[0], r[25], r[32] = len(r), 2 if is_dir else 0, len(name)
        struct.pack_into("<I4xI", r, 2, lba, size)
        r[33:33 + len(name)] = name
        return bytes(r)

    img = bytearray(24 * SECTOR)
    img[16 * SECTOR:16 * SECTOR + 6] = b"\x01CD001"
    img[16 * SECTOR + 156:16 * SECTOR + 190] = rec(b"\x00", 18, SECTOR, True)
    root = rec(b"\x00", 18, SECTOR, True) + rec(b"\x01", 18, SECTOR, True) + rec(b"MOHRS", 19, 2 * SECTOR, True) + rec(b"SYSTEM.CNF;1", 22, 5)
    img[18 * SECTOR:18 * SECTOR + len(root)] = root
    sub = rec(b"\x00", 19, 2 * SECTOR, True) + rec(b"\x01", 18, SECTOR, True)
    img[19 * SECTOR:19 * SECTOR + len(sub)] = sub  # the ELF's record sits in the directory's second sector
    img[20 * SECTOR:20 * SECTOR + 48] = rec(b"MOH3RDVD.ELF;1", 21, 3)
    img[21 * SECTOR:21 * SECTOR + 3] = b"ELF"
    img[22 * SECTOR:22 * SECTOR + 5] = b"BOOT2"
    assert list(iso_files(io.BytesIO(img))) == [("MOHRS/MOH3RDVD.ELF", 21, 3), ("SYSTEM.CNF", 22, 5)]

    global CFG
    real_cfg = CFG
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        CFG = d / "launcher.json"
        try:
            (d / "t.iso").write_bytes(img)
            load_iso(d / "t.iso", lambda _: None, d / "out", hashlib.sha1(b"ELF").hexdigest())
            assert (d / "out/MOH3RDVD.ELF").read_bytes() == b"ELF" and (d / "out/SYSTEM.CNF").read_bytes() == b"BOOT2"
            for bad_sha, image in (("0" * 40, img), (None, img[:16 * SECTOR] + bytes(8 * SECTOR))):  # wrong version, not an ISO
                (d / "bad.iso").write_bytes(image)
                try:
                    load_iso(d / "bad.iso", lambda _: None, d / "out2", bad_sha)
                    raise AssertionError("bad image accepted")
                except ValueError:
                    pass
            assert not (d / "out2").exists()
        finally:
            CFG = real_cfg
    evil = bytearray(img)
    evil[20 * SECTOR:20 * SECTOR + 48] = rec(b"..\\..\\X.ELF;1", 21, 3).ljust(48, b"\0")
    try:
        list(iso_files(io.BytesIO(evil)))
        raise AssertionError("path escape accepted")
    except ValueError:
        pass
    print("selftest ok")


def main(argv):
    cmd = argv[0] if argv else "gui"
    if cmd == "gui":
        try:
            import tkinter  # noqa: F401
        except ImportError as e:
            print(__doc__)
            print(f"No window ({e}; Debian/Ubuntu: sudo apt install python3-tk): use the commands above.\n")
            cmd = "status"
        else:
            return gui()
    if cmd == "status":
        state = status()
        for label, ok, detail in state:
            print(f"[{'ok' if ok else '--'}] {label}: {detail}")
        return 0 if all(ok for _, ok, _ in state) else 1
    if cmd == "load" and len(argv) == 2:
        load_iso(argv[1])
        build()
    elif cmd == "build":
        build()
    elif cmd == "play":
        return play().wait()
    elif cmd == "selftest":
        selftest()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except (ValueError, RuntimeError, OSError) as e:
        sys.exit(f"error: {e}")
