# 🍅 Toma Timer

A lightweight, fast Pomodoro timer with a clean interface, session logging,
data export, and productivity statistics — built with Python + CustomTkinter.

## Features

- **Clean GUI** with dark/light theme toggle
- **Customizable** focus/break lengths and sessions-per-cycle
- **Session logging** in a local SQLite database
- **Data export** to CSV and JSON
- **Stats dashboard** with matplotlib charts:
  - Daily sessions (last 30 days)
  - Daily focus minutes (last 30 days)
  - Sessions by hour of day
  - Sessions by weekday
- **Productivity metrics**: total/avg session length, sessions per
  day/week/month, current streak, best day, most productive hour
- **Sound notifications** on session end — use the built-in chime or pick a
  custom `.mp3` / `.flac` / `.wav` / `.ogg` file
- **System tray** integration — timer keeps running in the background when the
  window is closed; show/pause/reset/quit from the tray
- **Pausable, resettable, skippable** at any time

## Requirements

- Python 3.10+ (developed on 3.14)
- A Tk-capable Python build (standard on most distros)
- An audio player on `PATH`: `ffplay`, `mpv`, `paplay`, `mpg123`, or `aplay`
  (for sound notifications — the app runs fine without one, just silently)
- Linux: a StatusNotifierItem host for the system tray (GNOME needs an
  extension like AppIndicator; KDE/budgie/xfce have one built in)

## Setup

```bash
# Create a virtual environment (skip if using a system Python with Tk)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

> **Note for `uv`-managed Python:** if Tk scripts aren't found, `main.py`
> auto-detects them from the interpreter's sibling `lib/` directory. No manual
> env vars needed.

## Run

```bash
source .venv/bin/activate
python src/main.py
```

Or use the launcher script:

```bash
./run.sh
```

## Usage

1. Press **Start** to begin a focus session (default 25 min).
2. When it ends, a chime plays and a break begins (short or long after every
   Nth focus session).
3. Use **Pause / Reset / Skip** as needed.
4. Open the **Stats** tab to view charts and metrics.
5. Use **Export CSV / JSON** to download your session history.
6. Tweak durations, sound, and behaviour in **⚙ Settings**.
7. Closing the window hides to the tray (if available); use the tray's
   **Quit** to exit fully.

## Data location

- Config: `~/.config/toma-timer/config.json`
- Database: `~/.local/share/toma-timer/sessions.db`
- Exports: `~/.local/share/toma-timer/exports/`

## Project structure

```
src/
├── main.py          # Entry point
├── app.py           # CustomTkinter GUI (Timer + Stats tabs, settings)
├── timer.py         # Pomodoro engine (threaded state machine)
├── database.py      # SQLite logging
├── export.py        # CSV / JSON export
├── stats.py         # Metrics + matplotlib figures
├── sound.py         # Notification sound (system player + synth chime)
├── tray.py          # System tray (pystray)
└── config.py        # Settings persistence
```

## License

MIT
