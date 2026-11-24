"""MCP server (stdio now, streamable HTTP in Phase 8).

Phase 0: the server starts and exposes zero tools. Tools arrive in Phase 5.
"""
from mcp.server.mcpserver import MCPServer


def create_server() -> MCPServer:
    return MCPServer(
        "campfire",
        instructions="Campfire: a taste engine for discovering restaurants.",
    )


server = create_server()


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
