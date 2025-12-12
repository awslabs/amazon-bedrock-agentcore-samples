"""
Cleanup script to delete existing AgentCore Memory resource.
Run this before starting the application if you need to recreate memory with new configuration.

Usage:
    python cleanup_memory.py
"""

import logging

from memory_setup import SlideMemoryManager

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def main():
    """Delete existing slide deck memory resource"""

    print("\n" + "=" * 60)
    print("  AgentCore Memory Cleanup Utility")
    print("=" * 60 + "\n")

    print("⚠️  WARNING: This will delete the existing memory resource")
    print("    and all learned user preferences will be lost.\n")

    try:
        # Create memory manager
        memory_mgr = SlideMemoryManager()

        # Delete existing memory
        deleted = memory_mgr.delete_existing_memory()

        if deleted:
            print("\n" + "=" * 60)
            print("✅ Cleanup completed successfully!")
            print("=" * 60)
            print("\nYou can now run the application to create fresh memory:")
            print("  • Web app: python web/app.py")
            print("  • Main demo: python main.py")
            print()
        else:
            print("\n" + "=" * 60)
            print("ℹ️  No cleanup needed - memory doesn't exist")
            print("=" * 60)
            print("\nYou can proceed with running the application.")
            print()

    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")
        print("\n" + "=" * 60)
        print("❌ Cleanup failed - see error above")
        print("=" * 60)
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
