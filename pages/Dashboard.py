import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go

from utils.page_style import apply_theme
from utils.football_data import get_standings_with_fallback, get_standings, FOOTBALL_DATA_KEY, TEAM_IDS
from utils.groq_client import get_client, generate_ai_insight
from utils.video_processing import list_uploaded_videos

st.set_page_config(page_title="False9 AI — Dashboard", page_icon="⚽", layout="wide")
apply_theme()

st.markdown('<div class="f9-badge">Dashboard</div>', unsafe_allow_html=True)
st.title("Command Center")
st.caption(
    "Live where the data actually exists today; honest placeholders where "
    "it doesn't yet (those land in the phases noted below)."
)

# ---------------------------------------------------------------------------
# KPI row — real numbers derived from actual app state, not invented stats.
# ---------------------------------------------------------------------------
queries_answered = len(
    [m for m in st.session_state.get("messages", []) if m["role"] == "assistant"]
)
data_status = "Connected" if FOOTBALL_DATA_KEY else "Not configured"

kpis = [
    ("6", "Competitions live"),
    (str(len(set(TEAM_IDS.values()))), "Teams mapped"),
    (str(queries_answered), "Assistant answers this session"),
    (data_status, "Football-data.org"),
]

kpi_html = '<div style="display:flex; gap:16px; flex-wrap:wrap;">'
for value, label in kpis:
    kpi_html += (
        '<div class="f9-card" style="flex:1; min-width:180px; text-align:center;">'
        f'<div class="kpi-value" data-target="{value}" '
        'style="font-family:\'Bebas Neue\',sans-serif; font-size:40px; color:#FFB454;">'
        f'{value}</div>'
        '<div style="font-size:13px; color:#9FB3A6; letter-spacing:.05em; '
        f'text-transform:uppercase;">{label}</div>'
        '</div>'
    )
kpi_html += "</div>"
st.markdown(kpi_html, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Two-column layout: real chart + AI insight | honest empty states
# ---------------------------------------------------------------------------
left, right = st.columns([1.3, 1])

with left:
    st.markdown("### League Form")
    if not FOOTBALL_DATA_KEY:
        st.warning("Add FOOTBALL_DATA_KEY to .streamlit/secrets.toml to see this chart.")
    else:
        competition = st.selectbox(
            "Competition", ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1", "World Cup"],
            label_visibility="collapsed",
        )
        rows, used_previous_season = get_standings_with_fallback(competition)
        if used_previous_season:
            st.caption("New season hasn't started — showing last season's final table.")
        if rows:
            fig = go.Figure(go.Bar(
                x=[r["points"] for r in rows][::-1],
                y=[r["team"] for r in rows][::-1],
                orientation="h",
                marker=dict(color="#FFB454"),
            ))
            fig.update_layout(
                height=360,
                margin=dict(l=0, r=10, t=10, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#E9EDE4"),
                xaxis=dict(title="Points", gridcolor="rgba(233,237,228,.1)"),
                yaxis=dict(gridcolor="rgba(233,237,228,.05)"),
            )
            st.plotly_chart(fig, use_container_width=True)

            with st.spinner("Generating insight..."):
                client = get_client()
                standings_text = get_standings(competition)
                insight = generate_ai_insight(client, competition, standings_text)
            if insight:
                st.markdown(
                    f'<div class="f9-card"><b>🧠 AI Insight</b><br>{insight}</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("No standings data available right now.")

with right:
    st.markdown("### Coming Online")
    st.markdown(
        '<div class="f9-card"><b>🗺️ Heat Maps</b><br>'
        "Now live — team and per-player positional heat maps from your "
        "tracked clips.</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="f9-card"><b>📈 Predictions</b><br>'
        "Now live — match outcome probabilities (Poisson model) and player "
        "performance projections.</div>",
        unsafe_allow_html=True,
    )
    uploads = list_uploaded_videos()
    if uploads:
        upload_lines = "<br>".join(v.name for v in uploads[:5])
        st.markdown(
            f'<div class="f9-card"><b>📁 Recent Uploads</b><br>{upload_lines}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="f9-card"><b>📁 Recent Uploads</b><br>'
            "No uploads yet — try the Upload page.</div>",
            unsafe_allow_html=True,
        )

st.markdown("### Jump to")
c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    if st.button("⚽ Assistant", use_container_width=True):
        st.switch_page("pages/Assistant.py")
with c2:
    if st.button("📊 Statistics", use_container_width=True):
        st.switch_page("pages/Statistics.py")
with c3:
    if st.button("🎥 Upload", use_container_width=True):
        st.switch_page("pages/Upload.py")
with c4:
    if st.button("🧭 Tracking", use_container_width=True):
        st.switch_page("pages/Tracking.py")
with c5:
    if st.button("🗺️ Heatmaps", use_container_width=True):
        st.switch_page("pages/Heatmaps.py")
with c6:
    if st.button("📈 Predictions", use_container_width=True):
        st.switch_page("pages/Predictions.py")

# ---------------------------------------------------------------------------
# Tiny count-up animation on the KPI numbers. st.markdown can't execute
# <script> tags (React ignores them), so this runs through a components.html
# iframe instead, reaching into the parent page the same way the landing
# hero does. Purely cosmetic — degrades gracefully to a static number if
# anything here fails.
# ---------------------------------------------------------------------------
components.html("""
<script>
try {
    const doc = window.parent.document;
    const els = doc.querySelectorAll('.kpi-value');
    els.forEach((el) => {
        const target = el.dataset.target;
        const num = parseInt(target, 10);
        if (isNaN(num)) return; // non-numeric KPI like "Connected" — leave as-is
        let current = 0;
        const step = Math.max(1, Math.ceil(num / 20));
        const tick = () => {
            current = Math.min(current + step, num);
            el.textContent = current;
            if (current < num) requestAnimationFrame(tick);
        };
        tick();
    });
} catch (err) {
    console.warn("[False9] KPI count-up failed (numbers still show statically):", err);
}
</script>
""", height=0)