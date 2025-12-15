#!/usr/bin/env python3
"""
Main demo script for Slide Deck Agent - Memory Importance Demonstration

This script demonstrates the importance of Agent Memory by comparing:
1. Basic Agent: Creates slides without memory (default settings every time)
2. Memory Agent: Learns user preferences and creates personalized presentations

Usage:
    python main.py [--mode MODE] [--user-id USER_ID]

Modes:
    web     - Start web interface (default)
    cli     - Command line interactive demo
    demo    - Automated demo with sample interactions
    compare - Direct comparison with sample requests
"""

from web.app import create_app
from memory_setup import setup_slide_deck_memory
from agents.memory_agent import MemoryEnabledSlideDeckAgent
from agents.basic_agent import BasicSlideDeckAgent
from config import ensure_directories, DEFAULT_USER_ID, get_session_id
import os
import sys
import argparse
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def print_banner():
    """Print the demo banner"""
    print("=" * 80)
    print("🧠 SLIDE DECK AGENT DEMO - The Importance of Agent Memory")
    print("=" * 80)
    print()
    print(
        "This demo showcases how Agent Memory transforms AI interactions by comparing:"
    )
    print("📊 Basic Agent:       Creates slides without learning or memory")
    print("🧠 Memory Agent:      Learns preferences and personalizes presentations")
    print()


def setup_demo_environment() -> tuple:
    """Setup the demo environment with both agents"""
    print("🚀 Setting up demo environment...")

    # Ensure directories exist
    ensure_directories()

    # Initialize basic agent
    print("   ⚙️  Initializing basic agent (no memory)...")
    basic_agent = BasicSlideDeckAgent()

    # Initialize memory system and memory agent
    print("   🧠 Setting up memory system...")
    memory, session_manager, memory_mgr = setup_slide_deck_memory()

    print("   👤 Creating user session...")
    user_session = session_manager.create_memory_session(
        actor_id=DEFAULT_USER_ID, session_id=get_session_id()
    )

    print("   🤖 Initializing memory-enabled agent...")
    memory_agent = MemoryEnabledSlideDeckAgent(user_session)

    print("✅ Demo environment ready!")
    print()

    return basic_agent, memory_agent, user_session


def run_cli_demo():
    """Run interactive CLI demo"""
    print_banner()
    basic_agent, memory_agent, user_session = setup_demo_environment()

    print("🎯 INTERACTIVE DEMO MODE")
    print("Type 'exit' to quit, 'help' for commands")
    print()

    while True:
        try:
            print("Available commands:")
            print("  1. basic    - Test basic agent")
            print("  2. memory   - Test memory agent")
            print("  3. compare  - Compare both agents")
            print("  4. prefs    - View learned preferences")
            print("  5. help     - Show this help")
            print("  6. exit     - Quit demo")
            print()

            choice = input("Choose option (1-6): ").strip()

            if choice in ["exit", "6"]:
                print("👋 Thank you for trying the Agent Memory demo!")
                break

            elif choice in ["help", "5"]:
                continue

            elif choice in ["1", "basic"]:
                run_basic_agent_test(basic_agent)

            elif choice in ["2", "memory"]:
                run_memory_agent_test(memory_agent)

            elif choice in ["3", "compare"]:
                run_agent_comparison(basic_agent, memory_agent)

            elif choice in ["4", "prefs"]:
                show_learned_preferences(memory_agent)

            else:
                print("❌ Invalid choice. Please select 1-6.")

            input("\\nPress Enter to continue...")
            print("\\n" + "=" * 50 + "\\n")

        except KeyboardInterrupt:
            print("\\n\\n👋 Demo interrupted. Goodbye!")
            break
        except Exception as e:
            logger.error(f"Demo error: {e}")
            print(f"❌ Error: {e}")


def run_basic_agent_test(basic_agent):
    """Test the basic agent"""
    print("\\n📊 BASIC AGENT TEST (No Memory)")
    print("-" * 40)

    request = input("Enter presentation request (or press Enter for sample): ").strip()

    if not request:
        request = """Create a presentation about "Introduction to Cloud Computing" for IT professionals.
        Include overview, benefits, service models, deployment types, and security considerations.
        Use professional blue theme with modern fonts."""

        print(f"Using sample request: {request[:100]}...")

    print("\\n⏳ Creating presentation with basic agent...")
    try:
        result = basic_agent.create_presentation(request)
        print("\\n✅ Basic Agent Result:")
        print("-" * 30)
        print(result)
    except Exception as e:
        print(f"❌ Error: {e}")


def run_memory_agent_test(memory_agent):
    """Test the memory-enabled agent"""
    print("\\n🧠 MEMORY AGENT TEST (With Learning)")
    print("-" * 40)

    request = input("Enter presentation request (or press Enter for sample): ").strip()

    if not request:
        request = """Create a presentation about "Sustainable Energy Solutions" for environmental conference.
        Include current challenges, renewable technologies, implementation strategies, and future outlook.
        I prefer green color schemes and clean, professional designs for environmental topics."""

        print(f"Using sample request: {request[:100]}...")

    print("\\n⏳ Creating presentation with memory-enabled agent...")
    try:
        result = memory_agent.create_presentation(request)
        print("\\n✅ Memory Agent Result:")
        print("-" * 30)
        print(result)
    except Exception as e:
        print(f"❌ Error: {e}")


def run_agent_comparison(basic_agent, memory_agent):
    """Compare both agents with the same request"""
    print("\\n⚖️  AGENT COMPARISON")
    print("-" * 40)

    request = input(
        "Enter request for both agents (or press Enter for sample): "
    ).strip()

    if not request:
        request = """Create a presentation about "Digital Marketing Trends 2024" for marketing professionals.
        Include current trends, social media evolution, AI in marketing, data analytics, and future predictions.
        Target audience: Marketing managers and digital strategists."""

        print(f"Using sample request: {request[:100]}...")

    print("\\n🔄 Testing both agents with the same request...")

    # Test basic agent
    print("\\n1️⃣ Basic Agent (No Memory):")
    print("-" * 25)
    try:
        basic_result = basic_agent.create_presentation(request)
        print("✅", basic_result[:200], "..." if len(basic_result) > 200 else "")
    except Exception as e:
        print(f"❌ Basic agent error: {e}")

    # Test memory agent
    print("\\n2️⃣ Memory Agent (With Learning):")
    print("-" * 30)
    try:
        memory_result = memory_agent.create_presentation(request)
        print("✅", memory_result[:200], "..." if len(memory_result) > 200 else "")
    except Exception as e:
        print(f"❌ Memory agent error: {e}")

    print("\\n🔍 KEY DIFFERENCES:")
    print("• Basic Agent: Uses default settings, no learning")
    print("• Memory Agent: Applies learned preferences, context-aware")


def show_learned_preferences(memory_agent):
    """Show current learned preferences"""
    print("\\n🧠 LEARNED PREFERENCES")
    print("-" * 30)

    try:
        preferences = memory_agent.get_user_preferences_tool()
        print(preferences)
    except Exception as e:
        print(f"❌ Error retrieving preferences: {e}")


def run_automated_demo():
    """Run automated demo with predefined scenarios"""
    print_banner()
    basic_agent, memory_agent, user_session = setup_demo_environment()

    print("🤖 AUTOMATED DEMO - Agent Memory Learning Journey")
    print()

    scenarios = [
        {
            "name": "Tech Presentation - Learning Blue Preference",
            "request": """Create a presentation about "Cybersecurity Fundamentals" for IT training.
            Include threat landscape, security frameworks, best practices, and incident response.
            I really prefer blue color schemes for technical content as they convey trust and professionalism.""",
        },
        {
            "name": "Business Presentation - Learning Professional Style",
            "request": """Create a presentation about "Digital Transformation Strategy" for executives.
            Include market drivers, technology trends, implementation roadmap, and ROI analysis.
            I like professional, corporate styling with clean fonts for business presentations.""",
        },
        {
            "name": "Adaptive Presentation - Testing Memory",
            "request": """Create a presentation about "AI in Finance" for financial services conference.
            Include applications, risk management, regulatory considerations, and future outlook.
            This is a technical topic for finance professionals.""",
        },
    ]

    for i, scenario in enumerate(scenarios, 1):
        print(f"\\n{i}. {scenario['name']}")
        print("=" * 60)

        # Test with basic agent
        print("\\n📊 Basic Agent Response:")
        try:
            basic_agent.create_presentation(scenario["request"])
            print("✅ Created presentation with default styling")
        except Exception as e:
            print(f"❌ Error: {e}")

        # Test with memory agent
        print("\\n🧠 Memory Agent Response:")
        try:
            memory_agent.create_presentation(scenario["request"])
            print("✅ Created presentation with learned preferences")
        except Exception as e:
            print(f"❌ Error: {e}")

        if i < len(scenarios):
            input("\\nPress Enter for next scenario...")

    print("\\n" + "=" * 60)
    print("🎉 DEMO COMPLETE!")
    print("\\nKey Takeaways:")
    print("• Basic agent: Consistent but generic output")
    print("• Memory agent: Learns and adapts to user preferences")
    print("• Each interaction improves future presentations")


def run_web_interface():
    """Start the web interface"""
    print_banner()
    print("🌐 Starting Web Interface...")
    print()
    print("The web interface provides:")
    print("• Interactive comparison between basic and memory agents")
    print("• Real-time preference learning visualization")
    print("• HTML and PowerPoint file generation")
    print("• File download and preview capabilities")
    print()

    try:
        app = create_app()
        print("✅ Web interface ready!")
        print("🌐 Open your browser to: http://localhost:5000")
        print("📱 Press Ctrl+C to stop the server")
        print()

        app.run(host="127.0.0.1", port=5000, debug=False)

    except Exception as e:
        logger.error(f"Web interface error: {e}")
        print(f"❌ Failed to start web interface: {e}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Slide Deck Agent Demo - Memory Importance Demonstration"
    )
    parser.add_argument(
        "--mode",
        choices=["web", "cli", "demo", "compare"],
        default="web",
        help="Demo mode (default: web)",
    )
    parser.add_argument(
        "--user-id", default=DEFAULT_USER_ID, help="User ID for memory session"
    )

    args = parser.parse_args()

    # Update global user ID if provided
    if args.user_id != DEFAULT_USER_ID:
        import config

        config.DEFAULT_USER_ID = args.user_id

    try:
        if args.mode == "web":
            run_web_interface()
        elif args.mode == "cli":
            run_cli_demo()
        elif args.mode == "demo":
            run_automated_demo()
        elif args.mode == "compare":
            print_banner()
            basic_agent, memory_agent, _ = setup_demo_environment()
            run_agent_comparison(basic_agent, memory_agent)

    except KeyboardInterrupt:
        print("\\n\\n👋 Demo interrupted. Goodbye!")
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        print(f"\\n❌ Demo failed: {e}")
        print("\\nPlease check:")
        print("• AWS credentials are configured")
        print("• Required dependencies are installed")
        print("• Network connectivity to AWS services")


if __name__ == "__main__":
    main()
