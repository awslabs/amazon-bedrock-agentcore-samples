"""
Vehicle-related endpoints for the Insurance API
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
import logging
from services import data_service
from services.utils import create_success_response

# Set up logger
logger = logging.getLogger("insurance_api")

# Create router
router = APIRouter()

@router.post("/vehicle_info")
async def get_vehicle_info(request: Request):
    """Get vehicle information"""
    try:
        data = await request.json()
        make = data.get("make")
        model = data.get("model")
        year = data.get("year")
        
        if not all([make, model, year]):
            raise HTTPException(
                status_code=400, 
                detail="Missing required parameters: make, model, year"
            )
        
        # Get vehicle info from real data
        vehicle_info = data_service.get_vehicle_info(make, model, str(year))
        
        if not vehicle_info:
            # Return default vehicle info if not found
            vehicle_info = data_service.get_default_vehicle_info(make, model, year)
        
        # Format response to match Lambda function expectations
        response_data = {
            "status": "success",
            "vehicle_info": vehicle_info
        }
        
        return JSONResponse(content=response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in vehicle_info endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/vehicle_safety")
async def get_vehicle_safety(request: Request):
    """Get vehicle safety information"""
    try:
        data = await request.json()
        make = data.get("make")
        model = data.get("model")
        
        if not all([make, model]):
            raise HTTPException(
                status_code=400,
                detail="Missing required parameters: make, model"
            )
        
        # Mock safety information
        safety_info = {
            "make": make,
            "model": model,
            "overall_rating": 5,
            "frontal_crash": 5,
            "side_crash": 5,
            "rollover": 4,
            "safety_features": [
                "Automatic Emergency Braking",
                "Blind Spot Monitoring", 
                "Lane Departure Warning",
                "Adaptive Cruise Control"
            ]
        }
        
        response_data = {
            "status": "success",
            "safety_info": safety_info
        }
        
        return JSONResponse(content=response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in vehicle_safety endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")