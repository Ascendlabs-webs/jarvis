"""Windows tray home for Hey Jev: icon, mode switch, global Right-Alt hotkey, autostart.

Runs the voice assistant headless (pythonw, no console). Status shows in the
tray tooltip; finishers (timer done, errors) pop a balloon. Talk with Right Alt
(hold it) or switch to Hey Jev always-listening mode from the menu.
"""
import os
import queue
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None

try:
    import pystray
    from pystray import Menu, MenuItem
except ImportError:
    pystray = None

from pynput import keyboard

controls = queue.Queue()
_state = {"text": "Starting", "mode": "ptt"}
_icon = None


def make_icon(color=(35, 134, 54)):
    img = Image.new("RGB", (64, 64), (17, 17, 17))
    d = ImageDraw.Draw(img)
    d.ellipse((14, 14, 50, 50), fill=color)
    return img


def notify(state, detail=""):
    _state["text"] = f"{state}" + (f" {detail}" if detail else "")
    if _icon:
        _icon.title = f"Hey Jev — {_state['text'][:120]}"
        if state in ("Time's up", "Something went wrong"):
            _icon.notify(detail or state, "Hey Jev")
        elif state == "Ready" and not _state.get("welcomed"):
            _state["welcomed"] = True
            _icon.notify("Hold Right Alt and talk, or say \u201cHey Jev\u201d in Hey-Jev mode.", "Hey Jev is ready")


def set_mode(name):
    _state["mode"] = name
    controls.put(("mode", name))
    notify("Ready", "Say \u201cHey Jev\u201d and your command" if name == "wake"
            else "Hold right Alt to talk")


# Windows reports Right Alt as AltGr (plus a phantom Left Ctrl), never as alt_r.
# Match what the OS actually delivers so hold-to-talk fires.
_PTT_KEYS = tuple(k for k in (keyboard.Key.alt_r, getattr(keyboard.Key, "alt_gr", None)) if k is not None)


def on_press(key):
    if key in _PTT_KEYS:
        controls.put("press")


def on_release(key):
    if key in _PTT_KEYS:
        controls.put("release")


def quit_app(icon, _item):
    icon.stop()


_mutex_handle = None


def _single_instance():
    """Only one tray app at a time: extras (double-clicks, relogins) exit silently."""
    global _mutex_handle
    if sys.platform == "win32":
        import ctypes
        import time as _time
        from ctypes import wintypes
        log = os.path.join(os.environ.get("TEMP", HERE), "heyjev_single.log")
        pid = os.getpid()
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"{_time.strftime('%H:%M:%S')} pid={pid} trying\n")
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        # kept in a global so the handle stays open (and the mutex held) for life
        _mutex_handle = kernel32.CreateMutexW(None, False, "Local\\HeyJevTrayMutex")
        twin = ctypes.get_last_error() == 183  # ERROR_ALREADY_EXISTS
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"{_time.strftime('%H:%M:%S')} pid={pid} {'EXIT-twin' if twin else 'HELD'}\n")
        if twin:
            sys.exit(0)


def run_tray():
    global _icon
    if pystray is None or Image is None:
        raise RuntimeError("tray needs pystray + pillow: pip install pystray pillow")
    try:
        import sounddevice  # noqa: F401  (mic must exist before we claim the mutex)
    except ImportError:
        raise RuntimeError("tray needs sounddevice: pip install sounddevice")
    _single_instance()
    with open(os.path.join(os.environ.get("TEMP", HERE), "heyjev_single.log"),
              "a", encoding="utf-8") as f:
        f.write(f"holder pid={os.getpid()} exe={sys.executable}\n")
    if pystray is None or Image is None:
        raise RuntimeError("tray needs pystray + pillow: pip install pystray pillow")

    from siri import run_voice_assistant  # lazy: pulls torch/laya, slow first import

    worker = threading.Thread(
        target=run_voice_assistant,
        kwargs={"notify": notify, "controls": controls, "mode": _state["mode"], "mic": ""},
        daemon=True,
    )
    worker.start()

    keys = keyboard.Listener(on_press=on_press, on_release=on_release)
    keys.daemon = True
    keys.start()

    menu = Menu(
        MenuItem(lambda _: _state["text"][:80], lambda *_: None, enabled=False),
        Menu.SEPARATOR,
        MenuItem("Hold Right Alt", lambda *_: set_mode("ptt"),
                 checked=lambda _: _state["mode"] == "ptt"),
        MenuItem("Hey Jev (always listening)", lambda *_: set_mode("wake"),
                 checked=lambda _: _state["mode"] == "wake"),
        Menu.SEPARATOR,
        MenuItem("Quit", quit_app),
    )
    _icon = pystray.Icon("hey-jev", make_icon(), "Hey Jev — Starting", menu)
    notify("Starting", "Loading Whisper\u2026")
    _icon.run()


STARTUP_BAT = (
    "@echo off\r\n"
    f'start /min "" "{HERE}\\.venv\\Scripts\\pythonw.exe" "{HERE}\\tray.py"\r\n'
)


def install_autostart():
    """ISTA: drop a launcher in the user's Startup folder. Returns its path."""
    startup = os.path.join(os.environ["APPDATA"],
                           r"Microsoft\Windows\Start Menu\Programs\Startup")
    path = os.path.join(startup, "HeyJev.bat")
    with open(path, "w", encoding="utf-8") as f:
        f.write(STARTUP_BAT)
    return path


if __name__ == "__main__":
    if "--install-autostart" in sys.argv:
        print(install_autostart())
    else:
        run_tray()
