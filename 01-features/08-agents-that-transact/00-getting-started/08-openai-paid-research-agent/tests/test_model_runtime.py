from paid_research.model_runtime import configure_model_runtime


def test_direct_openai_runtime_defaults(monkeypatch) -> None:
    monkeypatch.delenv("BEDROCK_OPENAI_ENABLED", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("PAID_RESEARCH_WEB_SEARCH_ENABLED", raising=False)

    runtime = configure_model_runtime()

    assert runtime.provider == "openai"
    assert runtime.model == "gpt-5.6-sol"
    assert runtime.include_web_search is True


def test_bedrock_runtime_disables_web_search_by_default(monkeypatch) -> None:
    monkeypatch.setenv("BEDROCK_OPENAI_ENABLED", "true")
    monkeypatch.setenv("BEDROCK_OPENAI_REGION", "us-east-1")
    monkeypatch.delenv("BEDROCK_OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("BEDROCK_OPENAI_WEB_SEARCH_ENABLED", raising=False)
    monkeypatch.setattr(
        "aws_bedrock_token_generator.provide_token",
        lambda region: f"token-for-{region}",
    )

    runtime = configure_model_runtime()

    assert runtime.provider == "bedrock"
    assert runtime.model == "openai.gpt-5.5"
    assert runtime.region == "us-east-1"
    assert runtime.include_web_search is False
