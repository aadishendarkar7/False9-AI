"""
Video upload + player detection/tracking helpers.

Detection uses a standard YOLOv8 model pretrained on COCO, filtered to the
"person" class (class id 0) as a stand-in for "player detection" — there's
no free, pretrained football-specific model, and training one needs a
labeled dataset + real GPU time, which is out of scope here. This is the
same starting point most hobbyist football-analytics projects use.

Tracking uses Ultralytics' built-in BoT-SORT tracker (model.track()), with
a custom config (models/botsort_custom.yaml) tuned for longer occlusion
tolerance — no separate tracker package to install or wire up by hand.
"""
import json
import time
from pathlib import Path

import cv2
import imageio
import numpy as np
import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parent.parent
UPLOADS_DIR = ROOT / "uploads"
OUTPUTS_DIR = ROOT / "outputs"

UPLOADS_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}


def save_uploaded_video(uploaded_file) -> Path:
    """Save a Streamlit UploadedFile to uploads/, timestamped so re-uploading
    a same-named file never silently overwrites an earlier one."""
    suffix = Path(uploaded_file.name).suffix
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    dest = UPLOADS_DIR / f"{timestamp}_{Path(uploaded_file.name).stem}{suffix}"
    with open(dest, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return dest


def list_uploaded_videos() -> list[Path]:
    if not UPLOADS_DIR.exists():
        return []
    return sorted(
        (p for p in UPLOADS_DIR.iterdir() if p.suffix.lower() in ALLOWED_EXTENSIONS),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def get_video_info(path: Path) -> dict:
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    cap.release()
    duration = frame_count / fps if fps else 0
    return {
        "fps": round(fps, 1),
        "frame_count": frame_count,
        "width": width,
        "height": height,
        "duration_sec": round(duration, 1),
    }


def get_sample_frame(path: Path, frame_number: int = 0):
    cap = cv2.VideoCapture(str(path))
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return None
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


@st.cache_resource(show_spinner=False)
def load_model(model_name: str = "yolov8n.pt"):
    """Loads a YOLOv8 model, auto-downloading the small pretrained weights
    file (~6MB) on first run via ultralytics. Cached as a resource so it
    only loads once per session instead of on every rerun/button click."""
    from ultralytics import YOLO
    return YOLO(model_name)


# A clean cyan accent — higher contrast against grass than amber, and reads
# as "tech/analytics" rather than "yellow warning tape." BGR order for cv2.
BOX_COLOR = (235, 200, 40)  # BGR -> a vivid sky-blue/cyan
LABEL_BG_COLOR = (25, 25, 25)  # near-black, blended translucent
LABEL_TEXT_COLOR = (255, 255, 255)


def draw_player_box(frame_bgr: np.ndarray, xyxy, label: str) -> np.ndarray:
    """Custom box style: anti-aliased cyan outline + a translucent label
    pill (blended, not a solid block), instead of Ultralytics' default
    thick solid-color box — which is also what was reading as blurry, since
    unaliased cv2 shapes get exaggerated into visible jagged/blurred edges
    once the video is compressed."""
    x1, y1, x2, y2 = [int(v) for v in xyxy]

    cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), BOX_COLOR, 2, lineType=cv2.LINE_AA)

    (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    label_y1 = max(0, y1 - text_h - 12)

    overlay = frame_bgr.copy()
    cv2.rectangle(overlay, (x1, label_y1), (x1 + text_w + 12, y1), LABEL_BG_COLOR, -1)
    cv2.addWeighted(overlay, 0.6, frame_bgr, 0.4, 0, dst=frame_bgr)

    cv2.putText(
        frame_bgr, label, (x1 + 6, y1 - 6),
        cv2.FONT_HERSHEY_SIMPLEX, 0.55, LABEL_TEXT_COLOR, 1, lineType=cv2.LINE_AA,
    )
    return frame_bgr


def detect_players_on_frame(model, frame_rgb: np.ndarray):
    """Runs detection on a single frame, filtered to the 'person' class.
    Note: this is a single independent frame with no tracking — there's no
    persistent player identity here (that only exists once you run Step 3,
    which uses ByteTrack). Returns (annotated_frame_rgb, player_count)."""
    results = model.predict(frame_rgb, classes=[0], verbose=False)
    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR).copy()

    boxes = results[0].boxes
    for box in boxes:
        conf = float(box.conf[0])
        draw_player_box(frame_bgr, box.xyxy[0].tolist(), f"Player ({conf:.0%})")

    annotated_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    return annotated_rgb, len(boxes)


def get_player_thumbnail(video_path: Path, frame_number: int, bbox_xywh: tuple, padding: int = 15):
    """Crops a specific player's bounding box out of a specific frame —
    this is the actual answer to 'how do I know who Player 3 is': track IDs
    are just numbers, so seeing a real cropped photo of that player is what
    ties the number to an actual person in the footage."""
    frame = get_sample_frame(video_path, frame_number)
    if frame is None:
        return None
    x, y, w, h = bbox_xywh
    x1 = max(0, int(x - w / 2) - padding)
    y1 = max(0, int(y - h / 2) - padding)
    x2 = int(x + w / 2) + padding
    y2 = int(y + h / 2) + padding
    crop = frame[y1:y2, x1:x2]
    return crop if crop.size > 0 else None


def get_custom_tracker_config() -> str:
    """Builds a tracker config by taking whatever version of ultralytics is
    actually installed's own current botsort.yaml and only overriding
    track_buffer (longer occlusion tolerance) — rather than hand-maintaining
    a full copy of a schema that changes between ultralytics versions (which
    is exactly what broke last time: a missing 'with_reid' field)."""
    import ultralytics

    default_path = Path(ultralytics.__file__).parent / "cfg" / "trackers" / "botsort.yaml"
    with open(default_path) as f:
        config = yaml.safe_load(f)

    config["track_buffer"] = 60  # default 30 -> 60: survive longer occlusion gaps

    custom_path = OUTPUTS_DIR / "_botsort_custom.yaml"
    with open(custom_path, "w") as f:
        yaml.dump(config, f)

    return str(custom_path)


def track_players_in_video(model, video_path: Path, max_frames: int = 300, progress_callback=None) -> dict:
    """Runs YOLO + ByteTrack over up to `max_frames` frames of the video.
    Writes an annotated output video to outputs/ and a JSON file of
    per-frame track positions (the raw data the analytics engine and
    heatmaps consume). Returns a summary dict.

    Uses imageio's ffmpeg writer (real H.264) rather than cv2.VideoWriter's
    default mp4v codec, which most browsers silently can't decode for
    playback — that mismatch is what made earlier output videos look like
    they'd frozen on a single frame."""
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    cap.release()

    out_path = OUTPUTS_DIR / f"{video_path.stem}_tracked.mp4"
    writer = imageio.get_writer(
        str(out_path), fps=fps, codec="libx264", quality=10, macro_block_size=None
    )

    track_data = []
    seen_ids = set()
    frame_idx = 0

    results_stream = model.track(
        source=str(video_path),
        classes=[0],
        tracker=get_custom_tracker_config(),
        persist=True,
        stream=True,
        verbose=False,
    )

    for result in results_stream:
        if frame_idx >= max_frames:
            break

        frame_bgr = result.orig_img.copy()

        if result.boxes.id is not None:
            ids = result.boxes.id.int().tolist()
            xyxy_list = result.boxes.xyxy.tolist()
            xywh_list = result.boxes.xywh.tolist()
            for track_id, xyxy, (x, y, w, h) in zip(ids, xyxy_list, xywh_list):
                draw_player_box(frame_bgr, xyxy, f"Player {track_id}")
                seen_ids.add(track_id)
                track_data.append({
                    "frame": frame_idx, "track_id": track_id,
                    "x": round(x, 1), "y": round(y, 1),
                    "w": round(w, 1), "h": round(h, 1),
                })

        writer.append_data(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))

        frame_idx += 1
        if progress_callback:
            progress_callback(frame_idx, max_frames)

    writer.close()

    data_path = OUTPUTS_DIR / f"{video_path.stem}_tracking_data.json"
    with open(data_path, "w") as f:
        json.dump(track_data, f)

    return {
        "output_video": out_path,
        "data_file": data_path,
        "frames_processed": frame_idx,
        "unique_players_tracked": len(seen_ids),
    }