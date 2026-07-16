"""
Heat map helpers, built on top of the tracking data Phase 6 (Tracking.py)
already produces and saves to outputs/*_tracking_data.json.
"""
import json
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = ROOT / "outputs"


def list_tracking_data_files() -> list[Path]:
    if not OUTPUTS_DIR.exists():
        return []
    return sorted(
        OUTPUTS_DIR.glob("*_tracking_data.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


@st.cache_data(show_spinner=False)
def load_tracking_data(path: Path) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def track_id_summary(data: list[dict]) -> list[dict]:
    """Per-track-id frame counts, sorted by most frames seen — a proxy for
    time-on-screen/involvement."""
    counts: dict[int, int] = {}
    for row in data:
        counts[row["track_id"]] = counts.get(row["track_id"], 0) + 1
    return sorted(
        ({"track_id": tid, "frames_seen": c} for tid, c in counts.items()),
        key=lambda r: r["frames_seen"],
        reverse=True,
    )
