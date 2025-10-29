import os
import logging
from functools import lru_cache
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel
from traceloop.sdk import Traceloop
from traceloop.sdk.decorators import workflow, task
from ddgs import DDGS


logging.basicConfig(level=logging.ERROR, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(os.getenv("AGENT_RUNTIME_LOG_LEVEL", "INFO").upper())

app = BedrockAgentCoreApp()


def _init_traceloop():
    Traceloop.init(app_name="strands-traceloop-agent", disable_batch=True)


@task(name="tool.web_search")
@tool
def web_search(query: str) -> str:
    try:
        ddgs = DDGS()
        results = ddgs.text(query, max_results=5)
        formatted_results = []
        for i, result in enumerate(results, 1):
            formatted_results.append(
                f"{i}. {result.get('title', 'No title')}\n"
                f"   {result.get('body', 'No summary')}\n"
                f"   Source: {result.get('href', 'No URL')}\n"
            )
        return (
            "\n".join(formatted_results) if formatted_results else "No results found."
        )
    except Exception as exc:
        return f"Error searching the web: {exc}"


def _bedrock_model() -> BedrockModel:
    region = os.getenv("AWS_DEFAULT_REGION", "us-west-2")
    model_id = os.getenv(
        "BEDROCK_MODEL_ID", "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
    )
    return BedrockModel(
        model_id=model_id, region_name=region, temperature=0.0, max_tokens=1024
    )


@app.entrypoint
@workflow(name="strands_travel_agent")
def strands_agent_bedrock(payload, context=None) -> str:
    agent = _agent()
    user_input = payload.get("prompt")
    logger.info(
        "[%s] User input: %s", getattr(context, "session_id", "unknown"), user_input
    )
    response = agent(user_input)
    return response.message["content"][0]["text"]


@lru_cache(maxsize=1)
def _agent() -> Agent:
    _init_traceloop()
    return Agent(
        model=_bedrock_model(), system_prompt=_system_prompt(), tools=[web_search]
    )


def _system_prompt() -> str:
    return (
        "You are an experienced travel agent specializing in personalized travel recommendations "
        "with access to recent web information. Provide recommendations with current context and "
        "concise planning details."
    )


if __name__ == "__main__":
    app.run()
