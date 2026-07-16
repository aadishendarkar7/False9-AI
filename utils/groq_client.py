"""
Shared Groq client + intent detection.

Pulled out of app.py so pages/Assistant.py (and later, other pages that
want to ask the model something) don't need their own copy.
"""
import json

import streamlit as st
from groq import Groq

from utils.football_data import get_standings, get_upcoming_fixtures

MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = (
    "You are False9 AI, a sharp, knowledgeable football (soccer) analyst and "
    "assistant. You help with tactics, formations, match analysis, stats, "
    "and general football conversation. Be concise, confident, and use "
    "correct footballing terminology. If fixture, standings, or match "
    "analytics data is provided in the user's message as [Live data], use "
    "it directly and don't say you lack real-time data. "
    "One honest limitation to be upfront about if asked: tracked players "
    "are labeled Player 1, Player 2, etc. by an arbitrary tracking ID, not "
    "their real jersey number — there's no jersey-number recognition in "
    "this pipeline. Also, there's no possession, passing, chance-creation, "
    "or shot data available — only player positions, distance, and speed "
    "from tracked video. Don't invent numbers for things you don't have "
    "data on; say plainly that it isn't tracked."
)


@st.cache_resource
def get_client() -> Groq:
    if "GROQ_API_KEY" not in st.secrets:
        st.error(
            "No Groq API key found. Add GROQ_API_KEY to .streamlit/secrets.toml."
        )
        st.stop()
    return Groq(api_key=st.secrets["GROQ_API_KEY"])


@st.cache_data(ttl=3600, show_spinner=False)
def extract_intent(_client: Groq, user_prompt: str) -> dict:
    """Ask the model what football data (if any) the user is asking for.
    Returns {"type": "fixtures"|"standings"|"match_analytics"|"none",
    "team": str|None, "competition": str|None}.

    Cached: this was firing an extra uncached Groq call on every single
    chat message just to classify intent, even for repeated/similar
    questions. Leading underscore on _client tells st.cache_data not to
    try to hash the Groq client object itself."""
    system = (
        "Extract football data intent from the user's message. "
        "Respond with ONLY a JSON object, no other text, no markdown fences. "
        "Schema: {\"type\": \"fixtures\" | \"standings\" | \"match_analytics\" "
        "| \"none\", \"team\": string or null, \"competition\": string or null}. "
        "Use \"fixtures\" if they're asking about a specific team's next "
        "game(s)/schedule. Use \"standings\" if they're asking about a "
        "league table/rankings/tournament groups. Use \"match_analytics\" if "
        "they're asking about a tracked/uploaded/analyzed match — player "
        "distance, speed, sprints, movement, or comparing tracked players. "
        "Use \"none\" for general questions. \"competition\" should be one "
        "of: premier league, la liga, bundesliga, serie a, ligue 1, "
        "champions league, world cup — or null."
    )
    try:
        resp = _client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=150,
            temperature=0,
        )
        raw = resp.choices[0].message.content.strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(raw)
    except Exception:
        return {"type": "none", "team": None, "competition": None}


def build_match_analytics_context(video_stem: str) -> str:
    """Formats the current tracked-video analytics (distance/speed/sprints
    per player) as text for the assistant. Returns "" if this video hasn't
    been tracked/calibrated yet."""
    from utils.heatmaps import list_tracking_data_files, load_tracking_data
    from utils.analytics import load_calibration, compute_player_analytics
    from utils.video_processing import get_video_info, list_uploaded_videos

    matching_data = [f for f in list_tracking_data_files() if f.stem.replace("_tracking_data", "") == video_stem]
    if not matching_data:
        return ""

    data = load_tracking_data(matching_data[0])
    calibration = load_calibration(video_stem)
    if not calibration or not data:
        return ""

    matching_videos = [v for v in list_uploaded_videos() if v.stem == video_stem]
    fps = get_video_info(matching_videos[0])["fps"] if matching_videos else 25

    analytics = compute_player_analytics(data, calibration, fps)
    if not analytics:
        return ""

    lines = [
        f"Player {a['track_id']}: {a['distance_m']}m covered, "
        f"{a['avg_speed_kmh']} km/h avg, {a['max_speed_kmh']} km/h max, "
        f"{a['sprint_count']} sprints"
        for a in analytics[:15]
    ]
    return (
        "Tracked match analytics (from uploaded video, real pitch-calibrated "
        "distance/speed — players identified by an arbitrary Player number, "
        "not real jersey number; no possession/pass/shot data exists):\n"
        + "\n".join(lines)
    )


def build_data_context(client: Groq, user_prompt: str, selected_video_stem: str | None = None) -> str:
    """Simple RAG step: if the user seems to want fixtures/standings/match
    analytics, fetch it and return a context string to append to their
    message."""
    from utils.football_data import FOOTBALL_DATA_KEY

    intent = extract_intent(client, user_prompt)

    if intent.get("type") == "match_analytics" and selected_video_stem:
        analytics_context = build_match_analytics_context(selected_video_stem)
        if analytics_context:
            return f"\n\n[Live data]\n{analytics_context}"

    if not FOOTBALL_DATA_KEY:
        return ""

    if intent.get("type") == "fixtures" and intent.get("team"):
        fixtures = get_upcoming_fixtures(intent["team"])
        if fixtures:
            return f"\n\n[Live data]\n{fixtures}"

    if intent.get("type") == "standings" and intent.get("competition"):
        standings = get_standings(intent["competition"])
        if standings:
            return f"\n\n[Live data]\n{standings}"

    return ""


@st.cache_data(ttl=600, show_spinner=False)
def generate_ai_insight(_client: Groq, competition_name: str, standings_text: str) -> str:
    """Short, punchy 2-3 sentence read on the current table, for the
    Dashboard's 'AI Insight' card. Cached 10 min per competition — this is
    a nice-to-have card, not something worth spending API calls on every
    single page rerun. (Leading underscore on _client tells st.cache_data
    not to try to hash the Groq client object.)"""
    if not standings_text:
        return ""
    try:
        resp = _client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": (
                    "You are a sharp football analyst. Given a league table, "
                    "write a punchy 2-3 sentence read on what's happening at "
                    "the top of it — the title race, a surprise package, "
                    "whatever's most interesting. No preamble, no lists."
                )},
                {"role": "user", "content": f"{competition_name} standings:\n{standings_text}"},
            ],
            max_tokens=200,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return ""