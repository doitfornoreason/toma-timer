# Work Log — Toma Timer

## [2026-07-19] Initial build (Phase 1–7)
- did: Planned + implemented full Pomodoro timer app
  - Stack: Python 3.14 + CustomTkinter + matplotlib + pystray + SQLite
  - Modules: config, database, timer (threaded state machine), sound, export, stats, tray, app, main
  - GUI: Timer tab (countdown, progress, cycle dots, start/pause/reset/skip) + Stats tab (4 matplotlib charts + metrics) + Settings dialog (durations, auto-start, sound file picker, theme)
  - Dark/light theme toggle, CSV/JSON export, system tray (graceful degrade when no StatusNotifierItem host)
  - Sound: system player (ffplay/mpv/paplay/mpg123/aplay) + synth default chime, custom mp3/flac/wav/ogg support
- decided:
  - CustomTkinter over web/Tauri (lightweight, native tray, matches "no interactive graph" constraint)
  - matplotlib over Plotly (static graphs, no extra weight — per user)
  - uv-managed Python for Tk (system python lacked libtk8.6.so; sudo unavailable); main.py auto-detects TCL/TK lib path
  - Sound via system player, not pygame (pygame build hung; avoids heavy dep)
  - Tray optional + watchdog: if dock fails, deactivate so close=quit instead of hiding to unreachable tray
- open:
  - Packaging (PyInstaller single binary) — not done
  - .desktop file for app menu integration — not done
  - Real-desktop tray testing (this Wayland env has no StatusNotifierItem host)
- issues:
  - pygame build hung → dropped, use system audio players
  - system python missing libtk8.6.so → use uv python with Tk; auto-set TCL_LIBRARY/TK_LIBRARY in main.py
  - pystray AssertionError spam on dock fail → redirect stderr + watchdog deactivation
- tested:
  - DB start/end/query, engine cycle+pause+resume+reset+skip+logging, stats metrics+figure (dark/light), CSV/JSON export
  - GUI smoke test (tab switch, stats refresh, timer controls, settings dialog, export, theme toggle) — 0 errors
