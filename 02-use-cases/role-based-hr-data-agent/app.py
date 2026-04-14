#!/usr/bin/env python3
"""
HR DLP Demo — Streamlit frontend.

All configuration is read dynamically from SSM Parameter Store on startup:
  /app/hrdlp/runtime-url            — Amazon Bedrock AgentCore Runtime invocation URL
  /app/hrdlp/gateway-url            — Amazon Bedrock AgentCore Gateway MCP endpoint
  /app/hrdlp/cognito-token-url      — Amazon Cognito OAuth2 token endpoint
  /app/hrdlp/personas/*/client-id   — Per-persona Cognito app client ID
  /app/hrdlp/personas/*/client-secret — Per-persona client secret (SecureString)

Usage:
  streamlit run app.py
"""

import base64
import json
import os
from datetime import datetime
from typing import Optional

import boto3
import requests
import streamlit as st

# ---------------------------------------------------------------------------
# SSM helpers
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def _ssm_client():
    region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
    return boto3.client("ssm", region_name=region)


def _get_param(name: str, secure: bool = False) -> Optional[str]:
    try:
        resp = _ssm_client().get_parameter(Name=name, WithDecryption=secure)
        return resp["Parameter"]["Value"]
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Config — loaded once per session
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="Loading configuration from SSM…")
def load_config() -> dict:
    runtime_url  = _get_param("/app/hrdlp/runtime-url")
    gateway_url  = _get_param("/app/hrdlp/gateway-url")
    token_url    = _get_param("/app/hrdlp/cognito-token-url")

    personas = {}
    for persona in ["hr-manager", "hr-specialist", "employee", "admin"]:
        client_id     = _get_param(f"/app/hrdlp/personas/{persona}/client-id")
        client_secret = _get_param(f"/app/hrdlp/personas/{persona}/client-secret", secure=True)
        if client_id and client_secret:
            personas[persona] = {"client_id": client_id, "client_secret": client_secret}

    missing = []
    if not runtime_url:  missing.append("/app/hrdlp/runtime-url")
    if not gateway_url:  missing.append("/app/hrdlp/gateway-url")
    if not token_url:    missing.append("/app/hrdlp/cognito-token-url")
    if not personas:     missing.append("/app/hrdlp/personas/*/client-id and client-secret")

    return {
        "runtime_url": runtime_url,
        "gateway_url": gateway_url,
        "token_url": token_url,
        "personas": personas,
        "missing": missing,
    }


# ---------------------------------------------------------------------------
# Persona display definitions
# ---------------------------------------------------------------------------

PERSONAS = {
    "HR Manager": {
        "key": "hr-manager",
        "icon": "👔",
        "description": "Full access — compensation, PII, and address visible",
        "scopes": ["read", "pii", "address", "comp"],
        "color": "#1f77b4",
        "expected_tools": 3,
    },
    "HR Specialist": {
        "key": "hr-specialist",
        "icon": "👨‍💼",
        "description": "Profiles + PII; compensation and address redacted",
        "scopes": ["read", "pii"],
        "color": "#ff7f0e",
        "expected_tools": 2,
    },
    "Employee": {
        "key": "employee",
        "icon": "👤",
        "description": "Search only; all sensitive fields redacted",
        "scopes": ["read"],
        "color": "#2ca02c",
        "expected_tools": 1,
    },
    "Admin": {
        "key": "admin",
        "icon": "🛡️",
        "description": "Full administrative access",
        "scopes": ["read", "pii", "address", "comp"],
        "color": "#9467bd",
        "expected_tools": 3,
    },
}

SUGGESTED_QUERIES = [
    "What can you help me with?",
    "Find all software engineers",
    "Show me Sarah Johnson's profile",
    "What is John Smith's compensation?",
    "Search for HR department employees",
]

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def get_token(config: dict, persona_key: str) -> Optional[str]:
    """Obtain a client_credentials access token for the given persona."""
    creds = config["personas"].get(persona_key)
    if not creds:
        add_log(f"No credentials found in SSM for persona: {persona_key}", "error", "Cognito")
        return None
    add_log(f"POST {config['token_url']} (grant_type=client_credentials)", "info", "Cognito")
    encoded = base64.b64encode(f"{creds['client_id']}:{creds['client_secret']}".encode()).decode()
    try:
        resp = requests.post(
            config["token_url"],
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "Authorization": f"Basic {encoded}"},
            data={"grant_type": "client_credentials"},
            timeout=10,
        )
        resp.raise_for_status()
        token_data = resp.json()
        expires = token_data.get("expires_in", "?")
        scopes = token_data.get("scope", "")
        add_log(f"Token issued (expires {expires}s) | scopes: {scopes}", "success", "Cognito")
        return token_data.get("access_token")
    except Exception as e:
        add_log(f"Token request failed: {e}", "error", "Cognito")
        st.error(f"Token request failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Runtime / Gateway calls
# ---------------------------------------------------------------------------

def call_runtime(config: dict, token: str, prompt: str, session_id: str = "") -> tuple[list, Optional[str]]:
    """POST to AgentCore Runtime and return (raw_chunks, final_text)."""
    add_log(f"POST {config['runtime_url'].split('/runtimes/')[0]}/runtimes/…/invocations", "info", "Runtime")
    add_log(f"Session: {session_id[:16]}…", "info", "Runtime")

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    chunks, llm_response = [], None
    try:
        resp = requests.post(
            config["runtime_url"],
            headers=headers,
            json={"prompt": prompt, "sessionId": session_id or str(id(prompt))},
            stream=True,
            timeout=120,
        )
        if resp.status_code != 200:
            add_log(f"HTTP {resp.status_code}: {resp.text[:120]}", "error", "Runtime")
            st.error(f"Runtime returned HTTP {resp.status_code}: {resp.text[:200]}")
            return [], None

        add_log(f"HTTP 200 — streaming response…", "success", "Runtime")

        for line in resp.iter_lines():
            if not line:
                continue
            decoded = line.decode("utf-8")
            if decoded.startswith("data: "):
                decoded = decoded[6:]
            chunks.append(decoded)
            try:
                data = json.loads(decoded)

                # Error returned as JSON body (e.g. missing sessionId)
                if "error" in data and "result" not in data:
                    add_log(f"Runtime error: {data['error']}", "error", "Runtime")
                    st.error(f"Runtime error: {data['error']}")
                    return [], None

                if "result" in data:
                    result = data["result"]
                    model = data.get("model", "")
                    tool_count = data.get("tool_count", "?")
                    add_log(f"Tools used: {tool_count} | Model: {model.split('/')[-1] if model else 'unknown'}", "info", "Runtime")
                    if isinstance(result, dict) and "content" in result:
                        content = result["content"]
                        llm_response = content[0].get("text", str(result)) if content else str(result)
                    else:
                        llm_response = str(result)
                    add_log(f"Response received ({len(llm_response)} chars)", "success", "Runtime")

                elif data.get("type") == "response":
                    llm_response = data.get("message", "")
                    add_log(f"Response received ({len(llm_response)} chars)", "success", "Runtime")

                elif data.get("type") == "status":
                    add_log(data.get("message", ""), "info", "Runtime")

                elif data.get("type") == "tools_discovered":
                    tools = data.get("tools", [])
                    add_log(f"Tools discovered: {len(tools)}", "success", "Gateway")
                    for t in tools:
                        add_log(f"  - {t}", "info", "Gateway")

                elif data.get("type") == "tool_result":
                    add_log(data.get("message", "Tool call completed"), "success", "Lambda")

                elif data.get("type") == "error":
                    add_log(data.get("message", "Unknown error"), "error", "Runtime")

            except json.JSONDecodeError:
                pass

    except requests.Timeout:
        add_log("Request timed out after 120s", "error", "Runtime")
        st.error("Request timed out — the agent may still be processing.")
    except Exception as e:
        add_log(f"Exception: {e}", "error", "Runtime")
        st.error(f"Runtime error: {e}")
    return chunks, llm_response


def discover_tools(config: dict, token: str) -> list[str]:
    """Call Gateway tools/list and return tool names."""
    add_log("POST tools/list → Gateway", "info", "Gateway")
    try:
        resp = requests.post(
            config["gateway_url"],
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            timeout=30,
        )
        resp.raise_for_status()
        tools = resp.json().get("result", {}).get("tools", [])
        add_log(f"HTTP 200 — {len(tools)} tool(s) visible to this persona", "success", "Gateway")
        for t in tools:
            short = t["name"].replace("hr-lambda-target___", "")
            add_log(f"  ✓ {short}", "info", "Gateway")
        return [t["name"] for t in tools]
    except Exception as e:
        add_log(f"Tool discovery failed: {e}", "error", "Gateway")
        st.error(f"Tool discovery failed: {e}")
        return []


def call_tool(config: dict, token: str, tool_name: str, arguments: dict):
    """Call a specific tool via the Gateway."""
    try:
        resp = requests.post(
            config["gateway_url"],
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": tool_name, "arguments": arguments}},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"Tool call failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------

def _init_state():
    import uuid
    defaults = {
        "selected_persona": "HR Manager",
        "token": None,  # nosec B105 - not a hardcoded password; None is the initial unauthenticated state
        "tools": [],
        "logs": [],
        "llm_response": None,
        "conversation_history": [],
        "is_processing": False,
        "session_id": str(uuid.uuid4()),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def add_log(message: str, level: str = "info", component: str = ""):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    st.session_state.logs.append({"ts": ts, "msg": message, "level": level, "comp": component})


def _switch_persona(name: str):
    import uuid
    st.session_state.selected_persona = name
    st.session_state.token = None
    st.session_state.tools = []
    st.session_state.logs = []
    st.session_state.llm_response = None
    st.session_state.conversation_history = []
    st.session_state.session_id = str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

st.set_page_config(page_title="HR DLP Demo", page_icon="🔒", layout="wide")
_init_state()

# Load config (cached — only hits SSM once per process)
config = load_config()

if config["missing"]:
    st.error(
        "**Missing SSM parameters** — run the full deployment sequence first:\n\n"
        "```\nbash scripts/prereq.sh --region us-east-1 --env dev\n"
        "python scripts/agentcore_gateway.py create --config prerequisite/prereqs_config.yaml\n"
        "python scripts/create_cedar_policies.py --region us-east-1 --env dev\n"
        "python scripts/agentcore_agent_runtime.py create\n```\n\n"
        f"Missing: `{'`, `'.join(config['missing'])}`"
    )
    st.stop()

st.title("🔒 HR DLP Gateway — Interactive Demo")
st.caption("Role-based data access with automatic field-level redaction via Amazon Bedrock AgentCore")

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("👥 Persona")

    for display_name, meta in PERSONAS.items():
        is_active = st.session_state.selected_persona == display_name
        label = f"{meta['icon']} {display_name}"
        if st.button(label, key=f"btn_{display_name}", use_container_width=True,
                     type="primary" if is_active else "secondary"):
            _switch_persona(display_name)
            st.rerun()

    st.divider()
    p = PERSONAS[st.session_state.selected_persona]
    st.markdown(f"### {p['icon']} {st.session_state.selected_persona}")
    st.caption(p["description"])
    st.markdown(f"**Scopes:** `{'`, `'.join(p['scopes'])}`")
    st.markdown(f"**Expected tools:** {p['expected_tools']}")

    st.divider()
    st.header("Actions")

    if st.button("🔑 Get OAuth Token", use_container_width=True):
        with st.spinner("Requesting token from Cognito…"):
            token = get_token(config, p["key"])
        if token:
            st.session_state.token = token
            st.session_state.llm_response = None
            st.session_state.conversation_history = []
            add_log(f"Token obtained for {st.session_state.selected_persona}", "success", "Cognito")
            st.success("Token obtained")
        st.rerun()

    if st.button("🔧 Discover Tools", use_container_width=True,
                 disabled=not st.session_state.token):
        with st.spinner("Calling Gateway tools/list…"):
            tools = discover_tools(config, st.session_state.token)
        st.session_state.tools = tools
        add_log(f"Discovered {len(tools)} tools", "success", "Gateway")
        for t in tools:
            add_log(f"  - {t}", "info", "Gateway")
        st.rerun()

    if st.button("🗑️ Clear", use_container_width=True):
        st.session_state.logs = []
        st.session_state.llm_response = None
        st.rerun()

    # Connection info (collapsed)
    with st.expander("ℹ️ Connection info"):
        st.caption(f"**Runtime:** `{config['runtime_url'][:60]}…`")
        st.caption(f"**Gateway:** `{config['gateway_url'][:60]}…`")
        st.caption(f"**Token URL:** `{config['token_url'][:60]}…`")

# ---------------------------------------------------------------------------
# Main area — two columns
# ---------------------------------------------------------------------------
col_chat, col_tools = st.columns([1, 1])

# ---- Left column: agent chat ----
with col_chat:
    st.header("💬 Agent Chat")

    if st.session_state.token:
        st.success(f"✅ Authenticated as **{st.session_state.selected_persona}**")
    else:
        st.warning("No token — click **Get OAuth Token** in the sidebar")

    # Suggested queries
    st.markdown("**Quick examples:**")
    for q in SUGGESTED_QUERIES:
        if st.button(q, key=f"quick_{q[:20]}", use_container_width=True,
                     disabled=not st.session_state.token):
            st.session_state.logs = []
            add_log(f"Query: {q}", "info", "Client")
            with st.spinner("Processing…"):
                _, llm_response = call_runtime(config, st.session_state.token, q, st.session_state.session_id)
            if llm_response:
                st.session_state.llm_response = llm_response
                st.session_state.conversation_history.append({"role": "user", "content": q})
                st.session_state.conversation_history.append({"role": "assistant", "content": llm_response})
            st.rerun()

    st.divider()

    # Custom query
    query = st.text_area("Custom query:", value="Show me John Smith's full profile",
                         height=80, disabled=not st.session_state.token)
    if st.button("🚀 Send", use_container_width=True,
                 disabled=(not st.session_state.token or st.session_state.is_processing)):
        st.session_state.is_processing = True
        st.session_state.logs = []
        add_log(f"Sending query as {st.session_state.selected_persona}", "info", "Client")
        with st.spinner("Processing…"):
            _, llm_response = call_runtime(config, st.session_state.token, query, st.session_state.session_id)
        if llm_response:
            st.session_state.llm_response = llm_response
            st.session_state.conversation_history.append({"role": "user", "content": query})
            st.session_state.conversation_history.append({"role": "assistant", "content": llm_response})
        st.session_state.is_processing = False
        st.rerun()

    # Response display
    if st.session_state.llm_response:
        st.divider()
        st.subheader("🤖 Agent Response")
        st.markdown(st.session_state.llm_response)
        if st.button("Clear response"):
            st.session_state.llm_response = None
            st.session_state.conversation_history = []
            st.rerun()

    # Conversation history
    if st.session_state.conversation_history:
        with st.expander("💬 Conversation history", expanded=False):
            for msg in st.session_state.conversation_history:
                prefix = "**You:**" if msg["role"] == "user" else "**Agent:**"
                text = msg["content"]
                st.markdown(f"{prefix} {text[:300]}{'…' if len(text) > 300 else ''}")
                st.markdown("---")

# ---- Right column: direct tool calling + logs ----
with col_tools:
    st.header("🔧 Direct Tool Calling")

    if not st.session_state.tools:
        st.info("Click **Discover Tools** in the sidebar to see what this persona can access.")
    else:
        tool_labels = {
            "hr-lambda-target___search_employee": "Search Employee",
            "hr-lambda-target___get_employee_profile": "Get Employee Profile",
            "hr-lambda-target___get_employee_compensation": "Get Employee Compensation",
        }
        available = {k: v for k, v in tool_labels.items() if k in st.session_state.tools}

        if not available:
            st.warning("No recognized tools visible for this persona.")
        else:
            selected_tool = st.selectbox(
                "Tool:", options=list(available.keys()),
                format_func=lambda x: available[x],
            )

            with st.form(key="tool_form"):
                if selected_tool == "hr-lambda-target___search_employee":
                    search_q = st.text_input("Search query:", value="John")
                    tenant   = st.text_input("Tenant ID:", value="tenant-alpha")
                    submitted = st.form_submit_button("🚀 Call Tool", use_container_width=True)
                    if submitted:
                        result = call_tool(config, st.session_state.token, selected_tool,
                                           {"query": search_q, "tenantId": tenant})
                        if result:
                            st.json(result)

                elif selected_tool == "hr-lambda-target___get_employee_profile":
                    emp_id  = st.text_input("Employee ID:", value="EMP001")
                    tenant  = st.text_input("Tenant ID:", value="tenant-alpha")
                    inc_pii = st.checkbox("Include PII")
                    inc_addr = st.checkbox("Include Address")
                    submitted = st.form_submit_button("🚀 Call Tool", use_container_width=True)
                    if submitted:
                        result = call_tool(config, st.session_state.token, selected_tool,
                                           {"employee_id": emp_id, "tenantId": tenant,
                                            "include_pii": inc_pii, "include_address": inc_addr})
                        if result:
                            st.json(result)

                elif selected_tool == "hr-lambda-target___get_employee_compensation":
                    emp_id  = st.text_input("Employee ID:", value="EMP001")
                    tenant  = st.text_input("Tenant ID:", value="tenant-alpha")
                    submitted = st.form_submit_button("🚀 Call Tool", use_container_width=True)
                    if submitted:
                        result = call_tool(config, st.session_state.token, selected_tool,
                                           {"employee_id": emp_id, "tenantId": tenant})
                        if result:
                            st.json(result)

    # Activity log
    if st.session_state.logs:
        st.divider()
        st.subheader("📝 Activity Log")
        log_icons = {"error": "🔴", "success": "🟢", "warning": "🟡", "info": "⚪"}
        with st.container(height=250):
            for entry in st.session_state.logs[-15:]:
                icon = log_icons.get(entry["level"], "⚪")
                comp = f"[{entry['comp']}] " if entry["comp"] else ""
                st.markdown(f"{icon} `{entry['ts']}` {comp}{entry['msg']}")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.markdown(
    "**Flow:** Client → Cognito OAuth2 → AgentCore Runtime → AgentCore Gateway "
    "→ Request Interceptor → Cedar Policy Engine → HR Lambda → Response Interceptor (DLP) → Response"
)
