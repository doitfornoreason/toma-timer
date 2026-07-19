"""System tray integration for Toma Timer using pystray.

Runs the tray icon on its own thread. GUI interactions are marshalled back to
the Tk main loop via the provided `app` reference and `app.after()`.

The tray is optional: if no StatusNotifierItem host is available (common on
bare Wayland), the icon fails to dock and we deactivate cleanly so the app
degrades to "close = quit" instead of hiding to an unreachable tray.
"""
from __future__ import annotations

import io
import threading
from contextlib import redirect_stderr

from PIL import Image, ImageDraw

import pystray
from pystray import MenuItem as Item

# Docking errors we treat as "no tray available".
_DOCK_FAIL_MARKERS = ("AssertionError", "Failed to dock", "assert")


def _make_icon_image() -> Image.Image:
    """Draw a simple tomato-like icon (red circle + green stem)."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([10, 14, 54, 58], fill=(220, 50, 40, 255))      # body
    d.ellipse([18, 22, 30, 34], fill=(255, 130, 110, 200))    # highlight
    d.polygon([(28, 10), (36, 10), (40, 18), (24, 18)], fill=(40, 160, 70, 255))  # stem
    d.rectangle([31, 6, 33, 12], fill=(40, 160, 70, 255))
    return img


class TrayController:
    """Owns the pystray icon and wires tray actions to the GUI."""

    def __init__(self, app) -> None:
        self.app = app
        self._icon: pystray.Icon | None = None
        self._thread: threading.Thread | None = None
        self._stderr_buf = io.StringIO()
        self.active = False  # True only once the icon has docked successfully

    def start(self) -> None:
        image = _make_icon_image()
        menu = pystray.Menu(
            Item("Show Toma Timer", self._on_show, default=True),
            Item("Start / Pause", self._on_toggle),
            Item("Reset", self._on_reset),
            pystray.Menu.SEPARATOR,
            Item("Quit", self._on_quit),
        )
        self._icon = pystray.Icon("toma-timer", image, "Toma Timer", menu)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        # Watchdog: after a short grace period, decide if we docked.
        threading.Thread(target=self._watchdog, daemon=True).start()

    def _run(self) -> None:
        # Capture pystray's stderr so docking failures don't spam the console.
        with redirect_stderr(self._stderr_buf):
            try:
                self._icon.run()
            except Exception:
                pass

    def _watchdog(self) -> None:
        """After a grace period, inspect captured stderr. If docking failed,
        stop the icon and mark the tray inactive."""
        import time
        time.sleep(2.0)
        out = self._stderr_buf.getvalue()
        if any(m in out for m in _DOCK_FAIL_MARKERS):
            # No usable tray host: shut the icon down and stay inactive.
            try:
                self._icon.stop()
            except Exception:
                pass
            self.active = False
        else:
            self.active = True

    def is_active(self) -> bool:
        return self.active

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2)

    # ---- tray callbacks (run on the pystray thread) ----
    def _on_show(self, icon, item) -> None:
        self.app.after(0, self._show_window)

    def _on_toggle(self, icon, item) -> None:
        from timer import State
        def do():
            if self.app.engine.state == State.IDLE:
                self.app.engine.start_focus()
            elif self.app.engine.state == State.PAUSED:
                self.app.engine.resume()
            else:
                self.app.engine.pause()
        self.app.after(0, do)

    def _on_reset(self, icon, item) -> None:
        self.app.after(0, self.app.engine.reset)

    def _on_quit(self, icon, item) -> None:
        self.app.after(0, self.app._quit)

    def _show_window(self) -> None:
        self.app.after(0, lambda: (self.app.deiconify(), self.app.lift(), self.app.focus_force()))
