"""
Free football-data.org API helpers.

Pulled out of app.py so every page (Assistant, Statistics, Dashboard, etc.)
can share the same team-ID map, competition codes, and fetch functions
instead of each page re-implementing its own copy.
"""
import datetime
import json
from pathlib import Path

import requests
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
FOOTBALL_DATA_KEY = st.secrets.get("FOOTBALL_DATA_KEY", "")

COMPETITION_CODES = {
    "premier league": "PL", "epl": "PL", "pl": "PL",
    "la liga": "PD", "laliga": "PD",
    "bundesliga": "BL1",
    "serie a": "SA",
    "ligue 1": "FL1",
    "champions league": "CL", "ucl": "CL",
    "world cup": "WC", "fifa world cup": "WC", "wc": "WC",
}

_TEAM_IDS_PATH = ROOT / "data" / "team_ids.json"
if _TEAM_IDS_PATH.exists():
    with open(_TEAM_IDS_PATH) as f:
        TEAM_IDS = json.load(f)
else:
    # Starter set — run scripts/fetch_team_ids.py to generate the full file.
    TEAM_IDS = {
        "arsenal": 57, "manchester city": 65, "man city": 65, "liverpool": 64,
        "manchester united": 66, "man united": 66, "chelsea": 61,
        "tottenham": 73, "real madrid": 86, "barcelona": 81,
        "bayern munich": 5, "psg": 524, "juventus": 109,
        "ac milan": 98, "inter milan": 108,
    }


@st.cache_data(ttl=300, show_spinner=False)
def get_upcoming_fixtures(team_name: str) -> str:
    """Next 5 scheduled matches for a team. Cached 5 min so we don't blow
    through football-data.org's 10-req/min free limit."""
    team_id = TEAM_IDS.get(team_name.lower().strip())
    if not team_id or not FOOTBALL_DATA_KEY:
        return ""
    try:
        resp = requests.get(
            f"https://api.football-data.org/v4/teams/{team_id}/matches",
            headers={"X-Auth-Token": FOOTBALL_DATA_KEY},
            params={"status": "SCHEDULED", "limit": 5},
            timeout=8,
        )
        resp.raise_for_status()
        matches = resp.json().get("matches", [])
    except Exception:
        return ""
    if not matches:
        return ""
    lines = [
        f"- {m['utcDate'][:10]}: {m['homeTeam']['name']} vs "
        f"{m['awayTeam']['name']} ({m['competition']['name']})"
        for m in matches[:5]
    ]
    return "Upcoming fixtures:\n" + "\n".join(lines)


@st.cache_data(ttl=300, show_spinner=False)
def get_standings_table(competition_name: str, season: int | None = None) -> list[dict]:
    """Raw standings rows for a competition — used by both the text
    formatter below (for AI context) and the Dashboard's chart, so we only
    hit the API once per competition per cache window instead of twice.
    `season` is the starting year of a season (e.g. 2025 for 2025-26);
    omit for football-data.org's default ("current") season.

    Returns ALL teams (previously capped at 10) — domestic leagues have
    18-20, the World Cup has 48 across 12 groups. football-data.org
    returns multiple "standings" blocks per competition (TOTAL/HOME/AWAY
    splits for leagues; one block per group for tournaments) — we only
    keep "TOTAL" blocks to avoid triple-counting every team."""
    code = COMPETITION_CODES.get(competition_name.lower().strip())
    if not code or not FOOTBALL_DATA_KEY:
        return []
    try:
        params = {"season": season} if season is not None else {}
        resp = requests.get(
            f"https://api.football-data.org/v4/competitions/{code}/standings",
            headers={"X-Auth-Token": FOOTBALL_DATA_KEY},
            params=params,
            timeout=8,
        )
        resp.raise_for_status()
        standings_blocks = resp.json()["standings"]
    except Exception:
        return []

    rows = []
    for block in standings_blocks:
        if block.get("type") != "TOTAL":
            continue  # skip HOME-only / AWAY-only splits
        group_label = block.get("group")  # e.g. "GROUP_A" for tournaments, None for leagues
        for row in block["table"]:
            rows.append({
                "position": row["position"],
                "team": row["team"]["name"],
                "points": row["points"],
                "played": row["playedGames"],
                "won": row.get("won", 0),
                "draw": row.get("draw", 0),
                "lost": row.get("lost", 0),
                "goals_for": row.get("goalsFor", 0),
                "goals_against": row.get("goalsAgainst", 0),
                "goal_difference": row.get("goalDifference", 0),
                "form": row.get("form"),  # e.g. "W,W,D,L,W" — None if unavailable
                "group": group_label,
            })
    return rows


def get_standings_with_fallback(competition_name: str) -> tuple[list[dict], bool]:
    """Same as get_standings_table, but if the 'current' season shows 0
    games played for every team (i.e. it's the off-season and the new
    season hasn't started yet — true for all our supported leagues as of
    mid-July 2026), falls back to last season's final standings instead of
    just returning nothing. Returns (rows, used_previous_season)."""
    rows = get_standings_table(competition_name)
    if rows and sum(r["played"] for r in rows) > 0:
        return rows, False

    today = datetime.date.today()
    # European season-year convention: a season starting in year Y is
    # labeled Y (e.g. "2025" = 2025-26). Before ~August, "this year's"
    # season is actually last year's start year.
    current_season_start = today.year - 1 if today.month < 7 else today.year
    previous_season_start = current_season_start - 1

    fallback_rows = get_standings_table(competition_name, season=previous_season_start)
    if fallback_rows:
        return fallback_rows, True
    return rows, False


def get_standings(competition_name: str) -> str:
    """Current league table for a competition, as text (for AI context).
    Falls back to last season's final table during the off-season."""
    rows, used_previous_season = get_standings_with_fallback(competition_name)
    if not rows:
        return ""
    lines = [
        f"{r['position']}. {r['team']} — {r['points']} pts ({r['played']} played)"
        + (f" [{r['group']}]" if r.get("group") else "")
        for r in rows
    ]
    header = (
        "Standings from last completed season (current season hasn't "
        "started yet):" if used_previous_season else "Current standings (all teams):"
    )
    return header + "\n" + "\n".join(lines)