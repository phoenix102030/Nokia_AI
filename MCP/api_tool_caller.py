# api_tool_caller.py
# This module contains functions that make HTTP requests to our MCP server.
# It acts as the bridge between our agent's decision and the server's tools.

import httpx  # An excellent async HTTP client, a modern alternative to 'requests'
import json

# The address where your launch_async_server.py is running
MCP_SERVER_URL = "http://127.0.0.1:8000"

async def call_api_tool(endpoint: str, tool_name: str, params: dict) -> str:
    """A generic function to call any tool on the MCP server."""
    url = f"{MCP_SERVER_URL}/tools{endpoint}"
    payload = {"tool_name": tool_name, "parameters": params}
    
    print(f"📡 Making API call to '{url}' with payload: {payload}")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=20.0)
            response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes
            # The server already returns a JSON string, which is what the agent loop expects.
            return response.text
    except httpx.RequestError as e:
        error_message = f"API call to {e.request.url} failed: {e}"
        print(f"❌ {error_message}")
        return json.dumps({"error": error_message})
    except Exception as e:
        error_message = f"An unexpected error occurred during the API call: {e}"
        print(f"❌ {error_message}")
        return json.dumps({"error": error_message})

# --- Define a specific function for each tool ---
# The agent will call these functions.

async def get_busiest_lanes(top_n: int = 5) -> str:
    """Calls the server to get the top N lanes by average occupancy."""
    return await call_api_tool(
        endpoint="/get_busiest_lanes",
        tool_name="get_busiest_lanes_by_occupancy",
        params={"top_n": top_n}
    )

async def get_lanes_with_most_traffic(top_n: int = 5) -> str:
    """Calls the server to get the top N lanes by total vehicles entered."""
    return await call_api_tool(
        endpoint="/get_lanes_with_most_traffic",
        tool_name="get_lanes_with_most_traffic",
        params={"top_n": top_n}
    )

async def get_total_vehicles_entered() -> str:
    """Calls the server to get the total number of vehicles that have ever entered."""
    return await call_api_tool(
        endpoint="/get_total_vehicles_entered",
        tool_name="get_total_vehicles_entered",
        params={} # This tool takes no parameters
    )