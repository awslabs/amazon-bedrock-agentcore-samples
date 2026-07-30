"""Configure the OpenAI Agents SDK for OpenAI or Bedrock-hosted OpenAI models."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ModelRuntime:
    model: str
    include_web_search: bool
    provider: str
    region: str | None = None


def configure_model_runtime() -> ModelRuntime:
    """Configure the Agents SDK and return provider-specific model settings."""
    if not _env_bool("BEDROCK_OPENAI_ENABLED", False):
        return ModelRuntime(
            model=os.getenv("OPENAI_MODEL", "gpt-5.6-sol"),
            include_web_search=_env_bool("PAID_RESEARCH_WEB_SEARCH_ENABLED", True),
            provider="openai",
        )

    try:
        from aws_bedrock_token_generator import provide_token
    except ImportError as exc:
        raise RuntimeError("Bedrock-hosted OpenAI requires aws-bedrock-token-generator") from exc

    from agents import set_default_openai_client, set_tracing_disabled
    from openai import AsyncOpenAI

    region = os.getenv("BEDROCK_OPENAI_REGION", "us-east-1")
    base_url = os.getenv("OPENAI_BASE_URL", "").strip() or (
        f"https://bedrock-mantle.{region}.api.aws/openai/v1"
    )
    token = provide_token(region=region)
    set_default_openai_client(
        AsyncOpenAI(api_key=token, base_url=base_url),
        use_for_tracing=False,
    )
    set_tracing_disabled(True)

    return ModelRuntime(
        model=os.getenv("BEDROCK_OPENAI_MODEL", "openai.gpt-5.5"),
        include_web_search=_env_bool("BEDROCK_OPENAI_WEB_SEARCH_ENABLED", False),
        provider="bedrock",
        region=region,
    )
