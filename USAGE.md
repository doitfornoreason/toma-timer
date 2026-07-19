# Usage & Cross-Platform Notes

## Syncing across machines

1. Push this repo to a remote (GitHub/GitLab/etc.)
2. Clone on Ubuntu:
   ```bash
   git clone <remote-url>
   cd toma-timer
   ```
3. Set up:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

## Ubuntu tips

### Python + Tk

- Ubuntu's system Python (from `python3` package) includes Tk **by default**.
  Just install `python3-tk` if it's missing:
  ```bash
  sudo apt install python3-tk
  ```
- On Arch, uv-managed Python auto-detects TCL/TK libs. On Ubuntu, system
  Python works out of the box — no env var hacks needed.

### Sound

- The app tries `ffplay` (ffmpeg) → `mpv` → `paplay` (PulseAudio) →
  `mpg123` → `aplay` for notification sounds.
- Ubuntu typically has `paplay` available through PulseAudio/PipeWire.
  Install ffmpeg for best coverage:
  ```bash
  sudo apt install ffmpeg
  ```

### System tray

- Ubuntu GNOME **does not** ship a StatusNotifierItem host by default.
  Install an extension:
  - [AppIndicator/KStatusNotifierItem Support](https://extensions.gnome.org/extension/615/appindicator-and-kstatusnotifieritem-support/)
- KDE, Budgie, Xfce, Cinnamon have tray support built in.
- If tray fails to dock, the app falls back to close=quit behaviour
  (no hidden unreachable window).

### Wayland notes

- On Ubuntu 22.04+ the default session is Wayland. The app works fine,
  but tray icons may not appear without the GNOME extension above.
- x11 sessions have no tray issues.

### File locations (same on all Linux)

| Data | Path |
|------|------|
| Config | `~/.config/toma-timer/config.json` |
| Database | `~/.local/share/toma-timer/sessions.db` |
| Exports | `~/.local/share/toma-timer/exports/` |

Back up the `sessions.db` file if you want to preserve data when moving
machines, or just copy the whole `~/.local/share/toma-timer/` directory.

### Ubuntu 24.04 specific

- Python 3.12 ships with working Tk — no extra steps.
- The `matplotlib` backend (`TkAgg`) works out of the box.
- If you see blurry text, set `CTK_WIDGET_SCALING` or adjust the
  font scaling in `app.py` (`ctk.set_widget_scaling(1.5)` →
  try `1.25` or `1.0` for HiDPI).

## Running

```bash
source .venv/bin/activate
python src/main.py
```

Or use the launcher:
```bash
./run.sh
```
