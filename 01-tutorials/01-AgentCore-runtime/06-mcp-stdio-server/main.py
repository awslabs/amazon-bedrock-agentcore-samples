from fastmcp import FastMCP
from fastmcp.client.transports import StdioTransport
from fastmcp.server.proxy import ProxyClient
from starlette.responses import JSONResponse

# Create a proxy directly from a config dictionary
transport = StdioTransport(
    command="uv",
    args=["run", "awslabs.aws-documentation-mcp-server"],
)

# Create a proxy to the configured server (auto-creates ProxyClient)
proxy = FastMCP.as_proxy(ProxyClient(transport), name="Proxy", stateless_http=True)


@proxy.custom_route("/ping", ["GET"])
def ping(req):
    return JSONResponse({"status": "healthy"})


# Run the proxy with stdio transport for local access
if __name__ == "__main__":
    proxy.run(transport="streamable-http", host="0.0.0.0", port=8000)
