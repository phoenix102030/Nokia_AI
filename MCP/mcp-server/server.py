# mcp-server/server.py
# Updated server that imports tools from the shared tools.py file.

import os
import sys
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastmcp import FastMCP

# Add the shared directory to the Python path so we can import 'tools'
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))
from tools import TOOL_IMPLEMENTATIONS, AVAILABLE_TOOLS_SCHEMA

load_dotenv()

@asynccontextmanager
async def app_lifespan(server: FastMCP):
    """Manages resources during the server's lifespan, like database connections."""
    print("Lifespan Handler: Server is starting up.")
    # The database client is already initialized in tools.py
    yield
    print("Lifespan Handler: Server is shutting down.")

# --- Server Initialization ---
mcp = FastMCP(
    name="MongoToolServer",
    instructions="This server provides tools to interact with a local MongoDB database.",
    lifespan=app_lifespan
)
print("🚀 FastMCP server object created.")

# --- Dynamic Tool Registration ---
# Loop through the shared tool implementations and register them with the FastMCP server
for tool_name, tool_func in TOOL_IMPLEMENTATIONS.items():
    # Dynamically register each function using the @mcp.tool() decorator
    mcp.tool()(tool_func)
    print(f"✅ Tool '{tool_name}' registered.")


# --- Expose the ASGI Application ---
# Uvicorn will run this 'app' object
app = mcp.http_app()
print("✅ ASGI application ready for Uvicorn.")
