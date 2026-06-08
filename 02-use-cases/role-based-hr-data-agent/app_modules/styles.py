"""Dark theme CSS styles for the Streamlit HR Data Agent UI."""

import streamlit as st


def apply_custom_styles() -> None:
    st.markdown(
        """
        <style>
        /* ---- Base ---- */
        .stApp { background-color: #0f1117; color: #e0e0e0; }
        .main .block-container { padding-top: 2rem; max-width: 900px; }

        /* ---- Chat bubbles ---- */
        .user-msg {
            background: #1e3a5f; border-radius: 12px 12px 2px 12px;
            padding: 0.8rem 1rem; margin: 0.4rem 0; animation: fadeInUp 0.3s ease;
        }
        .agent-msg {
            background: #1a1f2e; border: 1px solid #2d3748;
            border-radius: 2px 12px 12px 12px;
            padding: 0.8rem 1rem; margin: 0.4rem 0; animation: fadeInUp 0.3s ease;
        }

        /* ---- Persona badges ---- */
        .persona-badge {
            display: inline-block; padding: 0.2rem 0.7rem;
            border-radius: 20px; font-size: 0.8rem; font-weight: 600;
        }
        .badge-manager  { background: #1f4e79; color: #90cdf4; }
        .badge-specialist { background: #2d3748; color: #f6ad55; }
        .badge-employee { background: #1a3328; color: #68d391; }
        .badge-admin    { background: #3b1f5e; color: #d6bcfa; }

        /* ---- Redacted fields ---- */
        .redacted { color: #fc8181; font-style: italic; font-size: 0.85rem; }

        /* ---- Animations ---- */
        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(8px); }
            to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes thinking-pulse {
            0%, 100% { opacity: 0.4; } 50% { opacity: 1; }
        }
        .thinking { animation: thinking-pulse 1.2s infinite; color: #63b3ed; }
        </style>
        """,
        unsafe_allow_html=True,
    )
