"""MCP client wiring -- built once per matching run (same lifecycle as
ModelRouter), not per candidate. See app/mcp/server.py for the tools this
talks to.
"""

from langchain_mcp_adapters.client import MultiServerMCPClient

from app.config.settings import Settings


def get_mcp_client(settings: Settings) -> MultiServerMCPClient:
    return MultiServerMCPClient(
        {
            "adequia": {
                "transport": "streamable_http",
                "url": f"{settings.mcp_server_url}/mcp",
            },
        }
    )
