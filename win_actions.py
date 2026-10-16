"""Windows hands for Hey Jev: apps, Spotify media keys, browser, chimes, volume, dark mode, lock/sleep.

Mac originals all shell to osascript/afplay; every function here uses only the
Win32 API, os.startfile, taskkill, webbrowser, winsound, or PowerShell. No new dependencies.
"""
import ctypes
import os
import shutil
import subprocess
import time
import webbrowser

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi

SW_HIDE, SW_RESTORE, SW_MINIMIZE = 0, 9, 6
VK_PLAY_PAUSE, VK_NEXT, VK_PREV = 0xB3, 0xB0, 0xB1
KEYEVENTF_KEYUP = 0x0002

BROWSERS_WIN = {"chrome": "chrome", "brave": "brave"}  # via `start`; safari -> default


# ---------------------------------------------------------------- windows
def _windows_for_exe(exe):
    """Visible titled top-level windows owned by a process image name."""
    exe = exe.lower()
    out = []
    HWND, LPARAM, BOOL, DWORD = ctypes.wintypes.HWND, ctypes.wintypes.LPARAM, ctypes.wintypes.BOOL, ctypes.wintypes.DWORD
    pid = DWORD()

    @ctypes.WINFUNCTYPE(BOOL, HWND, LPARAM)
    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or not user32.GetWindowTextLengthW(hwnd):
            return True
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        h = kernel32.OpenProcess(0x1000, False, pid.value)
        if h:
            try:
                buf = ctypes.create_string_buffer(260)
                if psapi.GetModuleFileNameExA(h, None, buf, 260):
                    if os.path.basename(buf.value.decode(errors="replace")).lower() == exe:
                        out.append(hwnd)
            finally:
                kernel32.CloseHandle(h)
        return True

    user32.EnumWindows(cb, 0)
    return out


def find_window(exe):
    wins = _windows_for_exe(exe)
    return wins[0] if wins else None


# ---------------------------------------------------------------- apps
def resolve_target(name):
    """App name -> launchable thing: existing path, PATH hit, else the bare name
    (cmd's `start` resolves App Paths registry + PATH, e.g. Spotify, chrome)."""
    if os.path.exists(name):
        return name
    hit = shutil.which(name)
    return hit or name


def open_app_win(name, wait=5.0):
    target = resolve_target(name)
    if os.path.exists(target) or shutil.which(target):
        subprocess.Popen([target] if os.path.exists(target) else [target],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run(["cmd", "/c", "start", "", target],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    exe = os.path.basename(target).lower()
    if not exe.endswith(".exe"):
        exe += ".exe"
    t = time.time()
    while time.time() - t < wait and not find_window(exe):
        time.sleep(0.2)
    focus_exe(exe)


def focus_exe(exe):
    hwnd = find_window(exe)
    if not hwnd:
        raise RuntimeError(f"{exe} has no window to focus")
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)


def quit_exe(exe):
    r = subprocess.run(["taskkill", "/IM", exe, "/F"],
                       capture_output=True, text=True)
    if r.returncode and "not found" not in (r.stderr + r.stdout).lower():
        raise RuntimeError((r.stderr or r.stdout).strip() or "taskkill failed")


def hide_exe(exe):
    hwnd = find_window(exe)
    if not hwnd:
        raise RuntimeError(f"{exe} has no window to hide")
    user32.ShowWindow(hwnd, SW_HIDE)


def minimise_exe(exe):
    hwnd = find_window(exe)
    if not hwnd:
        raise RuntimeError(f"{exe} has no window to minimise")
    user32.ShowWindow(hwnd, SW_MINIMIZE)


def process_running(exe):
    r = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {exe}", "/NH"],
                       capture_output=True, text=True)
    return exe.lower() in r.stdout.lower()


# ---------------------------------------------------------------- spotify (media keys, no API key needed)
def media_key(vk):
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def ensure_spotify():
    if not process_running("Spotify.exe"):
        open_app_win("Spotify", wait=8.0)
        time.sleep(1.0)


# ---------------------------------------------------------------- browser
def open_site_win(url, browser_key=None):
    exe = BROWSERS_WIN.get(browser_key) if browser_key else None
    if exe:
        subprocess.run(["cmd", "/c", "start", "", exe, "--new-tab", url],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        webbrowser.open(url, new=2)


def new_tab_win(browser_key=None):
    exe = BROWSERS_WIN.get(browser_key) if browser_key else None
    if exe:
        open_app_win(exe)
        time.sleep(0.3)
        from pynput.keyboard import Controller, Key  # local: pynput already a dep
        k = Controller()
        with k.pressed(Key.ctrl):
            k.press("t")
            k.release("t")
    else:
        webbrowser.open("", new=2)


# ---------------------------------------------------------------- volume / system (PowerShell / rundll32, no extra deps)
def _ps(cmd):
    r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                       capture_output=True, text=True, timeout=10)
    if r.returncode:
        raise RuntimeError(r.stderr.strip() or "PowerShell failed")
    return r.stdout.strip()


def volume_win(delta=None, absolute=None, mute=None):
    """Rough volume control via PowerShell COM. absolute/delta are 0-100."""
    if mute is True:
        _ps("(New-Object -ComObject WScript.Shell).SendKeys([char]173)")  # volume mute key
        return
    if mute is False:
        _ps("(New-Object -ComObject WScript.Shell).SendKeys([char]173)")  # toggle; better than nothing
        return
    if absolute is not None:
        # Approximate with media keys or note limitation; full control needs pycaw
        steps = max(0, min(50, absolute // 2))
        for _ in range(steps):
            user32.keybd_event(0xAF, 0, 0, 0)  # VK_VOLUME_UP
            user32.keybd_event(0xAF, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.02)
        return
    if delta is not None:
        vk = 0xAF if delta > 0 else 0xAE  # VOLUME_UP / VOLUME_DOWN
        n = abs(delta) // 2
        for _ in range(max(1, n)):
            user32.keybd_event(vk, 0, 0, 0)
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.02)


def dark_mode_win(on=None):
    """Set Windows app theme. on=True dark, False light, None toggle."""
    if on is None:
        # Toggle: read current then flip
        try:
            cur = _ps('(Get-ItemProperty -Path "HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize" -Name AppsUseLightTheme).AppsUseLightTheme')
            on = cur.strip() == "1"
        except Exception:
            on = True
    val = 0 if on else 1
    _ps(f'New-ItemProperty -Path "HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize" -Name AppsUseLightTheme -Value {val} -Type Dword -Force | Out-Null')
    _ps(f'New-ItemProperty -Path "HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize" -Name SystemUsesLightTheme -Value {val} -Type Dword -Force | Out-Null')


def lock_win():
    subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=False)


def sleep_win():
    subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], check=False)


# ---------------------------------------------------------------- sound
def chime(kind="ok"):
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_OK if kind == "ok" else winsound.MB_ICONASTERISK)
    except Exception:
        pass


# ---------------------------------------------------------------- patch table for siri.ACTIONS
def patch_actions(actions, apps):
    """Swap the macOS hands for Windows ones. apps maps key -> Mac app name."""
    WIN_EXE = {"spotify": "Spotify.exe"}

    def exe_for(key):
        if key in WIN_EXE:
            return WIN_EXE[key]
        base = apps.get(key, key)
        return base if base.lower().endswith(".exe") else base + ".exe"

    actions["app_open"] = lambda key: open_app_win(apps.get(key, key))
    actions["app_quit"] = lambda key: quit_exe(exe_for(key))
    actions["app_hide"] = lambda key: hide_exe(exe_for(key))
    actions["app_minimise"] = lambda key: minimise_exe(exe_for(key))
    actions["app_focus"] = lambda key: (open_app_win(apps.get(key, key))
                                        if not find_window(exe_for(key))
                                        else focus_exe(exe_for(key)))
    actions["media_play"] = lambda _: (ensure_spotify(), media_key(VK_PLAY_PAUSE))
    actions["media_pause"] = lambda _: (ensure_spotify(), media_key(VK_PLAY_PAUSE))
    actions["media_next"] = lambda _: (ensure_spotify(), media_key(VK_NEXT))
    actions["media_previous"] = lambda _: (ensure_spotify(), media_key(VK_PREV))
    # Volume / system
    actions["volume_up"] = lambda _: volume_win(delta=20)
    actions["volume_down"] = lambda _: volume_win(delta=-20)
    actions["volume_mute"] = lambda _: volume_win(mute=True)
    actions["volume_unmute"] = lambda _: volume_win(mute=False)
    actions["volume_set"] = lambda lvl: volume_win(absolute=int(lvl) if isinstance(lvl, (int, str)) and str(lvl).isdigit() else 50)
    actions["display_dark_on"] = lambda _: dark_mode_win(True)
    actions["display_dark_off"] = lambda _: dark_mode_win(False)
    actions["display_toggle"] = lambda _: dark_mode_win(None)
    actions["system_lock"] = lambda _: lock_win()
    actions["system_sleep"] = lambda _: sleep_win()
    # Spotify volume roughly via media keys (precise API needs extra dep)
    actions["spotify_volume_up"] = lambda _: (ensure_spotify(), media_key(0xAF))  # volume up while focused
    actions["spotify_volume_down"] = lambda _: (ensure_spotify(), media_key(0xAE))
    return actions
