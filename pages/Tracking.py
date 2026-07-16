import time

import cv2
import numpy as np
import streamlit as st
from PIL import Image
from streamlit_image_coordinates import streamlit_image_coordinates

from utils.page_style import apply_theme
from utils.video_processing import (
    list_uploaded_videos, get_sample_frame, load_model,
    detect_players_on_frame, track_players_in_video,
)
from utils.analytics import compute_homography, save_calibration, load_calibration

st.set_page_config(page_title="False9 AI — Tracking", page_icon="⚽", layout="wide")
apply_theme()

st.markdown('<div class="f9-badge">Tactical AI</div>', unsafe_allow_html=True)
st.title("Player Detection & Tracking")
st.caption(
    "Detection finds players in a single frame using YOLOv8 (pretrained on "
    "COCO, filtered to the 'person' class — there's no free football-specific "
    "model, so this is the same starting point most hobbyist football-"
    "analytics projects use). Tracking extends that across the whole clip "
    "with BoT-SORT, giving each player a consistent ID frame-to-frame — "
    "though on broadcast TV footage with camera cuts/replays/zooms, some ID "
    "switches are expected no matter how well-tuned the tracker is, since no "
    "tracker can maintain identity across an actual scene change. A single "
    "fixed/wide camera angle (no cuts) will track far more consistently."
)

videos = list_uploaded_videos()
if not videos:
    st.warning("No videos uploaded yet.")
    if st.button("Go to Upload →"):
        st.switch_page("pages/Upload.py")
    st.stop()

video = st.selectbox("Choose a video", videos, format_func=lambda p: p.name)

st.markdown("### Step 1 — Detect players in a sample frame")
st.caption(
    "This is a single, independent frame — there's no persistent player "
    "identity here yet (no 'Player 1' that stays Player 1 across frames). "
    "That only exists once you run Step 3 below, which uses ByteTrack to "
    "keep each player's ID consistent throughout the clip."
)
if st.button("Detect players"):
    with st.spinner("Loading model + running detection..."):
        frame = get_sample_frame(video, frame_number=0)
        if frame is None:
            st.error("Couldn't read a frame from this video.")
        else:
            model = load_model()
            annotated, count = detect_players_on_frame(model, frame)
            st.image(annotated, caption=f"{count} players detected")

st.markdown("### Step 2 — Calibrate the pitch (needed for real distance/speed)")
st.caption(
    "Distance and speed are meaningless in raw pixels. Click the pitch's 4 "
    "corners, in order — top-left, top-right, bottom-right, bottom-left, as "
    "they appear in frame — and this converts every tracked position into "
    "real meters. Skip this if you only want heat maps, not real distances."
)

existing_calibration = load_calibration(video.stem)
if existing_calibration:
    st.success(
        f"Already calibrated for this video "
        f"({existing_calibration['pitch_length_m']}m x {existing_calibration['pitch_width_m']}m pitch)."
    )

col_a, col_b = st.columns(2)
with col_a:
    pitch_length = st.number_input("Pitch length (m)", value=105.0, min_value=1.0)
with col_b:
    pitch_width = st.number_input("Pitch width (m)", value=68.0, min_value=1.0)

if "calib_points" not in st.session_state:
    st.session_state.calib_points = []
if "calib_last_click" not in st.session_state:
    st.session_state.calib_last_click = None

calib_frame = get_sample_frame(video, frame_number=0)
if calib_frame is not None:
    corner_labels = ["top-left", "top-right", "bottom-right", "bottom-left"]
    next_idx = len(st.session_state.calib_points)

    if next_idx < 4:
        st.write(f"Click the **{corner_labels[next_idx]}** pitch corner.")
    else:
        st.write("All 4 points collected.")

    # Draw already-clicked points on a copy of the frame so it's clear
    # what's been marked so far.
    preview = calib_frame.copy()
    for i, (px, py) in enumerate(st.session_state.calib_points):
        cv2.circle(preview, (int(px), int(py)), 8, (255, 180, 84), -1)
        cv2.putText(preview, str(i + 1), (int(px) + 10, int(py)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 180, 84), 2)

    pil_img = Image.fromarray(preview)
    coords = streamlit_image_coordinates(pil_img, width=preview.shape[1], key="calib_click")

    if coords is not None and coords != st.session_state.calib_last_click:
        st.session_state.calib_last_click = coords
        if len(st.session_state.calib_points) < 4:
            st.session_state.calib_points.append((coords["x"], coords["y"]))
            st.rerun()

    col_c, col_d = st.columns(2)
    with col_c:
        if st.button("Reset points"):
            st.session_state.calib_points = []
            st.session_state.calib_last_click = None
            st.rerun()
    with col_d:
        if len(st.session_state.calib_points) == 4:
            if st.button("Save calibration", type="primary"):
                homography = compute_homography(
                    st.session_state.calib_points, pitch_length, pitch_width
                )
                save_calibration(video.stem, homography, pitch_length, pitch_width)
                st.session_state.calib_points = []
                st.success("Calibration saved.")
                st.rerun()

st.markdown("### Step 3 — Track players across the clip")
max_frames = st.slider(
    "Frames to process", min_value=50, max_value=1000, value=300, step=50,
    help="Higher = more of the video, but slower — especially on CPU. "
         "Start low to confirm it works before running a longer clip.",
)
if st.button("Run tracking", type="primary"):
    try:
        progress_bar = st.progress(0, text="Starting...")
        start_time = time.time()

        def on_progress(done, total):
            elapsed = time.time() - start_time
            rate = done / elapsed if elapsed > 0 else 0
            remaining = (total - done) / rate if rate > 0 else 0
            progress_bar.progress(
                done / total,
                text=f"Frame {done}/{total} — {elapsed:.0f}s elapsed, ~{remaining:.0f}s remaining",
            )

        with st.spinner("Loading model..."):
            model = load_model()

        result = track_players_in_video(
            model, video, max_frames=max_frames, progress_callback=on_progress
        )
        total_time = time.time() - start_time
        progress_bar.empty()

        st.success(
            f"Processed {result['frames_processed']} frames in {total_time:.0f}s — "
            f"{result['unique_players_tracked']} unique players tracked."
        )
        st.video(str(result["output_video"]))
        st.caption(
            f"Tracking data saved to {result['data_file'].name} — "
            "the Heatmaps page will use this (and real distance/speed too, if "
            "you calibrated above)."
        )
    except Exception as e:
        st.error("Tracking failed — full details below:")
        st.exception(e)

st.markdown("---")
if st.button("← Back to Dashboard"):
    st.switch_page("pages/Dashboard.py")