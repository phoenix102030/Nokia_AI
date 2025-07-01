import logging
from fastapi import FastAPI
from pydantic import BaseModel
from pymongo import MongoClient
import re

# Configure logging
logging.basicConfig(
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    level=logging.INFO,
    force=True
)

# MongoDB connection
DB_CONNECTION = 'mongodb://localhost:27017/'
client = MongoClient(DB_CONNECTION)
db = client['mcp']  # Use or create 'mcp' database

# FastAPI app
app = FastAPI(
    title="MCP Server",
    description="Handles NLI queries and logs to MongoDB"
)

# Request schema
class QueryRequest(BaseModel):
    query: str

# Endpoint to process natural language queries
@app.post("/nli/query")
def process_query(req: QueryRequest):
    text = req.query.strip().lower()
    # Addition operation
    if 'add' in text or 'sum' in text:
        nums = list(map(int, re.findall(r'\d+', text)))
        result = sum(nums)
        db.logs.insert_one({'query': req.query, 'operation': 'add', 'operands': nums, 'result': result})
        return {'operation': 'add', 'operands': nums, 'result': result}
    # Echo operation
    if 'echo' in text:
        db.logs.insert_one({'query': req.query, 'operation': 'echo', 'echoed': req.query})
        return {'operation': 'echo', 'echoed': req.query}
    # Unknown command
    db.logs.insert_one({'query': req.query, 'operation': 'unknown'})
    return {'message': "Sorry, I don't understand that command."}
