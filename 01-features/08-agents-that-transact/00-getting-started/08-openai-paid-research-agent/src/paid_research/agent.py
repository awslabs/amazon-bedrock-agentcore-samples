"""OpenAI Agents SDK financial research agent with an AgentCore payment tool."""

from __future__ import annotations

import argparse
import asyncio
import os
from collections.abc import Sequence

from agents import Agent, ModelSettings, Runner, WebSearchTool, function_tool, trace
from dotenv import load_dotenv

from .model_runtime import configure_model_runtime
from .x402 import X402PaymentClient

INSTRUCTIONS = """Role: Financial research analyst.

Goal: Produce an evidence-backed research brief. Use public sources first and buy
premium evidence only when it materially closes a named evidence gap.

Payment rules:
- Use paid_research_fetch only for the exact premium URL supplied in the task.
- Before buying, state internally which evidence gap the purchase should close.
- Never invent a price, source, payment result, or remaining budget.
- A payment failure or budget rejection is final for that source. Do not seek a
  trial URL, alternate merchant, redirect, or workaround.
- Call payment_session_status after a successful paid fetch so the final brief can
  report the remaining session budget.

Evidence and output:
- Cite URLs next to the claims they support.
- Label facts from public sources separately from facts from paid data.
- Distinguish direct evidence from inference and name material conflicts.
- Include: executive summary, evidence table, analysis, risks and limitations,
  paid-data ledger, and sources.
- Do not execute trades or present the brief as personalized investment advice.

Stop when the requested brief is supported by useful evidence, or when the
remaining evidence gap cannot be closed within the available tools and budget."""


def build_agent(
    payment_client: X402PaymentClient,
    *,
    require_payment_approval: bool = False,
    model: str | None = None,
    include_web_search: bool = True,
) -> Agent:
    async def paid_research_fetch(url: str) -> str:
        """Fetch one approved premium research URL and settle an x402 payment if required."""
        return await asyncio.to_thread(payment_client.fetch, url)

    async def payment_session_status() -> str:
        """Return the current maximum and remaining AgentCore payment-session budget."""
        return await asyncio.to_thread(payment_client.session_status)

    paid_tool = function_tool(
        paid_research_fetch,
        needs_approval=require_payment_approval,
        timeout=90.0,
    )
    status_tool = function_tool(payment_session_status, timeout=30.0)

    reasoning_effort = os.getenv("OPENAI_REASONING_EFFORT", "medium")
    tools = []
    if include_web_search:
        tools.append(WebSearchTool(search_context_size="medium"))
    tools.extend([paid_tool, status_tool])

    return Agent(
        name="Budget-bounded financial research analyst",
        instructions=INSTRUCTIONS,
        model=model or os.getenv("OPENAI_MODEL", "gpt-5.6-sol"),
        model_settings=ModelSettings(
            reasoning={"effort": reasoning_effort},
            verbosity="medium",
            parallel_tool_calls=False,
        ),
        tools=tools,
    )


def build_prompt(query: str, paid_url: str | None) -> str:
    paid_context = (
        f"\nApproved premium URL for this task: {paid_url}"
        if paid_url
        else "\nNo premium URL was supplied. Do not call paid_research_fetch."
    )
    return (
        f"Research request: {query}\n"
        f"{paid_context}\n\n"
        "Use premium data only if public evidence leaves a material gap. "
        "Record whether a payment was made and what evidence it added."
    )


async def run_research(
    query: str,
    *,
    paid_url: str | None = None,
    require_payment_approval: bool = False,
    approve_interactively: bool = True,
) -> str:
    payment_client = X402PaymentClient.from_env()
    runtime = configure_model_runtime()
    agent = build_agent(
        payment_client,
        require_payment_approval=require_payment_approval,
        model=runtime.model,
        include_web_search=runtime.include_web_search,
    )
    prompt = build_prompt(query, paid_url)

    with trace("AgentCore paid financial research"):
        result = await Runner.run(agent, prompt)
        if result.interruptions:
            if not approve_interactively:
                return "Payment approval required; run paused before the paid tool call."

            print("\nThe run paused before spending. Pending paid tool call(s):")
            for interruption in result.interruptions:
                print(f"- {interruption}")
            approved = input("Approve all pending paid calls? [y/N] ").strip().lower() == "y"

            state = result.to_state()
            for interruption in result.interruptions:
                if approved:
                    state.approve(interruption)
                else:
                    state.reject(interruption)
            result = await Runner.run(agent, state)

    return str(result.final_output)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a budget-bounded OpenAI financial research agent")
    parser.add_argument("query", help="Research question, company, or market topic")
    parser.add_argument(
        "--paid-url",
        default=os.getenv("PAID_RESEARCH_URL"),
        help="Exact approved x402 URL the agent may buy",
    )
    parser.add_argument(
        "--require-payment-approval",
        action="store_true",
        help="Pause for human approval before each paid tool call",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    load_dotenv()
    args = _parser().parse_args(argv)
    output = asyncio.run(
        run_research(
            args.query,
            paid_url=args.paid_url,
            require_payment_approval=args.require_payment_approval,
        )
    )
    print(output)


if __name__ == "__main__":
    main()
