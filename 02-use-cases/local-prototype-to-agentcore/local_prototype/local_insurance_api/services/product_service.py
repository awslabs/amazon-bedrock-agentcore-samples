"""
Insurance product service for the Insurance API
"""
from typing import Dict, List, Any, Optional
import logging
from services.utils import get_product_recommendation

logger = logging.getLogger("insurance_api")

def filter_products_by_id(products: List[Dict[str, Any]], product_id: Optional[str or List[str]]) -> List[Dict[str, Any]]:
    """Filter products by ID or list of IDs"""
    if not product_id:
        return products
        
    if isinstance(product_id, list):
        return [p for p in products if p.get("id") in product_id]
    else:
        return [p for p in products if p.get("id") == product_id]

def filter_products_by_price_range(products: List[Dict[str, Any]], price_range: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter products by price range"""
    if not price_range or not isinstance(price_range, dict):
        return products
        
    filtered_products = products
    min_price = price_range.get("min")
    max_price = price_range.get("max")
    
    if min_price is not None:
        filtered_products = [p for p in filtered_products if p.get("base_premium", 0) >= min_price]
    
    if max_price is not None:
        filtered_products = [p for p in filtered_products if p.get("base_premium", 0) <= max_price]
    
    return filtered_products

def filter_products_by_coverage(products: List[Dict[str, Any]], coverage_includes: Optional[List[str]]) -> List[Dict[str, Any]]:
    """Filter products by required coverages"""
    if not coverage_includes or not isinstance(coverage_includes, list):
        return products
        
    filtered_products = []
    for product in products:
        coverage_options = product.get("coverage_options", {})
        include_product = True
        
        for coverage in coverage_includes:
            # Check if this coverage is included in the product
            if coverage == "liability" and not coverage_options.get("liability"):
                include_product = False
                break
            elif coverage in ["collision", "comprehensive", "uninsured_motorist", "rental_reimbursement", "roadside_assistance"]:
                if not coverage_options.get(coverage, False):
                    include_product = False
                    break
            elif coverage == "medical_payments" and not coverage_options.get("medical_payments"):
                include_product = False
                break
        
        if include_product:
            filtered_products.append(product)
    
    return filtered_products

def filter_products_by_discounts(products: List[Dict[str, Any]], discount_includes: Optional[List[str]]) -> List[Dict[str, Any]]:
    """Filter products by required discounts"""
    if not discount_includes or not isinstance(discount_includes, list):
        return products
        
    filtered_products = []
    for product in products:
        eligible_discount_ids = product.get("eligible_discounts", [])
        include_product = True
        
        for discount_id in discount_includes:
            if discount_id not in eligible_discount_ids:
                include_product = False
                break
        
        if include_product:
            filtered_products.append(product)
    
    return filtered_products

def sort_products(products: List[Dict[str, Any]], sort_by: Optional[str], sort_order: str = "asc") -> List[Dict[str, Any]]:
    """Sort products by specified field"""
    if not sort_by:
        return products
        
    reverse_sort = sort_order.lower() == "desc"
    
    if sort_by == "price":
        return sorted(products, key=lambda p: p.get("base_premium", 0), reverse=reverse_sort)
    elif sort_by == "name":
        return sorted(products, key=lambda p: p.get("name", ""), reverse=reverse_sort)
    elif sort_by == "rating":
        # Calculate rating based on product type (just for sorting)
        def get_rating(product):
            if "premium" in product.get("id", ""):
                return 4.8
            elif "standard" in product.get("id", ""):
                return 4.5
            else:
                return 4.0
        return sorted(products, key=get_rating, reverse=reverse_sort)
    
    return products

def format_product_for_response(product: Dict[str, Any], discounts: List[Dict[str, Any]], 
                               include_details: bool = True, 
                               format_type: str = "full",
                               product_index: int = 0) -> Dict[str, Any]:
    """Format a single product for API response"""
    # Calculate sample price ranges based on various factors
    min_price = product.get("base_premium", 0)
    max_price = min_price * 1.8  # Maximum price could be 80% higher
    
    # Get eligible discounts details
    eligible_discount_ids = product.get("eligible_discounts", [])
    eligible_discounts = []
    
    for discount in discounts:
        if discount.get("id") in eligible_discount_ids:
            eligible_discounts.append({
                "name": discount.get("name"),
                "description": discount.get("description"),
                "percentage": discount.get("percentage")
            })
    
    # Create sample coverage examples
    coverage_examples = []
    coverage_options = product.get("coverage_options", {})
    
    if coverage_options.get("liability"):
        liability_limits = coverage_options.get("liability", [100000])
        coverage_examples.append({
            "type": "Liability",
            "limits": f"${liability_limits[-1]:,} per accident",
            "included": True
        })
        
    coverage_examples.append({
        "type": "Collision",
        "limits": "Covers repair costs",
        "included": coverage_options.get("collision", False)
    })
    
    coverage_examples.append({
        "type": "Comprehensive",
        "limits": "Covers non-collision damage",
        "included": coverage_options.get("comprehensive", False)
    })
    
    if coverage_options.get("medical_payments"):
        medical_limits = coverage_options.get("medical_payments", [0])
        coverage_examples.append({
            "type": "Medical Payments",
            "limits": f"${medical_limits[-1]:,} per person",
            "included": medical_limits[-1] > 0
        })
        
    if coverage_options.get("rental_reimbursement", False):
        coverage_examples.append({
            "type": "Rental Reimbursement",
            "limits": "Up to $50 per day",
            "included": True
        })
        
    if coverage_options.get("roadside_assistance", False):
        coverage_examples.append({
            "type": "Roadside Assistance",
            "limits": "24/7 emergency service",
            "included": True
        })
    
    # Add a sample customer rating
    rating = 4.0 if "basic" in product["id"] else 4.5 if "standard" in product["id"] else 4.8
    
    # Create basic product info
    product_info = {
        "id": product["id"],
        "name": product["name"],
        "description": product["description"],
        "base_price": product.get("base_premium", 0)
    }
    
    # Add additional details based on format options
    if include_details or format_type == "full":
        product_info.update({
            "price_range": {
                "min": round(min_price, 2),
                "max": round(max_price, 2),
                "currency": "USD",
                "billing_period": "semi-annual"
            },
            "coverage_examples": coverage_examples,
            "eligible_discounts": eligible_discounts,
            "customer_rating": rating,
            "reviews_count": 120 + (50 * product_index),
            "recommended_for": get_product_recommendation(product["id"])
        })
    
    return product_info

def create_product_response(products: List[Dict[str, Any]], 
                          discounts: List[Dict[str, Any]],
                          request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create the complete insurance products response"""
    # Get format options
    include_details = request_data.get("include_details", True)
    format_type = request_data.get("format", "full")
    
    # Format each product
    formatted_products = [
        format_product_for_response(
            product, 
            discounts, 
            include_details, 
            format_type, 
            idx
        ) for idx, product in enumerate(products)
    ]
    
    # Extract request parameters
    product_id_filter = request_data.get("product_id")
    price_range = request_data.get("price_range")
    coverage_includes = request_data.get("coverage_includes")
    discount_includes = request_data.get("discount_includes")
    sort_by = request_data.get("sort_by")
    sort_order = request_data.get("sort_order", "asc")
    
    # Create the response with appropriate metadata
    response_data = {
        "status": "success",
        "total_products": len(formatted_products),
        "filters_applied": {
            "product_id": product_id_filter is not None,
            "price_range": price_range is not None,
            "coverage_includes": coverage_includes is not None,
            "discount_includes": discount_includes is not None
        },
        "sort": {"by": sort_by, "order": sort_order} if sort_by else None,
        "format": format_type,
        "last_updated": "2025-07-01T09:30:00Z",
        "currency": "USD",
        "products": formatted_products
    }
    
    # For summary format, exclude some metadata
    if format_type == "summary":
        response_data.pop("filters_applied", None)
        response_data.pop("sort", None)
    
    return response_data