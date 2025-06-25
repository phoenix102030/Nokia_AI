# fastmcp_async.py
# The ASYNCHRONOUS version of our custom micro-framework.
# It's designed to work with async tool functions and the 'motor' driver.

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient # <-- Use Motor for async
import json

class MCPApplication:
    """
    An ASYNC wrapper around FastAPI to simplify creating tool-based servers.
    """
    def __init__(self, db_connection_string: str):
        """
        Initializes the async server application and connects to the database.
        
        Args:
            db_connection_string (str): The MongoDB connection string.
        """
        self.app = FastAPI()
        # Motor connects lazily, so no 'await' is needed here.
        self.db_client = AsyncIOMotorClient(db_connection_string)
        self._setup_root_endpoint()
        print(f"✅ Async MCP Server initialized. Database connection configured.")
        print(f"   NOTE: A 'database not found' error on first tool call is normal if the DB is new.")


    def _setup_root_endpoint(self):
        """Creates a default root endpoint to check server status."""
        @self.app.get("/")
        def read_root():
            return {"status": "Async MCP Server is running and ready for tool calls."}

    def tool(self, name: str):
        """
        A decorator to register an ASYNC Python function as a tool endpoint.
        
        Args:
            name (str): The API endpoint path for this tool (e.g., "/get_busiest_lanes").
        """
        def decorator(func):
            # Define the expected structure for the request body
            class ToolRequest(BaseModel):
                tool_name: str
                parameters: dict

            # The wrapper function MUST be async to use 'await'
            @self.app.post(f"/tools{name}")
            async def wrapper(request: ToolRequest):
                print(f"➡️ Received API call for tool: '{request.tool_name}' with parameters: {request.parameters}")
                
                try:
                    # Execute the original async tool function from the toolbox
                    # We pass the db_client and unpack the parameters from the request
                    result_json_str = await func(db_client=self.db_client, **request.parameters)
                    
                    # The tool functions already return JSON strings, so we parse them
                    # to let FastAPI handle the response correctly.
                    return json.loads(result_json_str)

                except Exception as e:
                    print(f"❌ Error executing tool '{request.tool_name}': {e}")
                    raise HTTPException(status_code=500, detail=str(e))
            
            # Here, we return the original function, but the decorator has already
            # registered the 'wrapper' with FastAPI. This allows us to chain decorators
            # or use the original function elsewhere if needed.
            return func
        return decorator

    def launch(self):
        """Returns the underlying FastAPI app instance for Uvicorn to run."""
        return self.app