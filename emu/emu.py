"""Drive EmuHawk through bridge.lua.

Usage:
  py -3 emu.py start <rom>          launch EmuHawk with the bridge loaded
  py -3 emu.py run "<cmd>" ...      run commands (see bridge.lua), wait for completion
  py -3 emu.py stop                 close EmuHawk

Shorthand inside run: "a" = press A 6, "b" = press B 6, "sel", "start",
"up 16", "down 16", "left 16", "right 16" (frames held).
"""
import os
import subprocess
import sys
import time

DIR = os.path.dirname(os.path.abspath(__file__))
CMD = os.path.join(DIR, "cmd.txt")
DONE = os.path.join(DIR, "done.txt")
EMUHAWK = r"C:\projects\pokemon-platinum-dexnav\bizhawk\EmuHawk.exe"

SHORTHAND = {
    "a": "press A 6", "b": "press B 6", "x": "press X 6", "y": "press Y 6",
    "sel": "press Select 6", "start": "press Start 6",
}


def expand(cmd):
    parts = cmd.split()
    if cmd in SHORTHAND:
        return SHORTHAND[cmd]
    if parts[0] in ("up", "down", "left", "right"):
        frames = parts[1] if len(parts) > 1 else "16"
        return f"press {parts[0].capitalize()} {frames}"
    if parts[0] == "mash":  # mash <btn> <count>
        btn, count = parts[1], int(parts[2])
        return "\n".join([f"press {btn} 4\nwait 20"] * count)
    return cmd


def run(cmds, timeout=600):
    if os.path.exists(DONE):
        os.remove(DONE)
    with open(CMD + ".tmp", "w") as f:
        f.write("\n".join(expand(c) for c in cmds) + "\n")
    os.replace(CMD + ".tmp", CMD)
    end = time.time() + timeout
    while time.time() < end:
        if os.path.exists(DONE):
            time.sleep(0.05)
            with open(DONE) as f:
                print(f.read().strip())
            os.remove(DONE)
            return
        time.sleep(0.1)
    sys.exit("timed out waiting for emulator")


def test_config():
    """A copy of BizHawk's config without the mouse bound to the NDS touch axes: that binding feeds the
    mouse position every frame and overrides the stylus coordinates the bridge sets. The user's own
    config.ini is left alone."""
    import json
    src = os.path.join(os.path.dirname(EMUHAWK), "config.ini")
    dst = os.path.join(os.path.dirname(EMUHAWK), "config-test.ini")
    cfg = json.load(open(src, encoding="utf-8-sig"))
    for name, axes in cfg.get("AllTrollersAnalog", {}).items():
        if name == "NDS Controller":
            for axis in ("Touch X", "Touch Y"):
                if axis in axes:
                    axes[axis]["Value"] = ""
    # the Lua console is its own window and ignores the minimized start: open it on the second monitor
    # (right of the 2560-wide primary) so it never lands on the user's game
    lua = cfg.setdefault("CommonToolSettings", {}).setdefault("BizHawk.Client.EmuHawk.LuaConsole", {})
    lua.update({"_wndx": 2600, "_wndy": 100, "SaveWindowPosition": True, "TopMost": False})
    cfg["MainWndx"], cfg["MainWndy"] = 2600, 600
    json.dump(cfg, open(dst, "w", encoding="utf-8"), indent=2)
    return dst


def window_titles(pid):
    """Titles of the process's visible windows (to report a modal dialog that blocked startup)."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    titles = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            titles.append(buf.value)
        return True

    user32.EnumWindows(each, 0)
    return titles


def minimize_windows(pid):
    """Minimize every visible window of the process (main window and Lua console) without activating them."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True

    user32.EnumWindows(each, 0)
    for hwnd in found:
        user32.ShowWindow(hwnd, 7)  # SW_SHOWMINNOACTIVE


def main():
    op = sys.argv[1]
    if op == "start":
        for p in (CMD, DONE):
            if os.path.exists(p):
                os.remove(p)
        # start minimized and inactive (SW_SHOWMINNOACTIVE) so a test run never takes focus from what the user is
        # doing; set EMU_SHOW=1 to get a normal window
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = int(os.environ.get("EMU_SHOW", "7"))
        proc = subprocess.Popen([EMUHAWK, f"--config={test_config()}", f"--lua={os.path.join(DIR, 'bridge.lua')}", sys.argv[2]],
                         cwd=os.path.dirname(EMUHAWK), startupinfo=si)
        for _ in range(600):
            if os.path.exists(os.path.join(DIR, "buttons.txt")):
                minimize_windows(proc.pid)
                print("ready")
                return
            time.sleep(0.1)
        sys.exit("emulator did not load the bridge; its windows: " + "; ".join(window_titles(proc.pid)))
    elif op == "run":
        run(sys.argv[2:])
    elif op == "stop":
        subprocess.run(["taskkill", "/IM", "EmuHawk.exe", "/F"], capture_output=True)
        # taskkill returns before the process is gone; a lingering instance would steal bridge commands
        for _ in range(200):
            out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq EmuHawk.exe"], capture_output=True, text=True).stdout
            if "EmuHawk.exe" not in out:
                break
            time.sleep(0.1)


if __name__ == "__main__":
    main()
