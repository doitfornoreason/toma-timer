"""Toma Timer entry point.

Run with:  python src/main.py   (or activate venv first)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Make `src/` importable as top-level modules (config, timer, app, ...).
sys.path.insert(0, str(Path(__file__).resolve().parent))


def _ensure_tcl_tk_lib() -> None:
    """Some standalone Python builds (e.g. uv-managed CPython) ship Tcl/Tk
    scripts outside the interpreter's default search path. If init.tcl can't
    be found, point TCL_LIBRARY/TK_LIBRARY at the sibling lib dir."""
    for var, sub in (("TCL_LIBRARY", "tcl8.6"), ("TK_LIBRARY", "tk8.6")):
        if os.environ.get(var):
            continue
        candidate = Path(sys.executable).resolve().parent.parent / "lib" / sub
        if (candidate / ("init.tcl" if var == "TCL_LIBRARY" else "tk.tcl")).exists():
            os.environ[var] = str(candidate)


_ensure_tcl_tk_lib()

import customtkinter as ctk

from app import TomaTimerApp
from tray import TrayController


def main() -> None:
    app = TomaTimerApp()

    # System tray (runs in background; lets timer keep ticking when window hidden)
    try:
        tray = TrayController(app)
        tray.start()
        app.tray = tray
    except Exception as exc:  # noqa: BLE001
        # Tray is optional - app still works without it.
        print(f"[toma-timer] Tray disabled: {exc}", file=sys.stderr)
        app.tray = None

    app.mainloop()


if __name__ == "__main__":
    main()
