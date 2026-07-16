import pandas as pd
import streamlit as st

from utils.page_style import apply_theme
from utils.football_data import get_standings_with_fallback, FOOTBALL_DATA_KEY

st.set_page_config(page_title="False9 AI — Statistics", page_icon="⚽", layout="wide")
apply_theme()

st.markdown('<div class="f9-badge">Match Intelligence</div>', unsafe_allow_html=True)
st.title("Statistics")
st.caption(
    "Live standings, every team, with full W-D-L, goal difference, and "
    "recent form where the API provides it. The full analytics engine "
    "(xG, shot maps, pass accuracy) still needs match-video tracking — "
    "see Heatmaps/Predictions for what's already built from that."
)

if not FOOTBALL_DATA_KEY:
    st.warning(
        "Add FOOTBALL_DATA_KEY to .streamlit/secrets.toml to see live "
        "standings here."
    )
    st.stop()

competition = st.selectbox(
    "Competition",
    ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1", "Champions League", "World Cup"],
)

with st.spinner("Fetching standings..."):
    rows, used_previous_season = get_standings_with_fallback(competition)

if used_previous_season:
    st.info("The new season hasn't started yet — showing last season's final table.")

if not rows:
    st.info("No standings data available for this competition right now.")
    st.stop()

is_grouped = any(r.get("group") for r in rows)
if is_grouped:
    st.caption(
        "Grouped tournament — top 2 of each group advance to the knockout "
        "rounds (highlighted green). Since the 2026 World Cup's group stage "
        "is already finished, this reflects each team's group-stage form only."
    )

# ---------------------------------------------------------------------------
# Standout stat cards — real, derived from the fetched data, not invented.
# ---------------------------------------------------------------------------
leader = min(rows, key=lambda r: r["position"])
best_attack = max(rows, key=lambda r: r["goals_for"])
played_rows = [r for r in rows if r["played"] > 0]
best_defense = min(played_rows, key=lambda r: r["goals_against"]) if played_rows else None
best_gd = max(rows, key=lambda r: r["goal_difference"])

card_html = '<div style="display:flex; gap:16px; flex-wrap:wrap; margin-bottom:20px;">'
stat_cards = [("🥇", leader["team"], "Leader" if not is_grouped else "Top seed"),
              ("⚽", f"{best_attack['team']} ({best_attack['goals_for']})", "Best attack")]
if best_defense:
    stat_cards.append(("🛡️", f"{best_defense['team']} ({best_defense['goals_against']})", "Best defense"))
stat_cards.append(("📈", f"{best_gd['team']} ({best_gd['goal_difference']:+d})", "Best goal difference"))

for emoji, value, label in stat_cards:
    card_html += (
        '<div class="f9-card" style="flex:1; min-width:200px; text-align:center;">'
        f'<div style="font-size:28px;">{emoji}</div>'
        f'<div style="font-family:\'Bebas Neue\',sans-serif; font-size:20px; color:#FFB454; margin:4px 0;">{value}</div>'
        f'<div style="font-size:12px; color:#9FB3A6; letter-spacing:.05em; text-transform:uppercase;">{label}</div>'
        '</div>'
    )
card_html += "</div>"
st.markdown(card_html, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Full table — real detail, color-coded, form dots where the API has it.
# ---------------------------------------------------------------------------
FORM_COLORS = {"W": "#00FFA3", "D": "#9FB3A6", "L": "#FF4B4B"}


def form_dots(form_str):
    if not form_str:
        return "—"
    results = form_str.split(",")[-5:]
    dots = "".join(
        f'<span style="display:inline-block; width:9px; height:9px; border-radius:50%; '
        f'background:{FORM_COLORS.get(r.strip(), "#555")}; margin-right:3px;"></span>'
        for r in results
    )
    return dots


groups = sorted(set(r["group"] for r in rows if r.get("group"))) if is_grouped else [None]

for group in groups:
    if group:
        st.markdown(f"#### {group.replace('_', ' ').title()}")
    group_rows = [r for r in rows if r.get("group") == group] if group else rows
    group_rows = sorted(group_rows, key=lambda r: r["position"])

    qualify_cutoff = 2 if is_grouped else 4
    relegation_cutoff = len(group_rows) - 3 if not is_grouped else None

    table_html = (
        '<table style="width:100%; border-collapse:collapse; font-size:14px;">'
        '<thead><tr style="color:#9FB3A6; text-transform:uppercase; font-size:11px; letter-spacing:.05em;">'
        '<th style="text-align:left; padding:8px;">#</th>'
        '<th style="text-align:left; padding:8px;">Team</th>'
        '<th style="padding:8px;">P</th><th style="padding:8px;">W</th>'
        '<th style="padding:8px;">D</th><th style="padding:8px;">L</th>'
        '<th style="padding:8px;">GF</th><th style="padding:8px;">GA</th>'
        '<th style="padding:8px;">GD</th><th style="padding:8px;">Pts</th>'
        '<th style="padding:8px;">Form</th></tr></thead><tbody>'
    )
    for r in group_rows:
        border_color = "transparent"
        if r["position"] <= qualify_cutoff:
            border_color = "#00FFA3"
        elif relegation_cutoff and r["position"] > relegation_cutoff:
            border_color = "#FF4B4B"
        table_html += (
            f'<tr style="border-left:3px solid {border_color}; background:rgba(233,237,228,.03);">'
            f'<td style="padding:8px; color:#9FB3A6;">{r["position"]}</td>'
            f'<td style="padding:8px; font-weight:600;">{r["team"]}</td>'
            f'<td style="padding:8px; text-align:center;">{r["played"]}</td>'
            f'<td style="padding:8px; text-align:center;">{r["won"]}</td>'
            f'<td style="padding:8px; text-align:center;">{r["draw"]}</td>'
            f'<td style="padding:8px; text-align:center;">{r["lost"]}</td>'
            f'<td style="padding:8px; text-align:center;">{r["goals_for"]}</td>'
            f'<td style="padding:8px; text-align:center;">{r["goals_against"]}</td>'
            f'<td style="padding:8px; text-align:center;">{r["goal_difference"]:+d}</td>'
            f'<td style="padding:8px; text-align:center; color:#FFB454; font-weight:700;">{r["points"]}</td>'
            f'<td style="padding:8px; text-align:center;">{form_dots(r.get("form"))}</td>'
            '</tr>'
        )
    table_html += "</tbody></table>"
    st.markdown(table_html, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

st.caption(
    "Green = qualification zone, red = relegation zone — an approximate "
    "visual convention, not each competition's exact official rule."
)