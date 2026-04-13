"""Code Review Agent — analyzes code for quality, security, and best practices."""

METADATA = {
    "name": "code_review_agent",
    "description": "Agent for automated code review, security scanning, and best practice enforcement across repositories",
    "protocol": "HTTP",
    "entrypoint": "code_review_agent.py",
    "version": "1.0.0",
    "team": "Engineering",
    "capabilities": ["code-review", "security-scanning", "best-practices", "static-analysis"],
    "tools": [
        {"name": "review_code", "description": "Review code for quality issues, bugs, and improvements"},
        {"name": "security_scan", "description": "Scan code for security vulnerabilities and compliance issues"},
    ],
}

from strands import Agent, tool  # noqa: E402
from strands.models import BedrockModel  # noqa: E402
from bedrock_agentcore.runtime import BedrockAgentCoreApp  # noqa: E402

app = BedrockAgentCoreApp()


@tool
def review_code(code_snippet: str, language: str = "python") -> str:
    """Review code for quality issues, bugs, and improvements."""
    return f"""{{"language": "{language}",
"issues_found": 3,
"severity_summary": {{"critical": 0, "warning": 2, "info": 1}},
"findings": [
  {{"severity": "warning", "line": 12, "message": "Unused variable 'temp_result'", "suggestion": "Remove or use the variable"}},
  {{"severity": "warning", "line": 28, "message": "Function exceeds 50 lines — consider refactoring", "suggestion": "Extract helper functions"}},
  {{"severity": "info", "line": 5, "message": "Missing type hints on function parameters", "suggestion": "Add type annotations"}}
],
"overall_quality": "GOOD",
"recommendation": "Address warnings before merging"}}"""


@tool
def security_scan(code_snippet: str, language: str = "python") -> str:
    """Scan code for security vulnerabilities and compliance issues."""
    return f"""{{"language": "{language}",
"vulnerabilities_found": 1,
"severity_summary": {{"critical": 0, "high": 0, "medium": 1, "low": 0}},
"findings": [
  {{"severity": "medium", "type": "CWE-798", "message": "Potential hardcoded credential detected", "suggestion": "Use environment variables or secrets manager"}}
],
"compliance": {{"owasp_top10": "PASS", "cwe_top25": "PASS_WITH_WARNINGS"}},
"recommendation": "Resolve medium-severity finding before deployment"}}"""


agent = Agent(
    model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0"),
    tools=[review_code, security_scan],
    system_prompt="You are a senior code reviewer. Use your tools to analyze code for quality, security, and best practices.",
)


@app.entrypoint
def invoke(payload, context=None):
    result = agent(payload.get("prompt", "Review the submitted code"))
    return {"result": str(result)}


if __name__ == "__main__":
    app.run()
