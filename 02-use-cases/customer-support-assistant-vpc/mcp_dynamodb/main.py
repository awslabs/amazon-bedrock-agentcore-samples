from fastmcp import FastMCP
import boto3

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")

# TODO: Dynamic table names
# Reference the tables
reviews_table = dynamodb.Table("dynamodb-stack-reviews")
products_table = dynamodb.Table("dynamodb-stack-products")

# Initialize FastMCP
mcp = FastMCP(host="0.0.0.0", stateless_http=True)


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
def get_products(product_id: str):
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
    mcp.run(transport="streamable-http")
