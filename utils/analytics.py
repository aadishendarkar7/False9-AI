"""
Pitch calibration + the analytics engine.

Calibration: a homography computed from 4 user-clicked pitch corners,
mapping video-frame pixels to real pitch meters. Without this, "distance
covered" is meaningless (pixels aren't a unit of distance).

Analytics: distance/speed/sprints, computed from tracking data run through
that homography. This is genuinely real, but derived from raw per-frame
detections — not a professional radar-tracking system. Expect some noise,
especially on lower frame-processing rates or shaky footage.
"""
import json
from pathlib import Path

import cv2
import numpy as np
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = ROOT / "outputs"

# Standard sports-science sprint threshold.
SPRINT_THRESHOLD_MS = 7.0
# Frame-to-frame speeds above this are almost certainly detection noise or
# a track-ID switch, not a real human being — excluded rather than let one
# bad frame distort the whole total.
MAX_PLAUSIBLE_SPEED_MS = 12.0


def calibration_path(video_stem: str) -> Path:
    return OUTPUTS_DIR / f"{video_stem}_calibration.json"


def save_calibration(video_stem: str, homography: np.ndarray, pitch_length_m: float, pitch_width_m: float):
    data = {
        "homography": homography.tolist(),
        "pitch_length_m": pitch_length_m,
        "pitch_width_m": pitch_width_m,
    }
    OUTPUTS_DIR.mkdir(exist_ok=True)
    with open(calibration_path(video_stem), "w") as f:
        json.dump(data, f)


def load_calibration(video_stem: str):
    path = calibration_path(video_stem)
    if not path.exists():
        return None
    with open(path) as f:
        data = json.load(f)
    data["homography"] = np.array(data["homography"])
    return data


def compute_homography(pixel_points: list[tuple[float, float]], pitch_length_m: float, pitch_width_m: float) -> np.ndarray:
    """pixel_points must be 4 points clicked in order: top-left, top-right,
    bottom-right, bottom-left of the pitch as visible in frame."""
    src = np.array(pixel_points, dtype="float32")
    dst = np.array([
        [0, 0],
        [pitch_length_m, 0],
        [pitch_length_m, pitch_width_m],
        [0, pitch_width_m],
    ], dtype="float32")
    homography, _ = cv2.findHomography(src, dst)
    return homography


def pixels_to_pitch(homography: np.ndarray, points_px: list[tuple[float, float]]) -> list[tuple[float, float]]:
    pts = np.array(points_px, dtype="float32").reshape(-1, 1, 2)
    transformed = cv2.perspectiveTransform(pts, homography)
    return [(p[0][0], p[0][1]) for p in transformed]


@st.cache_data(show_spinner=False)
def compute_player_analytics(tracking_data: list[dict], calibration: dict, fps: float) -> list[dict]:
    """Returns per-player: track_id, distance_m, avg_speed_kmh,
    max_speed_kmh, sprint_count — sorted by distance covered, descending.

    Cached: this was recomputing every player's full distance/speed/sprint
    history from scratch on every rerun — including just switching which
    player is selected in a dropdown, even though the underlying tracking
    data hadn't changed at all."""
    if not calibration:
        return []
    homography = calibration["homography"]

    by_track: dict[int, list[dict]] = {}
    for row in tracking_data:
        by_track.setdefault(row["track_id"], []).append(row)

    results = []
    for track_id, rows in by_track.items():
        rows.sort(key=lambda r: r["frame"])
        pixel_points = [(r["x"], r["y"]) for r in rows]
        pitch_points = pixels_to_pitch(homography, pixel_points)

        total_distance = 0.0
        max_speed = 0.0
        sprint_frames = 0
        speeds = []

        for i in range(1, len(pitch_points)):
            dt = (rows[i]["frame"] - rows[i - 1]["frame"]) / fps
            if dt <= 0:
                continue
            dx = pitch_points[i][0] - pitch_points[i - 1][0]
            dy = pitch_points[i][1] - pitch_points[i - 1][1]
            dist = (dx ** 2 + dy ** 2) ** 0.5
            speed = dist / dt

            if speed > MAX_PLAUSIBLE_SPEED_MS:
                continue  # treat as noise/ID-switch, not a real movement

            total_distance += dist
            speeds.append(speed)
            max_speed = max(max_speed, speed)
            if speed >= SPRINT_THRESHOLD_MS:
                sprint_frames += 1

        avg_speed = sum(speeds) / len(speeds) if speeds else 0.0

        results.append({
            "track_id": track_id,
            "distance_m": round(total_distance, 1),
            "avg_speed_kmh": round(avg_speed * 3.6, 1),
            "max_speed_kmh": round(max_speed * 3.6, 1),
            "sprint_count": sprint_frames,
        })

    return sorted(results, key=lambda r: r["distance_m"], reverse=True)


@st.cache_data(show_spinner=False)
def get_speed_timeseries(tracking_data: list[dict], track_id: int, calibration: dict, fps: float) -> list[dict]:
    """Per-frame speed over time for one player — the raw series behind
    the fatigue/work-rate decline graph. Same noise-filtering as the main
    analytics function, for consistency."""
    if not calibration:
        return []
    homography = calibration["homography"]

    rows = sorted((r for r in tracking_data if r["track_id"] == track_id), key=lambda r: r["frame"])
    if len(rows) < 2:
        return []
    pixel_points = [(r["x"], r["y"]) for r in rows]
    pitch_points = pixels_to_pitch(homography, pixel_points)

    series = []
    for i in range(1, len(pitch_points)):
        dt = (rows[i]["frame"] - rows[i - 1]["frame"]) / fps
        if dt <= 0:
            continue
        dx = pitch_points[i][0] - pitch_points[i - 1][0]
        dy = pitch_points[i][1] - pitch_points[i - 1][1]
        dist = (dx ** 2 + dy ** 2) ** 0.5
        speed = dist / dt
        if speed > MAX_PLAUSIBLE_SPEED_MS:
            continue
        series.append({
            "time_sec": round(rows[i]["frame"] / fps, 1),
            "speed_kmh": round(speed * 3.6, 1),
        })
    return series


@st.cache_data(show_spinner=False)
def get_sprint_positions(tracking_data: list[dict], track_id: int, calibration: dict, fps: float) -> list[tuple]:
    """Pitch-meter positions (real coordinates) where this player was
    sprinting (>= SPRINT_THRESHOLD_MS) — shows WHERE they sprinted, not
    just how many times."""
    if not calibration:
        return []
    homography = calibration["homography"]

    rows = sorted((r for r in tracking_data if r["track_id"] == track_id), key=lambda r: r["frame"])
    if len(rows) < 2:
        return []
    pixel_points = [(r["x"], r["y"]) for r in rows]
    pitch_points = pixels_to_pitch(homography, pixel_points)

    sprint_points = []
    for i in range(1, len(pitch_points)):
        dt = (rows[i]["frame"] - rows[i - 1]["frame"]) / fps
        if dt <= 0:
            continue
        dx = pitch_points[i][0] - pitch_points[i - 1][0]
        dy = pitch_points[i][1] - pitch_points[i - 1][1]
        dist = (dx ** 2 + dy ** 2) ** 0.5
        speed = dist / dt
        if SPRINT_THRESHOLD_MS <= speed <= MAX_PLAUSIBLE_SPEED_MS:
            sprint_points.append(pitch_points[i])
    return sprint_points


def find_most_similar_player(all_analytics: list[dict], track_id: int):
    """Cosine similarity on [distance, avg_speed, max_speed, sprint_count]
    across players tracked IN THIS CLIP ONLY. Explicitly not a claim of a
    cross-match player-embeddings database — we don't have one. With only
    a handful of players and one data point each, this is a simple,
    honest similarity score, not a research-grade embedding space."""
    target = next((a for a in all_analytics if a["track_id"] == track_id), None)
    if not target or len(all_analytics) < 2:
        return None

    def vec(a):
        return np.array([a["distance_m"], a["avg_speed_kmh"], a["max_speed_kmh"], a["sprint_count"]], dtype=float)

    target_vec = vec(target)
    if np.linalg.norm(target_vec) == 0:
        return None

    best = None
    best_score = -1
    for a in all_analytics:
        if a["track_id"] == track_id:
            continue
        v = vec(a)
        norm_product = np.linalg.norm(target_vec) * np.linalg.norm(v)
        if norm_product == 0:
            continue
        similarity = float(np.dot(target_vec, v) / norm_product)
        if similarity > best_score:
            best_score = similarity
            best = a

    if best is None:
        return None
    return {"track_id": best["track_id"], "similarity_pct": round(best_score * 100, 1)}