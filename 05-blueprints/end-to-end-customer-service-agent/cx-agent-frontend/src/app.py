"""Main Streamlit application."""

import uuid
from datetime import datetime

import streamlit as st

from components.chat import render_message, render_sidebar
from components.config import render_agentcore_config
from models.message import Message
from services.conversation_client import ConversationClient
from services.agentcore_client import AgentCoreClient


def init_session_state():
    """Initialize session state variables."""
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "user_id" not in st.session_state:
        st.session_state.user_id = f"user_{str(uuid.uuid4())[:8]}"
    if "agent_runtime_arn" not in st.session_state:
        st.session_state.agent_runtime_arn = ""
    if "region" not in st.session_state:
        st.session_state.region = "us-east-1"
    if "use_agentcore" not in st.session_state:
        st.session_state.use_agentcore = False
    if "auth_token" not in st.session_state:
        st.session_state.auth_token = ""


def main():
    """Main application."""
    st.set_page_config(
        page_title="CX Agent Chat",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Custom CSS for better design
    st.markdown(
        """
    <style>
    .stButton > button {
        border-radius: 20px;
        border: 1px solid #e0e0e0;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    .feedback-section {
        background-color: #f8f9fa;
        padding: 10px;
        border-radius: 10px;
        margin: 10px 0;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    st.title("🤖 CX Agent Chat")
    if st.session_state.get("use_agentcore", False):
        st.caption("Powered by AWS Bedrock AgentCore Runtime")
    else:
        st.caption("Powered by LiteLLM Gateway hosted on AWS")

    init_session_state()

    # Render configuration
    config_valid = render_agentcore_config()
    model = render_sidebar()

    # Initialize client based on configuration
    if st.session_state.use_agentcore and config_valid:
        auth_token = st.session_state.get("auth_token", "")
        client = AgentCoreClient(
            agent_runtime_arn=st.session_state.agent_runtime_arn,
            region=st.session_state.region,
            auth_token=auth_token,
        )
        if auth_token:
            st.info("🚀 Connected to AgentCore Runtime")
        else:
            st.warning("⚠️ AgentCore configured but no auth token provided")
    else:
        client = ConversationClient()
        if st.session_state.use_agentcore:
            st.warning("⚠️ AgentCore configuration invalid, using local backend")
        else:
            st.info("🔧 Using local backend")

    # Display chat messages
    for message in st.session_state.messages:
        render_message(message, client)

    # Chat input
    if prompt := st.chat_input("Type your message..."):
        # Generate new conversation ID if needed
        if not st.session_state.conversation_id:
            st.session_state.conversation_id = str(uuid.uuid4())

        # Add user message
        user_message = Message(role="user", content=prompt, timestamp=datetime.now())
        st.session_state.messages.append(user_message)
        render_message(user_message)

        # Send message and get response
        with st.spinner("Thinking..."):
            if isinstance(client, AgentCoreClient):
                response = client.send_message(
                    st.session_state.conversation_id,
                    prompt,
                    model,
                    st.session_state.user_id,
                )
            else:
                response = client.send_message(
                    st.session_state.conversation_id,
                    prompt,
                    model,
                    st.session_state.user_id,
                )

            if response:
                # Add assistant message
                metadata = {
                    "model": model,
                    "status": response.get("status", "success"),
                }

                # Add tools_used to metadata if available
                if "tools_used" in response and response["tools_used"]:
                    metadata["tools_used"] = ",".join(response["tools_used"])

                # Add all metadata from API response
                if "metadata" in response and response["metadata"]:
                    metadata.update(response["metadata"])

                assistant_message = Message(
                    role="assistant",
                    content=response.get("response", response.get("message", "")),
                    timestamp=datetime.now(),
                    metadata=metadata,
                )
                st.session_state.messages.append(assistant_message)
                render_message(assistant_message, client)

        st.rerun()


if __name__ == "__main__":
    main()
