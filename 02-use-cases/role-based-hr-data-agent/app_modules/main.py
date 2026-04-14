"""
Streamlit entry point for the Role-Based HR Data Agent demo (Amazon Bedrock AgentCore Runtime).

Handles OAuth callback, authentication check, and chat interface rendering.
"""

import uuid
from urllib.parse import parse_qs, urlparse

import streamlit as st

from app_modules.auth import AuthManager
from app_modules.chat import ChatManager
from app_modules.styles import apply_custom_styles

# Persona display config
PERSONAS = {
    "HR Manager": {
        "icon": "👔",
        "badge_class": "badge-manager",
        "description": "Full access — all fields visible",
        "scopes": ["read", "pii", "address", "comp"],
    },
    "HR Specialist": {
        "icon": "👨‍💼",
        "badge_class": "badge-specialist",
        "description": "Profiles + PII; compensation and address redacted",
        "scopes": ["read", "pii"],
    },
    "Employee": {
        "icon": "👤",
        "badge_class": "badge-employee",
        "description": "Search only; all sensitive fields redacted",
        "scopes": ["read"],
    },
}

SUGGESTED_QUERIES = [
    "Find all engineers in the company",
    "Show me Sarah Johnson's profile",
    "What is John Smith's compensation?",
    "Search for HR department employees",
]


def main():
    st.set_page_config(
        page_title="HR Data Agent",
        page_icon="🔐",
        layout="centered",
        initial_sidebar_state="expanded",
    )
    apply_custom_styles()

    auth = AuthManager()
    chat = ChatManager()

    # ------------------------------------------------------------------
    # OAuth callback handling
    # ------------------------------------------------------------------
    query_params = st.query_params
    if "code" in query_params and not auth.is_authenticated():
        code = query_params["code"]
        tokens = auth.exchange_code(code)
        if tokens:
            auth.store_tokens(tokens)
            st.query_params.clear()
            st.rerun()
        else:
            st.error("Authentication failed. Please try again.")

    # ------------------------------------------------------------------
    # Login screen
    # ------------------------------------------------------------------
    if not auth.is_authenticated():
        st.title("🔐 HR Data Agent")
        st.markdown("Secure HR data access with role-based DLP enforcement via Amazon Bedrock AgentCore.")
        st.markdown("---")
        if st.button("Login with Cognito", use_container_width=True):
            st.markdown(f'<meta http-equiv="refresh" content="0; url={auth.get_auth_url()}">',
                        unsafe_allow_html=True)
        return

    # ------------------------------------------------------------------
    # Authenticated — Chat interface
    # ------------------------------------------------------------------
    token_claims = auth.decode_token(auth.get_access_token())

    # Session state
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------
    with st.sidebar:
        st.title("HR Data Agent")
        st.markdown("---")

        # Persona selector (for demo — switches OAuth persona client)
        st.subheader("Demo Persona")
        selected_persona = st.selectbox("Select Role", list(PERSONAS.keys()))
        p = PERSONAS[selected_persona]
        st.markdown(
            f'<span class="persona-badge {p["badge_class"]}">{p["icon"]} {selected_persona}</span>',
            unsafe_allow_html=True,
        )
        st.caption(p["description"])
        st.markdown(f"**Scopes:** `{'`, `'.join(p['scopes'])}`")

        st.markdown("---")
        st.subheader("Suggested Queries")
        for q in SUGGESTED_QUERIES:
            if st.button(q, key=f"suggest_{q[:20]}"):
                st.session_state.messages.append({"role": "user", "content": q})
                st.rerun()

        st.markdown("---")
        if st.button("Clear conversation"):
            st.session_state.messages = []
            st.session_state.session_id = str(uuid.uuid4())
            st.rerun()

        if st.button("Logout"):
            auth.logout()
            st.rerun()

    # ------------------------------------------------------------------
    # Chat area
    # ------------------------------------------------------------------
    st.title("🔐 HR Data Agent")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask about employees..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown('<span class="thinking">Thinking...</span>', unsafe_allow_html=True)
            response = chat.send_message(
                message=prompt,
                session_id=st.session_state.session_id,
                access_token=auth.get_access_token(),
                message_placeholder=placeholder,
            )
            if response:
                st.session_state.messages.append({"role": "assistant", "content": response})
