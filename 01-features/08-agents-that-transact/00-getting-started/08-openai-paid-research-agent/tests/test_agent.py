from paid_research.agent import build_agent, build_prompt


class FakePaymentClient:
    def fetch(self, url: str) -> str:
        return f'{{"ok": true, "url": "{url}"}}'

    def session_status(self) -> str:
        return '{"available_spend": "0.20"}'


def test_builds_current_agents_sdk_tool_contract() -> None:
    agent = build_agent(FakePaymentClient(), model="gpt-5.6-sol")

    assert agent.model == "gpt-5.6-sol"
    assert len(agent.tools) == 3
    assert agent.tools[1].name == "paid_research_fetch"
    assert agent.tools[2].name == "payment_session_status"


def test_can_disable_hosted_web_search_for_bedrock_compatibility() -> None:
    agent = build_agent(
        FakePaymentClient(),
        model="openai.gpt-5.5",
        include_web_search=False,
    )

    assert [tool.name for tool in agent.tools] == [
        "paid_research_fetch",
        "payment_session_status",
    ]


def test_prompt_disables_paid_tool_without_an_approved_url() -> None:
    prompt = build_prompt("Research AMZN", None)

    assert "Do not call paid_research_fetch" in prompt
