"""
Data access service for the Insurance API
"""
from typing import Dict, List, Optional, Any
import logging
from local_insurance_api.data_loader import InsuranceDataLoader

# Use a function to get the data loader to avoid circular imports
def get_data_loader():
    from local_insurance_api.app import data_loader
    return data_loader

logger = logging.getLogger("insurance_api")

def get_customer_by_id(customer_id: str) -> Optional[Dict[str, Any]]:
    """Get customer information by ID"""
    data_loader = get_data_loader()
    return data_loader.get_customer_by_id(customer_id)

def get_credit_report_by_customer_id(customer_id: str) -> Optional[Dict[str, Any]]:
    """Get credit report by customer ID"""
    data_loader = get_data_loader()
    return data_loader.get_credit_report_by_customer_id(customer_id)

def get_vehicle_info(make: str, model: str, year: str or int) -> Optional[Dict[str, Any]]:
    """Get vehicle information by make, model, and year"""
    data_loader = get_data_loader()
    return data_loader.get_vehicle_info(make, model, str(year))

def get_default_vehicle_info(make: str, model: str, year: int) -> Dict[str, Any]:
    """Get default vehicle info when not found in the database"""
    return {
        "make": make,
        "model": model,
        "year": str(year),
        "display_name": f"{year} {make} {model}",
        "category": "standard",
        "safety_rating": "4_star",
        "value": 25000,
        "current_value": 20000,
        "age": 2025 - int(year),
        "is_new": int(year) >= 2024
    }

def get_all_products() -> Dict[str, Any]:
    """Get all insurance product data"""
    data_loader = get_data_loader()
    return data_loader.products

def calculate_age_from_dob(dob: str) -> int:
    """Calculate age from date of birth"""
    data_loader = get_data_loader()
    return data_loader.calculate_age_from_dob(dob)