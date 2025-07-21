# import ast
import sys
from typing import Any, Optional
import streamlit as st
import requests
import base64
import hashlib
import os
import uuid
from urllib.parse import urlencode

# from streamlit_cookies_manager import EncryptedCookieManager
import json
import jwt
import time
import re
import urllib
from scripts.utils import read_config, get_aws_region, get_ssm_parameter
from streamlit_cookies_controller import CookieController

# ==== Configuration ====
AGENT_NAME = "default"

# crude way to parse args
if len(sys.argv) > 1:
    for arg in sys.argv:
        if arg.startswith("--agent="):
            AGENT_NAME = arg.split("=")[1]

COGNITO_DOMAIN = get_ssm_parameter(
    "/app/customersupport/agentcore/cognito_domain"
).replace("https://", "")
CLIENT_ID = get_ssm_parameter("/app/customersupport/agentcore/web_client_id")
REDIRECT_URI = "http://localhost:8501/"
SCOPES = "email openid profile"

# ==== Initialize cookies manager ====
cookies = CookieController()

st.set_page_config(layout="wide")

# if not cookies.ready():
#     st.stop()  # Wait for cookies to load


# ==== PKCE Helpers ====
def generate_pkce_pair():
    code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode("utf-8").rstrip("=")
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .decode("utf-8")
        .rstrip("=")
    )
    return code_verifier, code_challenge


# ==== Clickable URL Helpers ====
def make_urls_clickable(text):
    """Convert URLs in text to clickable HTML links."""
    # Comprehensive URL regex pattern
    url_pattern = r"https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?"

    def replace_url(match):
        url = match.group(0)
        # Clean URL and create clickable link with styling to match theme
        return f'<a href="{url}" target="_blank" style="color:#4fc3f7;text-decoration:underline;">{url}</a>'

    return re.sub(url_pattern, replace_url, text)


def create_safe_markdown_text(text, message_placeholder):
    safe_text = text.encode("utf-16", "surrogatepass").decode("utf-16")

    message_placeholder.markdown(safe_text, unsafe_allow_html=True)


# ==== Logout function ====
def logout():
    cookies.remove("tokens")
    # Clear cookies on logout as well (in case)
    # cookies.remove("code_verifier")
    # cookies.remove("code_challenge")
    # cookies.remove("oauth_state")
    # cookies.save()

    del st.session_state["session_id"]
    del st.session_state["messages"]
    del st.session_state["agent_arn"]
    del st.session_state["pending_assistant"]
    del st.session_state["region"]

    logout_url = f"https://{COGNITO_DOMAIN}/logout?" + urlencode(
        {"client_id": CLIENT_ID, "logout_uri": REDIRECT_URI}
    )

    create_safe_markdown_text(
        f'<meta http-equiv="refresh" content="0;url={logout_url}">', st
    )

    st.rerun()


# ==== Styles ====

st.markdown(
    """
        <style>
        body {
            background: #181c24 !important;
        }
        .stApp {
            background: #181c24 !important;
        }
        .css-1v0mbdj, .css-1dp5vir {
            border-radius: 14px !important;
            padding: 0.5rem 1rem !important;
        }
        .user-bubble {
            background: #23272f;
            color: #e6e6e6;
            border-radius: 16px;
            padding: 0.7rem 1.2rem;
            margin-bottom: 0.5rem;
            display: inline-block;
            border: 1px solid #3a3f4b;
        }
        .assistant-bubble {
            background: #0b2545;
            color: #e6e6e6;
            border-radius: 16px;
            padding: 0.7rem 1.2rem;
            margin-bottom: 0.5rem;
            display: block;
            border: 1px solid #298dff;
            animation: fadeInUp 0.3s ease-out;
            white-space: pre-wrap;
            word-wrap: break-word;
            max-width: 100%;
        }
        .assistant-bubble.streaming {
            border: 1px solid #4fc3f7;
            box-shadow: 0 0 10px rgba(79, 195, 247, 0.3);
            animation: pulse-border 2s infinite, fadeInUp 0.3s ease-out;
        }
        .thinking-bubble {
            background: #0b2545;
            color: #e6e6e6;
            border-radius: 16px;
            padding: 0.7rem 1.2rem;
            margin-bottom: 0.5rem;
            display: inline-block;
            border: 1px solid #298dff;
            animation: thinking-pulse 1.5s infinite, fadeInUp 0.3s ease-out;
        }
        .typing-cursor::after {
            content: '▋';
            color: #4fc3f7;
            animation: cursor-blink 1s infinite;
            margin-left: 2px;
        }
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        @keyframes pulse-border {
            0%, 100% {
                border-color: #298dff;
                box-shadow: 0 0 5px rgba(41, 141, 255, 0.3);
            }
            50% {
                border-color: #4fc3f7;
                box-shadow: 0 0 15px rgba(79, 195, 247, 0.6);
            }
        }
        @keyframes thinking-pulse {
            0%, 100% {
                opacity: 1;
                transform: scale(1);
            }
            50% {
                opacity: 0.8;
                transform: scale(1.02);
            }
        }
        @keyframes cursor-blink {
            0%, 50% {
                opacity: 1;
            }
            51%, 100% {
                opacity: 0;
            }
        }
        @keyframes slideInLeft {
            from {
                opacity: 0;
                transform: translateX(-30px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }
        .sidebar .sidebar-content {
            background: #181c24 !important;
        }
        h1, h2, h3, h4, h5, h6, p, label, .css-10trblm, .css-1cpxqw2 {
            color: #e6e6e6 !important;
        }
        hr {
            border: 1px solid #298dff !important;
        }
        </style>
        """,
    unsafe_allow_html=True,
)


# ==== Handle OAuth callback ====
query_params = st.query_params
if query_params.get("code") and query_params.get("state") and not cookies.get("tokens"):
    auth_code = query_params.get("code")
    returned_state = query_params.get("state")

    code_verifier = cookies.get("code_verifier")
    state = cookies.get("oauth_state")
    print(f"Check state {cookies.get('oauth_state')} against {returned_state}")

    if not state:
        st.stop()
    else:
        if returned_state != state:
            st.error("State mismatch - potential CSRF detected")
            st.stop()

    # Exchange authorization code for tokens
    token_url = f"https://{COGNITO_DOMAIN}/oauth2/token"
    data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": code_verifier,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(token_url, data=data, headers=headers)
    if response.ok:
        tokens = response.json()
        # st.success("Logged in successfully!")

        # Clear the cookies after login to avoid reuse of old code_verifier and state
        cookies.set("tokens", json.dumps(tokens))
        cookies.remove("code_verifier")
        cookies.remove("code_challenge")
        cookies.remove("oauth_state")
        # cookies.save()
        st.query_params.clear()
        # st.rerun()
    else:
        st.error(f"Failed to exchange token: {response.status_code} - {response.text}")

# ==== Sidebar with welcome, tokens, and logout ====
st.sidebar.title("Access Tokens")


def invoke_endpoint(
    agent_arn: str,
    payload,
    session_id: str,
    bearer_token: Optional[str],  # noqa: F821
    endpoint_name: str = "DEFAULT",
) -> Any:
    """Invoke agent endpoint using HTTP request with bearer token.

    Args:
        agent_arn: Agent ARN to invoke
        payload: Payload to send (dict or string)
        session_id: Session ID for the request
        bearer_token: Bearer token for authentication
        endpoint_name: Endpoint name, defaults to "DEFAULT"

    Returns:
        Response from the agent endpoint
    """
    # Escape agent ARN for URL
    escaped_arn = urllib.parse.quote(agent_arn, safe="")

    # Build URL
    url = f"https://bedrock-agentcore.{st.session_state['region']}.amazonaws.com/runtimes/{escaped_arn}/invocations"
    # Headers
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
    }

    # Parse the payload string back to JSON object to send properly
    # This ensures consistent payload structure between boto3 and HTTP clients
    try:
        body = json.loads(payload) if isinstance(payload, str) else payload
    except json.JSONDecodeError:
        # Fallback for non-JSON strings - wrap in payload object

        body = {"payload": payload}

    try:
        # Make request with timeout
        response = requests.post(
            url,
            params={"qualifier": endpoint_name},
            headers=headers,
            json=body,
            timeout=100,
            stream=True,
        )
        last_data = False
        for line in response.iter_lines(chunk_size=1):
            if line:
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    last_data = True
                    line = line[6:]
                    yield line
                elif line:
                    if last_data:
                        yield "\n" + line
                    last_data = False

    except requests.exceptions.RequestException as e:
        print("Failed to invoke agent endpoint: %s", str(e))
        raise


# ==== Main app ====
if cookies.get("tokens"):
    st.sidebar.code(cookies.get("tokens"))
    if st.sidebar.button("Logout"):
        logout()

    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid.uuid4())

    if "agent_arn" not in st.session_state:
        runtime_config = read_config(".bedrock_agentcore.yaml")
        st.session_state["agent_arn"] = runtime_config["agents"][AGENT_NAME][
            "bedrock_agentcore"
        ]["agent_arn"]

    if "region" not in st.session_state:
        st.session_state["region"] = get_aws_region()

    st.sidebar.write("Agent Arn")
    st.sidebar.code(st.session_state["agent_arn"])

    st.sidebar.write("Session Id")
    st.sidebar.code(st.session_state["session_id"])

    token = json.loads(cookies.get("tokens"))

    claims = jwt.decode(token["id_token"], options={"verify_signature": False})

    st.title("Customer Support Assistant")

    st.markdown(
        """
    <hr style='border:1px solid #298dff;'>
    """,
        unsafe_allow_html=True,
    )
    # Initialize chat history
    if "messages" not in st.session_state:
        default_prompt = (
            f"Hi my name is Maira Ladeira Tanke and my email is {claims.get('email')}"
        )
        st.session_state.messages = [
            {
                "role": "user",
                "content": default_prompt,
            }
        ]

        with st.chat_message("user"):
            create_safe_markdown_text(
                f'<span class="user-bubble">🧑‍💻 {default_prompt}</span>', st
            )
            st.session_state["pending_assistant"] = True

        start_time = int()
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            start_time = time.time()

            create_safe_markdown_text(
                '<span class="thinking-bubble">🤖 💭 Customer Support Assistant is thinking...</span>',
                message_placeholder,
            )

            # Stream the response with animations
            chunk_count = 0
            formatted_response = ""
            accumulated_response = ""

            for chunk in invoke_endpoint(
                agent_arn=st.session_state["agent_arn"],
                payload=json.dumps(
                    {
                        "prompt": default_prompt,
                        "actor_id": claims.get("cognito:username"),
                    }
                ),
                bearer_token=token["access_token"],
                session_id=st.session_state["session_id"],
            ):
                chunk = str(chunk)
                if chunk.strip():  # Only process non-empty chunks
                    accumulated_response += chunk
                    chunk_count += 1

                    if chunk_count % 3 == 0:  # Add cursor every few chunks for effect
                        accumulated_response += ""

                    # Update display with streaming animation (make URLs clickable)
                    clickable_streaming_text = make_urls_clickable(accumulated_response)

                    create_safe_markdown_text(
                        f'<div class="assistant-bubble streaming typing-cursor">🤖 {clickable_streaming_text}</div>',
                        message_placeholder,
                    )

                    # Small delay to make streaming visible and smooth
                    time.sleep(0.02)

        elapsed = time.time() - start_time

        clickable_answer = make_urls_clickable(accumulated_response)
        create_safe_markdown_text(
            f'<div class="assistant-bubble">🤖 {clickable_answer}<br><span style="font-size:0.9em;color:#888;">⏱️ Response time: {elapsed:.2f} seconds</span></div>',
            message_placeholder,
        )

        # Add user message to chat history

        st.session_state.messages.append(
            {"role": "assistant", "content": accumulated_response, "elapsed": elapsed}
        )
        st.session_state["pending_assistant"] = False
        st.rerun()
    else:
        # Display chat messages from history on app rerun
        messages_to_show = st.session_state.messages[:]
        # If waiting for assistant, don't show the last user message here (it will be shown in pending section)
        if (
            st.session_state.get("pending_assistant", False)
            and messages_to_show
            and messages_to_show[-1]["role"] == "user"
        ):
            messages_to_show = messages_to_show[:-1]
        for message in messages_to_show:
            bubble_class = (
                "user-bubble" if message["role"] == "user" else "assistant-bubble"
            )
            emoji = "🧑‍💻" if message["role"] == "user" else "🤖"
            with st.chat_message(message["role"]):
                if message["role"] == "assistant" and "elapsed" in message:
                    clickable_content = make_urls_clickable(message["content"])
                    create_safe_markdown_text(
                        f'<div class="{bubble_class}">{emoji} {clickable_content}<br><span style="font-size:0.9em;color:#888;">⏱️ Response time: {message["elapsed"]:.2f} seconds</span></div>',
                        st,
                    )
                else:
                    if message["role"] == "assistant":
                        clickable_content = make_urls_clickable(message["content"])
                        create_safe_markdown_text(
                            f'<div class="{bubble_class}">{emoji} {clickable_content}</div>',
                            st,
                        )
                    else:
                        create_safe_markdown_text(
                            f'<span class="{bubble_class}">{emoji} {message["content"]}</span>',
                            st,
                        )

    if prompt := st.chat_input("Ask customer support assistant questions!"):
        # Display user message in chat message container
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            create_safe_markdown_text(
                f'<span class="user-bubble">🧑‍💻 {prompt}</span>', st
            )
            st.session_state["pending_assistant"] = True

        start_time = int()
        # Display assistant response in chat message container
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            start_time = time.time()

            message_placeholder.markdown(
                '<span class="thinking-bubble">🤖 💭 Customer Support Assistant is thinking...</span>',
                unsafe_allow_html=True,
            )

            # Stream the response with animations
            chunk_count = 0
            formatted_response = ""
            accumulated_response = ""

            for chunk in invoke_endpoint(
                agent_arn=st.session_state["agent_arn"],
                payload=json.dumps(
                    {"prompt": prompt, "actor_id": claims.get("cognito:username")}
                ),
                bearer_token=token["access_token"],
                session_id=st.session_state["session_id"],
            ):
                chunk = str(chunk)
                if chunk.strip():  # Only process non-empty chunks
                    if ".prod.agent-credential-provider.cognito.aws.dev" in chunk:
                        accumulated_response = f"Please use {chunk}"
                    else:
                        accumulated_response += chunk
                    chunk_count += 1

                    if chunk_count % 3 == 0:  # Add cursor every few chunks for effect
                        accumulated_response += ""

                    # Update display with streaming animation (make URLs clickable)
                    clickable_streaming_text = make_urls_clickable(accumulated_response)

                    create_safe_markdown_text(
                        f'<div class="assistant-bubble streaming typing-cursor">🤖 {clickable_streaming_text}</div>',
                        message_placeholder,
                    )

                    if (
                        ".prod.agent-credential-provider.cognito.aws.dev"
                        in accumulated_response
                    ):
                        accumulated_response = str()

                    # Small delay to make streaming visible and smooth
                    time.sleep(0.02)

        elapsed = time.time() - start_time

        clickable_streaming_text = make_urls_clickable(accumulated_response)

        # clickable_answer = make_urls_clickable(accumulated_response)
        create_safe_markdown_text(
            f'<div class="assistant-bubble">🤖 {clickable_streaming_text}<br><span style="font-size:0.9em;color:#888;">⏱️ Response time: {elapsed:.2f} seconds</span></div>',
            message_placeholder,
        )
        # Add user message to chat history

        st.session_state.messages.append(
            {"role": "assistant", "content": accumulated_response, "elapsed": elapsed}
        )
        st.session_state["pending_assistant"] = False

else:
    code_verifier, code_challenge = generate_pkce_pair()
    cookies.set("code_verifier", code_verifier)
    cookies.set("code_challenge", code_challenge)
    state = str(uuid.uuid4())
    cookies.set("oauth_state", state)

    # cookies.save()

    # Show login link
    login_params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "code_challenge_method": "S256",
        "code_challenge": cookies.get("code_challenge"),
        "state": cookies.get("oauth_state"),
    }
    login_url = f"https://{COGNITO_DOMAIN}/oauth2/authorize?{urlencode(login_params)}"
    print(f"Login signed with state: {cookies.get('oauth_state')}")
    # st.markdown(f"[Login with Cognito]({login_url})")
    create_safe_markdown_text(
        f'<meta http-equiv="refresh" content="0;url={login_url}">', st
    )
