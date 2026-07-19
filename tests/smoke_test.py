"""Smoke test: build the GUI, drive it via after() callbacks, catch errors."""
import sys, traceback
from pathlib import Path
SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

# Import main first so _ensure_tcl_tk_lib() runs before tkinter is loaded.
import main  # noqa: F401  (side effect: sets TCL_LIBRARY/TK_LIBRARY)

import customtkinter as ctk
from app import TomaTimerApp
from timer import State

errors = []
def run():
    app = TomaTimerApp()
    app.tray = None  # skip tray in smoke test

    steps = []
    def step(fn, name, delay):
        def do():
            try:
                fn()
            except Exception:
                errors.append((name, traceback.format_exc()))
        app.after(delay, do)
        steps.append(name)

    # 1. switch to stats tab
    step(lambda: app.tabview.set("Stats"), "switch_stats", 300)
    # 2. refresh stats
    step(lambda: app._refresh_stats(), "refresh_stats", 600)
    # 3. switch back to timer
    step(lambda: app.tabview.set("Timer"), "switch_timer", 900)
    # 4. start focus
    step(lambda: app._on_start(), "start", 1200)
    # 5. pause
    step(lambda: app._on_pause(), "pause", 1500)
    # 6. resume
    step(lambda: app._on_pause(), "resume", 1800)
    # 7. reset
    step(lambda: app._on_reset(), "reset", 2100)
    # 8. open settings dialog
    dlg_holder = {}
    def open_settings():
        app._open_settings()
        dlg_holder["dlg"] = list(app.winfo_children())  # not reliable; just trigger
    step(open_settings, "open_settings", 2400)
    # 9. export csv + json
    step(lambda: app._export_csv(), "export_csv", 2700)
    step(lambda: app._export_json(), "export_json", 3000)
    # 10. toggle theme
    step(lambda: app.theme_switch.toggle(), "toggle_theme", 3300)
    # 11. quit
    step(lambda: app._quit(), "quit", 3600)

    app.after(4000, app._quit)
    app.mainloop()
    return errors

if __name__ == "__main__":
    errs = run()
    if errs:
        print(f"FAIL: {len(errs)} error(s)")
        for name, tb in errs:
            print(f"\n=== {name} ===")
            print(tb)
        sys.exit(1)
    print(f"SMOKE TEST PASSED ({len(errs)} errors)")
