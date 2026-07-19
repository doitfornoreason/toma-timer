"""Deep functional test: exercise full cycle + edge cases, surface logic bugs."""
import sys, traceback
from pathlib import Path
SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
import main  # noqa: F401  (sets TCL/TK env)

import database as db
from timer import TimerEngine, State

db.init_db()
failures = []
def check(cond, msg):
    if not cond:
        failures.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")

# --- Test 1: full cycle with auto-start (focus -> short -> focus -> ... -> long) ---
print("\n[T1] Full cycle with auto-start")
events = []
e = TimerEngine(
    focus_minutes=0.02, short_break_minutes=0.02, long_break_minutes=0.02,
    sessions_before_long_break=3, auto_start_breaks=True, auto_start_focus=True,
    on_state_change=lambda s, t: events.append((s.name, t)),
    on_session_end=lambda t, completed=False: events.append(("end", t, completed)),
)
before = db.count_rows()
e.start_focus()
import time
time.sleep(2.5)  # let several phases complete
e.stop_engine()
added = db.count_rows() - before
check(added >= 2, f"multiple sessions logged (got {added})")
check(e._cycle_position == 0, f"cycle resets after long break (pos={e._cycle_position})")
# verify a long_break occurred
types = [ev[1] for ev in events if ev[0] == "end"]
check("long_break" in types, f"long break triggered (types={types})")

# --- Test 2: no auto-start -> focus completes, next Start should be a BREAK not focus ---
print("\n[T2] After focus completes (no auto-start), state is IDLE")
events2 = []
e2 = TimerEngine(
    focus_minutes=0.02, short_break_minutes=0.02, long_break_minutes=0.02,
    sessions_before_long_break=4, auto_start_breaks=False, auto_start_focus=False,
    on_state_change=lambda s, t: events2.append((s.name, t)),
)
e2.start_focus()
time.sleep(1.0)
check(e2.state == State.IDLE, f"returns to IDLE after focus (state={e2.state.name})")
check(e2._cycle_position == 1, f"cycle pos advanced (pos={e2._cycle_position})")
# Now: what does Start do? It calls start_focus() -> begins ANOTHER focus, skipping break!
e2.start_focus()
time.sleep(0.2)
phases = [ev[0] for ev in events2]
check("FOCUS" in phases, "starts focus again")
# THIS IS THE BUG: break is skipped. Flag it.
if e2.state == State.FOCUS and "SHORT_BREAK" not in phases:
    failures.append("UX BUG: after focus completes with no auto-start, clicking Start begins another focus instead of the pending break")
    print("  FAIL: UX BUG — break skipped when user clicks Start after focus")
e2.stop_engine()

# --- Test 3: skip during focus counts as completed ---
print("\n[T3] Skip behavior")
e3 = TimerEngine(focus_minutes=25, short_break_minutes=5, long_break_minutes=15,
                 sessions_before_long_break=4, auto_start_breaks=False, auto_start_focus=False)
e3.start_focus()
time.sleep(0.2)
e3.skip()
check(e3.state == State.IDLE, f"skip -> IDLE (state={e3.state.name})")
check(e3._cycle_position == 1, f"skip advances cycle (pos={e3._cycle_position})")
e3.stop_engine()

# --- Test 4: reset marks incomplete ---
print("\n[T4] Reset marks session incomplete")
e4 = TimerEngine(focus_minutes=25, short_break_minutes=5, long_break_minutes=15,
                 sessions_before_long_break=4)
e4.start_focus()
time.sleep(0.2)
e4.reset()
check(e4.state == State.IDLE, f"reset -> IDLE (state={e4.state.name})")
e4.stop_engine()

# --- Test 5: pause/resume preserves remaining time ---
print("\n[T5] Pause/resume")
e5 = TimerEngine(focus_minutes=0.05, short_break_minutes=0.05, long_break_minutes=0.05,
                 sessions_before_long_break=4)
e5.start_focus()
time.sleep(0.5)
rem_before = e5.remaining
e5.pause()
time.sleep(1.0)
check(e5.state == State.PAUSED, f"paused (state={e5.state.name})")
check(e5.remaining == rem_before, f"time frozen while paused (rem={e5.remaining} vs {rem_before})")
e5.resume()
time.sleep(0.3)
check(e5.remaining < rem_before, f"time resumes counting (rem={e5.remaining} < {rem_before})")
e5.stop_engine()

print("\n" + "="*50)
if failures:
    print(f"{len(failures)} ISSUE(S) FOUND:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("ALL CHECKS PASSED")
