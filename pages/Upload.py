import streamlit as st

from utils.page_style import apply_theme
from utils.video_processing import save_uploaded_video, list_uploaded_videos, get_video_info

st.set_page_config(page_title="False9 AI — Upload", page_icon="⚽", layout="wide")
apply_theme()

st.markdown('<div class="f9-badge">Match Upload</div>', unsafe_allow_html=True)
st.title("Upload")
st.caption("Upload match footage here, then head to Tracking to detect and track players in it.")

uploaded_file = st.file_uploader("Match video", type=["mp4", "mov", "avi", "mkv"])
if uploaded_file is not None:
    if st.button("Save upload", type="primary"):
        with st.spinner("Saving..."):
            path = save_uploaded_video(uploaded_file)
        st.success(f"Saved as {path.name}")
        st.rerun()

st.markdown("### Your uploads")
videos = list_uploaded_videos()
if not videos:
    st.info("No videos uploaded yet.")
else:
    for video in videos:
        info = get_video_info(video)
        st.markdown(
            f'<div class="f9-card"><b>{video.name}</b><br>'
            f'{info["width"]}x{info["height"]} • {info["duration_sec"]}s • '
            f'{info["frame_count"]} frames @ {info["fps"]} fps</div>',
            unsafe_allow_html=True,
        )

st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    if st.button("← Back to Dashboard"):
        st.switch_page("pages/Dashboard.py")
with col2:
    if videos:
        if st.button("Go to Tracking →", type="primary"):
            st.switch_page("pages/Tracking.py")