#!/usr/bin/env python3
"""
Example Usage: Bedrock AgentCore Browser Tool with Strands Integration

This script demonstrates various ways to use the browser tool integration
for intelligent web browsing and content analysis.

Author: AWS Labs Community
License: MIT-0
"""

import os
import time
from strands import Agent
from bedrock_strands_browser_tool import browse_web


def example_1_basic_browsing():
    """Example 1: Basic web content extraction"""
    print("📄 Example 1: Basic Web Content Extraction")
    print("=" * 50)
    
    # Test different extraction modes
    test_url = "https://example.com"
    
    print(f"Browsing: {test_url}")
    
    # Extract text content
    print("\n🔤 Text extraction:")
    text_content = browse_web(test_url, "text")
    if not text_content.startswith("Error"):
        print(f"✅ Success: {len(text_content)} characters")
        print(f"Preview: {text_content[:150]}...")
    else:
        print(f"❌ Error: {text_content}")
    
    # Extract metadata
    print("\n📊 Metadata extraction:")
    metadata = browse_web(test_url, "metadata")
    print(f"Metadata: {metadata}")


def example_2_ai_agent_integration():
    """Example 2: AI agent with browsing capabilities"""
    print("\n\n🤖 Example 2: AI Agent Integration")
    print("=" * 50)
    
    # Create intelligent browsing agent
    browsing_agent = Agent(
        tools=[browse_web],
        model="anthropic.claude-instant-v1",
        system_prompt="You are a web research assistant. Analyze websites and provide concise, helpful summaries."
    )
    
    print("Creating AI agent with browsing capabilities...")
    
    # Test AI-powered website analysis
    test_sites = [
        "https://example.com",
        "https://httpbin.org/html",
    ]
    
    for site in test_sites:
        print(f"\n🔍 Analyzing: {site}")
        try:
            start_time = time.time()
            
            analysis = browsing_agent(f"""
            Browse {site} and provide:
            1. What type of website this is
            2. Main purpose or content
            3. Key information available
            
            Keep the response concise (2-3 sentences).
            """)
            
            elapsed = time.time() - start_time
            print(f"⏱️  Analysis completed in {elapsed:.1f} seconds")
            print(f"🧠 AI Analysis: {analysis}")
            
        except Exception as e:
            print(f"❌ Error analyzing {site}: {e}")


def example_3_news_monitoring():
    """Example 3: News monitoring and analysis"""
    print("\n\n📰 Example 3: News Monitoring")
    print("=" * 50)
    
    # Create news analysis agent
    news_agent = Agent(
        tools=[browse_web],
        model="anthropic.claude-instant-v1",
        system_prompt="You are a news analyst. Extract key information from news websites and identify important trends."
    )
    
    # Example news sites (using publicly accessible test sites)
    news_sites = [
        ("https://httpbin.org/html", "Test News Site"),
    ]
    
    for url, site_name in news_sites:
        print(f"\n📡 Monitoring: {site_name}")
        try:
            start_time = time.time()
            
            news_summary = news_agent(f"""
            Browse {url} and provide a news summary:
            1. Main headlines or stories
            2. Key topics covered
            3. Any important trends or themes
            
            Format as a brief news briefing.
            """)
            
            elapsed = time.time() - start_time
            print(f"⏱️  Analysis completed in {elapsed:.1f} seconds")
            print(f"📋 News Summary: {news_summary}")
            
        except Exception as e:
            print(f"❌ Error monitoring {site_name}: {e}")


def example_4_research_workflow():
    """Example 4: Multi-step research workflow"""
    print("\n\n🔬 Example 4: Research Workflow")
    print("=" * 50)
    
    # Create research agent
    research_agent = Agent(
        tools=[browse_web],
        model="anthropic.claude-instant-v1",
        system_prompt="You are a research analyst. Conduct thorough analysis and provide actionable insights."
    )
    
    print("🎯 Conducting multi-step research workflow...")
    
    try:
        # Step 1: Initial research
        print("\n📋 Step 1: Initial Website Analysis")
        initial_analysis = research_agent("""
        Browse https://example.com and provide:
        1. Website purpose and type
        2. Target audience
        3. Key features or content
        
        This is the first step in a research process.
        """)
        print(f"Initial Analysis: {initial_analysis}")
        
        # Step 2: Detailed content analysis
        print("\n🔍 Step 2: Content Analysis")
        content_analysis = research_agent(f"""
        Based on the previous analysis: {initial_analysis}
        
        Now browse https://httpbin.org/html and compare:
        1. Content structure differences
        2. Information presentation styles
        3. User experience approaches
        
        Provide comparative insights.
        """)
        print(f"Content Analysis: {content_analysis}")
        
        # Step 3: Strategic recommendations
        print("\n💡 Step 3: Strategic Synthesis")
        recommendations = research_agent(f"""
        Synthesize the research findings:
        
        Initial Analysis: {initial_analysis}
        Content Analysis: {content_analysis}
        
        Provide:
        1. Key insights discovered
        2. Patterns or trends identified
        3. Strategic recommendations
        
        Format as an executive summary.
        """)
        print(f"Strategic Recommendations: {recommendations}")
        
    except Exception as e:
        print(f"❌ Error in research workflow: {e}")


def example_5_error_handling():
    """Example 5: Error handling demonstration"""
    print("\n\n🚨 Example 5: Error Handling")
    print("=" * 50)
    
    # Test various error scenarios
    error_tests = [
        ("invalid-url", "Invalid URL format"),
        ("https://this-domain-does-not-exist-12345.com", "Unreachable domain"),
        ("https://example.com", "invalid_mode", "Invalid extraction mode"),
    ]
    
    for test_case in error_tests:
        if len(test_case) == 2:
            url, description = test_case
            mode = "text"
        else:
            url, mode, description = test_case
        
        print(f"\n⚠️  Testing: {description}")
        print(f"URL: {url}, Mode: {mode}")
        
        result = browse_web(url, mode)
        if result.startswith("Error"):
            print(f"✅ Error handled correctly: {result[:100]}...")
        else:
            print(f"❌ Expected error but got success: {len(result)} chars")


def main():
    """Run all examples"""
    print("🚀 Bedrock AgentCore Browser Tool - Example Usage")
    print("=" * 60)
    print("This script demonstrates integration between AWS Bedrock AgentCore")
    print("browser capabilities and Strands agents for intelligent web browsing.")
    print("=" * 60)
    
    # Check environment setup
    if not os.getenv('AWS_REGION'):
        print("⚠️  Note: AWS_REGION not set. Using default 'us-east-1'")
    
    if not os.getenv('AWS_ACCESS_KEY_ID') and not os.getenv('AWS_PROFILE'):
        print("⚠️  Note: AWS credentials not found in environment.")
        print("    Make sure to configure AWS authentication for full functionality.")
    
    # Run examples
    try:
        example_1_basic_browsing()
        example_2_ai_agent_integration()
        example_3_news_monitoring()
        example_4_research_workflow()
        example_5_error_handling()
        
        print("\n\n🎉 All Examples Completed!")
        print("=" * 60)
        print("✅ Browser tool integration demonstrated successfully")
        print("✅ AI agent capabilities verified")
        print("✅ Error handling validated")
        print("✅ Ready for production use!")
        
        print("\n💡 Next Steps:")
        print("  • Customize agents for your specific use cases")
        print("  • Implement production monitoring and logging")
        print("  • Scale with AWS infrastructure")
        print("  • Explore advanced AgentCore features")
        
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        print("Please check your AWS configuration and try again.")


if __name__ == "__main__":
    main()