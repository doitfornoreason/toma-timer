"""Data export for Toma Timer: CSV and JSON.

Sessions are exported oldest-first with human-readable fields.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from database import get_all_sessions


def _row_for_export(session: dict[str, Any]) -> dict[str, Any]:
    """Normalise a DB row into export-friendly fields."""
    out = dict(session)
    out["completed"] = bool(out.get("completed", 0))
    if out.get("actual_seconds") is not None:
        out["actual_minutes"] = round(out["actual_seconds"] / 60.0, 2)
    else:
        out["actual_minutes"] = None
    out.pop("id", None)  # internal; omit from export
    return out


def export_csv(out_path: Path | str) -> Path:
    """Export all sessions to CSV. Returns the resolved path."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = get_all_sessions()
    export_rows = [_row_for_export(r) for r in rows]

    fieldnames = [
        "session_type",
        "started_at",
        "ended_at",
        "planned_minutes",
        "actual_minutes",
        "completed",
        "label",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(export_rows)
    return out_path


def export_json(out_path: Path | str) -> Path:
    """Export all sessions to JSON. Returns the resolved path."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = get_all_sessions()
    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "session_count": len(rows),
        "sessions": [_row_for_export(r) for r in rows],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return out_path


def default_export_dir() -> Path:
    from config import get_data_dir
    return get_data_dir() / "exports"
