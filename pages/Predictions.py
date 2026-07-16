import streamlit as st

st.set_page_config(page_title="False9 AI — Predictions", page_icon="⚽", layout="wide")

try:
    from utils.page_style import apply_theme
    from utils.football_data import get_standings_with_fallback, FOOTBALL_DATA_KEY
    from utils.predictions import predict_match_outcome, project_full_match_stats
    from utils.heatmaps import list_tracking_data_files, load_tracking_data
    from utils.analytics import load_calibration, compute_player_analytics
    from utils.video_processing import get_video_info, get_player_thumbnail, list_uploaded_videos

    apply_theme()

    st.markdown('<div class="f9-badge">Prediction Engine</div>', unsafe_allow_html=True)
    st.title("Predictions")
    st.caption(
        "Honest scope: there's no historical-results dataset here to train a "
        "real ML model on for free, so match outcome uses a simplified Poisson "
        "goal-expectancy model — a real statistical baseline football analytics "
        "has used for decades, transparent about its assumptions rather than "
        "pretending to be more sophisticated than it is. Player projection is a "
        "simple linear extrapolation from tracked clip data, not a forecast."
    )

    tab1, tab2 = st.tabs(["Match Outcome", "Player Projection"])

    with tab1:
        st.markdown("### Match Outcome Predictor")
        if not FOOTBALL_DATA_KEY:
            st.warning("Add FOOTBALL_DATA_KEY to .streamlit/secrets.toml to use this.")
        else:
            competition = st.selectbox(
                "Competition",
                ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1", "World Cup"],
            )
            if competition == "World Cup":
                st.info(
                    "The 2026 World Cup's group stage is finished — most teams "
                    "have already been eliminated, and this data is only each "
                    "team's group-stage form (3 games), not their knockout-round "
                    "run. Treat this as a rough, honest estimate, not a read on "
                    "who's actually playing well right now."
                )
            rows, used_previous_season = get_standings_with_fallback(competition)
            if used_previous_season:
                st.info(
                    "The new season hasn't started yet — using last season's "
                    "final standings instead."
                )
            if not rows:
                st.info("No standings data available right now.")
            else:
                team_names = [r["team"] for r in rows]
                col1, col2 = st.columns(2)
                with col1:
                    team_a_name = st.selectbox("Team A", team_names, index=0)
                with col2:
                    default_b = 1 if len(team_names) > 1 else 0
                    team_b_name = st.selectbox("Team B", team_names, index=default_b)

                if st.button("Predict outcome", type="primary"):
                    team_a = next(r for r in rows if r["team"] == team_a_name)
                    team_b = next(r for r in rows if r["team"] == team_b_name)

                    total_goals = sum(r["goals_for"] for r in rows)
                    total_played = sum(r["played"] for r in rows)
                    league_avg = total_goals / total_played if total_played else 1.3

                    result = predict_match_outcome(team_a, team_b, league_avg)
                    if result:
                        c1, c2, c3 = st.columns(3)
                        c1.metric(f"{team_a_name} win", f"{result['team_a_win']*100:.0f}%")
                        c2.metric("Draw", f"{result['draw']*100:.0f}%")
                        c3.metric(f"{team_b_name} win", f"{result['team_b_win']*100:.0f}%")
                        st.caption(
                            f"Expected goals: {team_a_name} {result['lambda_a']} — "
                            f"{result['lambda_b']} {team_b_name}"
                        )
                    else:
                        st.info("Not enough data to predict this matchup.")
                        with st.expander("Why? (raw data used)"):
                            st.write(f"League avg goals/game: {league_avg}")
                            st.write(f"{team_a_name}: {team_a}")
                            st.write(f"{team_b_name}: {team_b}")

    with tab2:
        st.markdown("### Player Performance Projection")
        files = list_tracking_data_files()
        if not files:
            st.warning("No tracking data yet.")
            if st.button("Go to Tracking →"):
                st.switch_page("pages/Tracking.py")
        else:
            selected_file = st.selectbox(
                "Tracking dataset", files, format_func=lambda p: p.name, key="pred_file"
            )
            data = load_tracking_data(selected_file)
            video_stem = selected_file.stem.replace("_tracking_data", "")
            calibration = load_calibration(video_stem)

            if not calibration:
                st.info(
                    "This video hasn't been calibrated — calibrate it on the "
                    "Tracking page for real projections."
                )
            elif not data:
                st.info("No player positions in this dataset.")
            else:
                matching = [v for v in list_uploaded_videos() if v.stem == video_stem]
                fps = get_video_info(matching[0])["fps"] if matching else 25

                all_analytics = compute_player_analytics(data, calibration, fps)
                if not all_analytics:
                    st.info("No analytics available for this dataset.")
                else:
                    track_ids = [a["track_id"] for a in all_analytics]
                    chosen = st.selectbox(
                        "Choose a player", track_ids, key="pred_player",
                        format_func=lambda t: f"Player {t}",
                    )
                    player_stats = next(a for a in all_analytics if a["track_id"] == chosen)

                    player_frames_data = sorted(
                        (d for d in data if d["track_id"] == chosen), key=lambda d: d["frame"]
                    )

                    if matching and player_frames_data:
                        mid = player_frames_data[len(player_frames_data) // 2]
                        thumbnail = get_player_thumbnail(
                            matching[0], mid["frame"], (mid["x"], mid["y"], mid["w"], mid["h"])
                        )
                        if thumbnail is not None:
                            st.image(thumbnail, caption=f"Player {chosen}", width=160)

                    clip_duration_min = ((player_frames_data[-1]["frame"] + 1) / fps) / 60

                    projection = project_full_match_stats(player_stats["distance_m"], clip_duration_min)
                    if projection:
                        c1, c2 = st.columns(2)
                        c1.metric("Clip distance", f"{player_stats['distance_m']} m")
                        c2.metric("Projected over 90 min", f"{projection['projected_distance_m']} m")
                        st.caption(
                            f"Based on {projection['rate_m_per_min']} m/min observed in this "
                            f"clip ({clip_duration_min:.1f} min). Linear extrapolation only — "
                            "real players don't sustain a constant rate for a full match."
                        )

    st.markdown("---")
    if st.button("← Back to Dashboard"):
        st.switch_page("pages/Dashboard.py")

except Exception as e:
    st.error("Something failed on the Predictions page — full details below:")
    st.exception(e)
