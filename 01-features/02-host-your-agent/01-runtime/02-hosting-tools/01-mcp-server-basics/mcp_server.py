"""
Basic MCP Server — hosted on AgentCore Runtime.

Exposes three tools via the Model Context Protocol:
- add_numbers: adds two numbers
- multiply_numbers: multiplies two numbers
- greet: generates a greeting message

AgentCore Runtime expects the MCP server on 0.0.0.0:8000/mcp
using stateless streamable HTTP transport.
"""

from mcp.server.fastmcp import FastMCP

# stateless_http=True and json_response=True required for AgentCore Runtime compatibility
mcp = FastMCP("basic-tools", host="0.0.0.0", stateless_http=True, json_response=True)  # nosec B104


@mcp.tool()
def add_numbers(a: float, b: float) -> float:
    """Add two numbers together.

    Args:
        a: First number.
        b: Second number.

    Returns:
        The sum of a and b.
    """
    return a + b


@mcp.tool()
def multiply_numbers(a: float, b: float) -> float:
    """Multiply two numbers.

    Args:
        a: First number.
        b: Second number.

    Returns:
        The product of a and b.
    """
    return a * b


@mcp.tool()
def greet(name: str, language: str = "english") -> str:
    """Generate a greeting message.

    Args:
        name: The name of the person to greet.
        language: The language for the greeting (english, spanish, french).

    Returns:
        A greeting message.
    """
    greetings = {
        "english": f"Hello, {name}! Welcome!",
        "spanish": f"¡Hola, {name}! ¡Bienvenido!",
        "french": f"Bonjour, {name}! Bienvenue!",
    }
    return greetings.get(language.lower(), f"Hello, {name}!")


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
