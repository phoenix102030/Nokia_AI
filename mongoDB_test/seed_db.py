# seed_db.py
# This script connects to MongoDB and populates it with data from local JSON files.

import os
import json
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# --- Configuration ---
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "nokia_traffic_data"  # A more descriptive database name

# Define the data files and the collections they will map to.
# This assumes you run the script from the 'Nokia_AI' folder.
FILES_TO_LOAD = {
    "measurements": os.path.join("mongoDB_test", "data", "measurements.json"),
    "traffic_data": os.path.join("mongoDB_test", "data", "traffic_data.json")
}

def seed_database_from_files():
    """
    Connects to MongoDB, reads local JSON files, and inserts their data
    into new collections.
    """
    client = None  # Initialize client to None for the finally block
    try:
        # Establish a connection to the MongoDB server.
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.server_info()
        print("✅ Successfully connected to MongoDB.")

        db = client[DB_NAME]

        # Loop through the files defined in our configuration
        for collection_name, file_path in FILES_TO_LOAD.items():
            print(f"\n--- Processing {file_path} ---")

            # Check if the file exists before trying to open it
            if not os.path.exists(file_path):
                print(f"❌ ERROR: File not found at '{file_path}'. Please check the path.")
                continue

            # Get a handle to the collection
            collection = db[collection_name]

            # Clear any old data from the collection
            print(f"Clearing old data from '{collection_name}' collection...")
            collection.delete_many({})

            # Open the JSON file and load its content
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    print(f"Successfully loaded data from {file_path}.")
                except json.JSONDecodeError as e:
                    print(f"❌ ERROR: Could not decode JSON from {file_path}. Is it a valid JSON file? Details: {e}")
                    continue

            # Important: Check if the loaded data is a list of documents
            # or a single document that contains a list (like your example).
            if isinstance(data, dict) and 'measurements' in data:
                # This handles the structure from your first example { "measurements": [...] }
                records_to_insert = data['measurements']
            elif isinstance(data, list):
                # This handles a file that is just a JSON array [...]
                records_to_insert = data
            else:
                print(f"❌ ERROR: JSON in {file_path} is not in a recognized format (expected a list of objects or a dict with a 'measurements' key).")
                continue
                
            # Insert the data into the collection
            if records_to_insert:
                print(f"Inserting {len(records_to_insert)} documents into '{collection_name}'...")
                collection.insert_many(records_to_insert)
                print(f"✅ Successfully seeded '{collection_name}'.")
            else:
                print(f"No records found to insert for '{collection_name}'.")


    except ConnectionFailure as e:
        print(f"❌ MongoDB Connection Error: {e}")
        print("   Please ensure your MongoDB Docker container or Windows service is running.")

    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")

    finally:
        # Ensure the connection to the database is closed
        if client:
            client.close()
            print("\nConnection to MongoDB closed.")

# This line ensures the main function is called when you run the script
if __name__ == "__main__":
    seed_database_from_files()

