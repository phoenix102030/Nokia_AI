# mcp-server/compatible_server.py
import os
import sys
import json
import uuid
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import httpx
from contextlib import asynccontextmanager

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the original server
try:
    import server
    fastmcp_app = server.app
    print("✅ Successfully imported FastMCP app")
except Exception as e:
    print(f"❌ Error importing FastMCP app: {e}")
    raise

# Simple in-memory session storage
sessions = {}

# Create wrapper app
wrapper_app = FastAPI()

# Add CORS middleware
wrapper_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@wrapper_app.post("/mcp/session")
async def create_session():
    """Create a session for MCP compatibility"""
    session_id = str(uuid.uuid4())
    sessions[session_id] = {"created_at": "now"}
    print(f"✅ Created session: {session_id}")
    return {"session_id": session_id}

@wrapper_app.get("/mcp/manifest")
async def get_manifest(request: Request):
    """Get manifest with session compatibility"""
    # Try to get session ID from various sources
    session_id = (
        request.headers.get("X-Session-ID") or
        request.query_params.get("sessionId") or
        request.cookies.get("session_id")
    )
    
    # If no session ID, create a temporary one
    if not session_id:
        session_id = str(uuid.uuid4())
        sessions[session_id] = {"temp": True}
        print(f"⚠️ No session ID provided, created temporary: {session_id}")
    
    # Create headers for the request to FastMCP app
    headers = {
        "accept": "text/event-stream",
        "x-session-id": session_id
    }
    
    print(f"🔍 Forwarding manifest request with session: {session_id}")
    
    # Forward to original FastMCP app using httpx
    try:
        async with httpx.AsyncClient(app=fastmcp_app, base_url="http://test") as client:
            response = await client.get("/mcp/manifest", headers=headers)
            print(f"✅ Manifest response: {response.status_code}")
            
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.headers.get("content-type", "text/event-stream")
            )
    except Exception as e:
        print(f"❌ Error in manifest forwarding: {e}")
        return Response(
            content=json.dumps({"error": f"Manifest forwarding failed: {str(e)}"}),
            status_code=500,
            media_type="application/json"
        )

@wrapper_app.post("/mcp/invoke")
async def invoke_tool(request: Request):
    """Invoke tool with session compatibility"""
    # Get request body
    try:
        body = await request.json()
    except:
        body = {}
    
    # Get session ID
    session_id = (
        request.headers.get("X-Session-ID") or
        body.get("sessionId") or
        request.query_params.get("sessionId")
    )
    
    # If no session ID, create temporary
    if not session_id:
        session_id = str(uuid.uuid4())
        sessions[session_id] = {"temp": True}
        print(f"⚠️ No session ID in invoke, created temporary: {session_id}")
    
    # Prepare headers
    headers = {
        "accept": "text/event-stream",
        "content-type": "application/json",
        "x-session-id": session_id
    }
    
    print(f"🔍 Forwarding invoke request with session: {session_id}")
    
    # Forward to original FastMCP app
    try:
        async with httpx.AsyncClient(app=fastmcp_app, base_url="http://test") as client:
            response = await client.post("/mcp/invoke", json=body, headers=headers)
            print(f"✅ Invoke response: {response.status_code}")
            
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.headers.get("content-type", "text/event-stream")
            )
    except Exception as e:
        print(f"❌ Error in invoke forwarding: {e}")
        return Response(
            content=json.dumps({"error": f"Invoke forwarding failed: {str(e)}"}),
            status_code=500,
            media_type="application/json"
        )

@wrapper_app.get("/")
async def root():
    return {
        "message": "MCP Compatible Server",
        "endpoints": [
            "GET /mcp/manifest",
            "POST /mcp/invoke", 
            "POST /mcp/session"
        ],
        "status": "running"
    }

# Test endpoint
@wrapper_app.get("/test")
async def test():
    return {"message": "Test endpoint working"}