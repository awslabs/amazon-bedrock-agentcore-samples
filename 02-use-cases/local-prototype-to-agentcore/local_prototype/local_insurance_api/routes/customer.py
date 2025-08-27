"""
Customer-related endpoints for the Insurance API
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

@router.post("/customer_info")
async def get_customer_info(request: Request):
    """Get customer information"""
    try:
        data = await request.json()
        customer_id = data.get("customer_id")
        
        if not customer_id:
            raise HTTPException(status_code=400, detail="Missing customer_id parameter")
        
        # Get customer from real data
        customer = data_service.get_customer_by_id(customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        # Format response to match Lambda function expectations
        response_data = {
            "status": "success",
            "customer_info": {
                "full_name": f"{customer['first_name']} {customer['last_name']}",
                "age": data_service.calculate_age_from_dob(customer["dob"]),
                "email": customer["email"],
                "phone": customer["phone"],
                "address": customer["address"],
                "address_formatted": customer["address"],
                "license_number": customer["driving_history"]["license_number"],
                "date_of_birth": customer["dob"]
            }
        }
        
        return JSONResponse(content=response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in customer_info endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/customer_credit")
async def get_customer_credit(request: Request):
    """Get customer credit information"""
    try:
        data = await request.json()
        customer_id = data.get("customer_id")
        
        if not customer_id:
            raise HTTPException(status_code=400, detail="Missing customer_id parameter")
        
        # Get credit report from real data
        credit_info = data_service.get_credit_report_by_customer_id(customer_id)
        if not credit_info:
            raise HTTPException(status_code=404, detail="Credit information not found")
        
        # Format response to match Lambda function expectations
        response_data = {
            "status": "success",
            "credit_info": {
                "customer_id": credit_info["customer_id"],
                "credit_score": credit_info["credit_score"],
                "credit_history_length": 10,  # Could be calculated from report_date
                "payment_history": credit_info["payment_history"],
                "debt_to_income_ratio": credit_info["debt_to_income_ratio"]
            }
        }
        
        return JSONResponse(content=response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in customer_credit endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")