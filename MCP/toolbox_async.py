import json
import inspect
from datetime import datetime, time
from typing import Any, Dict, List, Literal, Optional
from motor.motor_asyncio import AsyncIOMotorClient

# ─── Registry & Decorator ────────────────────────────────────────────────────────

_toolbox_registry: Dict[str, Dict] = {}

def tool(name: str, description: str):
    """Decorator: register this async function as an MCP tool."""
    def decorator(func):
        _toolbox_registry[name] = {
            "function": func,
            "name": name,
            "description": description,
            "parameters": inspect.signature(func).parameters
        }
        return func
    return decorator

# ─── JSON Serializer for datetime/time ───────────────────────────────────────────

def json_serializer(obj):
    if isinstance(obj, (datetime, time)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

# ─── Helper: Pick the correct collection ─────────────────────────────────────────

async def _get_collection_for_tool(
    db_client: AsyncIOMotorClient,
    func_name: str
):
    # Any tool dealing with sensors/flow → measurements_db.data
    if any(k in func_name for k in ("sensor", "flow")):
        return db_client.measurements_db.data
    # All others → traffic_db.data
    return db_client.traffic_db.data

def _validate_top_n(val: Any, default: int = 5) -> int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return default

# ─── 1) Meta-Tool: List all tools ────────────────────────────────────────────────

@tool(
    name="list_available_tools",
    description="Returns a JSON-encoded list of all available tools (name, description, parameters)."
)
async def list_available_tools(
    db_client: AsyncIOMotorClient
) -> str:
    tools: List[Dict[str, Any]] = []
    for name, data in _toolbox_registry.items():
        params = []
        for p_name, p_obj in data["parameters"].items():
            if p_name == "db_client":
                continue
            ann = p_obj.annotation
            p_type = getattr(ann, "__name__", str(ann))
            default = (
                p_obj.default
                if p_obj.default is not inspect.Parameter.empty
                else "REQUIRED"
            )
            params.append({"name": p_name, "type": p_type, "default": default})
        tools.append({
            "name": name,
            "description": data["description"],
            "parameters": params
        })
    return json.dumps(tools, indent=2)

# ─── 2) Aggregation & Ranking Tools ─────────────────────────────────────────────

Metric = Literal["occupancy", "density", "speed", "entered", "waiting_time"]
SortOrder = Literal["highest", "lowest"]
VALID_METRICS = ["occupancy", "density", "speed", "entered", "waiting_time"]

@tool(
    name="get_lanes_by_metric",
    description="Ranks lanes by a metric (occupancy, speed, density, entered, waiting_time)."
)
async def get_lanes_by_metric(
    db_client: AsyncIOMotorClient,
    metric: Metric,
    order: SortOrder = "highest",
    top_n: int = 5
) -> str:
    if metric not in VALID_METRICS:
        return json.dumps({"error": f"Invalid metric '{metric}'. Must be one of {VALID_METRICS}."})
    limit = _validate_top_n(top_n)
    coll = await _get_collection_for_tool(db_client, "get_lanes_by_metric")
    pipeline = [
        {"$group": {"_id": "$lane_id", f"avg_{metric}": {"$avg": f"${metric}"}}},
        {"$sort": {f"avg_{metric}": -1 if order=="highest" else 1}},
        {"$limit": limit}
    ]
    result = await coll.aggregate(pipeline).to_list(length=limit)
    if not result:
        return json.dumps({"message": f"No data for metric '{metric}'."})
    return json.dumps({"data": result}, default=json_serializer)

@tool(
    name="get_sensors_with_highest_flow",
    description="Top N sensors by average flow (measurements_db)."
)
async def get_sensors_with_highest_flow(
    db_client: AsyncIOMotorClient,
    top_n: int = 5
) -> str:
    limit = _validate_top_n(top_n)
    coll = await _get_collection_for_tool(db_client, "get_sensors_with_highest_flow")
    pipeline = [
        {"$group": {"_id": "$sensor_id", "average_flow": {"$avg": "$flow"}}},
        {"$sort": {"average_flow": -1}},
        {"$limit": limit}
    ]
    result = await coll.aggregate(pipeline).to_list(length=limit)
    if not result:
        return json.dumps({"message": "No sensor flow data found."})
    return json.dumps({"data": result}, default=json_serializer)

@tool(
    name="get_peak_traffic_times",
    description="Find time intervals (timestamps) with highest total flow."
)
async def get_peak_traffic_times(
    db_client: AsyncIOMotorClient,
    top_n: int = 5
) -> str:
    limit = _validate_top_n(top_n)
    coll = await _get_collection_for_tool(db_client, "get_peak_traffic_times")
    pipeline = [
        {"$group": {"_id": "$timestamp", "total_flow": {"$sum": "$flow"}}},
        {"$sort": {"total_flow": -1}},
        {"$limit": limit}
    ]
    result = await coll.aggregate(pipeline).to_list(length=limit)
    if not result:
        return json.dumps({"message": "No traffic flow data found."})
    return json.dumps({"data": result}, default=json_serializer)

# ─── 3) Detailed Summaries & Averages ──────────────────────────────────────────

@tool(
    name="summarize_lane_activity",
    description="Summary for a lane: total entered, avg speed, avg occupancy, total waiting time, data points."
)
async def summarize_lane_activity(
    db_client: AsyncIOMotorClient,
    lane_id: str
) -> str:
    coll = await _get_collection_for_tool(db_client, "summarize_lane_activity")
    pipeline = [
        {"$match": {"lane_id": lane_id}},
        {"$group": {
            "_id": "$lane_id",
            "total_entered": {"$sum": "$entered"},
            "avg_speed": {"$avg": "$speed"},
            "avg_occupancy": {"$avg": "$occupancy"},
            "total_waiting_time": {"$sum": "$waiting_time"},
            "data_points": {"$sum": 1}
        }}
    ]
    result = await coll.aggregate(pipeline).to_list(length=1)
    if not result:
        return json.dumps({"message": f"No data for lane '{lane_id}'."})
    return json.dumps({"data": result[0]}, default=json_serializer)

@tool(
    name="get_average_flow_by_hour",
    description="Average flow for a given hour (0–23)."
)
async def get_average_flow_by_hour(
    db_client: AsyncIOMotorClient,
    hour: int
) -> str:
    if not 0 <= hour <= 23:
        return json.dumps({"error": "Hour must be between 0 and 23."})
    coll = await _get_collection_for_tool(db_client, "get_average_flow_by_hour")
    pipeline = [
        {"$addFields": {"ts_date": {"$toDate": "$timestamp"}}},
        {"$addFields": {"hour_of_day": {"$hour": "$ts_date"}}},
        {"$match": {"hour_of_day": hour}},
        {"$group": {"_id": hour, "avg_flow": {"$avg": "$flow"}}}
    ]
    result = await coll.aggregate(pipeline).to_list(length=1)
    if not result:
        return json.dumps({"message": f"No flow data for hour {hour}."})
    return json.dumps({"data": result[0]}, default=json_serializer)

@tool(
    name="get_average_speed_for_sensor",
    description="Average speed for a specific sensor_id."
)
async def get_average_speed_for_sensor(
    db_client: AsyncIOMotorClient,
    sensor_id: str
) -> str:
    coll = await _get_collection_for_tool(db_client, "get_average_speed_for_sensor")
    pipeline = [
        {"$match": {"sensor_id": sensor_id}},
        {"$group": {"_id": "$sensor_id", "avg_speed": {"$avg": "$speed"}}}
    ]
    result = await coll.aggregate(pipeline).to_list(length=1)
    if not result:
        return json.dumps({"message": f"No data for sensor '{sensor_id}'."})
    return json.dumps({"data": result[0]}, default=json_serializer)

# ─── 4) Time‐Range & Peak Queries ───────────────────────────────────────────────

@tool(
    name="get_sensor_data_in_time_range",
    description="All records for sensor_id between start_ts & end_ts (ISO format)."
)
async def get_sensor_data_in_time_range(
    db_client: AsyncIOMotorClient,
    sensor_id: str,
    start_ts: str,
    end_ts: str
) -> str:
    coll = await _get_collection_for_tool(db_client, "get_sensor_data_in_time_range")
    try:
        start = datetime.fromisoformat(start_ts)
        end = datetime.fromisoformat(end_ts)
    except Exception as e:
        return json.dumps({"error": f"Timestamp parse error: {e}"})
    pipeline = [
        {"$addFields": {"ts_date": {"$dateFromString": {"dateString": "$timestamp"}}}},
        {"$match": {"sensor_id": sensor_id, "ts_date": {"$gte": start, "$lte": end}}}
    ]
    docs = await coll.aggregate(pipeline).to_list(length=1000)
    if not docs:
        return json.dumps({"message": f"No data for sensor '{sensor_id}' in that range."})
    for d in docs:
        if "_id" in d: d["_id"] = str(d["_id"])
        if "ts_date" in d: d["ts_date"] = d["ts_date"].isoformat()
    return json.dumps({"data": docs}, default=json_serializer)

@tool(
    name="get_peak_flow_timestamp",
    description="Timestamp with the single highest average flow."
)
async def get_peak_flow_timestamp(
    db_client: AsyncIOMotorClient
) -> str:
    coll = await _get_collection_for_tool(db_client, "get_peak_flow_timestamp")
    pipeline = [
        {"$group": {"_id": "$timestamp", "avg_flow": {"$avg": "$flow"}}},
        {"$sort": {"avg_flow": -1}},
        {"$limit": 1}
    ]
    result = await coll.aggregate(pipeline).to_list(length=1)
    if not result:
        return json.dumps({"message": "No flow data available."})
    return json.dumps({"data": result[0]}, default=json_serializer)

# ─── 5) Chart‐Data Generator ────────────────────────────────────────────────────

@tool(
    name="generate_timeseries_chart_data",
    description="Chart-ready labels & datasets for a time-series metric."
)
async def generate_timeseries_chart_data(
    db_client: AsyncIOMotorClient,
    metric: Literal["speed","flow","occupancy","entered","waiting_time"],
    ids: List[str],
    start_time_iso: Optional[str] = None,
    end_time_iso: Optional[str] = None
) -> str:
    is_sensor = metric in ("speed","flow")
    coll = await _get_collection_for_tool(db_client, "generate_timeseries_chart_data")
    id_field = "sensor_id" if is_sensor else "lane_id"
    match: Dict[str, Any] = {id_field: {"$in": ids}}
    if start_time_iso and end_time_iso:
        try:
            s = datetime.fromisoformat(start_time_iso)
            e = datetime.fromisoformat(end_time_iso)
        except Exception as ex:
            return json.dumps({"error": f"Timestamp parse error: {ex}"})
        match["timestamp"] = {"$gte": s, "$lte": e}
    pipeline = [
        {"$match": match},
        {"$sort": {"timestamp": 1}},
        {"$group": {
            "_id": f"${id_field}",
            "labels": {"$push": "$timestamp"},
            "data": {"$push": f"${metric}"}
        }}
    ]
    rows = await coll.aggregate(pipeline).to_list(length=len(ids))
    if not rows:
        return json.dumps({"error":"No data for given IDs/time range."})
    labels = rows[0]["labels"]
    datasets = [{"label": r["_id"], "data": r["data"], "fill": False} for r in rows]
    chart = {"type":"line","data":{"labels":labels,"datasets":datasets}}
    return json.dumps({"chart": chart}, default=json_serializer)

# ─── 6) Count Tools ─────────────────────────────────────────────────────────────

@tool(
    name="count_all_lanes",
    description="Distinct lane count + up to 10 sample lane_ids."
)
async def count_all_lanes(
    db_client: AsyncIOMotorClient
) -> str:
    coll = await _get_collection_for_tool(db_client, "count_all_lanes")
    ids = await coll.distinct("lane_id")
    payload = {"total_lanes": len(ids), "lane_ids": ids[:10]}
    return json.dumps(payload)

@tool(
    name="count_all_sensors",
    description="Distinct sensor count + up to 10 sample sensor_ids."
)
async def count_all_sensors(
    db_client: AsyncIOMotorClient
) -> str:
    coll = await _get_collection_for_tool(db_client, "count_all_sensors")
    ids = await coll.distinct("sensor_id")
    payload = {"total_sensors": len(ids), "sensor_ids": ids[:10]}
    return json.dumps(payload)
