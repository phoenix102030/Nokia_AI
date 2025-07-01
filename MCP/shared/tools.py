# shared/tools.py
# The single source of truth for all database tools.

import motor.motor_asyncio
import os
import json
from bson import ObjectId

# --- Database Connection ---
# This client is created once and reused by all tool functions.
MONGO_URI = os.getenv("MCP_MONGODB_URI", "mongodb://localhost:27017")
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)

def json_encoder(obj):
    """A helper to convert MongoDB's ObjectId to a string for JSON."""
    if isinstance(obj, ObjectId):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

# --- Tool Schemas (The "Manual" for the LLM) ---
# This list of dictionaries describes each tool, its purpose, and its parameters.
# The client will send this to the LLM in the system prompt.
AVAILABLE_TOOLS_SCHEMA = [
    {
        "name": "list_databases",
        "description": "Lists the names of all available databases on the server.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "list_collections",
        "description": "Lists all collections within a specified database.",
        "parameters": {
            "type": "object",
            "properties": {
                "database_name": {"type": "string", "description": "The name of the database, e.g., 'traffic_data'."}
            },
            "required": ["database_name"]
        }
    },
    {
        "name": "find",
        "description": "Finds documents in a collection that match a query. Returns a list of documents.",
        "parameters": {
            "type": "object",
            "properties": {
                "database_name": {"type": "string", "description": "The database name, e.g., 'traffic_data'."},
                "collection_name": {"type": "string", "description": "The collection name, e.g., 'lane_data' or 'measurements'."},
                "filter": {"type": "object", "description": "The query filter. Example: {'metadata.lane_id': '1'}. Defaults to {} to find all.", "default": {}},
                "limit": {"type": "integer", "description": "The maximum number of documents to return.", "default": 5}
            },
            "required": ["database_name", "collection_name"]
        }
    },
    {
        "name": "get_lane_summary",
        "description": "Calculates the average speed, density, and time loss for a specific lane_id from the 'lane_data' collection.",
        "parameters": {
            "type": "object",
            "properties": {
                "database_name": {"type": "string", "description": "The database containing lane data, e.g., 'traffic_data'."},
                "lane_id": {"type": "string", "description": "The specific lane_id to summarize, e.g., ':13445139_0'."}
            },
            "required": ["database_name", "lane_id"]
        }
    }
]

# --- Tool Implementations (The Actual Python Functions) ---

async def list_databases() -> str:
    """Lists all available databases."""
    print("🛠️ Executing 'list_databases'")
    db_names = await client.list_database_names()
    return json.dumps({"databases": db_names})

async def list_collections(database_name: str) -> str:
    """Lists all collections in a given database."""
    print(f"🛠️ Executing 'list_collections' on database '{database_name}'")
    db = client[database_name]
    collection_names = await db.list_collection_names()
    return json.dumps({"collections": collection_names})

async def find(database_name: str, collection_name: str, filter: dict = {}, limit: int = 5) -> str:
    """Finds documents in a collection based on a query."""
    print(f"🛠️ Executing 'find' on '{database_name}.{collection_name}'")
    db = client[database_name]
    collection = db[collection_name]
    documents = []
    cursor = collection.find(filter).limit(limit)
    for doc in await cursor.to_list(length=limit):
        documents.append(doc)
    return json.dumps(documents, default=json_encoder)

async def get_lane_summary(database_name: str, lane_id: str) -> str:
    """Calculates an aggregate summary for a specific lane."""
    print(f"🛠️ Executing 'get_lane_summary' for lane_id '{lane_id}'")
    db = client[database_name]
    collection = db["lane_data"]
    pipeline = [
        {'$match': {'metadata.lane_id': lane_id}},
        {'$group': {
            '_id': '$metadata.lane_id',
            'avg_speed': {'$avg': '$measurement.speed'},
            'avg_density': {'$avg': '$measurement.density'},
            'avg_time_loss': {'$avg': '$measurement.time_loss'},
            'record_count': {'$sum': 1}
        }}
    ]
    result = await collection.aggregate(pipeline).to_list(length=1)
    return json.dumps(result, default=json_encoder)


# --- Tool Mapping ---
# This dictionary connects the tool names to their function implementations.
# The server will use this to know which function to run.
TOOL_IMPLEMENTATIONS = {
    "list_databases": list_databases,
    "list_collections": list_collections,
    "find": find,
    "get_lane_summary": get_lane_summary,
}

