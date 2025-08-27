"""
General endpoints for the Insurance API
"""
from fastapi import APIRouter, HTTPException
import logging
# Import data_loader from a function to avoid circular imports
def get_data_loader():
    from local_insurance_api.app import data_loader
    return data_loader
from local_insurance_api.services.utils import create_success_response

# Set up logger
logger = logging.getLogger("insurance_api")

# Create router
router = APIRouter()

@router.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Auto Insurance API",
        "version": "1.0.0",
        "status": "healthy",
        "endpoints": [
            "/customer_info",
            "/customer_credit", 
            "/vehicle_info",
            "/risk_factors",
            "/insurance_products",
            "/vehicle_safety",
            "/health"
        ]
    }

@router.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": "2025-06-19T18:00:00Z"}

@router.get("/test")
async def test():
    """Test endpoint with sample data"""
    # Get data_loader inside function to avoid circular imports
    data_loader = get_data_loader()
    customers = data_loader.customers
    vehicles = data_loader.vehicles
    
    return {
        "message": "Test successful - using real data",
        "sample_data": {
            "customers": [f"{c['first_name']} {c['last_name']} ({c['id']})" for c in customers[:3]],
            "vehicles": [f"{v['make']} {v['model']}" for v in vehicles[:3]],
            "data_source": "auto-insurance-prototype/data folder"
        }
    }