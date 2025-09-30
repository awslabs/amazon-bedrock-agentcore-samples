from fastmcp import FastMCP
import boto3
import logging
from botocore.config import Config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure boto3 with 30-second timeouts
boto_config = Config(
    connect_timeout=30, read_timeout=30, retries={"max_attempts": 3, "mode": "adaptive"}
)

# Initialize AWS clients with timeouts
ssm = boto3.client("ssm", config=boto_config)
dynamodb = boto3.resource("dynamodb", config=boto_config)


def get_table_names():
    """
    Retrieve DynamoDB table names from SSM parameters
    """
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

    return table_names


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
        logger.info(f"Fetching review with ID: {review_id}")
        response = reviews_table.get_item(Key={"review_id": review_id})
        item = response.get("Item")
        if not item:
            logger.warning(f"Review not found: {review_id}")
            return {"error": "Review not found"}
        logger.info(f"Successfully fetched review: {review_id}")
        return item
    except Exception as e:
        logger.error(f"Error fetching review {review_id}: {str(e)}")
        return {"error": str(e)}


@mcp.tool
def get_products(product_id: int):
    """
    Fetch a single product by product_id
    """
    try:
        logger.info(f"Fetching product with ID: {product_id}")
        response = products_table.get_item(Key={"product_id": product_id})
        item = response.get("Item")
        if not item:
            logger.warning(f"Product not found: {product_id}")
            return {"error": "Product not found"}
        logger.info(f"Successfully fetched product: {product_id}")
        return item
    except Exception as e:
        logger.error(f"Error fetching product {product_id}: {str(e)}")
        return {"error": str(e)}


# @mcp.tool
# def get_todo(todo_id: int):
#     """
#     Fetch a single todo by todo_id
#     """
#     return todo_id


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", stateless_http=True)
