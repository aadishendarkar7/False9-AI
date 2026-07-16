import streamlit as st
import streamlit.components.v1 as components

from utils.page_style import apply_theme

st.set_page_config(
    page_title="False9 AI",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_theme()

# ---------------------------------------------------------------------------
# Load hero UI
# ---------------------------------------------------------------------------
with open("ui/hero.html", encoding="utf-8") as f:
    html = f.read()
with open("ui/style.css", encoding="utf-8") as f:
    css = f.read()
with open("ui/script.js", encoding="utf-8") as f:
    js = f.read()

components.html(
    f"""
    <style>{css}</style>
    {html}
    <script>{js}</script>
    """,
    height=1080,
    scrolling=False,
)

# ---------------------------------------------------------------------------
# Hidden navigation proxies.
#
# The hero above renders inside a sandboxed iframe (components.html) — pure
# client-side JS with no direct line into Streamlit's Python/rerun cycle.
# The trick: put REAL Streamlit widgets here, visually hidden, and have the
# iframe's JS reach into the parent page (same-origin) and .click() them
# programmatically. A real button click is a real button click as far as
# Streamlit is concerned, so this triggers a proper rerun + st.switch_page —
# same underlying technique as the chat-autofill hack, just aimed at
# navigation instead of text input.
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Streamlit gives any element with an explicit key= a CSS class of
       .st-key-<that key> — the officially supported way to target specific
       elements, and far more reliable than the marker/:has() sibling-
       selector trick this used to use. */
    .st-key-nav_proxies {
        position: absolute;
        left: -9999px;
        top: -9999px;
        height: 0;
        overflow: hidden;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.container(key="nav_proxies"):
    nav_dashboard = st.button("nav_dashboard", key="nav_dashboard")
    nav_tracking = st.button("nav_tracking", key="nav_tracking")
    nav_statistics = st.button("nav_statistics", key="nav_statistics")
    nav_assistant = st.button("nav_assistant", key="nav_assistant")

# This is a fixed string we chose ourselves, not something typed by the
# user — so there's no need to relay it out of the iframe at all. (The
# previous version tried to pass it through a hidden text_input, which was
# unreliable: Streamlit doesn't always commit a text_input's value to the
# backend on every keystroke, so the nav button's click could fire before
# the text value was actually registered.)
ASSISTANT_QUICK_PROMPT = (
    "Give me a deep dive into an underrated piece of football tactics or "
    "history — something like the evolution of pressing systems, a famous "
    "tactical innovation, or a match that changed how the game is played — "
    "and explain why it actually mattered."
)

if nav_dashboard:
    st.switch_page("pages/Dashboard.py")
elif nav_tracking:
    st.switch_page("pages/Tracking.py")
elif nav_statistics:
    st.switch_page("pages/Statistics.py")
elif nav_assistant:
    st.session_state["pending_prompt"] = ASSISTANT_QUICK_PROMPT
    st.switch_page("pages/Assistant.py")