"""Toma Timer GUI built with CustomTkinter.

Layout:
  - Header: title + theme toggle + settings button
  - Tabview:
      Timer tab -> state label, big countdown, progress bar, control buttons,
                   session-cycle dots, todo list
      Stats tab -> metrics panel + embedded matplotlib figure + refresh/export
      Settings tab -> scrollable settings (durations, behaviour, sound, data)

Timer engine callbacks arrive on a background thread and are marshalled to the
Tk main loop via `after(0, ...)` because Tkinter is not thread-safe.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import customtkinter as ctk
from customtkinter import filedialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from config import load, save, DEFAULTS
from database import get_all_sessions, init_db
from export import default_export_dir, export_csv, export_json
from sound import play
from stats import build_figure, compute_metrics
from timer import State, TimerEngine

# Ensure local imports work when run as `python src/app.py` or `python -m src.app`
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Seconds->MM:SS
def fmt_time(seconds: int) -> str:
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60)
    return f"{m:02d}:{s:02d}"

STATE_LABELS = {
    State.IDLE: "Ready",
    State.FOCUS: "Focus",
    State.SHORT_BREAK: "Short Break",
    State.LONG_BREAK: "Long Break",
    State.PAUSED: "Paused",
}

STATE_COLORS = {
    State.IDLE: ("gray70", "gray30"),
    State.FOCUS: ("#ef4444", "#dc2626"),       # red
    State.SHORT_BREAK: ("#22c55e", "#16a34a"),  # green
    State.LONG_BREAK: ("#3b82f6", "#2563eb"),   # blue
    State.PAUSED: ("#f59e0b", "#d97706"),       # amber
}


class TomaTimerApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__(className="TomaTimer")
        self.wm_attributes('-type', 'normal')
        self.config = load()
        init_db()

        ctk.set_appearance_mode(self.config["theme"])
        ctk.set_default_color_theme(self.config["color_theme"])
        ctk.set_widget_scaling(1.5)
        ctk.set_window_scaling(1.15)

        self.title("Toma Timer")
        self.minsize(800, 600)
        self._set_window_icon()

        self.engine = TimerEngine(
            focus_minutes=self.config["focus_minutes"],
            short_break_minutes=self.config["short_break_minutes"],
            long_break_minutes=self.config["long_break_minutes"],
            sessions_before_long_break=self.config["sessions_before_long_break"],
            auto_start_breaks=self.config["auto_start_breaks"],
            auto_start_focus=self.config["auto_start_focus"],
            on_tick=self._on_tick,
            on_state_change=self._on_state_change,
            on_session_end=self._on_session_end,
        )

        self._build_ui()
        self._refresh_session_dots()
        self._fix_wm_properties()
        self.after(500, self._request_tile_hyprland)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.tray = None

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))

        self.theme_switch = ctk.CTkSwitch(
            header, text=self._theme_label(self.config["theme"]), command=self._toggle_theme,
            onvalue="dark", offvalue="light",
        )
        self.theme_switch.set(self.config["theme"])
        self.theme_switch.pack(side="right", padx=(8, 0))

        ctk.CTkButton(header, text="Settings", width=100, command=self._switch_to_settings).pack(side="right", padx=(0, 4))

        self.tabview = ctk.CTkTabview(self)
        self.tabview.add("Timer")
        self.tabview.add("Stats")
        self.tabview.add("Settings")
        self.tabview.pack(fill="both", expand=True, padx=16, pady=(4, 12))

        self._build_timer_tab(self.tabview.tab("Timer"))
        self._build_stats_tab(self.tabview.tab("Stats"))
        self._build_settings_tab(self.tabview.tab("Settings"))

    def _build_timer_tab(self, parent) -> None:
        center = ctk.CTkFrame(parent, fg_color="transparent")
        center.pack(expand=True, fill="both")

        ctk.CTkFrame(center, fg_color="transparent", height=0).pack(expand=True, fill="y")

        self.state_label = ctk.CTkLabel(center, text="Ready",
                                        font=ctk.CTkFont(size=18, weight="bold"))
        self.state_label.pack(pady=(0, 8))

        self.time_label = ctk.CTkLabel(
            center, text=fmt_time(self.config["focus_minutes"] * 60),
            font=ctk.CTkFont(size=90, weight="bold"),
        )
        self.time_label.pack(pady=(0, 12))

        self.progress = ctk.CTkProgressBar(center, width=400, height=12)
        self.progress.set(0)
        self.progress.pack(pady=(0, 16))

        self.dots_frame = ctk.CTkFrame(center, fg_color="transparent")
        self.dots_frame.pack(pady=(0, 16))
        self._dot_widgets: list[ctk.CTkLabel] = []

        btn_frame = ctk.CTkFrame(center, fg_color="transparent")
        btn_frame.pack(pady=(0, 8))

        self.start_btn = ctk.CTkButton(btn_frame, text="Start", width=110, command=self._on_start)
        self.start_btn.grid(row=0, column=0, padx=6)

        self.pause_btn = ctk.CTkButton(btn_frame, text="Pause", width=110, command=self._on_pause,
                                        state="disabled")
        self.pause_btn.grid(row=0, column=1, padx=6)

        self.reset_btn = ctk.CTkButton(btn_frame, text="Reset", width=110, command=self._on_reset,
                                        fg_color="transparent", border_width=1,
                                        text_color=("gray20", "gray90"))
        self.reset_btn.grid(row=0, column=2, padx=6)

        self.skip_btn = ctk.CTkButton(btn_frame, text="Skip", width=110, command=self._on_skip,
                                       fg_color="transparent", border_width=1,
                                       text_color=("gray20", "gray90"))
        self.skip_btn.grid(row=0, column=3, padx=6)

        # Todo list
        todo_container = ctk.CTkFrame(center, fg_color="transparent")
        todo_container.pack(fill="x", padx=0, pady=(8, 0))

        todo_header = ctk.CTkFrame(todo_container, fg_color="transparent")
        todo_header.pack(fill="x", padx=40)
        ctk.CTkLabel(todo_header, text="To-Do", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        self.todo_remove_btn = ctk.CTkButton(
            todo_header, text="Remove done", width=100, height=22,
            command=self._remove_completed_todos,
            fg_color="transparent", border_width=1,
            text_color=("gray20", "gray90"), font=ctk.CTkFont(size=11),
        )
        self.todo_remove_btn.pack(side="right")

        self.todo_scroll = ctk.CTkScrollableFrame(todo_container, height=120)
        self.todo_scroll.pack(fill="x", padx=40, pady=(4, 4))
        self._todo_widgets: list[ctk.CTkFrame] = []

        add_row = ctk.CTkFrame(todo_container, fg_color="transparent")
        add_row.pack(fill="x", padx=40)
        self.todo_entry = ctk.CTkEntry(add_row, placeholder_text="New todo...")
        self.todo_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.todo_entry.bind("<Return>", lambda e: self._add_todo())
        ctk.CTkButton(add_row, text="+", width=32, height=28, command=self._add_todo).pack(side="right")

        self._refresh_todo_list()

        ctk.CTkFrame(center, fg_color="transparent", height=0).pack(expand=True, fill="y")

        self.hint_label = ctk.CTkLabel(parent, text="", text_color="gray60",
                                        font=ctk.CTkFont(size=13))
        self.hint_label.pack(side="bottom", pady=(0, 12))

    def _build_stats_tab(self, parent) -> None:
        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(8, 4))
        ctk.CTkButton(top, text="Refresh", width=100, command=self._refresh_stats).pack(side="left")
        ctk.CTkButton(top, text="Export CSV", width=100, command=self._export_csv).pack(side="left", padx=6)
        ctk.CTkButton(top, text="Export JSON", width=100, command=self._export_json).pack(side="left")

        self.metrics_label = ctk.CTkLabel(parent, text="", anchor="w", justify="left",
                                          font=ctk.CTkFont(size=14))
        self.metrics_label.pack(fill="x", padx=12, pady=(8, 4))

        self.canvas_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.canvas_frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self._canvas: FigureCanvasTkAgg | None = None

        self._refresh_stats()

    # ------------------------------------------------------------------ #
    # Settings tab
    # ------------------------------------------------------------------ #
    def _switch_to_settings(self) -> None:
        self.tabview.set("Settings")

    def _build_settings_tab(self, parent) -> None:
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=8, pady=8)

        pad = {"padx": 16, "pady": 6}

        ctk.CTkLabel(scroll, text="Settings", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(16, 8))

        # --- Timer durations ---
        ctk.CTkLabel(scroll, text="Timer (minutes)", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=16)

        self.st_focus_var = ctk.IntVar(value=self.config["focus_minutes"])
        self.st_short_var = ctk.IntVar(value=self.config["short_break_minutes"])
        self.st_long_var = ctk.IntVar(value=self.config["long_break_minutes"])
        self.st_cycles_var = ctk.IntVar(value=self.config["sessions_before_long_break"])

        self._settings_slider_row(scroll, "Focus length", self.st_focus_var, 1, 120)
        self._settings_slider_row(scroll, "Short break", self.st_short_var, 1, 60)
        self._settings_slider_row(scroll, "Long break", self.st_long_var, 1, 60)
        self._settings_slider_row(scroll, "Sessions per cycle", self.st_cycles_var, 1, 12)

        # --- Behaviour ---
        ctk.CTkLabel(scroll, text="Behaviour", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=16, pady=(12, 0))

        self.st_auto_break_var = ctk.BooleanVar(value=self.config["auto_start_breaks"])
        self.st_auto_focus_var = ctk.BooleanVar(value=self.config["auto_start_focus"])
        self.st_sound_var = ctk.BooleanVar(value=self.config["sound_enabled"])

        ctk.CTkSwitch(scroll, text="Auto-start breaks", variable=self.st_auto_break_var, command=self._apply_settings_now).pack(anchor="w", **pad)
        ctk.CTkSwitch(scroll, text="Auto-start next focus", variable=self.st_auto_focus_var, command=self._apply_settings_now).pack(anchor="w", **pad)
        ctk.CTkSwitch(scroll, text="Sound notifications", variable=self.st_sound_var, command=self._apply_settings_now).pack(anchor="w", **pad)

        # --- Sound file ---
        ctk.CTkLabel(scroll, text="Sound", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=16, pady=(12, 0))
        sound_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        sound_frame.pack(fill="x", padx=16, pady=(8, 0))
        ctk.CTkLabel(sound_frame, text="Sound file:").pack(side="left")
        self.st_sound_path_entry = ctk.CTkEntry(sound_frame, placeholder_text="default chime")
        self.st_sound_path_entry.pack(side="left", fill="x", expand=True, padx=(8, 4))
        if self.config["sound_path"]:
            self.st_sound_path_entry.insert(0, self.config["sound_path"])
        ctk.CTkButton(sound_frame, text="Browse", width=80, command=self._st_browse_sound).pack(side="left")
        ctk.CTkButton(sound_frame, text="Test", width=60, command=self._st_test_sound).pack(side="left", padx=(4, 0))

        # --- Data ---
        ctk.CTkLabel(scroll, text="Data", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=16, pady=(12, 0))
        ctk.CTkButton(
            scroll, text="Delete All Records",
            fg_color="#b91c1c", hover_color="#991b1b",
            text_color="white",
            command=self._st_confirm_clear_data,
        ).pack(anchor="w", padx=16, pady=(8, 0))

        # --- Reset ---
        ctk.CTkButton(
            scroll, text="Reset to defaults",
            fg_color="transparent", border_width=1,
            command=self._st_reset_defaults,
        ).pack(anchor="w", padx=16, pady=(16, 24))

    def _settings_slider_row(self, parent, label_text: str, var: ctk.IntVar, lo: int, hi: int) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row, text=label_text, width=140, anchor="w").pack(side="left")

        entry = ctk.CTkEntry(row, width=60, justify="center")
        entry.insert(0, str(var.get()))
        entry.pack(side="right", padx=(4, 0))

        def sync_entry():
            try:
                v = int(entry.get())
                v = max(lo, min(hi, v))
                var.set(v)
                entry.delete(0, "end")
                entry.insert(0, str(v))
                slider.set(v)
                self._apply_settings_now()
            except ValueError:
                entry.delete(0, "end")
                entry.insert(0, str(var.get()))

        entry.bind("<Return>", lambda e: sync_entry())
        entry.bind("<FocusOut>", lambda e: sync_entry())

        def on_slider(v):
            iv = int(float(v))
            var.set(iv)
            entry.delete(0, "end")
            entry.insert(0, str(iv))
            self._apply_settings_now()

        slider = ctk.CTkSlider(row, from_=lo, to=hi, command=on_slider)
        slider.set(var.get())
        slider.pack(side="left", fill="x", expand=True, padx=(8, 8))

    def _st_browse_sound(self) -> None:
        path = filedialog.askopenfilename(
            title="Select notification sound",
            filetypes=[("Audio files", "*.mp3 *.flac *.wav *.ogg"), ("All files", "*.*")],
        )
        if path:
            self.st_sound_path_entry.delete(0, "end")
            self.st_sound_path_entry.insert(0, path)
            self._apply_settings_now()

    def _st_test_sound(self) -> None:
        play(self.st_sound_path_entry.get() or "", self.config.get("sound_volume", 0.7))

    def _st_confirm_clear_data(self) -> None:
        import tkinter.messagebox as mb
        if not mb.askyesno(
            "Delete All Records",
            "This will permanently delete ALL sessions and todos.\n\nAre you sure?",
            icon="warning", parent=self,
        ):
            return
        from database import clear_all_data
        clear_all_data()
        self._refresh_stats()
        self._refresh_todo_list()
        self._show_toast("All records deleted")

    def _st_reset_defaults(self) -> None:
        self._apply_settings(DEFAULTS)
        self._rebuild_settings_tab()
        self._show_toast("Settings reset to defaults")

    def _rebuild_settings_tab(self) -> None:
        """Destroy and rebuild the settings tab to reflect new values."""
        tab = self.tabview.tab("Settings")
        for w in list(tab.winfo_children()):
            w.destroy()
        self._build_settings_tab(tab)

    def _apply_settings_now(self) -> None:
        """Read current settings tab vars and apply."""
        new = {
            "focus_minutes": int(self.st_focus_var.get()),
            "short_break_minutes": int(self.st_short_var.get()),
            "long_break_minutes": int(self.st_long_var.get()),
            "sessions_before_long_break": int(self.st_cycles_var.get()),
            "auto_start_breaks": bool(self.st_auto_break_var.get()),
            "auto_start_focus": bool(self.st_auto_focus_var.get()),
            "sound_enabled": bool(self.st_sound_var.get()),
            "sound_path": self.st_sound_path_entry.get().strip(),
        }
        self._apply_settings(new)

    def _apply_settings(self, new_config: dict) -> None:
        self.config.update(new_config)
        save(self.config)
        self.engine.focus_minutes = new_config["focus_minutes"]
        self.engine.short_break_minutes = new_config["short_break_minutes"]
        self.engine.long_break_minutes = new_config["long_break_minutes"]
        self.engine.sessions_before_long_break = max(1, new_config["sessions_before_long_break"])
        self.engine.auto_start_breaks = new_config["auto_start_breaks"]
        self.engine.auto_start_focus = new_config["auto_start_focus"]
        ctk.set_appearance_mode(new_config["theme"])
        self.theme_switch.set(new_config["theme"])
        self.theme_switch.configure(text=self._theme_label(new_config["theme"]))
        self._refresh_session_dots()
        if self.engine.state == State.IDLE:
            self.time_label.configure(text=fmt_time(new_config["focus_minutes"] * 60))
        self._refresh_stats()

    # ------------------------------------------------------------------ #
    # Session dots
    # ------------------------------------------------------------------ #
    def _refresh_session_dots(self) -> None:
        for w in self._dot_widgets:
            w.destroy()
        self._dot_widgets.clear()
        states = self.engine.cycle_states
        n = self.engine.sessions_before_long_break
        for i in range(n):
            if i < len(states):
                if states[i] is True:
                    char, color = "*", "#3b82f6"
                elif states[i] is False:
                    char, color = "*", "#ef4444"
                else:
                    char, color = "o", "gray50"
            else:
                char, color = "o", "gray50"
            lbl = ctk.CTkLabel(self.dots_frame, text=char, font=ctk.CTkFont(size=24), text_color=color)
            lbl.pack(side="left", padx=6)
            self._dot_widgets.append(lbl)

    # ------------------------------------------------------------------ #
    # Marshalled callbacks
    # ------------------------------------------------------------------ #
    def _marshal(self, fn, *args):
        self.after(0, lambda: fn(*args))

    def _on_tick(self, remaining: int, total: int) -> None:
        self._marshal(self._ui_tick, remaining, total)

    def _on_state_change(self, state: State, session_type: str) -> None:
        self._marshal(self._ui_state_change, state, session_type)

    def _on_session_end(self, session_type: str, completed: bool) -> None:
        self._marshal(self._ui_session_end, session_type, completed)

    def _ui_tick(self, remaining: int, total: int) -> None:
        self.time_label.configure(text=fmt_time(remaining))
        if total > 0:
            self.progress.set(1 - (remaining / total))

    def _ui_state_change(self, state: State, session_type: str) -> None:
        label = STATE_LABELS.get(state, str(state))
        self.state_label.configure(text=label)
        self._refresh_session_dots()
        running = state in (State.FOCUS, State.SHORT_BREAK, State.LONG_BREAK)
        self.start_btn.configure(state="disabled" if running else "normal")
        self.pause_btn.configure(state="normal" if running else "disabled", text="Pause")
        if state == State.IDLE:
            self.progress.set(0)
            if self.engine._cycle_position >= self.engine.sessions_before_long_break:
                self.hint_label.configure(text="Next: Long Break")
            elif self.engine._cycle_position > 0:
                self.hint_label.configure(text=f"Focus sessions done: {self.engine._cycle_position}/{self.engine.sessions_before_long_break}")
            else:
                self.hint_label.configure(text="Press Start to begin a focus session")
        elif state == State.PAUSED:
            self.pause_btn.configure(text="Resume", state="normal")

    def _ui_session_end(self, session_type: str, completed: bool) -> None:
        if completed and self.config.get("sound_enabled", True):
            play(self.config.get("sound_path", ""), self.config.get("sound_volume", 0.7))
        self._refresh_stats()

    # ------------------------------------------------------------------ #
    # Button handlers
    # ------------------------------------------------------------------ #
    def _on_start(self) -> None:
        self.engine.start_focus()

    def _on_pause(self) -> None:
        if self.engine.state == State.PAUSED:
            self.engine.resume()
        else:
            self.engine.pause()

    def _on_reset(self) -> None:
        self.engine.reset()

    def _on_skip(self) -> None:
        self.engine.skip()

    # ------------------------------------------------------------------ #
    # Theme
    # ------------------------------------------------------------------ #
    def _toggle_theme(self) -> None:
        new_theme = self.theme_switch.get()
        ctk.set_appearance_mode(new_theme)
        self.theme_switch.configure(text=self._theme_label(new_theme))
        self.config["theme"] = new_theme
        save(self.config)
        self._refresh_stats()

    @staticmethod
    def _theme_label(theme: str) -> str:
        return "Dark" if theme == "dark" else "Light"

    # ------------------------------------------------------------------ #
    # To-Do list
    # ------------------------------------------------------------------ #
    def _refresh_todo_list(self) -> None:
        from database import get_all_todos
        for w in self._todo_widgets:
            w.destroy()
        self._todo_widgets.clear()
        todos = get_all_todos()
        for t in todos:
            row = ctk.CTkFrame(self.todo_scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)
            var = ctk.StringVar(value="on" if t["completed"] else "off")
            cb = ctk.CTkCheckBox(
                row, text="", width=20, variable=var, onvalue="on", offvalue="off",
                command=lambda tid=t["id"], v=var: self._toggle_todo(tid, v),
            )
            cb.pack(side="left", padx=(0, 6))
            lbl = ctk.CTkLabel(
                row, text=t["text"], anchor="w",
                font=ctk.CTkFont(size=14, overstrike=bool(t["completed"])),
                text_color=("gray30", "gray70") if t["completed"] else ("gray10", "gray90"),
            )
            lbl.pack(side="left", fill="x", expand=True)
            lbl.bind("<Double-Button-1>", lambda e, tid=t["id"]: self._delete_todo(tid))
            self._todo_widgets.append(row)

    def _add_todo(self) -> None:
        text = self.todo_entry.get().strip()
        if not text:
            return
        from database import add_todo
        add_todo(text)
        self.todo_entry.delete(0, "end")
        self._refresh_todo_list()

    def _toggle_todo(self, todo_id: int, var: ctk.StringVar) -> None:
        from database import set_todo_completed
        completed = var.get() == "on"
        set_todo_completed(todo_id, completed)
        self._refresh_todo_list()

    def _remove_completed_todos(self) -> None:
        from database import remove_completed_todos
        n = remove_completed_todos()
        self._refresh_todo_list()
        if n > 0:
            self._show_toast(f"Removed {n} completed todo(s)")

    def _delete_todo(self, todo_id: int) -> None:
        from database import delete_todo
        delete_todo(todo_id)
        self._refresh_todo_list()

    # ------------------------------------------------------------------ #
    # Stats
    # ------------------------------------------------------------------ #
    def _refresh_stats(self) -> None:
        sessions = get_all_sessions()
        metrics = compute_metrics(sessions)
        self.metrics_label.configure(text=self._format_metrics(metrics))
        if self._canvas is not None:
            self._canvas.get_tk_widget().destroy()
        theme = self.config.get("theme", "dark")
        fig = build_figure(sessions, theme=theme)
        self._canvas = FigureCanvasTkAgg(fig, master=self.canvas_frame)
        self._canvas.draw()
        self._canvas.get_tk_widget().pack(fill="both", expand=True)

    def _format_metrics(self, m: dict) -> str:
        hour_str = ""
        if m["most_productive_hour"] is not None:
            hour_str = f"{m['most_productive_hour']:02d}:00"
        lines = [
            f"Total focus sessions: {m['total_focus_sessions']}    |    "
            f"Total focus time: {m['total_focus_minutes']:.1f} min    |    "
            f"Avg session: {m['avg_focus_minutes']:.2f} min",
            f"Today: {m['sessions_today']}    |    This week: {m['sessions_this_week']}"
            f"    |    This month: {m['sessions_this_month']}",
            f"Current streak: {m['current_streak_days']} day(s)    |    "
            f"Best day: {m['best_day_date']} ({m['best_day_count']} sessions)    |    "
            f"Most productive hour: {hour_str or '-'}",
        ]
        return "\n".join(lines)

    def _export_csv(self) -> None:
        d = default_export_dir()
        path = export_csv(d / "toma_sessions.csv")
        self._show_toast(f"CSV exported to {path}")

    def _export_json(self) -> None:
        d = default_export_dir()
        path = export_json(d / "toma_sessions.json")
        self._show_toast(f"JSON exported to {path}")

    def _show_toast(self, msg: str) -> None:
        self.hint_label.configure(text=msg)
        self.after(4000, lambda: self.hint_label.configure(text=""))

    # ------------------------------------------------------------------ #
    # Window icon
    # ------------------------------------------------------------------ #
    def _set_window_icon(self) -> None:
        from pathlib import Path
        import tkinter as tk
        candidates = [
            Path(__file__).resolve().parent.parent / "assets" / "icons" / "toma-timer.png",
            Path(__file__).resolve().parent / "assets" / "icons" / "toma-timer.png",
        ]
        for p in candidates:
            if p.is_file():
                try:
                    self._icon_photo = tk.PhotoImage(file=str(p))
                    self.iconphoto(True, self._icon_photo)
                    return
                except Exception:
                    pass

    # ------------------------------------------------------------------ #
    # WM properties
    # ------------------------------------------------------------------ #
    def _fix_wm_properties(self) -> None:
        try:
            from Xlib import display
            from Xlib.xobject.drawable import Window
            d = display.Display()
            client = Window(d.display, self.winfo_id())
            parent = client.query_tree().parent
            val = "toma-timer\0toma-timer\0".encode()
            atom = d.intern_atom("WM_CLASS")
            typ = d.intern_atom("STRING")
            for win in (client, parent):
                win.change_property(atom, typ, 8, val)
            type_atom = d.intern_atom("_NET_WM_WINDOW_TYPE")
            normal = d.intern_atom("_NET_WM_WINDOW_TYPE_NORMAL")
            parent.change_property(type_atom, d.intern_atom("ATOM"), 32, [normal])
            pid_atom = d.intern_atom("_NET_WM_PID")
            card = d.intern_atom("CARDINAL")
            import os
            client.change_property(pid_atom, card, 32, [os.getpid()])
            d.flush()
        except Exception:
            pass

    def _request_tile_hyprland(self) -> None:
        import os
        if "HYPRLAND_INSTANCE_SIGNATURE" not in os.environ:
            return
        try:
            import json
            import subprocess
            result = subprocess.run(["hyprctl", "clients", "-j"], capture_output=True, text=True, timeout=3)
            if result.returncode != 0:
                return
            clients = json.loads(result.stdout)
            my_pid = os.getpid()
            for c in clients:
                if c.get("pid") == my_pid:
                    if c.get("floating", False):
                        addr = c["address"]
                        subprocess.run(["hyprctl", "dispatch", "togglefloating", f"window:{addr}"], capture_output=True, timeout=2)
                    break
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def _on_close(self) -> None:
        if self.tray is not None and self.tray.is_active():
            self.withdraw()
        else:
            self._quit()

    def _quit(self) -> None:
        self.engine.stop_engine()
        if self.tray is not None:
            self.tray.stop()
        self.destroy()
