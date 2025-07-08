# shared/tools.py
# All-in-one definition center for shared MongoDB tools.

import motor.motor_asyncio
import os
import json
from bson import ObjectId

# --- Database Connection ---
MONGO_URI = os.getenv("MCP_MONGODB_URI", "mongodb://localhost:27017")
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)

def json_encoder(obj):
    """Custom JSON encoder to handle MongoDB's ObjectId."""
    if isinstance(obj, ObjectId):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

# --- Tool Schemas (The "Manual" for the LLM) ---
AVAILABLE_TOOLS_SCHEMA = [
    {
        "name": "no_op",
        "description": "Call this tool when the user is not asking a question about the database but is just chatting or asking what you can do.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "The reason for not calling a database tool."}
            },
            "required": ["reason"]
        }
    },
    {
        "name": "get_database_schema",
        "description": "Scans the entire MongoDB instance and returns a list of all databases and the collections within each one. Use this for broad questions about what data is available.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "find",
        "description": (
            "Finds documents in a collection. IMPORTANT: In the 'lane_data' collection, "
            "'timestamp' is a top-level field, but 'lane_id' is nested inside 'metadata'. "
            "Also, 'lane_id' values may start with a colon ':'. "
            "Example filter: {'timestamp': '...', 'metadata.lane_id': ':...'}"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "database_name": {
                    "type": "string",
                    "description": "The database name, e.g., 'traffic_data'."
                },
                "collection_name": {
                    "type": "string",
                    "description": "The collection name, e.g., 'lane_data' or 'measurements'."
                },
                "filter": {
                    "type": "object",
                    "description": "The query filter. Defaults to {} to find all.",
                    "default": {}
                },
                "limit": {
                    "type": "integer",
                    "description": "The maximum number of documents to return.",
                    "default": 5
                }
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
                "metadata.lane_id": {"type": "string", "description": "The specific lane_id to summarize, e.g., '13445139_0' or ':13445139_0'."}
            },
            "required": ["database_name", "lane_id"]
        }
    }
]

# --- Tool Implementations (Python Functions) ---

async def no_op(reason: str) -> str:
    """A dummy function that just returns a helpful message."""
    print(f"🛠️ Tool 'no_op' called. Reason: {reason}")
    return json.dumps({
        "message": "I can help you query the traffic database. You can ask me to 'get the database schema', 'find documents', or 'get a summary for a specific lane'."
    })

async def get_database_schema() -> str:
    """
    A multi-step tool that lists all databases and their respective collections.
    """
    print("🛠️ Executing complex tool 'get_database_schema'")
    schema = {}
    # Exclude system databases that are not relevant to the user
    system_dbs = ["admin", "config", "local"]
    try:
        db_names = await client.list_database_names()
        for db_name in db_names:
            if db_name not in system_dbs:
                db = client[db_name]
                collections = await db.list_collection_names()
                schema[db_name] = collections
        return json.dumps(schema)
    except Exception as e:
        return json.dumps({"error": f"Failed to retrieve database schema: {e}"})


async def find(database_name: str, collection_name: str, filter: dict = {}, limit: int = 5) -> str:
    """Finds documents in a collection based on a query."""
    print(f"🛠️ Executing 'find' on '{database_name}.{collection_name}' with filter {filter}")
    db = client[database_name]
    collection = db[collection_name]
    documents = []
    # A limit of 0 means no limit.
    cursor = collection.find(filter)
    if limit > 0:
        cursor = cursor.limit(limit)

    for doc in await cursor.to_list(length=limit if limit > 0 else None):
        documents.append(doc)
    return json.dumps(documents, default=json_encoder)

async def get_lane_summary(database_name: str, lane_id: str) -> str:
    """
    Calculates an aggregate summary for a specific lane.
    This function is now robust and handles lane_ids with or without a leading colon.
    """
    print(f"🛠️ Executing 'get_lane_summary' for lane_id '{lane_id}'")
    
    id_with_colon = lane_id if lane_id.startswith(':') else f":{lane_id}"
    id_without_colon = lane_id.lstrip(':')

    db = client[database_name]
    collection = db["lane_data"]
    
    pipeline = [
        {'$match': {
            '$or': [
                {'metadata.lane_id': id_with_colon},
                {'metadata.lane_id': id_without_colon}
            ]
        }},
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
TOOL_IMPLEMENTATIONS = {
    "no_op": no_op,
    "get_database_schema": get_database_schema,
    "find": find,
    "get_lane_summary": get_lane_summary,
}