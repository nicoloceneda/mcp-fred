from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "fred-mcp",
    instructions=(
        "Query FRED API v1, GeoFRED maps API, and FRED API v2 release observations."
    ),
)
