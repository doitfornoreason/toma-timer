"""Configuration management for Toma Timer.

Defaults are merged with a user JSON file at ~/.config/toma-timer/config.json.
Falls back to defaults if the file is missing or corrupted.
"""
from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

# Default settings. Durations are in minutes.
DEFAULTS: dict[str, Any] = {
    # Timer durations (minutes)
    "focus_minutes": 25,
    "short_break_minutes": 5,
    "long_break_minutes": 15,
    "sessions_before_long_break": 4,
    # Behaviour
    "auto_start_breaks": False,
    "auto_start_focus": False,
    "sound_enabled": True,
    "sound_path": "",  # empty = built-in default beep
    "sound_volume": 0.7,
    # Appearance
    "theme": "dark",  # "dark" | "light"
    "color_theme": "blue",  # customtkinter colour theme
    "always_on_top": False,
    # Data
    "data_dir": "",  # empty = default (~/.local/share/toma-timer)
}

# Resolve config path: ~/.config/toma-timer/config.json
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "toma-timer"
CONFIG_PATH = CONFIG_DIR / "config.json"

# Default data dir: ~/.local/share/toma-timer
DATA_DIR_DEFAULT = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "toma-timer"


def get_data_dir(override: str = "") -> Path:
    """Return the active data directory, creating it if needed."""
    path = Path(override) if override else DATA_DIR_DEFAULT
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_db_path(config: dict[str, Any] | None = None) -> Path:
    """Return path to the SQLite database."""
    cfg = config if config is not None else load()
    return get_data_dir(cfg.get("data_dir", "")) / "sessions.db"


def load() -> dict[str, Any]:
    """Load config from disk, merged over DEFAULTS."""
    cfg = deepcopy(DEFAULTS)
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user = json.load(f)
            if isinstance(user, dict):
                cfg.update(user)
    except (json.JSONDecodeError, OSError):
        # Corrupted or unreadable: silently fall back to defaults.
        pass
    return cfg


def save(cfg: dict[str, Any]) -> None:
    """Persist config to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def update(**kwargs: Any) -> dict[str, Any]:
    """Update one or more settings and persist. Returns the new config."""
    cfg = load()
    cfg.update(kwargs)
    save(cfg)
    return cfg


def reset() -> dict[str, Any]:
    """Reset to defaults and persist."""
    save(deepcopy(DEFAULTS))
    return deepcopy(DEFAULTS)
