# Insurance API

A FastAPI-based application that simulates an auto insurance API with realistic sample data.

## Overview

This API provides endpoints to:
- Retrieve customer information
- Access vehicle data and safety ratings
- Calculate insurance premiums based on various factors
- Process risk assessments
- View available insurance products
- Manage and query insurance policies

## Setup

### Prerequisites

- Python 3.10+
- pip

### Installation

1. Create a virtual environment:
   ```bash
   python -m venv venv
   ```

2. Activate the virtual environment:
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Start the API server

```bash
python -m uvicorn server:app --port 8001
```

The API will be available at `http://localhost:8001`.

### API Endpoints

| Endpoint | Method | Description | Sample Request Body |
|----------|--------|-------------|---------------------|
| `/` | GET | Root endpoint with API info | N/A |
| `/health` | GET | Health check | N/A |
| `/customer_info` | POST | Get customer information | `{"customer_id": "cust-001"}` |
| `/customer_credit` | POST | Get customer credit information | `{"customer_id": "cust-001"}` |
| `/vehicle_info` | POST | Get vehicle information | `{"make": "Toyota", "model": "Camry", "year": 2022}` |
| `/risk_factors` | POST | Get risk assessment | `{"customer_id": "cust-001", "vehicle_info": {"make": "Toyota", "model": "Camry", "year": 2022}}` |
| `/insurance_products` | POST | Get available insurance products with filtering, sorting and formatting options | `{}` (see [Insurance Products Options](#insurance-products-options) below) |
| `/vehicle_safety` | POST | Get vehicle safety information | `{"make": "Toyota", "model": "Camry"}` |
| `/policies` | GET | Get all policies | N/A |
| `/policies` | POST | Filter policies by various criteria | `{"status": "active"}` (see [Policy Filtering Options](#policy-filtering-options) below) |
| `/policies/{policy_id}` | GET | Get a specific policy by ID | N/A |
| `/customer/{customer_id}/policies` | GET | Get all policies for a specific customer | N/A |
| `/test` | GET | Test endpoint with sample data | N/A |

## Sample curl Commands

### Root endpoint
```bash
curl http://localhost:8001/
```

### Health check
```bash
curl http://localhost:8001/health
```

### Get customer information
```bash
curl -X POST http://localhost:8001/customer_info \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "cust-001"}'
```

### Get vehicle information
```bash
curl -X POST http://localhost:8001/vehicle_info \
  -H "Content-Type: application/json" \
  -d '{"make": "Toyota", "model": "Camry", "year": 2022}'
```

### Get risk factors
```bash
curl -X POST http://localhost:8001/risk_factors \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "cust-001", "vehicle_info": {"make": "Toyota", "model": "Camry", "year": 2022}}'
```

### Get insurance products
```bash
curl -X POST http://localhost:8001/insurance_products \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Get all policies
```bash
curl http://localhost:8001/policies
```

### Get a specific policy
```bash
curl http://localhost:8001/policies/policy-001
```

### Get a customer's policies
```bash
curl http://localhost:8001/customer/cust-001/policies
```

## Policy Filtering Options

The `/policies` POST endpoint supports various filtering options:

| Parameter | Type | Description | Example |
|-----------|------|-------------|--------|
| `policy_id` | string | Filter by specific policy ID | `{"policy_id": "policy-001"}` |
| `customer_id` | string | Filter by customer ID | `{"customer_id": "cust-002"}` |
| `status` | string | Filter by status (active, expired, etc.) | `{"status": "active"}` |
| `include_vehicles` | boolean | Include vehicle details in response (default: true) | `{"include_vehicles": false}` |

### Example Policy Filter Query

```bash
curl -X POST http://localhost:8001/policies \
  -H "Content-Type: application/json" \
  -d '{
    "status": "active",
    "customer_id": "cust-001"
  }'
```

## Insurance Products Options

The `/insurance_products` endpoint supports various filtering, sorting, and formatting options:

### Filtering Options

| Parameter | Type | Description | Example |
|-----------|------|-------------|--------|
| `product_id` | string or array | Filter by specific product ID(s) | `{"product_id": "premium-auto"}` or `{"product_id": ["basic-auto", "standard-auto"]}` |
| `price_range` | object | Filter by price range | `{"price_range": {"min": 500, "max": 1200}}` |
| `coverage_includes` | array | Filter products that include specific coverages | `{"coverage_includes": ["collision", "comprehensive"]}` |
| `discount_includes` | array | Filter products that offer specific discounts | `{"discount_includes": ["loyalty", "good-student"]}` |

### Sorting Options

| Parameter | Type | Description | Example |
|-----------|------|-------------|--------|
| `sort_by` | string | Sort by "price", "name", or "rating" | `{"sort_by": "price"}` |
| `sort_order` | string | Sort in "asc" or "desc" order | `{"sort_order": "desc"}` |

### Response Formatting Options

| Parameter | Type | Description | Example |
|-----------|------|-------------|--------|
| `include_details` | boolean | Include full product details (default: true) | `{"include_details": false}` |
| `format` | string | Response format - "full" or "summary" (default: "full") | `{"format": "summary"}` |

### Example Complex Query

```bash
curl -X POST http://localhost:8001/insurance_products \
  -H "Content-Type: application/json" \
  -d '{
    "price_range": {"min": 500, "max": 1200},
    "coverage_includes": ["liability"],
    "sort_by": "price",
    "sort_order": "asc",
    "format": "full"
  }'
```

## Data

The API uses sample data located in the `data/` directory:

- `customers.json`: Customer profiles with personal information and driving history
- `vehicles.json`: Vehicle specifications and ratings
- `credit_reports.json`: Customer credit information
- `products.json`: Insurance product details
- `pricing_rules.json`: Rules for calculating premiums
- `policies.json`: Sample insurance policies

## Project Structure
```
insurance_api/
├── app.py                 # FastAPI application initialization
├── server.py              # Entry point for running the application
├── data_loader.py         # Utility to load and manage data from JSON files
├── data/                  # Directory containing sample data files
├── requirements.txt       # Project dependencies
├── routes/                # Endpoint handlers organized by domain
│   ├── __init__.py        # Package initialization
│   ├── customer.py        # Customer-related endpoints
│   ├── general.py         # Root, health, and test endpoints
│   ├── insurance.py       # Insurance-related endpoints
│   ├── policy.py          # Policy-related endpoints
│   └── vehicle.py         # Vehicle-related endpoints
└── services/              # Business logic organized by domain
    ├── __init__.py        # Package initialization
    ├── data_service.py    # Data access functions
    ├── policy_service.py  # Policy management functions
    ├── product_service.py # Insurance product business logic
    └── utils.py           # Utility functions
```

### Key Components

- **app.py**: Creates and configures the FastAPI application, including middleware and router registration.
- **server.py**: Simple entry point that runs the application.
- **routes/**: Contains endpoint handlers organized by domain (customer, vehicle, insurance, policy).
- **services/**: Contains business logic and data access functions.
- **data_loader.py**: Loads and provides access to sample data from JSON files.