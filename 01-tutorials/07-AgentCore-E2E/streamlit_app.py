import streamlit as st
from strands import Agent, tool
from retrieve_from_kb_with_refresh import create_agent_with_fresh_session
import asyncio

agent = create_agent_with_fresh_session()


# Streamlit UI
# UI Layout
# Move image to the very top of the page (before title and page config)
st.set_page_config(page_title="Strands Agents", page_icon="webjet-logo-au-white-2x.png", layout="wide")
st.image("webjet-logo-au-white-2x.png", width=150)
st.title("Ask Rach-e")

# Initialize chat history

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello, how can I help you?"}
    ]

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input at the bottom
user_input = st.chat_input("Type your message...")

if user_input:
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)



    with st.chat_message("assistant"):
        response_placeholder = st.empty()

        async def stream_response():
            full_response = ""
            async for event in agent.stream_async(user_input):
                if "data" in event:
                    full_response += event["data"]
                    response_placeholder.markdown(full_response)
            return full_response

        # Run the async stream in Streamlit
        full_response = asyncio.run(stream_response())
        st.session_state.messages.append({"role": "assistent", "content": full_response})



