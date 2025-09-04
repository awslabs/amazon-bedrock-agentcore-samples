"""
Policy-related endpoints for the Insurance API
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
import logging
# Import using a function pattern to avoid circular imports
def get_services():
    from local_insurance_api.services import data_service, policy_service
    return data_service, policy_service
# Removed unused import
# from local_insurance_api.services.utils import create_success_response

# Define constant for repeated error message
INTERNAL_SERVER_ERROR = "Internal server error"

# Set up logger
logger = logging.getLogger("insurance_api")

# Create router
router = APIRouter()

@router.get("/policies")
async def get_all_policies():
    """Get all policies"""
    try:
        _, policy_service = get_services()
        policies = policy_service.get_all_policies()
        response_data = {
            "status": "success",
            "count": len(policies),
            "policies": policies
        }
        return JSONResponse(content=response_data)
    except Exception as e:
        logger.error(f"Error in get_all_policies endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR)

@router.post("/policies")
async def get_filtered_policies(request: Request):
    """
    Get policies with optional filtering
    
    Optional parameters:
    - policy_id: string - Filter by specific policy ID
    - customer_id: string - Filter by customer ID
    - status: string - Filter by status (active, expired, etc.)
    - include_vehicles: boolean - Include vehicle details in response (default: true)
    """
    try:
        # Parse request data
        data = {}
        try:
            data = await request.json()
        except ValueError:
            # Empty request body or invalid JSON is fine
            pass
        
        # Get services
        data_service, policy_service = get_services()
        
        # Get all policies
        policies = policy_service.get_all_policies()
        
        # Filter by policy ID if provided
        policy_id = data.get("policy_id")
        if policy_id:
            policy = policy_service.get_policy_by_id(policy_id)
            policies = [policy] if policy else []
        
        # Filter by customer ID if provided
        customer_id = data.get("customer_id")
        if customer_id:
            policies = policy_service.get_policies_by_customer_id(customer_id)
        
        # Filter by status if provided
        status = data.get("status")
        if status:
            policies = policy_service.filter_policies_by_status(policies, status)
        
        # Create formatted response
        response_data = policy_service.create_policy_response(policies, data)
        
        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error(f"Error in get_filtered_policies endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR)

@router.get("/policies/{policy_id}")
async def get_policy_by_id(policy_id: str):
    """Get a specific policy by ID"""
    try:
        _, policy_service = get_services()
        policy = policy_service.get_policy_by_id(policy_id)
        if not policy:
            raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")
        
        response_data = {
            "status": "success",
            "policy": policy
        }
        return JSONResponse(content=response_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_policy_by_id endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR)

@router.get("/customer/{customer_id}/policies")
async def get_customer_policies(customer_id: str):
    """Get all policies for a specific customer"""
    try:
        # Get services
        data_service, policy_service = get_services()
        
        # Verify customer exists
        customer = data_service.get_customer_by_id(customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
            
        # Get customer policies
        policies = policy_service.get_policies_by_customer_id(customer_id)
        
        response_data = {
            "status": "success",
            "customer_id": customer_id,
            "count": len(policies),
            "policies": policies
        }
        return JSONResponse(content=response_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_customer_policies endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR)