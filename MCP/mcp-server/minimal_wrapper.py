# mcp-server/minimal_wrapper.py
import os
import sys
import json
import uuid
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import asyncio

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- MODIFIED ---
# Import the detailed schema and the tool implementations from tools.py
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))
try:
    from tools import TOOL_IMPLEMENTATIONS, AVAILABLE_TOOLS_SCHEMA
    print("✅ Successfully imported tools and schemas from tools.py")
except Exception as e:
    print(f"❌ Error importing from tools.py: {e}")
    raise

# Create a new FastAPI app
app = FastAPI(title="MCP Server", version="1.0.0")

# Add comprehensive CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Simple session storage
sessions = {}

@app.post("/mcp/session")
async def create_session():
    """Create a session for MCP compatibility"""
    session_id = str(uuid.uuid4())
    sessions[session_id] = {"created_at": "now"}
    return {"session_id": session_id}

@app.get("/mcp/manifest")
async def get_manifest(request: Request):
    """Return the detailed tool manifest directly from tools.py."""
    manifest = {
        "name": "MongoToolServer",
        "description": "This server provides tools to interact with a local MongoDB database.",
        "tools": AVAILABLE_TOOLS_SCHEMA
    }
    
    return Response(
        content=json.dumps(manifest),
        media_type="application/json",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*"
        }
    )

@app.post("/mcp/")
@app.post("/mcp")
async def mcp_jsonrpc_handler(request: Request):
    """Handle JSON-RPC 2.0 requests for MCP protocol"""
    try:
        body = await request.json()
        print(f"Received JSON-RPC request: {body}")
        
        method = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")
        
        if not method:
            return Response(
                content=json.dumps({
                    "jsonrpc": "2.0",
                    "error": {"code": -32600, "message": "Invalid Request: method required"},
                    "id": request_id
                }),
                status_code=400,
                media_type="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )
        
        # Handle different MCP methods
        if method == "initialize":
            protocol_version = params.get("protocolVersion", "1.0")
            response_data = {
                "jsonrpc": "2.0",
                "result": {
                    "protocolVersion": protocol_version,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "MongoToolServer", "version": "1.0.0"}
                },
                "id": request_id
            }
        
        # --- NEW CODE BLOCK ---
        # Handle the standard 'initialized' notification from the client.
        # According to the spec, we should not send a response body to notifications.
        elif method == "notifications/initialized":
            print("✅ Received 'initialized' notification. Handshake complete.")
            # Return HTTP 204 No Content, which is the correct way to handle this.
            return Response(status_code=204)
        
        elif method == "tools/list":
            response_data = {
                "jsonrpc": "2.0",
                "result": {"tools": AVAILABLE_TOOLS_SCHEMA},
                "id": request_id
            }
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_arguments = params.get("arguments", {})
            
            if not tool_name:
                response_data = {
                    "jsonrpc": "2.0",
                    "error": {"code": -32602, "message": "Invalid params: tool name required"},
                    "id": request_id
                }
            elif tool_name not in TOOL_IMPLEMENTATIONS:
                response_data = {
                    "jsonrpc": "2.0",
                    "error": {"code": -32601, "message": f"Method not found: {tool_name}"},
                    "id": request_id
                }
            else:
                try:
                    tool_func = TOOL_IMPLEMENTATIONS[tool_name]
                    result = await tool_func(**tool_arguments) if asyncio.iscoroutinefunction(tool_func) else tool_func(**tool_arguments)
                    response_data = {
                        "jsonrpc": "2.0",
                        "result": {"content": [{"type": "text", "text": result}]},
                        "id": request_id
                    }
                except Exception as e:
                    print(f"Tool execution failed for '{tool_name}': {e}")
                    response_data = {
                        "jsonrpc": "2.0",
                        "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
                        "id": request_id
                    }
        else:
            response_data = {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method not found: {method}"},
                "id": request_id
            }
        
        return Response(
            content=json.dumps(response_data),
            media_type="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )
            
    except json.JSONDecodeError:
        return Response(
            content=json.dumps({
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": "Parse error: Invalid JSON"},
                "id": None
            }),
            status_code=400,
            media_type="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )
    except Exception as e:
        print(f"Unexpected error in JSON-RPC handler: {e}")
        return Response(
            content=json.dumps({
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
                "id": None
            }),
            status_code=500,
            media_type="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )
    
@app.post("/mcp/invoke")
async def invoke_tool(request: Request):
    """Legacy REST API invoke tool endpoint"""
    try:
        body = await request.json()
        print(f"Received REST request: {body}")
        
        tool_name = body.get("tool") 
        tool_input = body.get("input", {})
        
        if not tool_name:
            return Response(
                content=json.dumps({"error": "Tool name required in 'tool' field"}),
                status_code=400,
                media_type="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )
        
        if tool_name not in TOOL_IMPLEMENTATIONS:
            return Response(
                content=json.dumps({"error": f"Tool '{tool_name}' not found"}),
                status_code=404,
                media_type="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )
        
        # Call the tool function
        tool_func = TOOL_IMPLEMENTATIONS[tool_name]
        try:
            result = await tool_func(**tool_input) if asyncio.iscoroutinefunction(tool_func) else tool_func(**tool_input)
            response_data = {"result": json.loads(result)}
            
            return Response(
                content=json.dumps(response_data),
                media_type="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )
        except Exception as e:
            print(f"Tool execution failed for '{tool_name}': {e}")
            return Response(
                content=json.dumps({"error": f"Tool execution failed: {str(e)}"}),
                status_code=500,
                media_type="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )
            
    except json.JSONDecodeError:
        return Response(
            content=json.dumps({"error": "Invalid JSON in request body"}),
            status_code=400,
            media_type="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )
    except Exception as e:
        print(f"Unexpected error in invoke_tool: {e}")
        return Response(
            content=json.dumps({"error": f"Internal server error: {str(e)}"}),
            status_code=500,
            media_type="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )


@app.get("/")
async def root():
    return {
        "message": "MCP MongoToolServer",
        "endpoints": [
            "GET /mcp/manifest",
            "POST /mcp/session"
        ],
        "status": "running"
    }

# Handle OPTIONS requests (preflight) for CORS
@app.options("/{full_path:path}")
async def options_handler(full_path: str, request: Request):
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS, PUT, DELETE",
            "Access-Control-Allow-Headers": "*",
        }
    )