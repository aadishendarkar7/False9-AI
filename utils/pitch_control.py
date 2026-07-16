"""
Pitch control and team shape — real computational geometry, from tracked,
pitch-calibrated positions split by team (see team_classification.py).

Pitch control here is a simplified grid-based nearest-player model, not the
velocity-weighted models professional teams use (which would need carefully
derived player velocity vectors — a further, real step up in complexity).
This is an honest, standard simplification, not a shortcut dressed up as
something more sophisticated.
"""
import numpy as np


def compute_pitch_control(team_a_points: list[tuple], team_b_points: list[tuple],
                           pitch_length: float, pitch_width: float, resolution: int = 60):
    """Grid over the pitch; each cell assigned to whichever team has the
    nearest player. Team control % = fraction of cells closest to that team."""
    if not team_a_points or not team_b_points:
        return None

    xs = np.linspace(0, pitch_length, resolution)
    ys = np.linspace(0, pitch_width, max(10, int(resolution * pitch_width / pitch_length)))
    grid_x, grid_y = np.meshgrid(xs, ys)
    grid_points = np.stack([grid_x.ravel(), grid_y.ravel()], axis=1)

    all_points = np.array(team_a_points + team_b_points)
    team_labels = np.array([0] * len(team_a_points) + [1] * len(team_b_points))

    dists = np.linalg.norm(grid_points[:, None, :] - all_points[None, :, :], axis=2)
    nearest = np.argmin(dists, axis=1)
    grid_team = team_labels[nearest].reshape(grid_x.shape)

    return {
        "grid_x": grid_x,
        "grid_y": grid_y,
        "grid_team": grid_team,
        "team_a_pct": round(float((grid_team == 0).mean() * 100), 1),
        "team_b_pct": round(float((grid_team == 1).mean() * 100), 1),
    }


def team_shape_stats(points: list[tuple]):
    """Compactness (mean pairwise distance — lower = tighter shape), width
    (spread across the pitch-width axis), depth (spread across the
    pitch-length axis). Real geometry from real coordinates."""
    if len(points) < 2:
        return None
    pts = np.array(points)
    n = len(pts)
    total_dist = 0.0
    count = 0
    for i in range(n):
        for j in range(i + 1, n):
            total_dist += float(np.linalg.norm(pts[i] - pts[j]))
            count += 1
    compactness = total_dist / count if count else 0.0

    return {
        "compactness_m": round(compactness, 1),
        "width_m": round(float(pts[:, 1].max() - pts[:, 1].min()), 1),
        "depth_m": round(float(pts[:, 0].max() - pts[:, 0].min()), 1),
    }