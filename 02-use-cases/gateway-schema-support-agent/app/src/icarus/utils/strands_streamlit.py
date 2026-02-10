import asyncio

import streamlit as st
from strands import Agent
from strands.types.content import Message
from streamlit.delta_generator import DeltaGenerator


class StrandsAgentStreamlitChat:
    DEFAULT_CHAT_INPUT_PLACEHOLDER = "Ask me anything..."

    def __init__(self, agent: Agent | None, chat_container: DeltaGenerator | None):
        self.agent = agent
        self.chat_container = chat_container or st.container()
        self._display_only_messages: dict[int, list[Message]] = {}

    def _show_text(self, role: str, value: str):
        with st.chat_message(name=role):
            st.markdown(value)

    def _show_tool_use(self, value: dict, expand: bool):
        tool_name = value["name"]
        with st.chat_message(name="assistant", avatar=":material/build:"):
            with st.expander(f"Tool Use: `{tool_name}`", expanded=expand):
                st.json(value)

    def _show_tool_result(self, value: dict, expand: bool):
        with st.chat_message(name="assistant", avatar=":material/terminal:"):
            with st.expander("Tool Result", expanded=expand):
                st.json(value)

    def show_message(self, message: Message, expand_all=False):
        for content_block in message["content"]:
            for key, value in content_block.items():
                if key == "text":
                    assert isinstance(value, str)
                    self._show_text(message["role"], value)

                elif key == "toolUse":
                    assert isinstance(value, dict)
                    self._show_tool_use(value, expand=expand_all)

                elif key == "toolResult":
                    assert isinstance(value, dict)
                    self._show_tool_result(value, expand=expand_all)

                else:
                    raise ValueError(f"Unknown content block key: {key}")

    def stream_messages(self, prompt: str):
        stream_container = st.container()
        static_container = st.empty()

        static_chat = static_container.chat_message("assistant")
        static_chat.markdown(":material/hourglass: Working...")

        async def agent_runner():
            assert self.agent is not None
            async for event in self.agent.stream_async(prompt):
                if "message" in event:
                    with stream_container:
                        self.show_message(event["message"])

        asyncio.run(agent_runner())
        static_container.empty()

    def add_display_only_message(self, message: str, position: int | None = None):
        """Only displays the message to the user as an assistant message
           (i.e., does not add the message to the agent's message history).

        Args:
            message: The message to be displayed
            position: The position in agent's message history BEFORE which,
                      this message will be displayed.
                      NOTE: -ve positions are ALWAYS displayed (in sorted order)
                            at the very beginning of the chat.
        """
        if position is None:
            position = len(self.agent.messages) if self.agent is not None else -1

        m = Message(role="assistant", content=[{"text": message}])

        if position in self._display_only_messages:
            self._display_only_messages[position].append(m)
        else:
            self._display_only_messages[position] = [m]

    def prompt_agent(self, prompt: str):
        with self.chat_container:
            with st.chat_message("user"):
                st.markdown(prompt)
            self.stream_messages(prompt)

    def draw_chat(
        self, disable_chat_input: bool = False, chat_input_placeholder: str | None = None
    ):
        with self.chat_container:
            # Show display-only messages with negative positions first
            for display_only_position in sorted(self._display_only_messages.keys()):
                if display_only_position < 0:
                    for display_only_message in self._display_only_messages[display_only_position]:
                        self.show_message(display_only_message)

            if self.agent is not None:
                for i, message in enumerate(self.agent.messages):
                    # Show display-only messages for current position
                    if i in self._display_only_messages:
                        for display_only_message in self._display_only_messages[i]:
                            self.show_message(display_only_message)

                    # Show the actual message
                    self.show_message(message)

        if chat_input_placeholder is None:
            chat_input_placeholder = self.DEFAULT_CHAT_INPUT_PLACEHOLDER

        disable_chat_input_ = disable_chat_input or self.agent is None
        prompt = st.chat_input(chat_input_placeholder, disabled=disable_chat_input_)
        if prompt:
            self.prompt_agent(prompt)
            st.rerun()
