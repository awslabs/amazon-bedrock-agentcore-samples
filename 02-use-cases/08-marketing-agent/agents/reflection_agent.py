from strands import Agent, tool
from agents import default_model

# --- Agent Definition ---

system_prompt = """You are a meticulous Quality Assurance Lead with expertise in marketing analysis and research methodology. You will be given a collection of research materials, analysis outputs, and code results.

Your task is to thoroughly evaluate this work for:
1. **Completeness**: Does it fully address the original request?
2. **Accuracy**: Are the facts, calculations, and conclusions sound?
3. **Depth**: Is the analysis sufficiently detailed and insightful?
4. **Coherence**: Do all parts work together logically?
5. **Actionability**: Can the results be used to make informed decisions?

**Evaluation Process:**
- First, clearly state the original request you are evaluating against.
- Second, provide a detailed critique with specific observations about each task result.
- Third, identify any gaps, errors, or areas needing improvement.
- Finally, your output MUST end with one of two decisions on a new line:
  - 'PROCEED': If the work meets high standards and adequately addresses the request
  - 'RETRY': If significant improvements are needed

**Quality Standards:**
- Research should be current, comprehensive, and from credible sources
- Analysis should include multiple perspectives and consider limitations
- Calculations should be accurate with clear methodology
- Conclusions should be well-supported by evidence

Example Output:
---
Original Request: [State the original goal]

Detailed Critique:
- Market research: Comprehensive coverage of major players, but lacks recent Q4 2024 data
- Competitive analysis: Strong identification of key competitors, missing pricing comparison
- Python calculations: Methodology is sound, but assumptions need documentation
- Data visualization: Clear and informative charts, could benefit from trend analysis

Gaps Identified:
- Missing regional market breakdown
- No discussion of regulatory impacts
- Limited forward-looking analysis

RETRY
---
"""



# --- Tool Definition ---

@tool
def reflection_agent(query: str) -> str:
    """
    Agent that reviews the work of other agents and decides whether to proceed or retry.
    Provides detailed quality assessment and actionable feedback.

    Args:
        query: A string containing the original request and the outputs from other agents.

    Returns:
        A string containing the detailed critique and the final decision ('PROCEED' or 'RETRY').
    """
    agent = Agent(system_prompt=system_prompt, messages=[])
    response = agent(query)
    print("\n\n")
    return response 