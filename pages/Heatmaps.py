import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from utils.page_style import apply_theme
from utils.heatmaps import list_tracking_data_files, load_tracking_data, track_id_summary
from utils.analytics import (
    load_calibration, compute_player_analytics, pixels_to_pitch,
    get_speed_timeseries, get_sprint_positions, find_most_similar_player,
)
from utils.video_processing import get_video_info, get_player_thumbnail, list_uploaded_videos
from utils.team_classification import classify_teams, TEAM_COLORS, TEAM_NAMES
from utils.pitch_control import compute_pitch_control, team_shape_stats

st.set_page_config(page_title="False9 AI — Heat Maps", page_icon="⚽", layout="wide")
apply_theme()

HEAT_COLORSCALE = [[0, "#0A2A1C"], [0.5, "#124B30"], [1, "#FFB454"]]
PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#E9EDE4"),
)


def add_pitch_shapes(fig, length, width):
    """Draws a schematic pitch outline — outline, halfway line, center
    circle — using real pitch dimensions from calibration."""
    fig.add_shape(type="rect", x0=0, y0=0, x1=length, y1=width,
                   line=dict(color="rgba(233,237,228,.4)"))
    fig.add_shape(type="line", x0=length / 2, y0=0, x1=length / 2, y1=width,
                  line=dict(color="rgba(233,237,228,.3)"))
    fig.add_shape(type="circle", x0=length / 2 - 9.15, y0=width / 2 - 9.15,
                  x1=length / 2 + 9.15, y1=width / 2 + 9.15,
                  line=dict(color="rgba(233,237,228,.3)"))
    return fig


st.markdown('<div class="f9-badge">Match Intelligence</div>', unsafe_allow_html=True)
st.title("Heat Maps")
st.caption(
    "Positions are raw video-frame pixels by default. Calibrate a video on "
    "the Tracking page (click its 4 pitch corners) to unlock real "
    "distance/speed/sprint numbers, plus the Team Tactics tab below."
)

files = list_tracking_data_files()
if not files:
    st.warning("No tracking data yet — run tracking on a video first.")
    if st.button("Go to Tracking →"):
        st.switch_page("pages/Tracking.py")
    st.stop()

try:
    selected_file = st.selectbox("Tracking dataset", files, format_func=lambda p: p.name)
    data = load_tracking_data(selected_file)

    if not data:
        st.info("This tracking run didn't capture any player positions.")
        st.stop()

    n_players = len(set(d["track_id"] for d in data))
    st.markdown(f"**{len(data)}** position samples across **{n_players}** tracked players.")

    video_stem = selected_file.stem.replace("_tracking_data", "")
    matching_videos = [v for v in list_uploaded_videos() if v.stem == video_stem]
    calibration = load_calibration(video_stem)
    fps = get_video_info(matching_videos[0])["fps"] if matching_videos else 25

    tab1, tab2, tab3 = st.tabs(["Team Heat Map", "Per-Player", "Team Tactics"])

    with tab1:
        fig = go.Figure(go.Histogram2d(
            x=[d["x"] for d in data], y=[d["y"] for d in data],
            colorscale=HEAT_COLORSCALE, nbinsx=40, nbinsy=25,
        ))
        fig.update_layout(
            height=420, **PLOT_LAYOUT,
            xaxis=dict(title="Frame X (pixels)", gridcolor="rgba(233,237,228,.1)"),
            yaxis=dict(title="Frame Y (pixels)", gridcolor="rgba(233,237,228,.1)", autorange="reversed"),
            margin=dict(l=0, r=0, t=10, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        summary = track_id_summary(data)
        st.markdown("#### Most-tracked players (by frames seen)")
        st.dataframe(
            pd.DataFrame(summary),
            use_container_width=True, hide_index=True,
            column_config={"track_id": "Player #", "frames_seen": "Frames Seen"},
        )

        track_ids = [row["track_id"] for row in summary]
        chosen = st.selectbox("Choose a player", track_ids, format_func=lambda t: f"Player {t}")
        player_points = sorted(
            (d for d in data if d["track_id"] == chosen), key=lambda d: d["frame"]
        )

        if matching_videos and player_points:
            mid_point = player_points[len(player_points) // 2]
            thumbnail = get_player_thumbnail(
                matching_videos[0], mid_point["frame"],
                (mid_point["x"], mid_point["y"], mid_point["w"], mid_point["h"]),
            )
            if thumbnail is not None:
                st.image(thumbnail, caption=f"Player {chosen} — this is who you're looking at", width=160)

        if calibration:
            all_analytics = compute_player_analytics(data, calibration, fps)
            player_stats = next((a for a in all_analytics if a["track_id"] == chosen), None)

            if player_stats:
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Distance covered", f"{player_stats['distance_m']} m")
                m2.metric("Avg speed", f"{player_stats['avg_speed_kmh']} km/h")
                m3.metric("Max speed", f"{player_stats['max_speed_kmh']} km/h")
                m4.metric("Sprints (>7 m/s)", player_stats["sprint_count"])
                st.caption(
                    "Real meters/speeds via pitch calibration — derived from "
                    "raw per-frame tracking, not radar-grade smoothing. "
                    "Expect some noise."
                )

                st.markdown("---")
                st.markdown("#### Player DNA")
                compare_ids = ["None"] + [t for t in track_ids if t != chosen]
                compare_choice = st.selectbox(
                    "Compare with (optional)", compare_ids,
                    format_func=lambda t: "None" if t == "None" else f"Player {t}",
                )

                metrics = ["distance_m", "avg_speed_kmh", "max_speed_kmh", "sprint_count"]
                metric_labels = ["Distance", "Avg Speed", "Max Speed", "Sprints"]
                frames_by_id = {s["track_id"]: s["frames_seen"] for s in summary}
                merged = {
                    a["track_id"]: {**a, "frames_seen": frames_by_id.get(a["track_id"], 0)}
                    for a in all_analytics
                }
                all_metrics = metrics + ["frames_seen"]
                all_labels = metric_labels + ["Involvement"]
                max_vals = {m: max(max((v[m] for v in merged.values()), default=1), 1) for m in all_metrics}

                def normalize(tid):
                    v = merged.get(tid)
                    if not v:
                        return [0] * len(all_metrics)
                    return [v[m] / max_vals[m] * 100 for m in all_metrics]

                r_chosen = normalize(chosen)
                fig_radar = go.Figure()
                fig_radar.add_trace(go.Scatterpolar(
                    r=r_chosen + [r_chosen[0]], theta=all_labels + [all_labels[0]],
                    fill="toself", name=f"Player {chosen}", line=dict(color="#FFB454"),
                ))
                if compare_choice != "None":
                    r_compare = normalize(compare_choice)
                    fig_radar.add_trace(go.Scatterpolar(
                        r=r_compare + [r_compare[0]], theta=all_labels + [all_labels[0]],
                        fill="toself", name=f"Player {compare_choice}", line=dict(color="#00FFA3"),
                    ))
                fig_radar.update_layout(
                    polar=dict(
                        radialaxis=dict(visible=True, range=[0, 100], gridcolor="rgba(233,237,228,.15)"),
                        bgcolor="rgba(0,0,0,0)",
                    ),
                    **PLOT_LAYOUT, showlegend=True, height=380,
                )
                st.plotly_chart(fig_radar, use_container_width=True)
                st.caption(
                    "Each axis is normalized to the highest value among "
                    "tracked players in this clip (100 = the top performer "
                    "on that metric here, not a universal benchmark)."
                )

                similar = find_most_similar_player(all_analytics, chosen)
                if similar:
                    st.info(
                        f"Most similar player in this match: Player "
                        f"{similar['track_id']} ({similar['similarity_pct']}% "
                        "similar) — based on this clip's stats only, not a "
                        "cross-match database."
                    )

                st.markdown("---")
                st.markdown("#### Work-rate over time")
                speed_series = get_speed_timeseries(data, chosen, calibration, fps)
                if speed_series:
                    fig_fatigue = go.Figure(go.Scatter(
                        x=[s["time_sec"] for s in speed_series],
                        y=[s["speed_kmh"] for s in speed_series],
                        mode="lines", line=dict(color="#FFB454", width=1.5),
                    ))
                    fig_fatigue.update_layout(
                        height=280, **PLOT_LAYOUT,
                        xaxis=dict(title="Time (s)", gridcolor="rgba(233,237,228,.1)"),
                        yaxis=dict(title="Speed (km/h)", gridcolor="rgba(233,237,228,.1)"),
                        margin=dict(l=0, r=0, t=10, b=0),
                    )
                    st.plotly_chart(fig_fatigue, use_container_width=True)
                    st.caption(
                        "Raw per-frame speed, not smoothed — a real decline "
                        "trend across a full match needs a longer clip than "
                        "a short one to be meaningful."
                    )
                else:
                    st.caption("Not enough data for a work-rate graph.")

                st.markdown("---")
                st.markdown("#### Sprint locations")
                sprint_points = get_sprint_positions(data, chosen, calibration, fps)
                if sprint_points:
                    fig_sprint = go.Figure(go.Scatter(
                        x=[p[0] for p in sprint_points], y=[p[1] for p in sprint_points],
                        mode="markers", marker=dict(color="#FF4B4B", size=9, opacity=.75),
                    ))
                    fig_sprint = add_pitch_shapes(fig_sprint, calibration["pitch_length_m"], calibration["pitch_width_m"])
                    fig_sprint.update_layout(
                        height=320, **PLOT_LAYOUT,
                        xaxis=dict(visible=False, range=[0, calibration["pitch_length_m"]]),
                        yaxis=dict(visible=False, range=[0, calibration["pitch_width_m"]], scaleanchor="x"),
                        margin=dict(l=0, r=0, t=10, b=0),
                    )
                    st.plotly_chart(fig_sprint, use_container_width=True)
                else:
                    st.caption("No sprints recorded for this player in this clip.")
        else:
            st.info(
                "This video hasn't been calibrated, so distance/speed/DNA/"
                "fatigue/sprint-map features aren't available — only "
                "pixel-space position below. Calibrate it on the Tracking "
                "page for all of this."
            )

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Movement trail**")
            fig2 = go.Figure(go.Scatter(
                x=[p["x"] for p in player_points], y=[p["y"] for p in player_points],
                mode="lines+markers", line=dict(color="#FFB454", width=2),
                marker=dict(size=4, color="#00FFA3"),
            ))
            fig2.update_layout(
                height=360, **PLOT_LAYOUT,
                xaxis=dict(gridcolor="rgba(233,237,228,.1)"),
                yaxis=dict(gridcolor="rgba(233,237,228,.1)", autorange="reversed"),
                margin=dict(l=0, r=0, t=10, b=0),
            )
            st.plotly_chart(fig2, use_container_width=True)
        with col2:
            st.markdown("**Positional heat map**")
            fig3 = go.Figure(go.Histogram2d(
                x=[p["x"] for p in player_points], y=[p["y"] for p in player_points],
                colorscale=HEAT_COLORSCALE, nbinsx=25, nbinsy=15,
            ))
            fig3.update_layout(
                height=360, **PLOT_LAYOUT,
                xaxis=dict(gridcolor="rgba(233,237,228,.1)"),
                yaxis=dict(gridcolor="rgba(233,237,228,.1)", autorange="reversed"),
                margin=dict(l=0, r=0, t=10, b=0),
            )
            st.plotly_chart(fig3, use_container_width=True)

    with tab3:
        st.markdown("#### Team Tactics")
        if not calibration:
            st.info("Calibrate this video on the Tracking page to unlock team tactics.")
        elif not matching_videos:
            st.info("Couldn't find the source video for team classification.")
        else:
            st.caption(
                "Team split is a heuristic (jersey-color clustering) — not "
                "perfect, especially for goalkeepers or similar-colored kits. "
                "Pitch control is a simplified nearest-player grid model, not "
                "the velocity-weighted models pro teams use."
            )
            with st.spinner("Classifying teams by jersey color..."):
                team_labels = classify_teams(matching_videos[0], data)

            frame_choices = sorted(set(d["frame"] for d in data))
            chosen_frame = st.select_slider("Moment to inspect", options=frame_choices)

            positions = {}
            for tid in set(d["track_id"] for d in data):
                rows = [d for d in data if d["track_id"] == tid]
                closest = min(rows, key=lambda r: abs(r["frame"] - chosen_frame))
                positions[tid] = (closest["x"], closest["y"])

            pixel_pts = list(positions.values())
            pitch_pts = pixels_to_pitch(calibration["homography"], pixel_pts)
            pitch_positions = dict(zip(positions.keys(), pitch_pts))

            team_a_pts = [pitch_positions[tid] for tid in positions if team_labels.get(tid, 0) == 0]
            team_b_pts = [pitch_positions[tid] for tid in positions if team_labels.get(tid, 0) == 1]

            control = compute_pitch_control(
                team_a_pts, team_b_pts,
                calibration["pitch_length_m"], calibration["pitch_width_m"],
            )

            if control:
                c1, c2 = st.columns(2)
                c1.metric(f"{TEAM_NAMES[0]} control", f"{control['team_a_pct']}%")
                c2.metric(f"{TEAM_NAMES[1]} control", f"{control['team_b_pct']}%")

                fig_pc = go.Figure(go.Heatmap(
                    x=control["grid_x"][0], y=control["grid_y"][:, 0], z=control["grid_team"],
                    colorscale=[[0, TEAM_COLORS[0]], [1, TEAM_COLORS[1]]],
                    opacity=0.35, showscale=False,
                ))
                fig_pc.add_trace(go.Scatter(
                    x=[p[0] for p in team_a_pts], y=[p[1] for p in team_a_pts],
                    mode="markers", marker=dict(color=TEAM_COLORS[0], size=12, line=dict(color="white", width=1)),
                    name=TEAM_NAMES[0],
                ))
                fig_pc.add_trace(go.Scatter(
                    x=[p[0] for p in team_b_pts], y=[p[1] for p in team_b_pts],
                    mode="markers", marker=dict(color=TEAM_COLORS[1], size=12, line=dict(color="white", width=1)),
                    name=TEAM_NAMES[1],
                ))
                fig_pc = add_pitch_shapes(fig_pc, calibration["pitch_length_m"], calibration["pitch_width_m"])
                fig_pc.update_layout(
                    height=420, **PLOT_LAYOUT,
                    xaxis=dict(visible=False, range=[0, calibration["pitch_length_m"]]),
                    yaxis=dict(visible=False, range=[0, calibration["pitch_width_m"]], scaleanchor="x"),
                    margin=dict(l=0, r=0, t=10, b=0),
                )
                st.plotly_chart(fig_pc, use_container_width=True)

                st.markdown("#### Team shape")
                shape_a = team_shape_stats(team_a_pts)
                shape_b = team_shape_stats(team_b_pts)
                sc1, sc2 = st.columns(2)
                with sc1:
                    st.markdown(f"**{TEAM_NAMES[0]}**")
                    if shape_a:
                        st.write(f"Compactness: {shape_a['compactness_m']} m")
                        st.write(f"Width: {shape_a['width_m']} m")
                        st.write(f"Depth: {shape_a['depth_m']} m")
                with sc2:
                    st.markdown(f"**{TEAM_NAMES[1]}**")
                    if shape_b:
                        st.write(f"Compactness: {shape_b['compactness_m']} m")
                        st.write(f"Width: {shape_b['width_m']} m")
                        st.write(f"Depth: {shape_b['depth_m']} m")
            else:
                st.info("Not enough players on each side at this moment to compute pitch control.")

except Exception as e:
    st.error("Something failed while building the heat maps — full details below:")
    st.exception(e)

st.markdown("---")
if st.button("← Back to Dashboard"):
    st.switch_page("pages/Dashboard.py")