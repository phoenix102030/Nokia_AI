# agent_ollama.py
# This script uses a local Ollama model as the agent's brain and connects
# directly to MongoDB to run tools.

import os
import json
import time
from openai import OpenAI
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv

# --- 1. SETUP: LOAD ENVIRONMENT & INITIALIZE CLIENTS ---

# Load variables from the .env file
load_dotenv()

# Configure the OpenAI client to connect to your local Ollama server
try:
    client = OpenAI(
        base_url=os.getenv("OPENAI_BASE_URL"),
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    # Get the model name from the environment file
    MODEL = os.getenv("MODEL_NAME")
    print(f"✅ OpenAI client configured to use Ollama with model: {MODEL}")
except Exception as e:
    print(f"❌ Error initializing client: {e}")
    print("   Please ensure your .env file is set up correctly for Ollama.")
    exit()

# Configure the MongoDB client
try:
    mongo_client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=5000)
    mongo_client.server_info()
    db = mongo_client["nokia_traffic_data"]
    print("✅ Successfully connected to MongoDB.")
except Exception as e:
    print(f"❌ Error connecting to MongoDB: {e}")
    exit()


# --- 2. DEFINE THE TOOL (AGENT'S CAPABILITIES) ---

def query_database(collection_name: str, limit: int = 5) -> str:
    """
    Queries either the 'measurements' or 'traffic_data' collection in MongoDB
    and returns a specified number of documents.
    """
    print(f"🔎 TOOL: Querying '{collection_name}' with limit={limit}...")
    try:
        collection = db[collection_name]
        documents = list(collection.find({}).limit(limit))

        if not documents:
            return json.dumps({"message": "No documents found."})

        # Convert MongoDB's ObjectId to a simple string for JSON
        for doc in documents:
            if '_id' in doc:
                doc['_id'] = str(doc['_id'])
        
        return json.dumps(documents)
    except Exception as e:
        return json.dumps({"error": str(e)})


# --- 3. DEFINE THE AGENT'S PROMPT AND TOOL "MENU" ---

tools_list = [
    {
        "type": "function",
        "function": {
            "name": "query_database",
            "description": "Get data from the traffic database. You must specify which collection to query: 'measurements' or 'traffic_data'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "collection_name": {
                        "type": "string",
                        "description": "The collection to query.",
                        "enum": ["measurements", "traffic_data"]
                    },
                    "limit": {
                        "type": "integer",
                        "description": "The maximum number of records to return. Defaults to 5."
                    }
                },
                "required": ["collection_name"]
            }
        }
    }
]

ASSISTANT_PROMPT = (
    "You are a helpful data analyst. Your task is to answer user questions by "
    "querying the 'measurements' or 'traffic_data' collections in the database using "
    "the `query_database` tool. Be concise."
)

# --- 4. MAIN APPLICATION LOGIC ---

def main():
    print("\n--- Initializing Local Agent with Ollama ---")

    # The Assistants API is simulated here with a standard Chat Completion call
    # because Ollama doesn't fully support the Assistants API state management (threads, runs).
    # We will manage the conversation history ourselves.
    
    messages = [{"role": "system", "content": ASSISTANT_PROMPT}]
    
    print("\n✅ Local agent is ready! Type 'exit' to quit.")
    print("---")

    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            break

        messages.append({"role": "user", "content": user_input})

        # First API call to see if a tool is needed
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools_list,
            tool_choice="auto",
        )
        response_message = response.choices[0].message

        # Check if the model wants to call a tool
        if response_message.tool_calls:
            print("🤖 Agent decided to use a tool...")
            tool_call = response_message.tool_calls[0]
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)

            # Call the local tool function
            if function_name == "query_database":
                function_response = query_database(
                    collection_name=arguments.get("collection_name"),
                    limit=arguments.get("limit", 5)
                )

                # Append the tool's response to the conversation history
                messages.append(response_message) # The assistant's decision to call the tool
                messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": function_response,
                    }
                )

                # Make a second API call with the tool's output
                final_response = client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                )
                print(f"Assistant: {final_response.choices[0].message.content}")
                messages.append(final_response.choices[0].message)
            
        else:
            # If no tool is needed, just print the response
            print(f"Assistant: {response_message.content}")
            messages.append(response_message)

if __name__ == "__main__":
    main()
