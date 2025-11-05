from mcp.server.fastmcp import FastMCP

mcp = FastMCP(host="127.0.0.1", stateless_http=True)


@mcp.tool()
def greet_user(name: str) -> str:
    """Greet a user by name"""
    return f"Hello, {name}! Nice to meet you."


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
