# tools.py
# Final version of the data analysis tools with smarter, more flexible functions.

import os
import json
from bson import ObjectId
import motor.motor_asyncio
import pandas as pd
import numpy as np
from datetime import datetime

# Required libraries: pip install "pandas" "numpy" "matplotlib" "seaborn"
import matplotlib.pyplot as plt
import seaborn as sns

# --- 1. SETUP: DATABASE CONNECTION ---
MONGO_URI = os.getenv("MCP_MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = "traffic_data" 

try:
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    print(f"✅ Tools: Successfully connected to MongoDB at {MONGO_URI}")
except Exception as e:
    print(f"❌ Tools ERROR: Could not connect to MongoDB. Details: {e}")
    db = None

# --- Helper Function for JSON serialization ---
def json_encoder(obj):
    """Custom JSON encoder to handle special data types from MongoDB and numpy."""
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (datetime, pd.Timestamp)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


# --- 2. TOOL SCHEMAS (The "Manual" for the LLM) ---
AVAILABLE_TOOLS_SCHEMA = [
    {
        "name": "get_daily_traffic_profile",
        "description": "Calculates the typical hourly profile for a metric (e.g., speed, density) for a specific lane, automatically separating results by Weekday and Weekend. This is the best tool for understanding typical daily patterns or peak times.",
        "parameters": {
            "type": "object",
            "properties": {
                "lane_id": {
                    "type": "string",
                    "description": "The specific lane_id to analyze from the 'lane_data' collection, e.g., ':13445139_0'."
                },
                "metric_field": {
                    "type": "string",
                    "description": "The measurement field to analyze, e.g., 'speed', 'density'."
                }
            },
            "required": ["lane_id", "metric_field"]
        }
    },
    {
        "name": "plot_time_series",
        "description": "Generates and saves a line plot of a specific metric over a time range for a given ID. If no time range is given, it plots all available data. Returns the file path of the saved image.",
        "parameters": {
            "type": "object",
            "properties": {
                "collection_name": {"type": "string", "enum": ["lane_data", "measurements"]},
                "metric_field": {"type": "string", "description": "The numeric field to plot, e.g., 'speed', 'flow'."},
                "id_value": {"type": "string", "description": "The specific lane_id or source_id to filter by."},
                "start_time": {"type": "string", "description": "Optional start of the time window in ISO format."},
                "end_time": {"type": "string", "description": "Optional end of the time window in ISO format."}
            },
            "required": ["collection_name", "metric_field", "id_value"]
        }
    },
    {
        "name": "get_descriptive_stats",
        "description": "Calculates descriptive statistics for a metric. If no time range is given, it analyzes all data for that ID. Use 'lane_data' for lanes or 'measurements' for detectors.",
        "parameters": {
            "type": "object",
            "properties": {
                "collection_name": {"type": "string", "enum": ["lane_data", "measurements"]},
                "metric_field": {"type": "string", "description": "The field to analyze, e.g., 'speed', 'density', 'count'."},
                "id_value": {"type": "string", "description": "The specific lane_id or source_id to filter by."},
                "start_time": {"type": "string", "description": "Optional start of the time window in ISO format."},
                "end_time": {"type": "string", "description": "Optional end of the time window in ISO format."}
            },
            "required": ["collection_name", "metric_field", "id_value"]
        }
    }
]

# --- 3. TOOL IMPLEMENTATIONS (The Actual Python Code) ---

async def _fetch_data_as_dataframe(collection_name: str, filter_query: dict) -> pd.DataFrame | None:
    """Helper function to fetch data and convert it to a pandas DataFrame."""
    if db is None: return None
    collection = db[collection_name]
    cursor = collection.find(filter_query)
    documents = await cursor.to_list(length=None)
    if not documents:
        return pd.DataFrame()
    df = pd.json_normalize(documents)
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    return df

async def get_daily_traffic_profile(lane_id: str, metric_field: str) -> str:
    """Analyzes the entire dataset for a lane to build a typical weekday/weekend profile."""
    print(f"🛠️ Executing 'get_daily_traffic_profile' for lane '{lane_id}' on metric '{metric_field}'")
    full_metric_field = f"measurement.{metric_field}"
    
    # Fetch ALL data for the given lane, with no time filter
    df = await _fetch_data_as_dataframe("lane_data", {"metadata.lane_id": lane_id})
    
    if df is None or df.empty:
        return json.dumps({"error": f"No data found for lane_id '{lane_id}'."})
    if full_metric_field not in df.columns:
        return json.dumps({"error": f"Metric '{metric_field}' not found."})

    # Add columns for hour of day and day type (Monday=0, Sunday=6)
    df['hour'] = df.index.hour
    df['day_type'] = np.where(df.index.dayofweek < 5, 'Weekday', 'Weekend')

    # Group by day type and hour, then calculate the mean of the metric
    profile = df.groupby(['day_type', 'hour'])[full_metric_field].mean().unstack(level=0)
    
    result_dict = profile.to_dict()
    print(f"   -> Successfully generated profile.")
    return json.dumps(result_dict, default=json_encoder)

async def get_descriptive_stats(collection_name: str, metric_field: str, id_value: str, start_time: str = None, end_time: str = None) -> str:
    """Calculates descriptive statistics. If start/end times are None, analyzes the whole dataset for the ID."""
    print(f"🛠️ Executing 'get_descriptive_stats' for ID '{id_value}' on metric '{metric_field}'")
    id_field = "metadata.source_id" if collection_name == "measurements" else "metadata.lane_id"
    full_metric_field = f"measurement.{metric_field}"
    
    filter_query = {id_field: id_value}
    if start_time and end_time:
        filter_query["timestamp"] = {"$gte": start_time, "$lte": end_time}
    
    df = await _fetch_data_as_dataframe(collection_name, filter_query)
    
    if df is None or df.empty:
        return json.dumps({"error": "No data found for the specified criteria."})
    if full_metric_field not in df.columns:
        return json.dumps({"error": f"Metric '{metric_field}' not found in '{collection_name}'."})

    stats = df[full_metric_field].describe(percentiles=[.05, .25, .5, .75, .95]).to_dict()
    return json.dumps(stats, default=json_encoder)

async def plot_time_series(collection_name: str, metric_field: str, id_value: str, start_time: str = None, end_time: str = None) -> str:
    """Generates a plot and returns the file path."""
    print(f"🛠️ Executing 'plot_time_series' for ID '{id_value}' on metric '{metric_field}'")
    id_field = "metadata.source_id" if collection_name == "measurements" else "metadata.lane_id"
    full_metric_field = f"measurement.{metric_field}"
    
    filter_query = {id_field: id_value}
    if start_time and end_time:
        filter_query["timestamp"] = {"$gte": start_time, "$lte": end_time}
        
    df = await _fetch_data_as_dataframe(collection_name, filter_query)
    
    if df is None or df.empty:
        return json.dumps({"error": "No data found to plot."})
    if full_metric_field not in df.columns:
        return json.dumps({"error": f"Metric '{metric_field}' not found."})

    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(12, 6))
    df[full_metric_field].plot(ax=ax, marker='o', linestyle='-')
    ax.set_title(f'Time Series for {metric_field.title()} on ID: {id_value}')
    ax.set_xlabel("Timestamp")
    ax.set_ylabel(metric_field.title())
    ax.tick_params(axis='x', rotation=45)
    fig.tight_layout()

    plots_dir = "plots"
    if not os.path.exists(plots_dir):
        os.makedirs(plots_dir)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(plots_dir, f"{metric_field}_{id_value.replace(':', '')}_{timestamp_str}.png")
    fig.savefig(file_path)
    plt.close(fig)
    print(f"   -> Plot saved to: {file_path}")
    
    return json.dumps({"status": "success", "plot_path": file_path})

# --- 4. TOOL MAPPING ---
# This dictionary maps the string names to the actual Python functions.
TOOL_IMPLEMENTATIONS = {
    "get_daily_traffic_profile": get_daily_traffic_profile,
    "plot_time_series": plot_time_series,
    "get_descriptive_stats": get_descriptive_stats,
}