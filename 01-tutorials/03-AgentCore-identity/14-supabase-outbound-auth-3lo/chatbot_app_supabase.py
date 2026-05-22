import streamlit as st
import os
import json
import requests
import urllib.parse
import logging
import re
import sys
import yaml
import uuid
import dotenv
from supabase import create_client, Client
from oauth2_callback_server import store_token_in_oauth2_callback_server

dotenv.load_dotenv(override=True)

logger = logging.getLogger()

qualifier = "DEFAULT"
CONTEXT_WINDOW = 10


def get_streamlit_url():
    try:
        with open("/opt/ml/metadata/resource-metadata.json", "r") as file:
            data = json.load(file)
            domain_id = data["DomainId"]
            space_name = data["SpaceName"]
    except FileNotFoundError:
        domain_id = None
        space_name = None
    except (json.JSONDecodeError, KeyError):
        sys.exit(1)

    if domain_id is not None:
        import boto3
        sagemaker_client = boto3.client("sagemaker")
        response = sagemaker_client.describe_space(DomainId=domain_id, SpaceName=space_name)
        return response["Url"] + "/proxy/8501/"
    return "http://localhost:8501"


def build_context(messages, context_window=CONTEXT_WINDOW):
    history = (
        messages[-context_window * 2:]
        if len(messages) > context_window * 2
        else messages
    )
    context = ""
    for msg in history:
        role = "User" if msg["role"] == "user" else "Assistant"
        context += f"{role}: {msg['content']}\n"
    return context


def make_urls_clickable(text):
    url_pattern = r"https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?"

    def replace_url(match):
        url = match.group(0)
        return f'<a href="{url}" target="_blank" style="color:#4fc3f7;text-decoration:underline;">{url}</a>'

    return re.sub(url_pattern, replace_url, text)


def load_bedrock_agentcore_config():
    """Load agent ARN and region from .bedrock_agentcore.yaml."""
    config_path = ".bedrock_agentcore.yaml"
    try:
        with open(config_path, "r") as file:
            config = yaml.safe_load(file)

        default_agent = config.get("default_agent")
        if not default_agent:
            raise ValueError("default_agent not found in configuration")

        agents = config.get("agents", {})
        if default_agent not in agents:
            raise ValueError(f"Agent '{default_agent}' not found in agents configuration")

        agent_config = agents[default_agent]
        bedrock_config = agent_config.get("bedrock_agentcore", {})
        aws_config = agent_config.get("aws", {})

        agent_session_id = bedrock_config.get("agent_session_id")
        agent_arn = bedrock_config.get("agent_arn")
        region = aws_config.get("region")

        if not agent_arn:
            raise ValueError("agent_arn not found in bedrock_agentcore configuration")
        if not region:
            raise ValueError("region not found in aws configuration")

        return {
            "agentSessionId": agent_session_id,
            "agentRuntimeArn": agent_arn,
            "region": region,
        }
    except FileNotFoundError:
        raise FileNotFoundError(
            "Configuration file '.bedrock_agentcore.yaml' not found."
        )
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing YAML configuration: {str(e)}")


def get_supabase_client() -> Client:
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_anon_key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not supabase_url or not supabase_anon_key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_ANON_KEY must be set in your .env file"
        )
    return create_client(supabase_url, supabase_anon_key)


# Load agent configuration
try:
    config = load_bedrock_agentcore_config()
    agentSessionId = config["agentSessionId"]
    agentRuntimeArn = config["agentRuntimeArn"]
    region = config["region"]
    config_error_message = None
except Exception as config_error:
    agentSessionId = None
    agentRuntimeArn = None
    region = None
    config_error_message = str(config_error)


class StreamingHttpBedrockAgentCoreClient:
    def __init__(self, region: str):
        self.region = region
        self.dp_endpoint = f"https://bedrock-agentcore.{region}.amazonaws.com"
        self.logger = logging.getLogger(f"bedrock_agentcore.streaming_http_runtime.{region}")

    def invoke_endpoint_streaming(
        self,
        agent_arn: str,
        payload,
        session_id: str,
        bearer_token: str,
        endpoint_name: str = "DEFAULT",
    ):
        escaped_arn = urllib.parse.quote(agent_arn, safe="")
        url = f"{self.dp_endpoint}/runtimes/{escaped_arn}/invocations"
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
        }
        try:
            body = json.loads(payload) if isinstance(payload, str) else payload
        except json.JSONDecodeError:
            body = {"payload": payload}

        try:
            response = requests.post(
                url,
                params={"qualifier": endpoint_name},
                headers=headers,
                json=body,
                timeout=100,
                stream=True,
            )
            response.raise_for_status()
            if "text/event-stream" in response.headers.get("content-type", ""):
                for line in response.iter_lines(chunk_size=1, decode_unicode=True):
                    if line and line.startswith("data: "):
                        chunk = line[6:]
                        if chunk.strip():
                            yield chunk
            else:
                if response.content:
                    yield response.text
        except requests.exceptions.RequestException as e:
            self.logger.error("Failed to invoke agent endpoint: %s", str(e))
            raise


def main():
    st.set_page_config(
        page_title="Bedrock AgentCore AI Chatbot",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    if config_error_message:
        st.markdown(
            f"""
            <div style='max-width:600px;margin:40px auto 30px auto;padding:40px;
                background:linear-gradient(145deg,#2d1b1b,#3d2424);border-radius:24px;
                border:2px solid rgba(255,87,87,0.4);'>
                <h2 style='color:#ff7675;'>Configuration Error</h2>
                <p style='color:#e17055;font-family:monospace;'>{config_error_message}</p>
                <p style='color:#fab1a0;'>Ensure <code>.bedrock_agentcore.yaml</code> exists and
                contains <code>agent_arn</code> and <code>region</code>.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.stop()

    # ── Authentication ──────────────────────────────────────────────────────────
    if "supabase_access_token" not in st.session_state:
        st.session_state["supabase_access_token"] = None

    if st.session_state["supabase_access_token"] is None:
        st.markdown(
            """
            <div style='max-width:480px;margin:40px auto 30px auto;padding:40px;
                background:linear-gradient(145deg,#1a1f2e,#242b3d);border-radius:24px;
                border:1px solid rgba(100,181,246,0.2);position:relative;overflow:hidden;'>
                <div style='position:absolute;top:0;left:0;right:0;height:3px;
                    background:linear-gradient(90deg,#3ecf8e,#1db974);'></div>
                <div style='text-align:center;margin-bottom:32px;'>
                    <div style='font-size:3.5rem;margin-bottom:12px;'>🔐</div>
                    <h2 style='color:#3ecf8e;font-weight:700;margin:0;font-size:1.8rem;'>
                        Bedrock AgentCore AI Login</h2>
                    <p style='color:#b3c5d7;font-size:1rem;margin:12px 0 0 0;'>
                        Sign in with your Supabase account</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("supabase_login_form"):
            st.markdown(
                """
                <style>
                .stTextInput>label { color:#3ecf8e !important; font-weight:600; }
                .stButton>button {
                    background:linear-gradient(135deg,#3ecf8e,#1db974);
                    color:#fff; font-weight:700; border-radius:14px; border:none;
                    padding:0.8rem 2rem; margin-top:15px; font-size:1.1rem;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )
            email = st.text_input("Email", key="supabase_email")
            password = st.text_input("Password", type="password", key="supabase_password")
            submitted = st.form_submit_button("Sign in with Supabase")

        if submitted:
            with st.spinner("Authenticating with Supabase..."):
                try:
                    supabase = get_supabase_client()
                    response = supabase.auth.sign_in_with_password(
                        {"email": email, "password": password}
                    )
                    st.session_state["supabase_access_token"] = response.session.access_token
                    st.success("Supabase authentication successful! Redirecting...")
                    st.rerun()
                except Exception as e:
                    st.error(f"Supabase authentication failed: {e}")
        return

    # ── Status panel ────────────────────────────────────────────────────────────
    st.markdown(
        f"""
        <div style="position:fixed;top:15px;right:25px;z-index:9999;padding:18px 24px;
            background:linear-gradient(145deg,#1a1f2e,#242b3d);border-radius:16px;
            box-shadow:0 4px 20px rgba(0,0,0,0.3);font-size:0.9em;color:#90caf9;
            border:1px solid rgba(62,207,142,0.2);">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;
            color:#3ecf8e;font-weight:600;">⚡ System Status</div>
        <div style="font-size:0.85em;line-height:1.6;">
            <div><span style="color:#b3c5d7;">Region: </span>
                 <span style="color:#fff;font-weight:500;">{region}</span></div>
            <div><span style="color:#b3c5d7;">Auth: </span>
                 <span style="color:#3ecf8e;font-weight:500;">Supabase JWT</span></div>
            <div><span style="color:#b3c5d7;">Agent: </span>
                 <span style="color:#3ecf8e;font-weight:500;">Active</span></div>
        </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── CSS ─────────────────────────────────────────────────────────────────────
    st.markdown(
        """
        <style>
        .stApp {
            background:linear-gradient(135deg,#0f1419,#1a1f2e,#0f1419) !important;
            font-family:'Inter','Segoe UI',Arial,sans-serif !important;
        }
        .user-bubble {
            background:linear-gradient(145deg,#242b3e,#1e2537);color:#e8f4fd;
            border-radius:18px 18px 4px 18px;padding:1rem 1.3rem;margin:0.8rem 0;
            display:inline-block;border:1px solid rgba(62,207,142,0.3);
            box-shadow:0 4px 15px rgba(0,0,0,0.2);max-width:85%;line-height:1.5;
        }
        .assistant-bubble {
            background:linear-gradient(145deg,#0a1929,#0f2d47,#0b1e36);color:#e8f4fd;
            border-radius:18px 18px 18px 4px;padding:1rem 1.3rem;margin:0.8rem 0;
            display:block;border:1px solid rgba(62,207,142,0.4);
            box-shadow:0 6px 20px rgba(0,0,0,0.3);max-width:90%;line-height:1.6;
        }
        .thinking-bubble {
            background:linear-gradient(145deg,#0a1929,#0f2d47);color:#e8f4fd;
            border-radius:18px;padding:1rem 1.3rem;margin:0.8rem 0;
            display:inline-block;border:1px solid rgba(62,207,142,0.5);
        }
        h1 {
            background:linear-gradient(135deg,#3ecf8e,#1db974);
            -webkit-background-clip:text;-webkit-text-fill-color:transparent;
            font-weight:700 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── Sidebar ──────────────────────────────────────────────────────────────────
    st.sidebar.markdown(
        """
        <div style='text-align:center;padding:1.5rem 0;border-bottom:1px solid rgba(62,207,142,0.2);margin-bottom:1.5rem;'>
            <div style='font-size:3rem;margin-bottom:1rem;'>🤖</div>
            <h2 style='color:#3ecf8e;font-weight:700;margin:0;'>Bedrock AgentCore AI</h2>
            <p style='color:#b3c5d7;font-size:0.9rem;margin:0.5rem 0 0 0;'>Supabase Inbound Auth</p>
        </div>
        <div style='margin-bottom:1.5rem;'>
            <h3 style='color:#3ecf8e;font-size:1rem;font-weight:600;margin-bottom:1rem;'>Features</h3>
            <div style='display:flex;flex-direction:column;gap:0.5rem;'>
                <div style='padding:0.5rem;background:rgba(62,207,142,0.1);border-radius:8px;'>
                    <span style='color:#b3c5d7;font-size:0.9rem;'>🔒 Supabase JWT Auth</span></div>
                <div style='padding:0.5rem;background:rgba(62,207,142,0.1);border-radius:8px;'>
                    <span style='color:#b3c5d7;font-size:0.9rem;'>📅 Google Calendar (3LO)</span></div>
                <div style='padding:0.5rem;background:rgba(62,207,142,0.1);border-radius:8px;'>
                    <span style='color:#b3c5d7;font-size:0.9rem;'>🔄 Real-time Streaming</span></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Main header ──────────────────────────────────────────────────────────────
    st.markdown(
        """
        <div style='text-align:center;padding:2rem 0 1rem 0;'>
            <div style='font-size:3.5rem;margin-bottom:0.5rem;'>🤖</div>
            <h1 style='margin:0;font-size:2.2rem;font-weight:700;'>Bedrock AgentCore AI Chatbot</h1>
            <p style='color:#b3c5d7;font-size:1.1rem;margin:0.5rem 0 0 0;'>
                Secured by Supabase · Google Calendar via 3LO</p>
        </div>
        <div style='height:2px;background:linear-gradient(90deg,#3ecf8e,#1db974);border-radius:1px;margin:1.5rem 0;'></div>
        """,
        unsafe_allow_html=True,
    )

    # ── Chat state ───────────────────────────────────────────────────────────────
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "agentSessionId" not in st.session_state:
        st.session_state["agentSessionId"] = (
            agentSessionId if agentSessionId else str(uuid.uuid4())
        )
    if "pending_assistant" not in st.session_state:
        st.session_state["pending_assistant"] = False

    # ── Render history ───────────────────────────────────────────────────────────
    messages_to_show = st.session_state.messages[:]
    if (
        st.session_state.get("pending_assistant", False)
        and messages_to_show
        and messages_to_show[-1]["role"] == "user"
    ):
        messages_to_show = messages_to_show[:-1]

    for message in messages_to_show:
        bubble_class = "user-bubble" if message["role"] == "user" else "assistant-bubble"
        emoji = "🧑‍💻" if message["role"] == "user" else "🤖"
        with st.chat_message(message["role"]):
            if message["role"] == "assistant" and "elapsed" in message:
                clickable_content = make_urls_clickable(message["content"])
                st.markdown(
                    f'<div class="{bubble_class}">{emoji} {clickable_content}'
                    f'<br><span style="font-size:0.9em;color:#888;">⏱️ {message["elapsed"]:.2f}s</span></div>',
                    unsafe_allow_html=True,
                )
            else:
                content = make_urls_clickable(message["content"]) if message["role"] == "assistant" else message["content"]
                tag = "div" if message["role"] == "assistant" else "span"
                st.markdown(
                    f'<{tag} class="{bubble_class}">{emoji} {content}</{tag}>',
                    unsafe_allow_html=True,
                )

    # ── Input ────────────────────────────────────────────────────────────────────
    if not st.session_state["pending_assistant"]:
        prompt = st.chat_input("What would you like to know?")
        if prompt:
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.session_state["pending_assistant"] = True
            st.rerun()

    # ── Invoke agent ─────────────────────────────────────────────────────────────
    if (
        st.session_state["pending_assistant"]
        and st.session_state.messages
        and st.session_state.messages[-1]["role"] == "user"
    ):
        user_msg = st.session_state.messages[-1]["content"]
        with st.chat_message("user"):
            st.markdown(
                f'<span class="user-bubble">🧑‍💻 {user_msg}</span>', unsafe_allow_html=True
            )

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            import time

            start_time = time.time()
            accumulated_response = ""

            try:
                session_id = st.session_state.get("agentSessionId")
                context = build_context(st.session_state.messages, CONTEXT_WINDOW)
                payload = json.dumps({"prompt": context})
                bearer_token = st.session_state.get("supabase_access_token")
                store_token_in_oauth2_callback_server(bearer_token)

                streaming_client = StreamingHttpBedrockAgentCoreClient(region)
                message_placeholder.markdown(
                    '<span class="thinking-bubble">🤖 💭 Thinking...</span>',
                    unsafe_allow_html=True,
                )

                formatted_response = ""
                chunk_count = 0

                for chunk in streaming_client.invoke_endpoint_streaming(
                    agent_arn=agentRuntimeArn,
                    payload=payload,
                    session_id=session_id,
                    bearer_token=bearer_token,
                    endpoint_name=qualifier,
                ):
                    if chunk.strip():
                        accumulated_response += chunk
                        chunk_count += 1

                        if '"End agent execution"' in accumulated_response:
                            message_placeholder.markdown(
                                '<span class="thinking-bubble">🤖 🔄 Processing...</span>',
                                unsafe_allow_html=True,
                            )
                            try:
                                begin_marker = '"Begin agent execution"'
                                end_marker = '"End agent execution"'
                                begin_pos = accumulated_response.find(begin_marker)
                                end_pos = accumulated_response.find(end_marker)
                                if begin_pos != -1 and end_pos != -1:
                                    json_part = accumulated_response[
                                        begin_pos + len(begin_marker): end_pos
                                    ].strip()
                                    json_start = json_part.find('{"role":')
                                    if json_start != -1:
                                        json_str = json_part[json_start:]
                                        brace_count = 0
                                        json_end = -1
                                        for i, char in enumerate(json_str):
                                            if char == "{":
                                                brace_count += 1
                                            elif char == "}":
                                                brace_count -= 1
                                                if brace_count == 0:
                                                    json_end = i + 1
                                                    break
                                        if json_end != -1:
                                            response_data = json.loads(json_str[:json_end])
                                            if (
                                                "content" in response_data
                                                and response_data["content"]
                                                and "text" in response_data["content"][0]
                                            ):
                                                formatted_response = response_data["content"][0]["text"]
                            except (json.JSONDecodeError, KeyError, IndexError) as e:
                                logger.info(f"JSON parsing error: {e}")
                                formatted_response = accumulated_response
                            break
                        else:
                            clickable = make_urls_clickable(accumulated_response)
                            message_placeholder.markdown(
                                f'<div class="assistant-bubble">🤖 {clickable}</div>',
                                unsafe_allow_html=True,
                            )
                            time.sleep(0.02)

                elapsed = time.time() - start_time
                answer = formatted_response or accumulated_response or "No response received"
                clickable_answer = make_urls_clickable(answer)
                message_placeholder.markdown(
                    f'<div class="assistant-bubble">🤖 {clickable_answer}'
                    f'<br><span style="font-size:0.9em;color:#888;">⏱️ {elapsed:.2f}s</span></div>',
                    unsafe_allow_html=True,
                )

            except Exception as e:
                error_msg = f"Sorry, I encountered an error: {str(e)}"
                message_placeholder.markdown(
                    f'<div class="assistant-bubble">🤖 ❌ {error_msg}</div>',
                    unsafe_allow_html=True,
                )
                answer = error_msg
                elapsed = time.time() - start_time

            final_answer = answer if "answer" in locals() else accumulated_response
            st.session_state.messages.append(
                {"role": "assistant", "content": final_answer, "elapsed": elapsed}
            )
            st.session_state["pending_assistant"] = False
            st.rerun()


if __name__ == "__main__":
    main()
