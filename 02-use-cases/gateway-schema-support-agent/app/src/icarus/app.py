import json
import shutil
import time
from pathlib import Path

import streamlit as st
import yaml
from strands import Agent
from streamlit.runtime.uploaded_file_manager import UploadedFile

from icarus.agent import DEFAULT_USER_MESSAGE
from icarus.agent import init_agent
from icarus.utils.strands_streamlit import StrandsAgentStreamlitChat

ALL_SESSIONS_DIR = Path("exp/sessions").resolve()
assert ALL_SESSIONS_DIR.exists(), f"Sessions directory does not exist: {ALL_SESSIONS_DIR}"


class SessionState:
    def __init__(self):
        self.disable_chat_input: bool = True
        self.session_dir: Path | None = None
        self.agent: Agent | None = None
        self.auto_exec_agent: bool = False


session_state: SessionState
if "instance" in st.session_state:
    session_state = st.session_state.instance
else:
    session_state = st.session_state.instance = SessionState()


def _parse_uploaded_file(uploaded_file: UploadedFile) -> dict:
    content = uploaded_file.read()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return yaml.safe_load(content)


def _get_chat_input_placeholder() -> str:
    chat_input_placeholder: str
    if session_state.session_dir is None:
        chat_input_placeholder = "Please upload an OpenAPI schema to get started..."
    elif session_state.agent is None:
        chat_input_placeholder = 'Click on "🚀" start chatting with Icarus...'
    else:
        chat_input_placeholder = "Ask me anything about your schema..."
    return chat_input_placeholder


def new_session_dir(schema: dict) -> Path:
    curr_session_dir = ALL_SESSIONS_DIR / time.strftime("%Y%m%d.%H%M%S")
    curr_session_dir.mkdir(exist_ok=False)

    schema_path = curr_session_dir / "schema.yaml"
    schema_path.write_text(yaml.dump(schema, sort_keys=False))
    return curr_session_dir


def load_session():
    load_session_id = st.query_params.get("session", None)
    if load_session_id is not None:
        session_dir = ALL_SESSIONS_DIR / load_session_id
        if not session_dir.exists():
            st.error(f"Session not found: {session_dir}")
            return

        session_state.session_dir = session_dir
        session_state.agent = init_agent(session_dir=session_state.session_dir)
        session_state.auto_exec_agent = False
        session_state.disable_chat_input = False


@st.dialog("Current Schema", width="large")
def show_schema():
    assert session_state.session_dir is not None
    schema_path = session_state.session_dir / "schema.yaml"
    st.code(schema_path.read_text(), language="yaml")


def draw_sidebar():
    schema_initialized = session_state.session_dir is not None
    agent_initialized = session_state.agent is not None

    with st.sidebar:
        uploaded_file = st.file_uploader(
            "Choose your OpenAPI schema file",
            type=["json", "yaml", "yml"],
            disabled=schema_initialized,
        )

        st.divider()

        if schema_initialized:
            assert session_state.session_dir is not None  # for type checkers

            if session_state.agent is None:
                st.success("Schema loaded successfully!", icon=":material/thumb_up:")

                initialize_agent = st.button("🚀", width="stretch", disabled=agent_initialized)
                if initialize_agent:
                    session_state.agent = init_agent(session_dir=session_state.session_dir)
                    session_state.auto_exec_agent = True
                    st.rerun()

            else:
                if st.button(
                    "Show current schema",
                    width="stretch",
                    icon=":material/open_in_browser:",
                    disabled=session_state.disable_chat_input,
                ):
                    show_schema()

        elif uploaded_file is not None:
            try:
                with st.spinner("Loading your schema..."):
                    parsed_schema = _parse_uploaded_file(uploaded_file)
                    session_dir = new_session_dir(parsed_schema)

                    ruleset_path = Path(".spectral.yaml").resolve()
                    assert ruleset_path.exists(), ruleset_path
                    shutil.copy(ruleset_path, session_dir / ruleset_path.name)

                    session_state.session_dir = session_dir

            except Exception as e:  # pylint:disable=broad-exception-caught
                st.error(f"Error parsing file: {e}", icon=":material/error:")
                return

            st.rerun()


def draw_chattab():
    chat_tab = st.container()
    chat_tab.header("💬 Chat with Icarus")

    strands_chat = StrandsAgentStreamlitChat(agent=session_state.agent, chat_container=chat_tab)
    strands_chat.add_display_only_message(
        "Hi! I'm Icarus, your AI assistant. How can I help you today?", position=-1
    )
    strands_chat.draw_chat(
        chat_input_placeholder=_get_chat_input_placeholder(),
        disable_chat_input=session_state.disable_chat_input,
    )

    if session_state.auto_exec_agent:
        session_state.auto_exec_agent = False
        strands_chat.prompt_agent(DEFAULT_USER_MESSAGE)
        session_state.disable_chat_input = False
        st.rerun()


def main():
    load_session()
    draw_sidebar()
    draw_chattab()


if __name__ == "__main__":
    main()
