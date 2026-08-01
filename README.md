# Promptly

Speak your prompts instead of typing them. A Windows desktop app that records your voice, transcribes it using Groq's Whisper API, and auto-pastes the text into whatever window is currently active — terminals, editors, browsers, chat apps, anywhere.

Built for use with [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and similar terminal-based AI tools, but works with any application that accepts text input.

---

## Features

- **Configurable global hotkey** — press to start recording, press again to stop. Works anywhere without admin privileges. The default is Ctrl+Alt+V; conflicts are reported and the previous working hotkey is restored.
- **Desktop app** — lives in your system tray. Click the tray icon to open the overlay, use it, close it when you're done.
- **Auto-paste** — transcribed text is automatically pasted into the active window via Ctrl+V, and also copied to the clipboard so you can paste it again anywhere.
- **Xbox Game Bar-style overlay** — a compact, dark, semi-transparent floating bar at the top-center of your screen. Shows the current state (Ready, Recording, Transcribing, Done, Error) with subtle color accents. Draggable to reposition. Has start/stop and close buttons.
- **System tray icon** — lives in your system tray with a context menu. Icon color changes to reflect the current state (gray = idle, red = recording, blue = transcribing, green = done).
- **First-launch setup** — on first run, the Settings dialog opens automatically so you can enter your API key. No manual setup needed.
- **Background transcription** — transcription runs in a background thread so the UI never freezes.
- **Test mode** — transcribe an audio or video file without needing a microphone. Supports WAV, MP3, M4A, OGG, FLAC, WEBM, MP4, AVI, MKV, MOV, WMV, TS.
- **Settings dialog** — configure your Groq API key, language, transcription mode, model, auto-paste, and hotkey. Settings are persisted through QSettings in the Windows registry.
- **Error handling** — friendly error messages for missing microphone, recordings that are too short, no speech detected, and API failures.
- **Portable** — single `.exe` file, no installation required. Works on any Windows 64-bit laptop.

---

## Quick Start (Using the .exe)

### 1. Download

Copy `Promptly.exe` to your laptop. Place it anywhere — Desktop, Documents, a dedicated folder, wherever you want.

### 2. Double-click

Double-click `Promptly.exe`. The Settings dialog will open automatically on first launch.

### 3. Enter your Groq API key

Get a free key at [console.groq.com/keys](https://console.groq.com/keys), paste it into the Settings dialog, and click **Save**.

### 4. You're ready

A gray microphone icon appears in your system tray. Click it to open the overlay, then:

- Press **Ctrl+Alt+V** or click **▶** to start recording
- Speak your prompt
- Press **Ctrl+Alt+V** or click **⏹** to stop
- Your text is transcribed and pasted into whatever window is active

That's it. No Python installation, no dependencies, no setup scripts.

---

## User Experience Walkthrough

### First time using the app

1. **Double-click** `Promptly.exe`
2. Settings dialog opens automatically (no API key detected)
3. Paste your Groq API key (`gsk_...`) → click **Save**
4. A gray 🎤 icon appears in your system tray — you're ready

### Day-to-day usage

1. The app is running in your system tray (gray mic icon)
2. **Click the tray icon** → overlay bar appears at the top-center of your screen
3. Click **▶** on the overlay (or press **Ctrl+Alt+V** anywhere) → red "Recording" state
4. Speak your prompt naturally
5. Click **⏹** on the overlay (or press **Ctrl+Alt+V** again) → blue "Transcribing" state
6. A moment later → green "Pasted" state → your text is typed into your active window
7. Click **×** to close the overlay when you're done
8. The app stays in the tray — click the tray icon anytime to open the overlay again

### Using the hotkey (fastest method)

You don't even need to open the overlay first:

1. Press **Ctrl+Alt+V** → overlay appears + recording starts immediately
2. Speak your prompt
3. Press **Ctrl+Alt+V** again → stops, transcribes, pastes

Two keystrokes and your spoken words appear in your terminal, editor, or browser.

---

## How It Works

```
┌───────────────┐     ┌────────────┐     ┌──────────────┐     ┌────────────┐
│ Ctrl+Alt+V    │────▶│  Recording │────▶│ Transcribing │────▶│   Pasted   │
│  or ▶ button  │     │  from mic  │     │  via Groq    │     │  + copied  │
└───────────────┘     └────────────┘     │  Whisper API │     │ to clipboard│
                                         └──────────────┘     └────────────┘
```

**Step by step:**

1. You trigger recording (**Ctrl+Alt+V**, ▶ button, or left-click the tray icon)
2. A red recording indicator appears on the overlay
3. You speak your prompt naturally
4. You stop recording (**Ctrl+Alt+V** again or ⏹ button)
5. The audio is sent to Groq's Whisper API for transcription
6. The transcribed text is copied to your clipboard **and** pasted into your active window via Ctrl+V
7. You press Enter in your terminal to submit

The entire cycle takes just a few seconds depending on recording length.

---

## Tech Stack

| Component | Technology | Purpose |
|---|---|---|
| GUI & System Tray | PyQt6 | Overlay widget, tray icon, settings dialog, signals/slots |
| Global Hotkey | Win32 `RegisterHotKey` via `ctypes` | Ctrl+Alt+V hotkey that works globally without admin privileges |
| Auto-Paste | Win32 `SendInput` via `ctypes` | Simulates Ctrl+V to paste into any window |
| Microphone Recording | `sounddevice` + `numpy` + `scipy` | Captures 16kHz mono audio, saves as WAV |
| Transcription | `groq` SDK | Calls Groq's Whisper API (cloud-based, no local GPU needed) |
| Clipboard | `pyperclip` | Cross-platform clipboard access |
| Configuration | `QSettings` | API key and settings persistence in the Windows registry |
| Packaging | PyInstaller | Bundles everything into a single `.exe` |

All Windows API calls use `ctypes` (built into Python) — no extra packages needed for hotkeys or auto-paste.

---

## Requirements

### For end users (running the .exe)

- **OS:** Windows 64-bit
- **Microphone:** Any default recording device (not needed for test mode)
- **Internet:** Required for Groq Whisper API
- **Groq API key:** Get one free at [console.groq.com/keys](https://console.groq.com/keys)

### For developers (running from source)

- **OS:** Windows (uses Win32 APIs for hotkeys and auto-paste)
- **Python:** 3.13+
- **Package manager:** [uv](https://docs.astral.sh/uv/)
- **Microphone:** Any default recording device (not needed for test mode)
- **Groq API key:** Get one free at [console.groq.com/keys](https://console.groq.com/keys)

---

## Setup (Running from Source)

### 1. Clone and install dependencies

```bash
cd voice-input
uv sync
```

This creates a virtual environment and installs the application dependencies.

### 2. Add your Groq API key

Run the app and enter your key in the Settings dialog. The key is stored by
QSettings in the current Windows user's registry and is not written beside the
executable.

Get your key at [console.groq.com/keys](https://console.groq.com/keys).

### 3. Run the app

```bash
uv run python main.py
```

The app starts silently — a gray microphone icon appears in your system tray.

---

## Usage

### Recording your voice

| Action | How |
|---|---|
| Start recording | Press **Ctrl+Alt+V**, or click **▶** on the overlay |
| Stop recording | Press **Ctrl+Alt+V** again, or click **⏹** on the overlay |
| Result | Text is pasted into your active window and copied to clipboard |

### Opening / closing the overlay

| Action | How |
|---|---|
| Open overlay | **Left-click** the tray icon |
| Close overlay | Click the **×** button on the overlay |
| Alternative close | **Left-click** the tray icon again (toggles) |

Note: Closing the overlay during recording will cancel it. Closing during transcription lets the transcription finish — the result still goes to your clipboard.

### Test mode (no microphone needed)

Right-click the tray icon → **"🧪 Test with audio file..."** → select any audio or video file. The app will transcribe it and paste the result. Your original file is not modified or deleted.

### System tray menu

Right-click the tray icon to access:

- **🎤 Show Overlay / Hide Overlay** — toggle the overlay window
- **🧪 Test with audio file...** — transcribe a file without a microphone
- **⚙️ Settings** — configure API key, model, and auto-paste
- **❌ Quit** — exit the app

### Settings

| Setting | Options | Default |
|---|---|---|
| Groq API Key | Your API key (`gsk_...`) | Empty until configured |
| Model | Whisper Large v3 Turbo (fast) / Whisper Large v3 (accurate) | Turbo |
| Auto-paste | On/Off | On |
| Hotkey | Any supported modified key combination | Ctrl+Alt+V |

Settings are saved through QSettings in the Windows registry.

---

## Overlay States

The floating overlay shows the current app state with distinct visual cues:

| State | Icon | Text | Background | Bottom accent |
|---|---|---|---|---|
| Ready | 🎤 | Promptly | Dark charcoal | Subtle white |
| Recording | ⏺ | Recording | Dark red tint | Subtle red |
| Transcribing | ⏳ | Transcribing | Dark blue tint | Subtle blue |
| Done | ✓ | Pasted | Dark green tint | Subtle green |
| Error | ⚠ | Error message | Dark red tint | Subtle red |

The overlay is:
- **Always on top** — visible over all windows
- **Draggable** — click and drag to reposition
- **Compact** — 340×44 pixels
- **Semi-transparent** — dark charcoal base with subtle colored accents
- **Drop-shadowed** — visible on both light and dark backgrounds

After Done or Error states, the application returns to Ready after a few seconds.

---

## Project Structure

```
voice-input/
├── main.py              # Entry point — bootstraps PyQt6 app
├── app.py               # PromptlyApp — orchestrates all components
├── recorder.py          # AudioRecorder — captures mic audio via sounddevice
├── transcriber.py       # Groq Whisper API transcription
├── paster.py            # Clipboard copy + Ctrl+V simulation via Win32
├── hotkey.py            # Global Ctrl+Alt+V hotkey via Win32 RegisterHotKey
├── overlay.py           # Floating overlay widget (Xbox Game Bar style)
├── settings_dialog.py   # Settings dialog (API key, model, auto-paste)
├── pyproject.toml       # Project config and dependencies
└── uv.lock              # Locked dependency versions
```

---

## Architecture

### State Machine

```
IDLE ──(Ctrl+Alt+V/▶)──▶ RECORDING ──(Ctrl+Alt+V/⏹)──▶ TRANSCRIBING ──(done)──▶ IDLE
  ▲                                              │
  └──────────────────(error)─────────────────────┘
```

The `PromptlyApp` in `app.py` manages five states:

- **IDLE** — waiting for the user to trigger recording
- **RECORDING** — microphone is capturing audio
- **TRANSCRIBING** — audio is being sent to Groq for transcription
- **DONE** — transcription was pasted or copied successfully
- **ERROR** — a recoverable error is shown and reported through the tray

### Thread Safety

- The **global hotkey** listener runs on its own daemon thread (Win32 message loop via `PeekMessageW`)
- When Ctrl+Alt+V is pressed, the hotkey thread emits a `pyqtSignal` that crosses safely to the Qt main thread
- **Transcription** runs in a `QThread` worker so the UI stays responsive during API calls
- All UI updates happen on the main Qt thread

### Audio Pipeline

1. `AudioRecorder` captures 16kHz mono audio from the default microphone into numpy buffers
2. Audio is saved to a temporary WAV file via `scipy.io.wavfile`
3. The WAV file is sent to Groq's Whisper API
4. The temp file is deleted after transcription (or kept in test mode)

### Auto-Paste Mechanism

1. `pyperclip.copy(text)` copies the transcribed text to the clipboard
2. Win32 `SendInput` simulates: Ctrl down → V down → V up → Ctrl up
3. The text is pasted into whatever window is currently focused
4. The text remains on the clipboard — you can Ctrl+V again anywhere

---

## Building the App

PyInstaller is included as a dev dependency. To build:

### Single-file .exe (recommended for sharing)

```bash
uv run pyinstaller --noconfirm --onefile --windowed --name "Promptly" \
  --distpath "dist-onefile" --workpath "build-onefile" main.py
```

Output: `dist-onefile/Promptly.exe` (~81MB)

### Folder build (faster startup)

```bash
uv run pyinstaller --noconfirm --windowed --name "Promptly" \
  --distpath "dist-folder" --workpath "build-folder" main.py
```

Output: `dist-folder/Promptly/` (~202MB total, starts instantly)

---

## Dependencies

Listed in `pyproject.toml`:

| Package | Version | Purpose |
|---|---|---|
| `groq` | >=1.1.2 | Groq API client for Whisper transcription |
| `numpy` | >=2.4.4 | Audio buffer handling |
| `pyperclip` | >=1.11.0 | Clipboard access |
| `PyQt6` | >=6.11.0 | GUI framework — overlay, tray icon, settings |
| `scipy` | >=1.17.1 | WAV file writing |
| `sounddevice` | >=0.5.5 | Microphone audio capture |

Managed by [uv](https://docs.astral.sh/uv/) — uses `uv.lock` for reproducible installs.

---

## Troubleshooting

### "I can't see the overlay"

Click the **tray icon** (the gray microphone in your system tray) to open the overlay. If you don't see the tray icon, check the overflow area — click the `^` arrow in the system tray to reveal hidden icons.

### "No microphone found"

Connect a microphone or headset. The app uses Windows' default recording device. You can verify your devices with: `uv run python -c "import sounddevice as sd; print(sd.query_devices())"`

### "Transcription failed"

- Check your internet connection
- Verify your Groq API key is valid in Settings (right-click tray → ⚙️ Settings)
- Ensure the Groq service is up at [status.groq.com](https://status.groq.com)

### "Ctrl+Alt+V doesn't work"

If another application has registered the same hotkey, Promptly shows a warning,
restores the previous working hotkey, and keeps running. Choose another hotkey
in Settings; the change takes effect immediately.

### "Text isn't being pasted"

Make sure the target window is the **active/focused window** when you stop recording. The paste happens via Ctrl+V into whatever window Windows considers active. Also check that auto-paste is enabled in Settings.

### "Settings didn't open on first launch"

This can happen if you previously had the app installed and your API key is still saved in Windows registry. The app remembers your key across reinstalls. If you need to change your key, right-click the tray icon → **⚙️ Settings** at any time.

### "API key error after reinstall"

The API key is stored in the Windows registry, not beside the executable, so
moving or replacing the app folder does not remove it. If you still get an
error, right-click the tray icon → **⚙️ Settings** and save the key again.
