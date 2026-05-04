"""
Chat manager — sends messages to the Amazon Bedrock AgentCore Runtime and streams responses.
"""

import json
import logging
import os
from typing import Optional

import boto3
import requests
import streamlit as st

from agent_config.utils import get_ssm_parameter
from app_modules.utils import make_urls_clickable

logger = logging.getLogger(__name__)


class ChatManager:
    """Manages chat interactions with the AgentCore Runtime."""

    def __init__(self):
        self.region = os.getenv("AWS_REGION", "us-east-1")
        # runtime-url is the full ARN-encoded invocation URL stored by agentcore_agent_runtime.py
        self.runtime_url = get_ssm_parameter("/app/hrdlp/runtime-url") or ""

    def send_message(
        self,
        message: str,
        session_id: str,
        access_token: str,
        message_placeholder,
    ) -> Optional[str]:
        """
        POST to AgentCore Runtime and stream the response into message_placeholder.
        """
        if not self.runtime_url:
            st.error("Runtime URL not configured. Check /app/hrdlp/runtime-id in SSM.")
            return None

        session = boto3.session.Session()
        credentials = session.get_credentials().get_frozen_credentials()

        payload = {"prompt": message, "sessionId": session_id}
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }

        try:
            with requests.post(
                self.runtime_url,
                json=payload,
                headers=headers,
                stream=True,
                timeout=120,
            ) as resp:
                resp.raise_for_status()
                full_response = ""
                for chunk in resp.iter_content(chunk_size=None, decode_unicode=True):
                    if chunk:
                        full_response += chunk
                        message_placeholder.markdown(
                            make_urls_clickable(full_response) + " ▌",
                            unsafe_allow_html=True,
                        )
                message_placeholder.markdown(
                    make_urls_clickable(full_response), unsafe_allow_html=True
                )
                return full_response
        except requests.Timeout:
            st.error("Request timed out. The agent may still be processing.")
        except requests.HTTPError as e:
            st.error(f"Runtime error: {e.response.status_code} — {e.response.text[:200]}")
        except Exception as e:
            st.error(f"Unexpected error: {e}")
        return None
