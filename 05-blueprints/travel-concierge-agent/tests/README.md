# Concierge Agent Tests

Test suite for the Concierge Agent with MCP tools (Cart, Travel, Itinerary).

## Prerequisites

- AWS credentials configured
- Agent infrastructure deployed (`npm run deploy`)
- `amplify_outputs.json` exists in project root

## Setup

```bash
cd tests
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Quick Start

```bash

# Confirm all tools are available
python tests/test_gateway_basic.py

# Confirm all tools return expected responses
python tests/test_gateway_tools.py

# Validate tool sequence for specific scenarios
python tests/test_agent_trajectories.py --session session_001

# Test Cognito/runtime and see streaming events
python tests/test_agent_remote.py -q "Hello"
```

---

## Test Files

| Test | Purpose |
|------|---------|
| `test_gateway_basic.py` | Confirms all tools are available via gateway and MCPClient filtering works |
| `test_gateway_tools.py` | Confirms all tools return expected responses (CSV-based, 33 tests) |
| `test_agent_trajectories.py` | Validates tool sequence and agent behavior for specific scenarios (26 sessions) |
| `test_agent_remote.py` | Tests Cognito auth, runtime connectivity, and streams all events for debugging |

## CSV Datasets

| File | Description |
|------|-------------|
| `gateway_tool_test_dataset.csv` | 33 gateway tool tests (write/verify pattern) |
| `agent_test_dataset.csv` | 26 agent trajectory tests |

---

## Usage Examples

### Gateway Basic Tests
```bash
python tests/test_gateway_basic.py
```

### Gateway Tool Tests
```bash
python tests/test_gateway_tools.py                    # Run all
python tests/test_gateway_tools.py --category cart    # By category
python tests/test_gateway_tools.py --test GT001       # Specific test
python tests/test_gateway_tools.py --verbose          # Verbose output
```

### Agent Trajectory Tests
```bash
python tests/test_agent_trajectories.py                        # Run all
python tests/test_agent_trajectories.py --session session_001  # Specific session
python tests/test_agent_trajectories.py --verbose              # Verbose output
```

### Agent Remote Tests
```bash
python tests/test_agent_remote.py                              # Interactive chat
python tests/test_agent_remote.py -q "Find flights to Paris"   # Single query
```

---

## Tools Tested

### Cart Tools (12)
`get_cart`, `add_to_cart`, `add_hotel_to_cart`, `add_flight_to_cart`, `remove_from_cart`, `clear_cart`, `request_purchase_confirmation`, `confirm_purchase`, `onboard_card`, `get_visa_iframe_config`, `check_user_has_payment_card`, `send_purchase_confirmation_email`

### Travel Tools (4)
`travel_search`, `travel_flight_search`, `travel_hotel_search`, `travel_places_search`

### Itinerary Tools (5)
`itinerary_get`, `itinerary_save`, `itinerary_remove`, `itinerary_clear`, `itinerary_update_date`
