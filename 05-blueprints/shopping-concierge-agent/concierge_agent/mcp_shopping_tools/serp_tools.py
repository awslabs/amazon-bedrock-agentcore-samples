import os
import logging
import boto3
from typing import Any, Dict
from serpapi import GoogleSearch

logger = logging.getLogger(__name__)


def get_ssm_parameter(parameter_name: str, region: str) -> str:
    """
    Fetch parameter from SSM Parameter Store.

    Args:
        parameter_name: SSM parameter name
        region: AWS region

    Returns:
        Parameter value
    """
    ssm = boto3.client("ssm", region_name=region)
    try:
        response = ssm.get_parameter(Name=parameter_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except ssm.exceptions.ParameterNotFound:
        raise ValueError(f"SSM parameter not found: {parameter_name}")
    except Exception as e:
        raise ValueError(f"Failed to retrieve SSM parameter {parameter_name}: {e}")


def get_serpapi_key() -> str:
    """
    Get SerpAPI key from AWS SSM Parameter Store.

    Returns:
        SerpAPI key
    """
    region = os.getenv("AWS_REGION", "us-east-1")
    return get_ssm_parameter("/concierge-agent/shopping/serp-api-key", region)


def search_amazon_products(query: str, max_results: int = 10) -> Dict[str, Any]:
    """
    Search for products on Amazon using SerpAPI.

    Args:
        query: Search query for products
        max_results: Maximum number of results to return

    Returns:
        Dict containing search results with product information
    """
    try:
        api_key = get_serpapi_key()

        # Search Amazon using SerpAPI
        params = {
            "engine": "amazon",
            "amazon_domain": "amazon.com",
            "k": query,
            "api_key": api_key,
        }

        search = GoogleSearch(params)
        results = search.get_dict()

        # Extract product information
        products = []
        organic_results = results.get("organic_results", [])[:max_results]

        for product in organic_results:
            product_info = {
                "asin": product.get("asin", ""),
                "title": product.get("title", ""),
                "link": product.get("link", ""),
                "price": (
                    product.get("price", {}).get("value", 0)
                    if isinstance(product.get("price"), dict)
                    else product.get("price", "N/A")
                ),
                "rating": product.get("rating", 0),
                "reviews": product.get("reviews", 0),
                "thumbnail": product.get("thumbnail", ""),
            }
            products.append(product_info)

        return {"success": True, "products": products, "total_results": len(products)}

    except Exception as e:
        logger.error(f"Error searching Amazon products: {e}")
        return {"success": False, "error": str(e), "products": [], "total_results": 0}


def search_products(user_id: str, question: str) -> Dict[str, Any]:
    """
    Process a product search request from user by searching products on Amazon via SerpAPI.

    Args:
        user_id: The unique identifier of the user for whom products are being searched.
        question: User's query text requesting product information

    Returns:
        Dict: A dictionary called 'product_list' with search results
            - 'answer': Description of found products or error message
            - 'asins': List of ASINs found
            - 'products': List of product details
    """
    try:
        logger.info(f"Processing product search for user {user_id}: {question}")

        # Search for products
        search_results = search_amazon_products(question)

        if not search_results["success"]:
            return {
                "answer": f"Product search failed: {search_results.get('error', 'Unknown error')}",
                "asins": [],
                "products": [],
            }

        products = search_results["products"]
        asins = [p["asin"] for p in products if p.get("asin")]

        if not products:
            return {
                "answer": "No products found matching your search criteria.",
                "asins": [],
                "products": [],
            }

        # Build response
        answer = f"Found {len(products)} products matching '{question}':\n\n"
        for i, product in enumerate(products, 1):
            price_str = (
                f"${product['price']}"
                if isinstance(product["price"], (int, float))
                else product["price"]
            )
            answer += f"{i}. {product['title']}\n"
            answer += f"   Price: {price_str}\n"
            if product.get("rating"):
                answer += f"   Rating: {product['rating']}/5 ({product.get('reviews', 0)} reviews)\n"
            answer += f"   ASIN: {product['asin']}\n"
            answer += f"   Link: {product['link']}\n\n"

        return {"answer": answer.strip(), "asins": asins, "products": products}

    except Exception as e:
        logger.error(f"Error in single_productsearch: {e}")
        return {
            "answer": f"An error occurred while searching for products: {str(e)}",
            "asins": [],
            "products": [],
        }


def generate_packing_list(user_id: str, question: str) -> Dict[str, Any]:
    """
    Process a user request to generate a packing list with product recommendations.
    Uses AI to generate a packing list and then searches Amazon for product recommendations
    for each item using SerpAPI.

    Args:
        user_id: The unique identifier of the user for whom products are being searched.
        question: User's query text requesting packing list (e.g., "I'm going to Hawaii for a week")

    Returns:
        Dict: called packing_list with results
            - 'answer': Formatted packing list with product recommendations
            - 'asins': Dict mapping packing list items to ASINs
            - 'items': List of packing list items with product details
    """
    try:
        logger.info(f"Generating packing list for user {user_id}: {question}")

        # Define common packing list categories based on the query
        # This is a simplified approach - in production, you might use an LLM to generate this
        packing_items = []

        # Extract trip context from question
        question_lower = question.lower()

        # Basic packing items everyone needs
        base_items = ["travel backpack", "toiletry bag", "phone charger"]

        # Add context-specific items
        if any(
            word in question_lower for word in ["beach", "hawaii", "tropical", "ocean"]
        ):
            packing_items.extend(
                [
                    "sunscreen SPF 50",
                    "beach towel",
                    "swimsuit",
                    "flip flops",
                    "sunglasses",
                ]
            )
        elif any(word in question_lower for word in ["ski", "snow", "winter", "cold"]):
            packing_items.extend(
                [
                    "winter jacket",
                    "thermal underwear",
                    "ski goggles",
                    "gloves",
                    "beanie",
                ]
            )
        elif any(word in question_lower for word in ["hiking", "camping", "outdoor"]):
            packing_items.extend(
                [
                    "hiking boots",
                    "water bottle",
                    "first aid kit",
                    "flashlight",
                    "sleeping bag",
                ]
            )
        elif any(word in question_lower for word in ["business", "work", "conference"]):
            packing_items.extend(
                ["business casual clothes", "laptop bag", "power bank", "notebook"]
            )
        else:
            # Generic travel items
            packing_items.extend(["travel pillow", "luggage tags", "packing cubes"])

        packing_items = base_items + packing_items

        # Search for products for each packing item
        results = []
        asins_dict = {}

        answer = f"Packing list for: {question}\n\n"

        for item in packing_items[:7]:  # Limit to 7 items to avoid too many API calls
            logger.info(f"Searching products for: {item}")
            search_results = search_amazon_products(item, max_results=3)

            if search_results["success"] and search_results["products"]:
                products = search_results["products"]
                item_asins = [p["asin"] for p in products if p.get("asin")]
                asins_dict[item] = item_asins

                answer += f"📦 {item.title()}\n"
                answer += "   Recommended products:\n"

                for i, product in enumerate(products[:3], 1):
                    price_str = (
                        f"${product['price']}"
                        if isinstance(product["price"], (int, float))
                        else product["price"]
                    )
                    answer += f"   {i}. {product['title'][:60]}...\n"
                    answer += f"      Price: {price_str}"
                    if product.get("rating"):
                        answer += f" | Rating: {product['rating']}/5"
                    answer += f"\n      ASIN: {product['asin']}\n"

                answer += "\n"

                results.append({"item": item, "products": products})

        if not results:
            return {
                "answer": "Unable to generate packing list with product recommendations at this time.",
                "asins": {},
                "items": [],
            }

        return {"answer": answer.strip(), "asins": asins_dict, "items": results}

    except Exception as e:
        logger.error(f"Error in generate_packinglist_with_productASINS: {e}")
        return {
            "answer": f"An error occurred while generating packing list: {str(e)}",
            "asins": {},
            "items": [],
        }
