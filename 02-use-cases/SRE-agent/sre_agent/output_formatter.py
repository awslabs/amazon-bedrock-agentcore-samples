#!/usr/bin/env python3

import logging
from typing import Any, Dict, List, Optional

# Configure logging with basicConfig
logging.basicConfig(
    level=logging.INFO,  # Set the log level to INFO
    # Define log message format
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


class SREOutputFormatter:
    """Simple markdown output formatter for SRE multi-agent responses."""

    def __init__(self):
        pass

    def _extract_steps_from_response(self, response: str) -> List[str]:
        """Extract numbered steps from agent response."""
        if not response:
            return []

        steps = []
        lines = response.split("\n")

        for line in lines:
            line = line.strip()
            # Look for numbered steps (1., 2., etc.) or bullet points
            if line and (
                line[0].isdigit() or line.startswith("-") or line.startswith("•")
            ):
                steps.append(line)

        return steps

    def format_investigation_response(
        self,
        query: str,
        agent_results: Dict[str, Any],
        metadata: Dict[str, Any],
        plan: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Format a complete investigation response in clean markdown."""

        # Extract key information
        plan_info = plan or metadata.get("investigation_plan", {})
        current_step = metadata.get("plan_step", 0) + 1
        total_steps = len(plan_info.get("steps", []))

        output = []

        # Header
        output.append("# 🔍 Investigation Results")
        output.append("")
        output.append(f"**Query:** {query}")
        # Only show step progress if we have valid step data
        if total_steps > 0 and current_step <= total_steps:
            output.append(f"**Status:** Step {current_step} of {total_steps} Complete")
        else:
            output.append("**Status:** Investigation Complete")
        output.append("")

        # Executive Summary Section
        executive_summary = self._generate_executive_summary(query, agent_results, metadata)
        if executive_summary:
            output.append(executive_summary)
            output.append("")

        # Key Findings Section
        if agent_results:
            output.append("## 🎯 Key Findings")
            output.append("")

            for agent_name, result in agent_results.items():
                if not result or result == "No response provided":
                    continue

                agent_display = agent_name.replace("_", " ").title()
                output.append(f"### {agent_display}")

                # Extract steps if this is a runbook response
                if (
                    "runbooks" in agent_name.lower()
                    or "operational" in agent_name.lower()
                ):
                    steps = self._extract_steps_from_response(result)
                    if steps:
                        output.append("")
                        output.append("**Runbook Steps Found:**")
                        for step in steps:
                            # Clean up step formatting
                            clean_step = step.strip()
                            if clean_step.startswith(
                                ("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")
                            ):
                                output.append(f"{clean_step}")
                            else:
                                output.append(f"- {clean_step}")
                        output.append("")
                    else:
                        # Show full response if no steps found
                        output.append(f"- {result}")
                        output.append("")
                else:
                    # For non-runbook agents, show full response
                    output.append(f"- {result}")
                    output.append("")

        # Next Steps Section
        if plan_info and current_step < total_steps:
            output.append("## 📋 Next Steps")
            output.append("")
            remaining_steps = plan_info.get("steps", [])[current_step:]
            for i, step in enumerate(remaining_steps, current_step + 1):
                output.append(f"{i}. {step}")
            output.append("")

        # Investigation Complete
        if current_step >= total_steps:
            output.append("## ✅ Investigation Complete")
            output.append("")
            output.append("All planned investigation steps have been executed.")
            output.append("")

        return "\n".join(output)


    def _generate_executive_summary(
        self,
        query: str,
        agent_results: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> str:
        """Generate executive summary using LLM analysis of investigation results."""
        if not agent_results:
            return ""

        try:
            from langchain_anthropic import ChatAnthropic
            from langchain_core.messages import HumanMessage, SystemMessage
            
            # Create LLM instance
            llm = ChatAnthropic(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                temperature=0.1,
            )
            
            # Prepare agent results for analysis
            formatted_results = []
            for agent_name, result in agent_results.items():
                if result and result != "No response provided":
                    formatted_results.append(f"**{agent_name}:**\n{result}\n")
            
            results_text = "\n".join(formatted_results)
            
            # System prompt for executive summary generation
            system_prompt = """You are an expert SRE analyst generating executive summaries for incident reports.

CRITICAL REQUIREMENTS:
- Base all conclusions ONLY on the provided agent investigation results
- Distinguish between performance degradation (slow responses) vs actual outages (services down)
- Only claim "outage" if evidence shows services completely non-responsive or failed
- Specify actual affected services mentioned in results, not the queried service if it doesn't exist
- Be conservative with severity assessments - require specific evidence

EXECUTIVE SUMMARY FORMAT:
```markdown
## 📋 Executive Summary

### 🎯 Key Insights
- **Root Cause**: [Primary issue identified with specific evidence]
- **Impact**: [Performance degradation/Service instability/Service outage - based on evidence]
- **Severity**: [Critical/High/Medium/Low with specific justification]

### ⚡ Next Steps
1. **Immediate** (< 1 hour): [Most urgent action based on findings]
2. **Short-term** (< 24 hours): [Resolution steps from investigation]
3. **Long-term** (< 1 week): [Prevention measures]
4. **Follow-up**: [Monitoring or review recommendations]

### 🚨 Critical Alerts
- [Only include if evidence shows immediate risks - no speculation]
```

SEVERITY GUIDELINES:
- Critical: Security issues, complete service failures, data loss
- High: Significant performance degradation (>5 sec response times), memory errors causing instability  
- Medium: Moderate performance issues, intermittent errors
- Low: Minor issues, warnings

IMPACT GUIDELINES:
- "Service outage": Only if evidence shows services completely down/failed
- "Performance degradation": For high latency, timeouts, but service still responding
- "Service instability": For memory errors, intermittent failures"""

            user_prompt = f"""Generate an executive summary for this SRE investigation:

**Original Query:** {query}

**Investigation Results:**
{results_text}

Generate a concise, accurate executive summary based only on the evidence provided above. Focus on what executives and on-call engineers need to know immediately."""

            # Generate executive summary
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = llm.invoke(messages)
            return response.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating executive summary with LLM: {e}")
            # Fallback to simple summary if LLM fails
            return self._generate_fallback_summary(query, agent_results)


    def _generate_fallback_summary(
        self,
        query: str,
        agent_results: Dict[str, Any]
    ) -> str:
        """Fallback executive summary if LLM generation fails."""
        return """## 📋 Executive Summary

### 🎯 Key Insights
- **Root Cause**: Investigation findings require analysis
- **Impact**: Service performance may be affected
- **Severity**: Medium

### ⚡ Next Steps
1. **Immediate** (< 1 hour): Review detailed findings below
2. **Short-term** (< 24 hours): Execute recommended remediation steps
3. **Long-term** (< 1 week): Monitor system metrics for improvement
4. **Follow-up**: Schedule post-incident review if applicable"""

    def format_plan_approval(self, plan: Dict[str, Any], query: str) -> str:
        """Format plan approval request in clean markdown."""
        output = []

        # Header
        output.append("# 📋 Investigation Plan")
        output.append("")
        output.append(f"**Query:** {query}")
        output.append(f"**Complexity:** {plan.get('complexity', 'unknown').title()}")
        output.append("")

        # Plan Steps
        steps = plan.get("steps", [])
        if steps:
            output.append("## Investigation Steps")
            output.append("")
            for i, step in enumerate(steps, 1):
                output.append(f"{i}. {step}")
            output.append("")

        # Plan Details
        reasoning = plan.get("reasoning", "Standard investigation approach")
        auto_execute = plan.get("auto_execute", False)

        output.append("## Plan Details")
        output.append("")
        output.append(f"**Reasoning:** {reasoning}")
        output.append(f"**Auto-execute:** {'Yes' if auto_execute else 'No'}")
        output.append("")

        # Actions
        output.append("## Available Actions")
        output.append("")
        output.append("- Type `proceed` or `yes` to execute the plan")
        output.append("- Type `modify` to suggest changes")
        output.append("- Ask specific questions about any step")
        output.append("")

        return "\n".join(output)


def create_formatter() -> SREOutputFormatter:
    """Create and return a new SRE output formatter instance."""
    return SREOutputFormatter()
