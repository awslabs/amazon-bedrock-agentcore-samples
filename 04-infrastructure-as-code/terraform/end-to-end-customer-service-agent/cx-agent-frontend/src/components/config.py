"""Configuration components for AgentCore."""

import streamlit as st


def render_agentcore_config():
    """Render AgentCore configuration in sidebar."""
    with st.sidebar:
        st.header("⚙️ Configuration")

        # Backend selection
        use_agentcore = st.checkbox(
            "Use AWS AgentCore",
            value=st.session_state.get("use_agentcore", False),
            help="Toggle between local backend and AWS AgentCore",
        )
        st.session_state.use_agentcore = use_agentcore

        if use_agentcore:
            st.subheader("AgentCore Settings")

            # Agent Runtime ARN
            agent_runtime_arn = st.text_input(
                "Agent Runtime ARN",
                value=st.session_state.get("agent_runtime_arn", ""),
                placeholder="arn:aws:bedrock-agent-runtime:region:account:agent/agent-id",
                help="AWS Bedrock Agent Runtime ARN",
            )
            st.session_state.agent_runtime_arn = agent_runtime_arn

            # Region
            region = st.selectbox(
                "AWS Region",
                [
                    "us-east-1",
                    "us-west-2",
                    "eu-west-1",
                    "eu-central-1",
                    "ap-southeast-1",
                ],
                index=0
                if st.session_state.get("region", "us-east-1") == "us-east-1"
                else [
                    "us-east-1",
                    "us-west-2",
                    "eu-west-1",
                    "eu-central-1",
                    "ap-southeast-1",
                ].index(st.session_state.get("region", "us-east-1")),
            )
            st.session_state.region = region

            # Auth Token
            auth_token = st.text_input(
                "JWT Auth Token",
                value=st.session_state.get("auth_token", ""),
                type="password",
                placeholder="Enter JWT token from Cognito",
                help="JWT token for authentication with AgentCore",
            )
            st.session_state.auth_token = auth_token

            # Validation
            config_valid = bool(agent_runtime_arn.strip() and auth_token.strip())
            if not agent_runtime_arn.strip():
                st.error("⚠️ Agent Runtime ARN is required")
            if not auth_token.strip():
                st.error("⚠️ JWT Auth Token is required")

            return config_valid
        else:
            st.info("Using local backend")
            return True
