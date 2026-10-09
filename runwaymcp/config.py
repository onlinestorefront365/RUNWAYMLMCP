"""Local per-user config (~/.runwaymcp/config.json, mode 0600)."""
from __future__ import annotations

import json
import os
from pathlib import Path


def path() -> Path:
    return Path(os.environ.get("RUNWAYMCP_HOME", Path.home() / ".runwaymcp")) / "config.json"


def load() -> dict:
    try:
        return json.loads(path().read_text())
    except (OSError, ValueError):
        return {}


def save(updates: dict) -> None:
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({**load(), **updates}))
    p.chmod(0o600)


def get_key() -> str | None:
    return os.environ.get("RUNWAYML_API_SECRET") or os.environ.get("RUNWAY_API_KEY") or load().get("api_key")
