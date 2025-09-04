"""
Policy-related services for the Insurance API
"""
from typing import Dict, List, Optional, Any
import logging
from app import data_loader

logger = logging.getLogger("insurance_api")

def get_all_policies() -> List[Dict[str, Any]]:
    """Get all policies"""
    return data_loader.policies.get("policies", [])

def get_policy_by_id(policy_id: str) -> Optional[Dict[str, Any]]:
    """Get policy by ID"""
    policies = data_loader.policies.get("policies", [])
    for policy in policies:
        if policy.get("id") == policy_id:
            return policy
    return None

def get_policies_by_customer_id(customer_id: str) -> List[Dict[str, Any]]:
    """Get policies for a specific customer"""
    policies = data_loader.policies.get("policies", [])
    return [policy for policy in policies if policy.get("customer_id") == customer_id]

def filter_policies_by_status(policies: List[Dict[str, Any]], status: str = None) -> List[Dict[str, Any]]:
    """Filter policies by status (active, expired, etc.)"""
    if not status:
        return policies
    
    return [policy for policy in policies if policy.get("status") == status]

def format_policy_response(policy: Dict[str, Any], include_vehicles: bool = True) -> Dict[str, Any]:
    """Format a single policy for API response"""
    formatted = {
        "id": policy.get("id"),
        "customer_id": policy.get("customer_id"),
        "type": policy.get("type"),
        "start_date": policy.get("start_date"),
        "end_date": policy.get("end_date"),
        "premium": policy.get("premium"),
        "status": policy.get("status"),
        "coverage": policy.get("coverage", {})
    }
    
    if include_vehicles:
        formatted["vehicles"] = policy.get("vehicles", [])
    
    return formatted

def create_policy_response(policies: List[Dict[str, Any]], params: Dict[str, Any]) -> Dict[str, Any]:
    """Create a formatted response for policy data"""
    include_vehicles = params.get("include_vehicles", True)
    
    formatted_policies = [
        format_policy_response(policy, include_vehicles) 
        for policy in policies
    ]
    
    return {
        "status": "success",
        "count": len(formatted_policies),
        "policies": formatted_policies
    }