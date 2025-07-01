# mcp-server/seed_data.py
# A Python script to seed the database with your JSON data.
# Run with: uv run python seed_data.py

import motor.motor_asyncio
import os
import json
import asyncio
from dotenv import load_dotenv

# Load environment variables from the .env file in the same directory
load_dotenv()

# --- Configuration ---
# Get the MongoDB connection string from the environment, with a default value
MONGO_URI = os.getenv("MCP_MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = "traffic_data"

# Construct the full paths to your data files, assuming they are in the root of the project
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANE_DATA_PATH = os.path.join(project_root, 'lane_data.json')
MEASUREMENTS_PATH = os.path.join(project_root, 'measurements.json')

async def seed_collection(collection_name, file_path):
    """
    Connects to the DB, drops the old collection, and inserts new data from a JSON file.
    
    Args:
        collection_name (str): The name of the collection to seed.
        file_path (str): The absolute path to the JSON data file.
    """
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[collection_name]
    
    print(f"--- Seeding '{collection_name}' ---")
    
    try:
        if not os.path.exists(file_path):
            print(f"❌ Error: Data file not found at {file_path}")
            return
            
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Drop the collection if it exists to ensure a clean slate
        await collection.drop()
        print(f"🧹 Dropped old '{collection_name}' collection.")

        # Insert the new data
        if data:
            result = await collection.insert_many(data)
            print(f"🌱 Inserted {len(result.inserted_ids)} documents into '{DB_NAME}.{collection_name}'.")
        else:
            print("⚠️ Data file is empty. Nothing to insert.")

    except Exception as e:
        print(f"❌ An error occurred while seeding '{collection_name}': {e}")
    finally:
        client.close()

async def main():
    """Runs the seeding process for all data files."""
    await seed_collection("lane_data", LANE_DATA_PATH)
    await seed_collection("measurements", MEASUREMENTS_PATH)

if __name__ == "__main__":
    print("Starting database seeding process...")
    # This runs the main asynchronous function
    asyncio.run(main())
    print("Seeding process complete.")
