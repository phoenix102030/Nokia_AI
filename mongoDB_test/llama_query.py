#!/usr/bin/env python3
import sys
import ast
import json
from pymongo import MongoClient
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import ChatOllama

PIPELINE_PROMPT = PromptTemplate.from_template(
    """
You are a MongoDB expert.

The collection is named "traffic_data" and each document has:
- location (string): The name of the junction or intersection.
- timestamp (string)
- count (integer): The number of vehicles recorded.

INSTRUCTIONS:
1.  **Count Vehicles Correctly**: To count vehicles, you MUST sum the "count" field (`{{"$sum": "$count"}}`). Do not count documents (`{{"$sum": 1}}`).
2.  **Filter Locations Correctly**: Any filtering on location names (like "junction", "road", etc.) MUST be applied to the "location" field. The filter must be case-insensitive.
    -   CORRECT   Example: `{{"$match": {{ "location": {{ "$regex": "some junction", "$options": "i" }} }} }}`
    -   INCORRECT Example: `{{"$match": {{ "$regex": "some junction", "$options": "i" }} }}`

Write **one** MongoDB aggregation pipeline (as a valid Python list of dicts) to answer the following question:

QUESTION:
{question}

Output **only** the Python list—no extra text.
"""
)

def run_pipeline_and_print(uri: str, pipeline):
    """
    Connects to MongoDB, runs the aggregation pipeline, and prints the result.
    """
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command('ismaster')
        coll   = client.traffic_db.traffic_data
        result = list(coll.aggregate(pipeline))
        client.close()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f":( Failed to run pipeline: {e}")


def ask_question(db_uri: str, question: str):
    """
    Uses an LLM to generate a MongoDB pipeline from a question,
    then executes it.
    """
    llm   = ChatOllama(model="llama3.2", temperature=0.0)
    chain = PIPELINE_PROMPT | llm | StrOutputParser()
    
    pipeline_str = chain.invoke({"question": question}).strip()

    print(":) Generated Pipeline (Robust Logic):\n", pipeline_str)

    try:
        # The double braces in the prompt might confuse the LLM, so we clean the output
        if pipeline_str.startswith("`") and pipeline_str.endswith("`"):
            pipeline_str = pipeline_str.strip('`')
        pipeline = ast.literal_eval(pipeline_str)
        if not isinstance(pipeline, list):
            raise ValueError("Pipeline is not a Python list")
    except Exception as e:
        print(":( Failed to parse pipeline:", e)
        print("Raw LLM output:\n", pipeline_str)
        return

    run_pipeline_and_print(db_uri, pipeline)

if __name__ == "__main__":
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print('Usage: python query_mongo.py "Your question here"')
        sys.exit(1)

    MONGO_URI = "mongodb://localhost:27017/"
    ask_question(MONGO_URI, sys.argv[1])