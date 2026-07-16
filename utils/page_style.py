"""
Shared dark "pitch/tactics" theme applied on every page, so Dashboard,
Assistant, Statistics etc. all look like one product instead of Streamlit
defaults bolted onto a fancy landing page.
"""
import streamlit as st


def apply_theme():
    st.markdown("""
        <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}

            [data-testid="stAppViewContainer"]{ background:#05130D; }
            [data-testid="stHeader"]{ background:rgba(5,19,13,.6); }

            /* sidebar re-skinned to match, instead of default white */
            [data-testid="stSidebar"]{
                background:#0A2A1C;
                border-right:1px solid rgba(233,237,228,.08);
            }
            [data-testid="stSidebar"] *{ color:#E9EDE4 !important; }
            [data-testid="stSidebarNav"] a{
                border-radius:6px;
            }
            [data-testid="stSidebarNav"] a:hover{
                background:rgba(255,180,84,.12);
            }

            h1, h2, h3, h4, p, span, div, label, li{ color:#E9EDE4; }

            /* futuristic chat input, reused wherever a page has chat */
            [data-testid="stChatInput"]{
                background: transparent !important;
                border: none !important;
                box-shadow: none !important;
                padding: 0 !important;
            }
            [data-testid="stChatInput"] > div{
                background: rgba(233,237,228,.06);
                border: 1px solid rgba(255,180,84,.3);
                border-radius: 999px;
            }
            [data-testid="stChatInput"]:focus-within > div{
                border-color: rgba(255,180,84,.75);
                box-shadow: 0 0 30px rgba(255,180,84,.2);
            }
            [data-testid="stChatInput"] textarea{ color:#E9EDE4 !important; }
            [data-testid="stChatInput"] textarea::placeholder{ color:#9FB3A6 !important; }
            [data-testid="stChatInput"] button{
                background: linear-gradient(90deg, #FFB454, #FF8A3D) !important;
                border-radius: 50% !important;
            }
            [data-testid="stChatInput"] button svg{ fill:#05130D !important; }

            [data-testid="stChatMessage"]{
                background: rgba(233,237,228,.04);
                border: 1px solid rgba(233,237,228,.08);
                border-radius: 12px;
            }

            .f9-card{
                background: rgba(233,237,228,.04);
                border: 1px solid rgba(233,237,228,.12);
                border-left: 3px solid #FFB454;
                border-radius: 6px;
                padding: 20px 24px;
                margin-bottom: 14px;
            }
            .f9-badge{
                display:inline-block;
                font-size:11px;
                letter-spacing:.15em;
                text-transform:uppercase;
                color:#FFB454;
                border:1px solid rgba(255,180,84,.4);
                border-radius:999px;
                padding:4px 12px;
                margin-bottom:14px;
            }
        </style>
    """, unsafe_allow_html=True)