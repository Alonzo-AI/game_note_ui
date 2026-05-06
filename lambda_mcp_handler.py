"""
AWS Lambda entrypoint for the FastMCP server.

This wraps the FastMCP ASGI app with Mangum so Lambda can serve it
through API Gateway Function URL / HTTP API.
"""

from mangum import Mangum

from mcp_server import build_mcp


def lambda_handler(event, context):
    """
    Lambda entrypoint.

    Create a fresh ASGI app/adapter per invocation so FastMCP lifespan
    initialization runs exactly once for that request lifecycle.
    """
    mcp = build_mcp()
    app = mcp.streamable_http_app()
    handler = Mangum(app)
    return handler(event, context)
