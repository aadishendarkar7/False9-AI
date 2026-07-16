"""
Team-side classification via jersey-color clustering.

Real technique, honestly scoped: there's no roster/team data available from
a single tracked clip, so players are split into two groups by clustering
the average color of their bounding-box crop (jersey color is the dominant
visual signal in a torso-region crop). This is a heuristic, not perfect —
goalkeepers in a different kit, referees, and visually similar kits can
confuse it. Flagged wherever it's used in the UI, not presented as
ground truth.
"""
import numpy as np
import streamlit as st
from scipy.cluster.vq import kmeans2

from utils.video_processing import get_sample_frame

# Distinct UI colors for "Team A" / "Team B" — arbitrary assignment, not
# tied to either team's real kit colors (we don't know which team is which).
TEAM_COLORS = {0: "#22D3FF", 1: "#FF6B6B"}
TEAM_NAMES = {0: "Team A", 1: "Team B"}


def _average_torso_color(frame_rgb: np.ndarray, bbox_xywh: tuple):
    """Average color of the upper-middle portion of a player's crop —
    the torso/jersey region, avoiding grass or background bleeding into
    the average from a full-body crop."""
    x, y, w, h = bbox_xywh
    x1, y1 = max(0, int(x - w / 2)), max(0, int(y - h / 2))
    x2, y2 = int(x + w / 2), int(y + h / 2)
    crop = frame_rgb[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    crop_h = crop.shape[0]
    torso = crop[int(crop_h * 0.15):int(crop_h * 0.55), :]
    if torso.size == 0:
        torso = crop
    return torso.reshape(-1, 3).mean(axis=0)


@st.cache_data(show_spinner=False)
def classify_teams(video_path, tracking_data: list[dict], sample_frames: int = 5) -> dict:
    """Returns {track_id: 0 or 1}. Samples a handful of frames per player
    (not every frame — one solid color read is enough and much faster)."""
    by_track: dict[int, list[dict]] = {}
    for row in tracking_data:
        by_track.setdefault(row["track_id"], []).append(row)

    track_colors = {}
    for track_id, rows in by_track.items():
        rows_sorted = sorted(rows, key=lambda r: r["frame"])
        step = max(1, len(rows_sorted) // sample_frames)
        sampled = rows_sorted[::step][:sample_frames]

        colors = []
        for row in sampled:
            frame = get_sample_frame(video_path, row["frame"])
            if frame is None:
                continue
            color = _average_torso_color(frame, (row["x"], row["y"], row["w"], row["h"]))
            if color is not None:
                colors.append(color)

        if colors:
            track_colors[track_id] = np.mean(colors, axis=0)

    if len(track_colors) < 2:
        return {tid: 0 for tid in track_colors}

    track_ids = list(track_colors.keys())
    color_matrix = np.array([track_colors[tid] for tid in track_ids])

    # normalize so brightness differences don't dominate over actual hue
    std = color_matrix.std(axis=0)
    std[std == 0] = 1e-6
    normalized = (color_matrix - color_matrix.mean(axis=0)) / std

    try:
        _, labels = kmeans2(normalized, 2, seed=42, minit="++")
    except Exception:
        return {tid: 0 for tid in track_ids}

    return {tid: int(label) for tid, label in zip(track_ids, labels)}