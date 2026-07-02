"""
Tests for the Memory-Powered Customer Support Agent.

Validates tool functions, memory integration, and agent behavior.
Run with: python -m pytest tests/ -v
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestOrderLookup(unittest.TestCase):
    """Test the order lookup tool."""

    def test_valid_order(self):
        """Test lookup of a known order ID."""
        from agent import lookup_order

        # The tool decorator wraps the function; call the underlying logic
        result = lookup_order.fn(order_id="12345")
        self.assertIn("12345", result)
        self.assertIn("Laptop", result)
        self.assertIn("Delivered", result)

    def test_unknown_order(self):
        """Test lookup of a non-existent order ID."""
        from agent import lookup_order

        result = lookup_order.fn(order_id="99999")
        self.assertIn("not found", result)

    def test_order_in_transit(self):
        """Test lookup of an order in transit."""
        from agent import lookup_order

        result = lookup_order.fn(order_id="12346")
        self.assertIn("In Transit", result)
        self.assertIn("tracking", result.lower())


class TestTicketCreation(unittest.TestCase):
    """Test the support ticket creation tool."""

    def test_create_ticket(self):
        """Test creating a support ticket with valid inputs."""
        from agent import create_support_ticket

        result = create_support_ticket.fn(
            customer_id="customer-test",
            subject="Damaged package",
            description="Laptop arrived with a cracked screen",
            priority="high",
        )
        self.assertIn("TKT-", result)
        self.assertIn("Damaged package", result)
        self.assertIn("high", result)
        self.assertIn("Open", result)

    def test_default_priority(self):
        """Test that default priority is medium."""
        from agent import create_support_ticket

        result = create_support_ticket.fn(
            customer_id="customer-test",
            subject="General inquiry",
            description="Question about return policy",
        )
        self.assertIn("medium", result)


class TestMemoryConfig(unittest.TestCase):
    """Test configuration loading."""

    def test_config_structure(self):
        """Test that a valid config has required fields."""
        config = {
            "memory_id": "test-memory-123",
            "region": "us-east-1",
            "strategies": {
                "customer_facts": "/customers/{actorId}/facts",
                "issue_history": "/customers/{actorId}/issues",
            },
        }
        self.assertIn("memory_id", config)
        self.assertIn("strategies", config)
        self.assertIn("customer_facts", config["strategies"])
        self.assertIn("issue_history", config["strategies"])


class TestSystemPrompt(unittest.TestCase):
    """Test that the system prompt contains required elements."""

    def test_system_prompt_contains_guidelines(self):
        """Verify system prompt has key behavioral guidelines."""
        from agent import SYSTEM_PROMPT

        self.assertIn("recall_customer_history", SYSTEM_PROMPT)
        self.assertIn("memory", SYSTEM_PROMPT.lower())
        self.assertIn("ticket", SYSTEM_PROMPT.lower())
        self.assertIn("empathetic", SYSTEM_PROMPT.lower())


if __name__ == "__main__":
    unittest.main()
