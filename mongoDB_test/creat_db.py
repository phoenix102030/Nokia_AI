from pymongo import MongoClient

def create_and_populate_mongo_db(connection_string: str = "mongodb://localhost:27017/") -> None:
    """
    Connects to MongoDB, creates a database and collection,
    and populates it with sample traffic data.
    """
    client = MongoClient(connection_string)
    db = client.traffic_db  
    collection = db.traffic_data 
    collection.drop()

    # Insert sample data
    rows = [
        {"location": "Junction A", "timestamp": "2025-05-14 08:00:00", "count": 120},
        {"location": "Junction B", "timestamp": "2025-05-14 08:05:00", "count": 85},
        {"location": "Junction C", "timestamp": "2025-05-14 08:10:00", "count": 95},
    ]
    collection.insert_many(rows)

    print("Database 'traffic_db' and collection 'traffic_data' created and populated.")
    client.close()

if __name__ == "__main__":
    create_and_populate_mongo_db()