"""
FastAPI application initialization for the Insurance API
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from data_loader import InsuranceDataLoader

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("insurance_api")

# Initialize data loader
data_loader = InsuranceDataLoader()

# Log data loading status
logger.info("Data loader initialized")
logger.info(f"Customers loaded: {len(data_loader.customers)}")
logger.info(f"Vehicles loaded: {len(data_loader.vehicles)}")
logger.info(f"Credit reports loaded: {len(data_loader.credit_reports)}")
if data_loader.customers:
    logger.info(f"First customer: {data_loader.customers[0].get('id', 'no-id')}")

def create_app() -> FastAPI:
    """Create and configure the FastAPI application"""
    
    # Initialize FastAPI app
    app = FastAPI(title="Auto Insurance API")
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Import and include routers
    from routes.general import router as general_router
    from routes.customer import router as customer_router
    from routes.vehicle import router as vehicle_router
    from routes.insurance import router as insurance_router
    from routes.policy import router as policy_router
    
    app.include_router(general_router)
    app.include_router(customer_router)
    app.include_router(vehicle_router)
    app.include_router(insurance_router)
    app.include_router(policy_router)
    
    return app

# Create the FastAPI app instance
app = create_app()