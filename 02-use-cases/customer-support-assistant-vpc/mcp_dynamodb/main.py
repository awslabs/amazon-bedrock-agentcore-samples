from fastmcp import FastMCP
import boto3
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize AWS clients
ssm = boto3.client("ssm")
dynamodb = boto3.resource("dynamodb")


def get_table_names():
    """
    Retrieve DynamoDB table names from SSM parameters
    """
    try:
        # Get both table names from SSM parameters
        response = ssm.get_parameters(
            Names=[
                "/app/customersupportvpc/dynamodb/reviews_table_name",
                "/app/customersupportvpc/dynamodb/products_table_name",
            ]
        )

        table_names = {}
        for param in response["Parameters"]:
            if "reviews" in param["Name"]:
                table_names["reviews"] = param["Value"]
                logger.info(f"Retrieved reviews table name: {param['Value']}")
            elif "products" in param["Name"]:
                table_names["products"] = param["Value"]
                logger.info(f"Retrieved products table name: {param['Value']}")

        # Check if we got both table names
        if "reviews" not in table_names or "products" not in table_names:
            missing = [k for k in ["reviews", "products"] if k not in table_names]
            raise ValueError(f"Failed to retrieve table names for: {missing}")

        return table_names

    except Exception as e:
        logger.error(f"Error retrieving table names from SSM: {e}")
        # Fallback to default names for backward compatibility
        logger.warning("Falling back to default table names")
        return {
            "reviews": "dynamodb-stack-reviews",
            "products": "dynamodb-stack-products",
        }


# Get table names dynamically
table_names = get_table_names()

# Reference the tables using dynamic names
reviews_table = dynamodb.Table(table_names["reviews"])
products_table = dynamodb.Table(table_names["products"])

logger.info(
    f"Initialized DynamoDB tables: reviews={table_names['reviews']}, products={table_names['products']}"
)

# Initialize FastMCP
mcp = FastMCP()


@mcp.tool
def get_reviews(review_id: str):
    """
    Fetch a single review by review_id
    """
    try:
        response = reviews_table.get_item(Key={"review_id": review_id})
        item = response.get("Item")
        if not item:
            return {"error": "Review not found"}
        return item
    except Exception as e:
        return {"error": str(e)}


@mcp.tool
def get_products(product_id: int):
    """
    Fetch a single product by product_id
    """
    try:
        response = products_table.get_item(Key={"product_id": product_id})
        item = response.get("Item")
        if not item:
            return {"error": "Product not found"}
        return item
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", stateless_http=True)
