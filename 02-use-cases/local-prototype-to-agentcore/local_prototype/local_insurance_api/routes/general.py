"""
General endpoints for the Insurance API
"""
from fastapi import APIRouter, HTTPException
import logging
from app import data_loader
from services.utils import create_success_response

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