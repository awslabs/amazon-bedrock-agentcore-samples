"""
Utility functions for the Insurance API
"""
from typing import Dict, List, Optional, Any

def get_product_recommendation(product_id: str) -> str:
    """Return recommendation text based on product ID"""
    if product_id == "basic-auto":
        return "New drivers, budget-conscious individuals, or second vehicles"
    elif product_id == "standard-auto":
        return "Families, daily commuters, and drivers with assets to protect"
    elif product_id == "premium-auto":
        return "Luxury vehicle owners, high-value asset protection, and maximum peace of mind"
    else:
        return "Drivers seeking quality coverage"

def create_success_response(data: Dict[str, Any], status_code: int = 200) -> Dict[str, Any]:
    """Create a standardized success response"""
    return {
        "status": "success",
        **data
    }