# ⚽ False9 AI — Football Analytics Platform

An AI-powered football analytics platform: an LLM assistant grounded in live match/standings data, computer-vision player detection and tracking from uploaded video, pitch-calibrated distance/speed analytics, team classification and pitch control, and a transparent (non-black-box) match-outcome predictor.

Built incrementally, end to end — landing page and animations, through a full computer-vision pipeline, to a multi-page analytics product.

## Live demo

_[Add your deployed Streamlit Community Cloud link here once deployed — see Deployment below]_

## Features

| Page | What it does |
|---|---|
| **Landing (`app.py`)** | Animated hero, tactical formation graphic, kickoff/goal-celebration micro-interactions |
| **Dashboard** | Live KPIs, league form chart, AI-generated insight on the current title race |
| **Assistant** | Groq-powered chat, grounded in live fixtures/standings and — if you've tracked a match — real per-player distance/speed data from it |
| **Statistics** | Full live standings for Premier League, La Liga, Bundesliga, Serie A, Ligue 1, Champions League, and the World Cup — every team, full W-D-L, form, goal difference |
| **Upload** | Upload match footage (mp4/mov/avi/mkv) |
| **Tracking** | YOLOv8 player detection → BoT-SORT tracking with persistent player IDs → 4-point pitch calibration (pixels → real meters) |
| **Heatmaps** | Team + per-player heat maps, movement trails, Player DNA radar comparison, work-rate-over-time graphs, sprint location maps, jersey-color team classification, Voronoi pitch control, team shape stats |
| **Predictions** | Match outcome probabilities (Poisson goal-expectancy model) and player performance projections |

## Tech stack

- **Frontend/app**: Streamlit (multi-page), custom HTML/CSS/JS for the landing hero
- **LLM**: Groq (free tier), `llama-3.3-70b-versatile`
- **Computer vision**: YOLOv8 (Ultralytics, COCO-pretrained) for detection, BoT-SORT for tracking
- **Data**: football-data.org (free tier) for live fixtures/standings
- **Analytics**: OpenCV homography for pitch calibration, NumPy/SciPy for geometry and clustering, Plotly for all charts

## Setup

```bash
git clone <your-repo-url>
cd false9-ai
python3.12 -m venv venv   # 3.12 recommended — see note below
source venv/bin/activate
pip install -r requirements.txt
```

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in:

```toml
GROQ_API_KEY = "gsk_..."           # free at console.groq.com/keys
FOOTBALL_DATA_KEY = "..."          # free at football-data.org/client/register
```

Run it:

```bash
streamlit run app.py
```

### A note on Python version

The computer-vision stack (OpenCV, PyTorch via Ultralytics) doesn't always have prebuilt wheels for the newest Python release the moment it comes out. **Python 3.12 is the safe, well-supported choice.** If you hit `ModuleNotFoundError` on `cv2` or similar after installing, that's almost always the cause — recreate the venv with `python3.12` instead of whatever's newest.

## Project structure

```
├── app.py                    # Landing page (hero, animations)
├── pages/                    # Streamlit multi-page app
│   ├── Dashboard.py
│   ├── Assistant.py
│   ├── Statistics.py
│   ├── Upload.py
│   ├── Tracking.py
│   ├── Heatmaps.py
│   └── Predictions.py
├── utils/                    # Shared logic
│   ├── page_style.py         # Shared theme across all pages
│   ├── football_data.py      # football-data.org API + off-season fallback
│   ├── groq_client.py        # LLM client, intent detection, RAG context
│   ├── video_processing.py   # Upload handling, YOLO detection/tracking
│   ├── analytics.py          # Pitch calibration + distance/speed/sprints
│   ├── team_classification.py# Jersey-color team clustering
│   ├── pitch_control.py      # Voronoi pitch control, team shape stats
│   ├── heatmaps.py           # Tracking-data loading helpers
│   └── predictions.py        # Poisson match-outcome model
├── ui/                       # Landing page HTML/CSS/JS
├── models/                   # Tracker configs (YOLO weights auto-download here on first run)
├── uploads/                  # User-uploaded match videos (gitignored)
├── outputs/                  # Generated tracking data, annotated videos, calibration (gitignored)
├── data/                     # team_ids.json (football-data.org team ID map)
└── scripts/                  # fetch_team_ids.py — regenerates the full team-ID map
```

## Honest limitations

This section exists on purpose — a real engineering project should be upfront about what it doesn't do, not just what it does.

- **Detection is generic, not football-specific.** YOLOv8's COCO-pretrained weights detect the "person" class — there's no free football-specific model, so this is the same starting point most hobbyist football-analytics projects use. No ball detection, no jersey-number recognition.
- **Players are identified by tracking ID, not jersey number.** "Player 7" means "the 7th unique track ByteTrack/BoT-SORT assigned," not squad number 7.
- **Tracking struggles across camera cuts.** No tracker can maintain identity across an actual scene change (replays, camera switches) — this is a fundamental limit of tracking-by-detection, not a bug. Fixed single-camera footage tracks far more reliably than broadcast TV footage.
- **No possession, passing, or shot data.** Distance/speed/sprints are real (once calibrated); "who created the most chances" or "pass accuracy" would need ball detection and event classification, which isn't built.
- **Match outcome prediction is a simplified Poisson model**, not a trained ML model — there's no free historical-results dataset to train one on. It's a real, transparent statistical baseline, not a black box, and not claimed to be state-of-the-art.
- **Team classification is a jersey-color heuristic** (k-means clustering), not a trained classifier — goalkeepers in a different kit or visually similar team colors can confuse it.
- **Pitch control is a simplified nearest-player grid model**, not the velocity-weighted models professional teams use.

## Roadmap (what could come next)

- Ball detection (COCO includes a "sports ball" class — reachable, but broadcast-footage detection is notoriously noisy without a fine-tuned model)
- Possession/pass-event detection built on top of ball tracking
- Pose estimation (Ultralytics ships pose models) for rough body-orientation analysis
- A proper multi-match player database, to make "similar players" and embeddings genuinely meaningful instead of within-clip-only

## Deployment

**Streamlit Community Cloud** (free) is the natural fit — connect this GitHub repo at [share.streamlit.io](https://share.streamlit.io), set `GROQ_API_KEY` and `FOOTBALL_DATA_KEY` in its Secrets settings (same TOML format as your local `secrets.toml`), and deploy.

**Honest caveat**: the free tier gives you roughly 1GB of RAM with no GPU. The chat/stats/dashboard pages will run fine there. The **computer-vision pipeline (Tracking) is genuinely resource-hungry** — PyTorch + YOLO inference on CPU with limited RAM may be slow or hit memory limits on longer clips. For a live recruiter-facing demo, consider either: keeping frame counts low (the Tracking page's slider defaults to 300), or treating the CV pages as a local-only demo and including a short screen-recording/GIF in this README instead of relying on it working smoothly on free hosting.

## Credits

Designed & developed by Aadi Shendarkar.