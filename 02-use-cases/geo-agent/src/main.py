"""Amazon Bedrock AgentCore entry point for the GEO Agent.

Defines the Strands Agent with four GEO tools (rewrite, score, llms.txt, store)
and exposes it as an AgentCore application with streaming response support.
"""

from strands import Agent
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from model.load import load_model
from tools.rewrite_content import rewrite_content_for_geo
from tools.evaluate_geo_score import evaluate_geo_score
from tools.generate_llms_txt import generate_llms_txt
from tools.store_geo_content import store_geo_content

app = BedrockAgentCoreApp()
log = app.logger

SYSTEM_PROMPT = """You are a Generative Engine Optimization (GEO) Expert Agent.

You have four tools:

1. rewrite_content_for_geo — Rewrites content for GEO best practices.
2. evaluate_geo_score — Evaluates a URL's GEO readiness across 3 dimensions.
3. generate_llms_txt — Generates an llms.txt file for a website.
4. store_geo_content — Fetches a URL, rewrites it for GEO, and stores in DynamoDB for edge serving.

Tool selection:
- User gives text/content → call rewrite_content_for_geo
- User gives URL for evaluation → call evaluate_geo_score
- User asks for llms.txt → call generate_llms_txt
- User asks to store/publish/deploy GEO content for a URL → call store_geo_content

<MANDATORY_OUTPUT_RULES>
After ANY tool returns its result, you MUST copy-paste the ENTIRE tool output
into your response WITHOUT modification. Do NOT summarize. Do NOT describe
what the tool did. Do NOT list improvements. Do NOT paraphrase.

Your response after a tool call should be ONLY:
1. One short intro sentence (max 15 words)
2. The COMPLETE tool output, copied verbatim

VIOLATION: Saying things like "The rewritten version includes..." or
"Here's a summary of changes..." instead of showing the actual content.

CORRECT EXAMPLE:
"Here's your GEO-optimized content:

[FULL TOOL OUTPUT HERE - every single line]"

WRONG EXAMPLE:
"The content has been rewritten with statistics, headings, and citations."
</MANDATORY_OUTPUT_RULES>
"""


@app.entrypoint
async def invoke(payload, context):
    """Handle an incoming AgentCore invocation by streaming the agent's response."""
    agent = Agent(
        model=load_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[rewrite_content_for_geo, evaluate_geo_score, generate_llms_txt, store_geo_content],
    )

    stream = agent.stream_async(payload.get("prompt"))

    async for event in stream:
        if "data" in event and isinstance(event["data"], str):
            yield event["data"]


if __name__ == "__main__":
    app.run()
