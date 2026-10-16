# Hey Jev

A voice assistant for **Mac and Windows**. Say "Hey Jev" or hold the right Option (Mac) / Right Alt (Windows) key, then speak. It runs the command and answers back.

- **Laya** (local preferred) or cloud LLM classifies every command in one call
- **Fish Audio S2.1 Pro** speaks every reply (emotion tags supported)
- **Whisper** local on Mac; cloud STT on Windows (Smart App Control can block local DLLs)
- Questions that are not commands go to Claude Haiku via OpenRouter

**Works on macOS and Windows.** Windows uses a system-tray icon (`tray.py`), media keys, PowerShell for theme/volume, and `rundll32` for lock/sleep.

## What it can do

Open / quit / hide / minimise / focus apps, open websites or a new browser tab, volume up/down/mute/set, Spotify play/pause/next/previous, dark mode, lock or sleep the computer. Compound commands work: "pause Spotify and open Slack".

### Adding apps

Edit `apps.json`:

```json
"notion": "Notion",
"claude_code": {"app": "Claude", "say": "Claude Code", "heard_as": ["cloud code", "clawed code"]}
```

Restart after changes. On Mac you can also use the Apps tab in the window.

Timers, reminders and dictation work on both platforms.

**Privacy:** On Windows, speech-to-text and classification use OpenRouter when local models are blocked. Dictation always uploads audio.

## What you need

- Python 3.10+
- Spotify desktop app (for music commands)
- Keys in a `.env` file in the repo root:

```
FISH_AUDIO_API_KEY=...
OPENROUTER_API_KEY=...
# OPENAI_API_KEY=...   # optional, for direct dictation
```

Fish Audio free model is available until end of November 2026.

## Windows setup

```bash
git clone https://github.com/Ascendlabs-webs/jarvis.git
cd jarvis
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install pystray pillow
```

Create the `.env` above, then:

```bash
.venv\Scripts\python tray.py
```

Tray icon appears. Hold **Right Alt** and talk, or choose "Hey Jev (always listening)" from the menu. Allow microphone access if prompted.

## Mac setup

```bash
git clone https://github.com/Ascendlabs-webs/jarvis.git
cd jarvis
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python setup.py py2app -A
open "dist/Hey Jev - Fish Audio.app"
```

Or from terminal: `.venv/bin/python siri.py --ui` / `--wake` / `--text "open spotify"`.

First launch on Mac: paste keys in the Keys tab (saved to Keychain), grant Microphone + Accessibility + Automation permissions.

## Running from the terminal (both platforms)

```bash
python siri.py               # hold-to-talk
python siri.py --wake        # always listening
python siri.py --text "open spotify and turn it down"
python siri.py --ui          # Mac window (shows as Python in Dock)
```

Keys can live in `.env` (takes priority over Keychain on Mac).

## Troubleshooting

- **Windows: tray won't start** – install `pystray pillow sounddevice`.
- **401 / missing keys** – check `.env`.
- **Commands fail** – on Windows volume/theme use approximate methods (media keys + registry). Full precise volume needs extra libraries.
- **Local Laya fails on Windows** – falls back to OpenRouter automatically.
- **Logs** – Mac: `~/Library/Logs/Hey Jev.log`. Windows: console output + `%TEMP%\heyjev_single.log`.

## Files

- `siri.py` – main logic, classification, actions, TTS, STT
- `win_actions.py` – Windows implementations of app/volume/theme/system actions
- `tray.py` – Windows system tray + hotkey
- `assistant_ui.py` / `app.py` / `setup.py` – Mac GUI and py2app
- `apps.json` – controllable apps
- `secrets_store.py` – Keychain / .env
- `dictation.py` / `bubble.py` – dictation

Voice ID is set near the top of `siri.py` (`VOICE_ID`). Change it and replies re-render on next launch.
