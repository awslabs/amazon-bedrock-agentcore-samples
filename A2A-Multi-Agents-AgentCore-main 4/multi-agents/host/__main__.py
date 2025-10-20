"""
Main entry point for the A2A Host Orchestrator Agent.

Run with: python -m host
"""

import asyncio
import logging
import uuid

from .host_agent import HostAgent


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)
logger = logging.getLogger(__name__)


async def _main():
    """Main entry point for CLI usage."""
    logger.info("Starting A2A Host Orchestrator Agent")

    # Create and initialize host agent
    host_agent = await HostAgent.create()

    logger.info("Host agent ready. Enter queries or 'quit' to exit.")
    logger.info("Available agents:")
    for agent_name, agent in host_agent.remote_agents.items():
        logger.info(f"  - {agent_name}: {agent.description}")

    print("\n" + "=" * 80)
    print("A2A Host Orchestrator Agent")
    print("=" * 80)
    print("\nAvailable agents:")
    for agent_name, agent in host_agent.remote_agents.items():
        print(f"  - {agent_name}: {agent.description}")
    print("\nEnter your queries below (type 'quit' to exit):")
    print("=" * 80 + "\n")

    session_id = str(uuid.uuid4())

    try:
        while True:
            # Get user input
            try:
                query = input("\nYou: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\nExiting...")
                break

            if not query:
                continue

            if query.lower() in ["quit", "exit", "q"]:
                print("\nGoodbye!")
                break

            # Stream response
            print("\nOrchestrator: ", end="", flush=True)
            async for event in host_agent.stream(query, session_id):
                if event.get("is_task_complete"):
                    content = event.get("content", "")
                    if content:
                        print(content)
                else:
                    updates = event.get("updates", "")
                    if updates:
                        print(f"[{updates}]", end=" ", flush=True)

    finally:
        # Cleanup
        await host_agent.close()
        logger.info("Host agent shutdown complete")


if __name__ == "__main__":
    asyncio.run(_main())
