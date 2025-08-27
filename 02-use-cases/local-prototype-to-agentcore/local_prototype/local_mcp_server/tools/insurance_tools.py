"""
Auto insurance API tools for LocalMCP MCP Server
"""

import requests
import sys
from pathlib import Path

# Add parent directory to path for imports
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

try:
    from ..config import AUTO_INSURANCE_API_URL
except ImportError:
    from config import AUTO_INSURANCE_API_URL


def register_insurance_tools(mcp):
    """Register all auto insurance API tools with the MCP server"""
    
    @mcp.tool()
    def get_customer_info(customer_id: str) -> str:
        """
        Get customer information from the auto insurance system.
        
        Args:
            customer_id: Customer ID to look up
            
        Returns:
            Customer information in formatted text
        """
        try:
            response = requests.post(
                f"{AUTO_INSURANCE_API_URL}/customer_info",
                json={"customer_id": customer_id}
            )
            
            # Log the response details for debugging
            print(f"\n[DEBUG] API Response: {response.status_code} {response.reason}")
            
            # Don't call raise_for_status() yet, handle errors explicitly
            if response.status_code != 200:
                return f"⚠️ INSURANCE API ERROR ⚠️\n\nThe insurance API returned an error:\n\nStatus: HTTP {response.status_code} - {response.reason}\nDetails: {response.text}\n\nPlease check your request parameters and try again."
                
            data = response.json()
            
            if data.get("status") == "success":
                customer = data.get("customer_info", {})
                result = f"Customer Information for ID: {customer_id}\n\n"
                result += f"Name: {customer.get('full_name')}\n"
                result += f"Age: {customer.get('age')}\n"
                result += f"Address: {customer.get('address_formatted')}\n"
                result += f"Email: {customer.get('email')}\n"
                return result
            else:
                return f"Error retrieving customer information: {data.get('error', 'Unknown error')}"
                
        except Exception as e:
            return f"Error connecting to auto insurance API: {str(e)}"

    @mcp.tool()
    def get_vehicle_info(make: str, model: str, year: int) -> str:
        """
        Get vehicle information from the auto insurance system.
        
        Args:
            make: Vehicle manufacturer
            model: Vehicle model
            year: Vehicle year
            
        Returns:
            Vehicle information in formatted text
        """
        try:
            response = requests.post(
                f"{AUTO_INSURANCE_API_URL}/vehicle_info",
                json={"make": make, "model": model, "year": year}
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "success":
                vehicle = data.get("vehicle_info", {})
                result = f"Vehicle Information for {year} {make} {model}\n\n"
                result += f"Display Name: {vehicle.get('display_name')}\n"
                result += f"Category: {vehicle.get('category')}\n"
                result += f"Safety Rating: {vehicle.get('safety_rating')}\n"
                result += f"Original Value: ${vehicle.get('value')}\n"
                result += f"Current Value: ${vehicle.get('current_value')}\n"
                result += f"Age: {vehicle.get('age')} years\n"
                result += f"Is New: {'Yes' if vehicle.get('is_new') else 'No'}\n"
                return result
            else:
                return f"Error retrieving vehicle information: {data.get('error', 'Unknown error')}"
                
        except Exception as e:
            return f"Error connecting to auto insurance API: {str(e)}"

    @mcp.tool()
    def get_insurance_quote(customer_id: str, make: str, model: str, year: int) -> str:
        """
        Get an insurance quote based on customer and vehicle information.
        
        Args:
            customer_id: Customer ID
            make: Vehicle manufacturer
            model: Vehicle model
            year: Vehicle year
            
        Returns:
            Insurance quote information
        """
        try:
            # First get risk factors
            risk_response = requests.post(
                f"{AUTO_INSURANCE_API_URL}/risk_factors",
                json={"customer_id": customer_id, "vehicle_info": {"make": make, "model": model, "year": year}}
            )
            risk_response.raise_for_status()
            risk_data = risk_response.json()
            
            # Then get products
            products_response = requests.post(
                f"{AUTO_INSURANCE_API_URL}/insurance_products",
                json={}
            )
            products_response.raise_for_status()
            products_data = products_response.json()
            
            # Format the response
            result = f"Insurance Quote for Customer {customer_id}, Vehicle: {year} {make} {model}\n\n"
            
            # Add risk factors
            if risk_data.get("status") == "success":
                risk_factors = risk_data.get("risk_factors", {})
                result += "Risk Assessment:\n"
                result += f"- Age Risk: {risk_factors.get('age_risk', 'unknown')}\n"
                result += f"- Driving History Risk: {risk_factors.get('driving_history_risk', 'unknown')}\n"
                result += f"- Credit Risk: {risk_factors.get('credit_risk', 'unknown')}\n"
                result += f"- Vehicle Risk: {risk_factors.get('vehicle_risk', 'unknown')}\n"
                result += f"- Overall Risk: {risk_factors.get('overall_risk', 'unknown')}\n\n"
            
            # Add product information
            if products_data.get("status") == "success":
                products = products_data.get("products", [])
                result += "Available Insurance Products:\n"
                for product in products:
                    result += f"- {product.get('name')}: {product.get('description')}\n"
                    result += f"  Base Price: ${product.get('base_price')}\n"
            
            return result
                
        except Exception as e:
            return f"Error generating insurance quote: {str(e)}"

    @mcp.tool()
    def get_vehicle_safety(make: str, model: str) -> str:
        """
        Get vehicle safety information from the auto insurance system.
        
        Args:
            make: Vehicle manufacturer
            model: Vehicle model
            
        Returns:
            Vehicle safety information
        """
        try:
            response = requests.post(
                f"{AUTO_INSURANCE_API_URL}/vehicle_safety",
                json={"make": make, "model": model}
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "success":
                safety_info = data.get("safety_info", {})
                result = f"Safety Information for {make} {model}\n\n"
                result += f"Safety Rating: {safety_info.get('safety_rating')}/5\n"
                result += f"Assessment: {safety_info.get('safety_assessment')}\n"
                return result
            else:
                return f"Error retrieving safety information: {data.get('error', 'Unknown error')}"
                
        except Exception as e:
            return f"Error connecting to auto insurance API: {str(e)}"
            
    @mcp.tool()
    def get_all_policies() -> str:
        """
        Get all insurance policies from the auto insurance system.
        
        Returns:
            List of all policies in formatted text
        """
        try:
            response = requests.get(f"{AUTO_INSURANCE_API_URL}/policies")
            
            # Handle errors explicitly
            if response.status_code != 200:
                return f"⚠️ INSURANCE API ERROR ⚠️\n\nThe insurance API returned an error:\n\nStatus: HTTP {response.status_code} - {response.reason}\nDetails: {response.text}\n\nPlease check your request parameters and try again."
                
            data = response.json()
            
            if data.get("status") == "success":
                policies = data.get("policies", [])
                result = f"Insurance Policies (Total: {len(policies)})\n\n"
                
                for i, policy in enumerate(policies, 1):
                    result += f"Policy #{i}: ID {policy.get('id')}\n"
                    result += f"  Customer: {policy.get('customer_id')}\n"
                    result += f"  Type: {policy.get('type')}\n"
                    result += f"  Status: {policy.get('status')}\n"
                    result += f"  Premium: ${policy.get('premium')}\n"
                    result += f"  Period: {policy.get('start_date')} to {policy.get('end_date')}\n\n"
                
                return result
            else:
                return f"Error retrieving policies: {data.get('error', 'Unknown error')}"
                
        except Exception as e:
            return f"Error connecting to auto insurance API: {str(e)}"
    
    @mcp.tool()
    def get_policy_by_id(policy_id: str) -> str:
        """
        Get a specific insurance policy by ID.
        
        Args:
            policy_id: Policy ID to look up
            
        Returns:
            Policy information in formatted text
        """
        try:
            response = requests.get(f"{AUTO_INSURANCE_API_URL}/policies/{policy_id}")
            
            # Handle errors explicitly
            if response.status_code != 200:
                return f"⚠️ INSURANCE API ERROR ⚠️\n\nThe insurance API returned an error:\n\nStatus: HTTP {response.status_code} - {response.reason}\nDetails: {response.text}\n\nPlease check your request parameters and try again."
                
            data = response.json()
            
            if data.get("status") == "success":
                policy = data.get("policy", {})
                result = f"Policy Information (ID: {policy.get('id')})\n\n"
                result += f"Customer ID: {policy.get('customer_id')}\n"
                result += f"Type: {policy.get('type')}\n"
                result += f"Status: {policy.get('status')}\n"
                result += f"Premium: ${policy.get('premium')}\n"
                result += f"Period: {policy.get('start_date')} to {policy.get('end_date')}\n\n"
                
                # Add coverage details
                coverage = policy.get('coverage', {})
                result += "Coverage:\n"
                for key, value in coverage.items():
                    result += f"  {key}: {value}\n"
                
                # Add vehicle details
                vehicles = policy.get('vehicles', [])
                if vehicles:
                    result += "\nVehicles:\n"
                    for i, vehicle in enumerate(vehicles, 1):
                        result += f"  Vehicle #{i}: {vehicle.get('year')} {vehicle.get('make')} {vehicle.get('model')}\n"
                
                return result
            else:
                return f"Error retrieving policy: {data.get('error', 'Unknown error')}"
                
        except Exception as e:
            return f"Error connecting to auto insurance API: {str(e)}"
    
    @mcp.tool()
    def get_customer_policies(customer_id: str) -> str:
        """
        Get all policies for a specific customer.
        
        Args:
            customer_id: Customer ID to look up policies for
            
        Returns:
            List of customer's policies in formatted text
        """
        try:
            response = requests.get(f"{AUTO_INSURANCE_API_URL}/customer/{customer_id}/policies")
            
            # Handle errors explicitly
            if response.status_code != 200:
                return f"⚠️ INSURANCE API ERROR ⚠️\n\nThe insurance API returned an error:\n\nStatus: HTTP {response.status_code} - {response.reason}\nDetails: {response.text}\n\nPlease check your request parameters and try again."
                
            data = response.json()
            
            if data.get("status") == "success":
                policies = data.get("policies", [])
                result = f"Policies for Customer {customer_id} (Total: {len(policies)})\n\n"
                
                for i, policy in enumerate(policies, 1):
                    result += f"Policy #{i}: ID {policy.get('id')}\n"
                    result += f"  Type: {policy.get('type')}\n"
                    result += f"  Status: {policy.get('status')}\n"
                    result += f"  Premium: ${policy.get('premium')}\n"
                    result += f"  Period: {policy.get('start_date')} to {policy.get('end_date')}\n\n"
                
                return result
            else:
                return f"Error retrieving customer policies: {data.get('error', 'Unknown error')}"
                
        except Exception as e:
            return f"Error connecting to auto insurance API: {str(e)}"
