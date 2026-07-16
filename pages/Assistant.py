import streamlit as st

from utils.page_style import apply_theme
from utils.groq_client import get_client, build_data_context, SYSTEM_PROMPT, MODEL
from utils.heatmaps import list_tracking_data_files

st.set_page_config(page_title="False9 AI — Assistant", page_icon="⚽", layout="wide")
apply_theme()

st.markdown('<div class="f9-badge">Football Assistant</div>', unsafe_allow_html=True)
st.title("⚽ False9 AI Assistant")
st.caption(
    "Ask about tactics, stats, fixtures, or anything football — and, if "
    "you've tracked a match below, real distance/speed/sprint data from it."
)

client = get_client()

# Let the assistant reference a specific analyzed match, if any exist.
tracking_files = list_tracking_data_files()
selected_video_stem = None
if tracking_files:
    with st.expander("📹 Reference a tracked match (optional)", expanded=False):
        choice = st.selectbox(
            "Which analyzed match should the assistant know about?",
            ["None"] + [f.name for f in tracking_files],
        )
        if choice != "None":
            selected_video_stem = choice.replace("_tracking_data.json", "")
            st.caption(
                f"Try asking: \"Who covered the most distance?\" or "
                f"\"Compare Player 2 and Player 5.\""
            )

if "messages" not in st.session_state:
    st.session_state.messages = []


def ask(user_prompt: str):
    """Send a message through the model and append both sides to history."""
    st.session_state.messages.append({"role": "user", "content": user_prompt})

    context = build_data_context(client, user_prompt, selected_video_stem)
    api_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    api_messages += st.session_state.messages[:-1]
    api_messages.append({"role": "user", "content": user_prompt + context})

    response = client.chat.completions.create(
        model=MODEL,
        messages=api_messages,
        max_tokens=1024,
    )
    reply = response.choices[0].message.content
    st.session_state.messages.append({"role": "assistant", "content": reply})


# If a quick-prompt card on the landing page sent us here with a question
# already queued up, answer it immediately on load.
pending = st.session_state.pop("pending_prompt", None)
if pending:
    with st.spinner("Reading the play..."):
        ask(pending)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

prompt = st.chat_input("Ask your football AI...")
if prompt:
    with st.chat_message("user"):
        st.write(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Reading the play..."):
            ask(prompt)
            st.write(st.session_state.messages[-1]["content"])