# toolbox.py

import json
from pymongo import MongoClient
from langchain_core.tools import tool

def _get_mongo_client():
    return MongoClient("mongodb://localhost:27017/")


@tool
def get_busiest_lanes_by_occupancy(top_n: int = 5) -> str:
    """
    Return the top N lanes from 'traffic_db' sorted by highest average occupancy.
    """
    client = _get_mongo_client()
    coll = client.traffic_db.data
    pipeline = [
        {"$group": {"_id": "$lane_id", "avg_occupancy": {"$avg": "$occupancy"}}},
        {"$sort": {"avg_occupancy": -1}},
        {"$limit": top_n}
    ]
    result = list(coll.aggregate(pipeline))
    client.close()
    return json.dumps(result) if result else "No lane occupancy data found."

@tool
def get_lanes_with_most_traffic(top_n: int = 5) -> str:
    """
    Return the top N lanes from 'traffic_db' that had the most vehicles enter.
    """
    client = _get_mongo_client()
    coll = client.traffic_db.data
    pipeline = [
        {"$group": {"_id": "$lane_id", "total_entered": {"$sum": "$entered"}}},
        {"$sort": {"total_entered": -1}},
        {"$limit": top_n}
    ]
    result = list(coll.aggregate(pipeline))
    client.close()
    return json.dumps(result) if result else "No lane traffic data found."

@tool
def get_total_vehicles_entered() -> str:
    """
    Return the total number of vehicles that have ever entered across all lanes in 'traffic_db'.
    """
    client = _get_mongo_client()
    coll = client.traffic_db.data
    pipeline = [
        {"$group": {"_id": None, "total_vehicles": {"$sum": "$entered"}}}
    ]
    result = list(coll.aggregate(pipeline))
    client.close()
    if result and result[0].get("total_vehicles") is not None:
        return json.dumps({"total_vehicles": result[0]["total_vehicles"]})
    else:
        return "No traffic data available."

@tool
def get_average_occupancy_by_hour(hour: int) -> str:
    """
    Return the average occupancy across all lanes for a specific hour (0–23).
    Assumes there is a 'timestamp' field in each document.
    """
    client = _get_mongo_client()
    coll = client.traffic_db.data
    pipeline = [
        {"$addFields": {"hour": {"$hour": "$timestamp"}}},
        {"$match": {"hour": hour}},
        {"$group": {"_id": None, "avg_occupancy": {"$avg": "$occupancy"}}}
    ]
    result = list(coll.aggregate(pipeline))
    client.close()
    if result and result[0].get("avg_occupancy") is not None:
        return json.dumps({"hour": hour, "avg_occupancy": result[0]["avg_occupancy"]})
    else:
        return f"No occupancy data found for hour {hour}."

# --------------------------------------
# Tools for measurements_db
# --------------------------------------

@tool
def get_average_speed_for_sensor(sensor_id: str) -> str:
    """
    Return the average speed recorded by a specific sensor ID from 'measurements_db'.
    """
    client = _get_mongo_client()
    coll = client.measurements_db.data
    pipeline = [
        {"$match": {"sensor_id": sensor_id}},
        {"$group": {"_id": "$sensor_id", "average_speed": {"$avg": "$speed"}}}
    ]
    result = list(coll.aggregate(pipeline))
    client.close()
    return json.dumps(result) if result else f"No data found for sensor_id {sensor_id}."

@tool
def get_sensors_with_highest_flow(top_n: int = 5) -> str:
    """
    Return the top N sensors (from 'measurements_db') with the highest average traffic flow.
    """
    client = _get_mongo_client()
    coll = client.measurements_db.data
    pipeline = [
        {"$group": {"_id": "$sensor_id", "average_flow": {"$avg": "$flow"}}},
        {"$sort": {"average_flow": -1}},
        {"$limit": top_n}
    ]
    result = list(coll.aggregate(pipeline))
    client.close()
    return json.dumps(result) if result else "No sensor flow data found."

@tool
def get_sensor_data_in_time_range(sensor_id: str, start_ts: str, end_ts: str) -> str:
    """
    Return all records for a given sensor_id in 'measurements_db' 
    between start_ts and end_ts (ISO-8601 strings).
    """
    from datetime import datetime
    client = _get_mongo_client()
    coll = client.measurements_db.data

    # Parse timestamps
    try:
        start = datetime.fromisoformat(start_ts)
        end = datetime.fromisoformat(end_ts)
    except Exception as e:
        client.close()
        return f"Error parsing timestamps: {e}"

    query = {
        "sensor_id": sensor_id,
        "timestamp": {"$gte": start, "$lte": end}
    }
    cursor = coll.find(query)
    data = list(cursor)
    client.close()

    if not data:
        return f"No data found for sensor {sensor_id} between {start_ts} and {end_ts}."
    # Convert BSON documents to JSON-friendly
    for doc in data:
        doc["_id"] = str(doc["_id"])
        doc["timestamp"] = doc["timestamp"].isoformat()
    return json.dumps(data)

@tool
def get_peak_flow_time() -> str:
    """
    Return the timestamp at which the overall average flow (across all sensors) was highest.
    Assumes each document has 'flow' and 'timestamp'.
    """
    from datetime import datetime
    client = _get_mongo_client()
    coll = client.measurements_db.data

    pipeline = [
        {
            "$group": {
                "_id": "$timestamp",
                "avg_flow": {"$avg": "$flow"}
            }
        },
        {"$sort": {"avg_flow": -1}},
        {"$limit": 1}
    ]
    result = list(coll.aggregate(pipeline))
    client.close()

    if result:
        peak_ts = result[0]["_id"]
        avg_flow = result[0]["avg_flow"]
        # Convert datetime to ISO
        if isinstance(peak_ts, datetime):
            peak_ts_str = peak_ts.isoformat()
        else:
            peak_ts_str = str(peak_ts)
        return json.dumps({"peak_timestamp": peak_ts_str, "avg_flow": avg_flow})
    else:
        return "No flow data available."
