# Claude Budget HUD

A minimal, always-on-top floating desktop overlay that tracks your Anthropic API monthly spend and displays remaining budget in real time.

```
[C]  $31.27 left
     This month: $18.73 used
     Updated 12s ago
```

---

## Features

- **Live budget tracking** — fetches usage from the Anthropic API every 60 seconds (configurable)
- **Secure key storage** — API key stored in OS-native keychain (Credential Manager / Keychain / libsecret), never on disk
- **Encrypted config** — monthly budget and preferences stored with AES-256-GCM
- **Frameless, transparent** — blends into your desktop without visual noise
- **Pin mode** — `Ctrl+Shift+P` makes the window fully click-through
- **Edit mode** — drag to reposition; gear icon opens settings on hover
- **Dark/light mode** — follows your preference
- **System tray** — right-click for quick access; left-click to show
- **Launch on startup** — optional, per-OS autostart support

---

## Requirements

- Python 3.11+
- Linux: `libsecret-1-0` system package (`sudo apt install libsecret-1-0`)

---

## Installation & Running

```bash
# 1. Clone
git clone https://github.com/ssajaia/claude-budget-hud
cd claude-budget-hud

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run in development
python main.py
```

---

## Building a Distributable

Install PyInstaller (included in requirements.txt), then:

### macOS — `.app` bundle
```bash
make build-mac
# Creates: dist/Claude Budget HUD.app

# Optional: wrap in DMG
hdiutil create -volname 'Claude Budget HUD' \
  -srcfolder 'dist/Claude Budget HUD.app' \
  -ov -format UDZO dist/ClaudeBudgetHUD.dmg
```

### Windows — `.exe`
```bash
make build-win
# Creates: dist\Claude Budget HUD\Claude Budget HUD.exe
# Double-click to run, no Python installation needed
```

### Linux — standalone binary / AppImage
```bash
make build-linux
# Creates: dist/Claude Budget HUD/Claude Budget HUD

# Wrap in AppImage (requires appimagetool):
appimagetool "dist/Claude Budget HUD" ClaudeBudgetHUD.AppImage
```

---

## First Launch

1. The app opens the **Settings** dialog automatically.
2. Enter your Anthropic API key (`sk-ant-...`) — it is immediately stored in your OS keychain and never written to disk.
3. Set your monthly budget (USD).
4. Click **Save**. The HUD appears and begins polling.

---

## Controls

| Action | Result |
|---|---|
| `Ctrl+Shift+P` | Toggle pin (click-through) mode |
| Drag (edit mode) | Reposition the HUD |
| Hover → gear icon | Open settings |
| System tray → right-click | Menu: Show / Settings / Quit |

---

## Security Notes

- **API key**: stored exclusively in the OS keychain. Never logged, never written to any file.
- **Config file** (`~/.local/share/claude-budget-hud/config.enc` on Linux, platform equivalent on macOS/Windows): encrypted with AES-256-GCM. The encryption key itself is also stored in the keychain, meaning the config file is only decryptable on the same machine by the same user.
- File permissions on the config and key files are set to `600` (owner read/write only) on Unix systems.
- No telemetry. No analytics. No network calls other than to `api.anthropic.com`.

---

## Architecture

```
claude_budget_hud/
├── main.py                      # Qt app bootstrap, tray icon
├── ui/
│   ├── hud_window.py            # Floating HUD widget
│   └── settings_dialog.py       # Settings modal
├── services/
│   ├── api_client.py            # Anthropic usage API (background thread)
│   ├── budget_calculator.py     # Pure arithmetic, no I/O
│   └── secure_storage.py        # keyring wrapper
├── utils/
│   ├── encryption.py            # AES-GCM config encryption
│   ├── os_window_control.py     # Click-through per OS
│   └── assets.py                # Icon generation
├── requirements.txt
├── claude_budget_hud.spec       # PyInstaller build spec
└── Makefile
```

---

## Cost Estimation

Usage cost is computed from raw token counts using Sonnet 3.5 pricing as a conservative default:

| Token type | Price |
|---|---|
| Input | $3.00 / MTok |
| Output | $15.00 / MTok |
| Cache write | $3.75 / MTok |
| Cache read | $0.30 / MTok |

|!| The repository never contains API keys, encrypted configs, or runtime-generated secrets. All sensitive data is stored via OS keychain or encrypted locally at runtime.

If you use other models heavily, the displayed cost may differ from your actual invoice. Check your Anthropic Console for exact billing figures.
