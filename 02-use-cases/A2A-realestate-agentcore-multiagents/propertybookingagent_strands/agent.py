"""
Property Booking Agent - Strands Implementation

This agent provides property booking and reservation management capabilities.
It can be run locally or deployed to Bedrock AgentCore.
"""

import os
import sys
import time
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from strands import Agent, tool
from strands.multiagent.a2a import A2AServer
import uuid

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from common.utils.logging_config import (
    setup_logging,
    generate_request_id,
    log_tool_execution,
    log_error
)

# Configure structured logging
logger = setup_logging("property_booking_agent", level=os.getenv("LOG_LEVEL", "INFO"), use_json=True)

# Mock booking database
MOCK_BOOKINGS = {}

# Mock available properties for booking
AVAILABLE_PROPERTIES = {
    "PROP001": {"title": "Modern Downtown Apartment", "price": 3500, "available": True},
    "PROP002": {"title": "Cozy Suburban House", "price": 2800, "available": True},
    "PROP003": {"title": "Luxury Penthouse", "price": 8500, "available": True},
    "PROP004": {"title": "Charming Studio Downtown", "price": 1800, "available": True},
    "PROP005": {"title": "Beachfront Villa", "price": 12000, "available": True},
    "PROP006": {"title": "Mountain Cabin Retreat", "price": 2200, "available": False},
    "PROP007": {"title": "Urban Loft", "price": 3200, "available": True},
    "PROP008": {"title": "Family Home with Yard", "price": 3000, "available": True}
}


@tool
def create_booking(
    property_id: str,
    customer_name: str,
    customer_email: str,
    customer_phone: str,
    move_in_date: str,
    lease_duration_months: int = 12
) -> str:
    """
    Create a booking reservation for a property.
    
    Args:
        property_id: The property ID to book (e.g., 'PROP001')
        customer_name: Full name of the customer
        customer_email: Email address of the customer
        customer_phone: Phone number of the customer
        move_in_date: Desired move-in date in YYYY-MM-DD format
        lease_duration_months: Length of lease in months (default: 12)
    
    Returns:
        Booking confirmation details
    """
    request_id = generate_request_id()
    start_time = time.time()
    
    try:
        logger.info(
            f"Creating property booking",
            extra={
                "event": "tool_execution_start",
                "tool_name": "create_booking",
                "agent_name": "property_booking_agent",
                "request_id": request_id,
                "property_id": property_id,
                "customer_email": customer_email,
                "lease_duration_months": lease_duration_months
            }
        )
        
        # Validate property exists and is available
        if property_id.upper() not in AVAILABLE_PROPERTIES:
            duration_ms = (time.time() - start_time) * 1000
            log_tool_execution(
                logger,
                tool_name="create_booking",
                agent_name="property_booking_agent",
                request_id=request_id,
                duration_ms=duration_ms,
                success=False,
                error="Property not found"
            )
            return f"Error: Property '{property_id}' not found. Please verify the property ID."
        
        property_info = AVAILABLE_PROPERTIES[property_id.upper()]
        
        if not property_info["available"]:
            duration_ms = (time.time() - start_time) * 1000
            log_tool_execution(
                logger,
                tool_name="create_booking",
                agent_name="property_booking_agent",
                request_id=request_id,
                duration_ms=duration_ms,
                success=False,
                error="Property not available"
            )
            return f"Error: Property '{property_id}' is not currently available for booking."
        
        # Validate move-in date format
        try:
            move_in_dt = datetime.strptime(move_in_date, "%Y-%m-%d")
            if move_in_dt < datetime.now():
                duration_ms = (time.time() - start_time) * 1000
                log_tool_execution(
                    logger,
                    tool_name="create_booking",
                    agent_name="property_booking_agent",
                    request_id=request_id,
                    duration_ms=duration_ms,
                    success=False,
                    error="Invalid move-in date"
                )
                return "Error: Move-in date cannot be in the past. Please provide a future date."
        except ValueError:
            duration_ms = (time.time() - start_time) * 1000
            log_tool_execution(
                logger,
                tool_name="create_booking",
                agent_name="property_booking_agent",
                request_id=request_id,
                duration_ms=duration_ms,
                success=False,
                error="Invalid date format"
            )
            return "Error: Invalid date format. Please use YYYY-MM-DD format (e.g., 2024-03-15)."
        
        # Calculate lease end date
        lease_end_dt = move_in_dt + timedelta(days=lease_duration_months * 30)
        
        # Generate booking ID
        booking_id = f"BOOK-{uuid.uuid4().hex[:8].upper()}"
        
        # Calculate total cost
        monthly_rent = property_info["price"]
        total_cost = monthly_rent * lease_duration_months
        deposit = monthly_rent * 2  # Typically 2 months deposit
        
        # Create booking record
        booking_data = {
            "booking_id": booking_id,
            "property_id": property_id.upper(),
            "property_title": property_info["title"],
            "customer_name": customer_name,
            "customer_email": customer_email,
            "customer_phone": customer_phone,
            "move_in_date": move_in_date,
            "lease_end_date": lease_end_dt.strftime("%Y-%m-%d"),
            "lease_duration_months": lease_duration_months,
            "monthly_rent": monthly_rent,
            "total_cost": total_cost,
            "security_deposit": deposit,
            "status": "confirmed",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Store booking
        MOCK_BOOKINGS[booking_id] = booking_data
        
        duration_ms = (time.time() - start_time) * 1000
        log_tool_execution(
            logger,
            tool_name="create_booking",
            agent_name="property_booking_agent",
            request_id=request_id,
            duration_ms=duration_ms,
            success=True,
            booking_id=booking_id
        )
        
        # Format confirmation
        confirmation = (
            f"✓ BOOKING CONFIRMED\n"
            f"{'=' * 60}\n\n"
            f"Booking ID: {booking_id}\n"
            f"Status: CONFIRMED\n\n"
            f"PROPERTY DETAILS:\n"
            f"  Property: {property_info['title']}\n"
            f"  Property ID: {property_id.upper()}\n\n"
            f"CUSTOMER INFORMATION:\n"
            f"  Name: {customer_name}\n"
            f"  Email: {customer_email}\n"
            f"  Phone: {customer_phone}\n\n"
            f"LEASE INFORMATION:\n"
            f"  Move-in Date: {move_in_date}\n"
            f"  Lease End Date: {lease_end_dt.strftime('%Y-%m-%d')}\n"
            f"  Lease Duration: {lease_duration_months} months\n\n"
            f"FINANCIAL DETAILS:\n"
            f"  Monthly Rent: ${monthly_rent:,.2f}\n"
            f"  Security Deposit: ${deposit:,.2f}\n"
            f"  Total Lease Cost: ${total_cost:,.2f}\n\n"
            f"Next Steps:\n"
            f"  1. You will receive a confirmation email at {customer_email}\n"
            f"  2. Security deposit of ${deposit:,.2f} is due within 48 hours\n"
            f"  3. Lease agreement will be sent for signing\n"
            f"  4. Property inspection scheduled before move-in\n\n"
            f"Reference your Booking ID ({booking_id}) for all future communications.\n"
        )
        
        return confirmation
    
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(
            logger,
            error=e,
            context="tool_execution",
            agent_name="property_booking_agent",
            request_id=request_id,
            tool_name="create_booking",
            duration_ms=duration_ms
        )
        return f"Error creating booking: {str(e)}"


@tool
def check_booking_status(booking_id: str) -> str:
    """
    Check the status of an existing booking.
    
    Args:
        booking_id: The booking ID to check (e.g., 'BOOK-ABC12345')
    
    Returns:
        Booking status and details
    """
    request_id = generate_request_id()
    start_time = time.time()
    
    try:
        logger.info(
            f"Checking booking status",
            extra={
                "event": "tool_execution_start",
                "tool_name": "check_booking_status",
                "agent_name": "property_booking_agent",
                "request_id": request_id,
                "booking_id": booking_id
            }
        )
        
        # Find booking
        if booking_id.upper() not in MOCK_BOOKINGS:
            duration_ms = (time.time() - start_time) * 1000
            log_tool_execution(
                logger,
                tool_name="check_booking_status",
                agent_name="property_booking_agent",
                request_id=request_id,
                duration_ms=duration_ms,
                success=False,
                error="Booking not found"
            )
            return f"Error: Booking with ID '{booking_id}' not found. Please check the booking ID and try again."
        
        booking = MOCK_BOOKINGS[booking_id.upper()]
        
        duration_ms = (time.time() - start_time) * 1000
        log_tool_execution(
            logger,
            tool_name="check_booking_status",
            agent_name="property_booking_agent",
            request_id=request_id,
            duration_ms=duration_ms,
            success=True
        )
        
        # Format booking details
        status_info = (
            f"BOOKING STATUS REPORT\n"
            f"{'=' * 60}\n\n"
            f"Booking ID: {booking['booking_id']}\n"
            f"Status: {booking['status'].upper()}\n"
            f"Created: {booking['created_at']}\n\n"
            f"PROPERTY:\n"
            f"  {booking['property_title']} (ID: {booking['property_id']})\n\n"
            f"CUSTOMER:\n"
            f"  Name: {booking['customer_name']}\n"
            f"  Email: {booking['customer_email']}\n"
            f"  Phone: {booking['customer_phone']}\n\n"
            f"LEASE DATES:\n"
            f"  Move-in: {booking['move_in_date']}\n"
            f"  Lease End: {booking['lease_end_date']}\n"
            f"  Duration: {booking['lease_duration_months']} months\n\n"
            f"FINANCIALS:\n"
            f"  Monthly Rent: ${booking['monthly_rent']:,.2f}\n"
            f"  Security Deposit: ${booking['security_deposit']:,.2f}\n"
            f"  Total Cost: ${booking['total_cost']:,.2f}\n"
        )
        
        return status_info
    
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(
            logger,
            error=e,
            context="tool_execution",
            agent_name="property_booking_agent",
            request_id=request_id,
            tool_name="check_booking_status",
            duration_ms=duration_ms
        )
        return f"Error checking booking status: {str(e)}"


@tool
def cancel_booking(booking_id: str, reason: Optional[str] = None) -> str:
    """
    Cancel an existing booking.
    
    Args:
        booking_id: The booking ID to cancel (e.g., 'BOOK-ABC12345')
        reason: Optional reason for cancellation
    
    Returns:
        Cancellation confirmation
    """
    request_id = generate_request_id()
    start_time = time.time()
    
    try:
        logger.info(
            f"Cancelling booking",
            extra={
                "event": "tool_execution_start",
                "tool_name": "cancel_booking",
                "agent_name": "property_booking_agent",
                "request_id": request_id,
                "booking_id": booking_id
            }
        )
        
        # Find booking
        if booking_id.upper() not in MOCK_BOOKINGS:
            duration_ms = (time.time() - start_time) * 1000
            log_tool_execution(
                logger,
                tool_name="cancel_booking",
                agent_name="property_booking_agent",
                request_id=request_id,
                duration_ms=duration_ms,
                success=False,
                error="Booking not found"
            )
            return f"Error: Booking with ID '{booking_id}' not found. Please check the booking ID."
        
        booking = MOCK_BOOKINGS[booking_id.upper()]
        
        if booking["status"] == "cancelled":
            duration_ms = (time.time() - start_time) * 1000
            log_tool_execution(
                logger,
                tool_name="cancel_booking",
                agent_name="property_booking_agent",
                request_id=request_id,
                duration_ms=duration_ms,
                success=False,
                error="Already cancelled"
            )
            return f"Error: Booking '{booking_id}' is already cancelled."
        
        # Update booking status
        booking["status"] = "cancelled"
        booking["cancelled_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if reason:
            booking["cancellation_reason"] = reason
        
        duration_ms = (time.time() - start_time) * 1000
        log_tool_execution(
            logger,
            tool_name="cancel_booking",
            agent_name="property_booking_agent",
            request_id=request_id,
            duration_ms=duration_ms,
            success=True
        )
        
        # Format cancellation confirmation
        confirmation = (
            f"✓ BOOKING CANCELLED\n"
            f"{'=' * 60}\n\n"
            f"Booking ID: {booking['booking_id']}\n"
            f"Status: CANCELLED\n"
            f"Cancelled At: {booking['cancelled_at']}\n\n"
            f"PROPERTY:\n"
            f"  {booking['property_title']} (ID: {booking['property_id']})\n\n"
            f"CUSTOMER:\n"
            f"  Name: {booking['customer_name']}\n"
            f"  Email: {booking['customer_email']}\n\n"
        )
        
        if reason:
            confirmation += f"CANCELLATION REASON:\n  {reason}\n\n"
        
        confirmation += (
            f"REFUND INFORMATION:\n"
            f"  A refund confirmation will be sent to {booking['customer_email']}\n"
            f"  Security deposit will be refunded within 7-10 business days\n"
            f"  Please allow 5-7 business days for processing\n"
        )
        
        return confirmation
    
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(
            logger,
            error=e,
            context="tool_execution",
            agent_name="property_booking_agent",
            request_id=request_id,
            tool_name="cancel_booking",
            duration_ms=duration_ms
        )
        return f"Error cancelling booking: {str(e)}"


@tool
def list_customer_bookings(customer_email: str) -> str:
    """
    List all bookings for a specific customer.
    
    Args:
        customer_email: Email address of the customer
    
    Returns:
        List of customer's bookings
    """
    request_id = generate_request_id()
    start_time = time.time()
    
    try:
        logger.info(
            f"Listing customer bookings",
            extra={
                "event": "tool_execution_start",
                "tool_name": "list_customer_bookings",
                "agent_name": "property_booking_agent",
                "request_id": request_id,
                "customer_email": customer_email
            }
        )
        
        # Find bookings for customer
        customer_bookings = []
        for booking_id, booking in MOCK_BOOKINGS.items():
            if booking["customer_email"].lower() == customer_email.lower():
                customer_bookings.append(booking)
        
        duration_ms = (time.time() - start_time) * 1000
        
        if not customer_bookings:
            log_tool_execution(
                logger,
                tool_name="list_customer_bookings",
                agent_name="property_booking_agent",
                request_id=request_id,
                duration_ms=duration_ms,
                success=True
            )
            return f"No bookings found for customer email: {customer_email}"
        
        # Format results
        results = [f"Found {len(customer_bookings)} booking(s) for {customer_email}:\n"]
        
        for i, booking in enumerate(customer_bookings, 1):
            result_text = (
                f"\n{i}. Booking ID: {booking['booking_id']}\n"
                f"   Property: {booking['property_title']}\n"
                f"   Status: {booking['status'].upper()}\n"
                f"   Move-in: {booking['move_in_date']}\n"
                f"   Monthly Rent: ${booking['monthly_rent']:,.2f}\n"
                f"   Created: {booking['created_at']}\n"
            )
            results.append(result_text)
        
        log_tool_execution(
            logger,
            tool_name="list_customer_bookings",
            agent_name="property_booking_agent",
            request_id=request_id,
            duration_ms=duration_ms,
            success=True
        )
        
        return "".join(results)
    
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(
            logger,
            error=e,
            context="tool_execution",
            agent_name="property_booking_agent",
            request_id=request_id,
            tool_name="list_customer_bookings",
            duration_ms=duration_ms
        )
        return f"Error listing customer bookings: {str(e)}"


def create_property_booking_agent() -> Agent:
    """
    Create and configure the Property Booking Agent.
    
    Returns:
        Configured Strands Agent instance
    """
    model_id = os.getenv("MODEL_ID", "us.anthropic.claude-3-5-haiku-20241022-v1:0")
    agent_name = os.getenv("AGENT_NAME", "Property Booking Agent")
    agent_description = os.getenv(
        "AGENT_DESCRIPTION",
        "Manages property bookings, reservations, and lease agreements for real estate properties"
    )
    
    logger.info(f"Creating agent: {agent_name}")
    logger.info(f"Using model: {model_id}")
    
    agent = Agent(
        name=agent_name,
        description=agent_description,
        tools=[create_booking, check_booking_status, cancel_booking, list_customer_bookings],
        model=model_id
    )
    
    return agent


def create_a2a_server() -> A2AServer:
    """
    Create and configure the A2A server for the Property Booking Agent.
    
    Returns:
        Configured A2AServer instance
    """
    agent = create_property_booking_agent()
    
    host = os.getenv("AGENT_HOST", "0.0.0.0")  # nosec B104 - required for container deployment
    port = int(os.getenv("AGENT_PORT", "5001"))
    version = os.getenv("AGENT_VERSION", "1.0.0")
    
    logger.info(f"Creating A2A server on {host}:{port}")
    
    # Create A2A server with agent
    a2a_server = A2AServer(
        agent=agent,
        host=host,
        port=port,
        version=version
    )
    
    return a2a_server


if __name__ == "__main__":
    # Create and start A2A server for local testing
    server = create_a2a_server()
    
    logger.info("Starting Property Booking Agent A2A server...")
    logger.info(f"Agent card available at: http://{server.host}:{server.port}/.well-known/agent-card.json")
    
    # Start the server
    server.serve()
