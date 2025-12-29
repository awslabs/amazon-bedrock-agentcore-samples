"""Bedrock Guardrails implementation."""

import boto3
import structlog

from cx_agent_backend.domain.entities.conversation import Message
from cx_agent_backend.domain.services.guardrail_service import (
    GuardrailAssessment,
    GuardrailResult,
    GuardrailService,
)

logger = structlog.get_logger()


class BedrockGuardrailService(GuardrailService):
    """Bedrock Guardrails implementation."""

    def __init__(self, guardrail_id: str, region: str | None = None):
        self._guardrail_id = guardrail_id
        self._client = boto3.client("bedrock-runtime", region_name=region)

    async def check_input(self, message: Message) -> GuardrailResult:
        """Check user input against Bedrock Guardrails."""
        return await self._check_content(message.content, "INPUT")

    async def check_output(self, message: Message) -> GuardrailResult:
        """Check AI output against Bedrock Guardrails."""
        return await self._check_content(message.content, "OUTPUT")

    async def _check_content(self, content: str, source: str) -> GuardrailResult:
        """Check content against Bedrock Guardrails."""
        if not self._guardrail_id:
            return GuardrailResult(
                assessment=GuardrailAssessment.ALLOWED,
                blocked_categories=[],
                message="",
            )

        try:
            response = self._client.apply_guardrail(
                guardrailIdentifier=self._guardrail_id,
                guardrailVersion="DRAFT",
                source=source,
                content=[{"text": {"text": content}}],
            )

            logger.info("Guardrail response", response=response)

            if response["action"] == "GUARDRAIL_INTERVENED":
                blocked_categories = []
                message = ""

                # Extract blocked categories
                for assessment in response.get("assessments", []):
                    for policy_type, policy_data in assessment.items():
                        if policy_type == "topicPolicy":
                            for topic in policy_data.get("topics", []):
                                blocked_categories.append(topic["name"])
                        elif policy_type == "sensitiveInformationPolicy":
                            for pii_entity in policy_data.get("piiEntities", []):
                                blocked_categories.append(f"PII-{pii_entity['type']}")
                            for regex_match in policy_data.get("regexes", []):
                                blocked_categories.append(
                                    f"REGEX-{regex_match['name']}"
                                )

                # Extract intervention message
                for output in response.get("outputs", []):
                    if output.get("text"):
                        message = output["text"]

                return GuardrailResult(
                    assessment=GuardrailAssessment.BLOCKED,
                    blocked_categories=blocked_categories,
                    message=message or "Content blocked by guardrails",
                )

            return GuardrailResult(
                assessment=GuardrailAssessment.ALLOWED,
                blocked_categories=[],
                message="",
            )

        except Exception as e:
            logger.error("Guardrail check failed", error=str(e))
            return GuardrailResult(
                assessment=GuardrailAssessment.ERROR,
                blocked_categories=[],
                message=f"Guardrail check failed: {str(e)}",
            )
