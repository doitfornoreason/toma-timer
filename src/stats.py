"""Statistics and visualisation for Toma Timer.

Two responsibilities:
  1. compute_metrics()  -> dict of summary numbers (avg length, totals, streaks, ...)
  2. build_figure()     -> matplotlib Figure with trend charts + time-of-day heatmap

The figure is theme-aware (dark/light) so it blends with the GUI.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import matplotlib
matplotlib.use("Agg")  # non-interactive backend; we render to canvas manually
import matplotlib.pyplot as plt
from matplotlib.figure import Figure


def _parse_dt(iso: str) -> datetime:
    """Parse an ISO-8601 string (with or without tz) to an aware datetime."""
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _to_local(dt: datetime) -> datetime:
    """Convert an aware UTC datetime to local time for display."""
    return dt.astimezone()


# ---------------------------------------------------------------------- #
# Metrics
# ---------------------------------------------------------------------- #
def compute_metrics(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute summary metrics from raw session rows."""
    # Only count completed focus sessions for productivity metrics.
    focus = [s for s in sessions if s["session_type"] == "focus" and s.get("completed")]
    all_focus = [s for s in sessions if s["session_type"] == "focus"]

    metrics: dict[str, Any] = {
        "total_focus_sessions": len(focus),
        "total_focus_minutes": 0,
        "avg_focus_minutes": 0.0,
        "total_sessions_all": len(sessions),
        "sessions_today": 0,
        "sessions_this_week": 0,
        "sessions_this_month": 0,
        "best_day_count": 0,
        "best_day_date": "",
        "current_streak_days": 0,
        "most_productive_hour": None,
        "most_productive_count": 0,
        "focus_dates": [],  # for streak calc
    }

    if not focus:
        return metrics

    total_seconds = sum(s.get("actual_seconds", 0) or 0 for s in focus)
    metrics["total_focus_minutes"] = round(total_seconds / 60.0, 1)
    metrics["avg_focus_minutes"] = round((total_seconds / len(focus)) / 60.0, 2)

    now = datetime.now(timezone.utc).astimezone()
    today = now.date()
    week_ago = today - timedelta(days=7)
    month_ago = today.replace(day=1)

    # Per-day focus counts (local date)
    day_counts: dict[str, int] = defaultdict(int)
    hour_counts: Counter = Counter()
    focus_dates: set[str] = set()

    for s in focus:
        dt = _to_local(_parse_dt(s["started_at"]))
        d = dt.date()
        day_counts[d.isoformat()] += 1
        focus_dates.add(d.isoformat())
        hour_counts[dt.hour] += 1
        if d == today:
            metrics["sessions_today"] += 1
        if d >= week_ago:
            metrics["sessions_this_week"] += 1
        if d >= month_ago:
            metrics["sessions_this_month"] += 1

    metrics["focus_dates"] = sorted(focus_dates)

    # Best day
    if day_counts:
        best_day, best_count = max(day_counts.items(), key=lambda kv: kv[1])
        metrics["best_day_count"] = best_count
        metrics["best_day_date"] = best_day

    # Current streak: consecutive days up to today with >=1 focus session
    streak = 0
    d = today
    while d.isoformat() in focus_dates:
        streak += 1
        d -= timedelta(days=1)
    metrics["current_streak_days"] = streak

    # Most productive hour
    if hour_counts:
        best_hour, best_hour_count = hour_counts.most_common(1)[0]
        metrics["most_productive_hour"] = best_hour
        metrics["most_productive_count"] = best_hour_count

    return metrics


# ---------------------------------------------------------------------- #
# Figure
# ---------------------------------------------------------------------- #
def _theme_colors(theme: str) -> dict[str, str]:
    if theme == "light":
        return {
            "bg": "#ffffff",
            "fg": "#1a1a1a",
            "grid": "#e0e0e0",
            "bar": "#3b82f6",
            "bar2": "#60a5fa",
            "heat_cmap": "Blues",
        }
    return {
        "bg": "#242424",
        "fg": "#e0e0e0",
        "grid": "#3a3a3a",
        "bar": "#3b82f6",
        "bar2": "#60a5fa",
        "heat_cmap": "Blues",
    }


def build_figure(sessions: list[dict[str, Any]], theme: str = "dark") -> Figure:
    """Build a matplotlib Figure with trend charts + heatmap."""
    colors = _theme_colors(theme)
    plt.rcParams.update({
        "figure.facecolor": colors["bg"],
        "axes.facecolor": colors["bg"],
        "axes.edgecolor": colors["fg"],
        "axes.labelcolor": colors["fg"],
        "xtick.color": colors["fg"],
        "ytick.color": colors["fg"],
        "text.color": colors["fg"],
        "axes.grid": True,
        "grid.color": colors["grid"],
        "grid.alpha": 0.5,
    })

    focus = [s for s in sessions if s["session_type"] == "focus" and s.get("completed")]

    fig = Figure(figsize=(11, 7), dpi=100, facecolor=colors["bg"])
    if not focus:
        ax = fig.add_subplot(111)
        ax.set_facecolor(colors["bg"])
        ax.text(0.5, 0.5, "No completed focus sessions yet.\nStart a session to see stats!",
                ha="center", va="center", fontsize=14, color=colors["fg"],
                transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
        fig.tight_layout()
        return fig

    # Last 30 days daily focus count + minutes
    daily_counts: dict[str, int] = defaultdict(int)
    daily_minutes: dict[str, float] = defaultdict(float)
    hour_counts: Counter = Counter()
    weekday_counts: Counter = Counter()

    for s in focus:
        dt = _to_local(_parse_dt(s["started_at"]))
        d = dt.date()
        daily_counts[d.isoformat()] += 1
        daily_minutes[d.isoformat()] += (s.get("actual_seconds", 0) or 0) / 60.0
        hour_counts[dt.hour] += 1
        weekday_counts[dt.weekday()] += 1

    # Build a contiguous 30-day window ending today
    today = datetime.now(timezone.utc).astimezone().date()
    days = [today - timedelta(days=i) for i in range(29, -1, -1)]
    day_labels = [d.strftime("%m/%d") for d in days]
    counts = [daily_counts.get(d.isoformat(), 0) for d in days]
    minutes = [daily_minutes.get(d.isoformat(), 0.0) for d in days]

    # --- Subplot 1: daily sessions (bars) ---
    ax1 = fig.add_subplot(2, 2, 1)
    ax1.bar(day_labels, counts, color=colors["bar"], width=0.8)
    ax1.set_title("Focus Sessions - Last 30 Days", fontsize=11, pad=8)
    ax1.set_ylabel("Sessions")
    ax1.tick_params(axis="x", labelsize=7, rotation=45)

    # --- Subplot 2: daily minutes (line) ---
    ax2 = fig.add_subplot(2, 2, 2)
    ax2.plot(day_labels, minutes, color=colors["bar2"], marker="o", markersize=3, linewidth=1.5)
    ax2.fill_between(day_labels, minutes, alpha=0.2, color=colors["bar2"])
    ax2.set_title("Focus Minutes - Last 30 Days", fontsize=11, pad=8)
    ax2.set_ylabel("Minutes")
    ax2.tick_params(axis="x", labelsize=7, rotation=45)

    # --- Subplot 3: time-of-day distribution ---
    ax3 = fig.add_subplot(2, 2, 3)
    hours = list(range(24))
    hour_vals = [hour_counts.get(h, 0) for h in hours]
    ax3.bar(hours, hour_vals, color=colors["bar"], width=0.8)
    ax3.set_title("Sessions by Hour of Day", fontsize=11, pad=8)
    ax3.set_xlabel("Hour (0-23)")
    ax3.set_ylabel("Sessions")
    ax3.set_xticks(range(0, 24, 2))

    # --- Subplot 4: weekday distribution ---
    ax4 = fig.add_subplot(2, 2, 4)
    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    wd_vals = [weekday_counts.get(i, 0) for i in range(7)]
    ax4.bar(weekday_names, wd_vals, color=colors["bar2"], width=0.6)
    ax4.set_title("Sessions by Weekday", fontsize=11, pad=8)
    ax4.set_ylabel("Sessions")

    fig.tight_layout(pad=2.0)
    return fig
