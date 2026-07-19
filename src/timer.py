"""Pomodoro timer engine.

State machine:
    IDLE -> FOCUS -> SHORT_BREAK -> FOCUS -> ... -> LONG_BREAK -> FOCUS ...
    (LONG_BREAK after every `sessions_before_long_break` focus sessions)

Runs a background thread that ticks every second. All UI updates happen
via callbacks invoked on the main thread via `after()` scheduling by the GUI.
"""
from __future__ import annotations

import threading
from enum import Enum
from typing import Callable

from database import end_session, start_session


class State(Enum):
    IDLE = "idle"
    FOCUS = "focus"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"
    PAUSED = "paused"  # virtual: remembers what was paused


class TimerEngine:
    """Drives the pomodoro cycle. Thread-safe via a lock.

    Callbacks (all optional, called from the background thread):
        on_tick(remaining_seconds: int, total_seconds: int)
        on_state_change(state: State, session_type: str)
        on_session_end(session_type: str, completed: bool)
    """

    def __init__(
        self,
        focus_minutes: int = 25,
        short_break_minutes: int = 5,
        long_break_minutes: int = 15,
        sessions_before_long_break: int = 4,
        auto_start_breaks: bool = False,
        auto_start_focus: bool = False,
        on_tick: Callable[[int, int], None] | None = None,
        on_state_change: Callable[[State, str], None] | None = None,
        on_session_end: Callable[[str, bool], None] | None = None,
    ) -> None:
        self.focus_minutes = focus_minutes
        self.short_break_minutes = short_break_minutes
        self.long_break_minutes = long_break_minutes
        self.sessions_before_long_break = max(1, sessions_before_long_break)
        self.auto_start_breaks = auto_start_breaks
        self.auto_start_focus = auto_start_focus

        self.on_tick = on_tick or (lambda rem, tot: None)
        self.on_state_change = on_state_change or (lambda s, t: None)
        self.on_session_end = on_session_end or (lambda t, c: None)

        # Wrap callbacks so an exception in a callback never kills the timer
        # thread. Callbacks are optional and must never break the cycle.
        self.on_tick = self._safe(self.on_tick)
        self.on_state_change = self._safe(self.on_state_change)
        self.on_session_end = self._safe(self.on_session_end)

        self.state: State = State.IDLE
        self._paused_state: State = State.IDLE  # what to resume to
        self.remaining: int = 0  # seconds left in current phase
        self.total: int = 0  # total seconds in current phase
        self.completed_focus_count: int = 0  # since last long break
        self._cycle_position: int = 0  # focus sessions in current cycle (0..N-1)
        self.cycle_states: list[bool | None] = []  # per-slot: True=completed, False=skipped-early, None=pending
        self._current_session_id: int | None = None
        self._current_session_type: str = ""
        self._elapsed_at_pause: int = 0

        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # not paused

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    @staticmethod
    def _safe(fn):
        """Wrap a callback so exceptions are logged, not raised."""
        import functools, traceback
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception:
                traceback.print_exc()
        return wrapper

    def start_focus(self) -> None:
        """Begin a focus session from idle."""
        with self._lock:
            if self.state != State.IDLE:
                return
            self._begin_phase(State.FOCUS)

    def pause(self) -> None:
        with self._lock:
            if self.state in (State.FOCUS, State.SHORT_BREAK, State.LONG_BREAK):
                self._paused_state = self.state
                self._elapsed_at_pause = self.total - self.remaining
                self.state = State.PAUSED
                self._pause_event.clear()
                self.on_state_change(State.PAUSED, self._current_session_type)

    def resume(self) -> None:
        with self._lock:
            if self.state == State.PAUSED:
                self.state = self._paused_state
                self._pause_event.set()
                self.on_state_change(self.state, self._current_session_type)

    def reset(self) -> None:
        """Stop current session, mark incomplete, return to idle."""
        with self._lock:
            if self._current_session_id is not None:
                elapsed = self.total - self.remaining
                end_session(self._current_session_id, completed=False, actual_seconds=elapsed)
                self.on_session_end(self._current_session_type, completed=False)
            self._hard_stop()
            self.cycle_states = []
            self.state = State.IDLE
            self.remaining = 0
            self.total = 0
            self.on_state_change(State.IDLE, "")

    def skip(self) -> None:
        """End current phase. If >5min left on a focus session, mark as
        incomplete (early skip) - cycle position does not advance."""
        with self._lock:
            if self._current_session_type == "focus" and self.remaining > 300:
                self._complete_current(completed=False)
            else:
                self._complete_current(completed=True)

    def stop_engine(self) -> None:
        """Fully tear down the background thread (app quit)."""
        self._stop_event.set()
        self._pause_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    # ------------------------------------------------------------------ #
    # Internal phase control
    # ------------------------------------------------------------------ #
    def _begin_phase(self, state: State) -> None:
        self._pause_event.set()  # a fresh phase is never paused
        self.state = state
        if state == State.FOCUS:
            minutes = self.focus_minutes
            session_type = "focus"
            # Ensure cycle_states covers the current position
            while len(self.cycle_states) <= self._cycle_position:
                self.cycle_states.append(None)
        elif state == State.SHORT_BREAK:
            minutes = self.short_break_minutes
            session_type = "short_break"
        elif state == State.LONG_BREAK:
            minutes = self.long_break_minutes
            session_type = "long_break"
        else:
            return

        self.total = int(minutes * 60)
        self.remaining = self.total
        self._current_session_type = session_type
        self._current_session_id = start_session(
            session_type=session_type,
            planned_minutes=minutes,
        )
        self.on_state_change(state, session_type)
        self.on_tick(self.remaining, self.total)
        self._ensure_thread()

    def _complete_current(self, completed: bool) -> None:
        """End the current phase and transition to the next."""
        if self._current_session_id is not None:
            elapsed = self.total - self.remaining
            end_session(self._current_session_id, completed=completed, actual_seconds=elapsed)
            self.on_session_end(self._current_session_type, completed=completed)

        finished_type = self._current_session_type
        self._current_session_id = None

        # Decide next phase
        if finished_type == "focus" and completed:
            if self._cycle_position < len(self.cycle_states):
                self.cycle_states[self._cycle_position] = True
            self._cycle_position += 1
            self.completed_focus_count += 1
            if self._cycle_position >= self.sessions_before_long_break:
                self._cycle_position = 0
                self.cycle_states = []
                next_state = State.LONG_BREAK
            else:
                next_state = State.SHORT_BREAK
        elif finished_type == "focus" and not completed:
            # Skip-early: don't advance cycle, mark as incomplete
            if self._cycle_position < len(self.cycle_states):
                self.cycle_states[self._cycle_position] = False
            next_state = State.IDLE
        else:
            # Just finished a break -> focus
            next_state = State.FOCUS

        if next_state == State.IDLE:
            self.state = State.IDLE
            self.remaining = 0
            self.on_state_change(State.IDLE, "")
        elif (next_state in (State.SHORT_BREAK, State.LONG_BREAK) and self.auto_start_breaks) \
                or (next_state == State.FOCUS and self.auto_start_focus):
            self._begin_phase(next_state)
        else:
            # Auto-start disabled: stop the thread, wait for user to start next phase
            self.state = State.IDLE
            self.remaining = 0
            self.on_state_change(State.IDLE, "")
            # but remember what's "next" so the GUI can prompt - keep simple: user clicks start

    def _hard_stop(self) -> None:
        self._stop_event.set()
        self._pause_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._stop_event.clear()
        self._thread = None
        self._current_session_id = None

    def _ensure_thread(self) -> None:
        # Wake any blocked (paused) thread so it picks up the new phase.
        self._pause_event.set()
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def _run(self) -> None:
        """Background loop: tick once per second while a phase is active."""
        import time

        while not self._stop_event.is_set():
            # Block while paused
            self._pause_event.wait(timeout=1.0)
            if self._stop_event.is_set():
                break
            if self.state == State.PAUSED:
                continue
            if self.state == State.IDLE:
                break

            time.sleep(1.0)
            if self._stop_event.is_set():
                break
            # Re-check pause/idle after sleep (skip/reset may have fired)
            if self.state == State.PAUSED:
                continue
            if self.state == State.IDLE:
                break

            with self._lock:
                # State may have changed (skip/reset) while we waited for lock
                if self.state in (State.IDLE, State.PAUSED):
                    continue
                self.remaining -= 1
                self.on_tick(self.remaining, self.total)
                if self.remaining <= 0:
                    self._complete_current(completed=True)
                    # If next phase auto-started, loop continues; else IDLE breaks loop
                    if self.state == State.IDLE:
                        break
