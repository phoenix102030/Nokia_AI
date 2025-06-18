# mcp_server.py
# This is the backend service (our "Clerk") that connects to MongoDB
# and provides a tool for the AI agent to use.

# --- 1. Imports ---
# Import the necessary libraries we installed
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from bson import ObjectId # Needed to handle MongoDB's unique _id format
import json

# --- 2. Pydantic Models ---
# These models define the exact structure of the data we expect to receive.
# This ensures that requests from the agent are valid.
class ToolParameters(BaseModel):
    user_id: str

class MCPRequest(BaseModel):
    tool_name: str
    parameters: ToolParameters

# --- 3. FastAPI App & Database Connection ---
# Create the main FastAPI application
app = FastAPI()

# Connect to the local MongoDB server running in Docker
try:
    client = MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=5000)
    # Trigger a connection test
    client.server_info() 
    db = client['agent_db'] # The database we created with seed_db.py
    users_collection = db['users'] # The collection with our user data
    print("Successfully connected to MongoDB.")
except Exception as e:
    print(f"Error: Could not connect to MongoDB. Is the Docker container running? Details: {e}")
    # Exit if we can't connect to the DB, as the app is useless without it.
    exit()

# --- 4. Helper Function ---
# MongoDB's default ID (_id) is a special BSON ObjectId, not a string.
# This helper function converts it to a string so it can be sent as JSON.
def mongo_id_serializer(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

# --- 5. The API Endpoint for our Tool ---
# This is the URL our agent will call. The decorator @app.post defines it as
# a POST request endpoint at the address '/tools/get_user_by_id'.
@app.post("/tools/get_user_by_id")
async def get_user_by_id_tool(request: MCPRequest):
    """
    This function is the tool. It gets a user_id from the agent's request,
    queries the database, and returns the user's data.
    """
    print(f"Received API call for tool: '{request.tool_name}' with user_id: '{request.parameters.user_id}'")
    
    # Extract the user_id from the validated request model
    user_id_to_find = request.parameters.user_id
    
    # Query the MongoDB collection
    user_data = users_collection.find_one({"user_id": user_id_to_find})

    if not user_data:
        # If no user is found, raise a standard HTTP 404 error
        print(f"User '{user_id_to_find}' not found in database.")
        raise HTTPException(status_code=404, detail=f"User '{user_id_to_find}' not found.")
    
    print(f"Found user data: {user_data}")
    
    # Use our helper to convert the response to valid JSON and return it
    # This sends the data back to the agent script that called it.
    return json.loads(json.dumps(user_data, default=mongo_id_serializer))

# A simple root endpoint to easily check if the server is running
@app.get("/")
def read_root():
    return {"status": "MCP Server is running and ready for tool calls."}