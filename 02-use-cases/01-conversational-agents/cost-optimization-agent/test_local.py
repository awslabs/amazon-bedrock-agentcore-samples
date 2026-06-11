"""
Test script for LLM-Powered Cost Optimization Agent
Demonstrates natural language understanding and intelligent tool selection
"""

import asyncio
from cost_optimization_agent import process_request


async def test_query(query: str, description: str):
    """Test a single query and display results"""
    print(f"\n{'=' * 80}")
    print(f"TEST: {description}")
    print(f"{'=' * 80}")
    print(f"Query: {query}\n")
    print("Response:")
    print("-" * 80)

    payload = {"prompt": query}

    full_response = []
    async for chunk in process_request(payload):
        if chunk.get("type") == "chunk":
            data = chunk.get("data", "")
            print(data, end="", flush=True)
            full_response.append(data)
        elif chunk.get("error"):
            print(f"\n❌ Error: {chunk['error']}")
            return

    print("\n" + "=" * 80 + "\n")
    return "".join(full_response)


async def main():
    """Run comprehensive tests showcasing LLM capabilities"""

    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║           LLM-POWERED COST OPTIMIZATION AGENT - TEST SUITE                   ║
║                                                                              ║
║  This test suite demonstrates the power of LLM-based tool selection         ║
║  vs simple keyword matching. Watch how the agent intelligently              ║
║  understands intent and selects the right tools!                            ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)

    # Test 1: Natural language variation (would fail with keyword matching)
    await test_query(
        "Are my costs higher than usual?", "Natural Language Understanding - Anomaly Detection"
    )

    # Test 2: Multi-tool orchestration (would fail with keyword matching)
    await test_query(
        "Show me my budget status and forecast for next month",
        "Multi-Tool Orchestration - Budget + Forecast",
    )

    # Test 3: Specific service query
    await test_query("How much am I spending on Amazon Bedrock?", "Service-Specific Cost Analysis")

    # Test 4: Complex reasoning query
    await test_query(
        "What are my top 3 most expensive services and how can I reduce costs?",
        "Complex Query with Reasoning + Recommendations",
    )

    # Test 5: Conversational follow-up
    await test_query("Give me a summary of my current AWS spending", "Current Month Cost Summary")

    # Test 6: Optimization advice
    await test_query(
        "I need to cut my AWS bill by 20%. What should I do?", "Cost Optimization Strategy"
    )

    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║                           TEST SUITE COMPLETE                                ║
║                                                                              ║
║  Notice how the LLM:                                                         ║
║  ✅ Understands natural language variations                                  ║
║  ✅ Selects appropriate tools automatically                                  ║
║  ✅ Combines multiple tools when needed                                      ║
║  ✅ Provides reasoning and analysis                                          ║
║  ✅ Gives actionable recommendations                                         ║
║                                                                              ║
║  Compare this to the keyword-based version which would fail on most of       ║
║  these queries!                                                              ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)


if __name__ == "__main__":
    asyncio.run(main())
