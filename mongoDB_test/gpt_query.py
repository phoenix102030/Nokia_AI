#!/usr/bin/env python3
import sys
import os
import ast
import json
from pymongo import MongoClient
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量（特别是 OPENAI_API_KEY）
load_dotenv()

# 这个平衡的提示对于像 GPT-4o 这样的高级模型来说效果很好
PIPELINE_PROMPT = PromptTemplate.from_template(
    """
You are an expert MongoDB data analyst. Your sole purpose is to write a single, valid MongoDB aggregation pipeline (as a Python list of dicts) to answer the user's question.

Use the "traffic_data" collection. Pay close attention to these rules:
1.  **To count vehicles, you MUST sum the `count` field.** The correct operation is `{{"$sum": "$count"}}`.
2.  **Location matching MUST be case-insensitive.** Use a regex for this.
3.  **To count categories** (like "how many junctions"), you MUST count the distinct values. A correct pipeline would first `$group` by the `location` field, and then use `$count`.

QUESTION:
{question}

Return only the raw Python list of dicts. Do not add any other text, comments, or explanations.
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
        print(f"🛑 Failed to run pipeline: {e}")


def ask_question(db_uri: str, question: str):
    """
    Uses GPT-4o to generate a MongoDB pipeline from a question,
    then executes it.
    """
    # 检查 API 密钥是否已设置
    if not os.getenv("OPENAI_API_KEY"):
        print("🛑 Error: OPENAI_API_KEY environment variable not set.")
        print("Please create a .env file and add your key.")
        return

    # 将 ChatOllama 替换为 ChatOpenAI，并指定 gpt-4o 模型
    try:
        llm = ChatOpenAI(model="gpt-4o", temperature=0.0)
    except Exception as e:
        print(f"🛑 Failed to initialize the language model: {e}")
        return
        
    chain = PIPELINE_PROMPT | llm | StrOutputParser()
    
    pipeline_str = chain.invoke({"question": question}).strip()

    print("🤖 Generated Pipeline (by GPT-4o):\n", pipeline_str)

    try:
        # 清理模型可能返回的 markdown 代码块标记
        if pipeline_str.startswith("```python"):
            pipeline_str = pipeline_str[len("```python"):].strip()
        if pipeline_str.startswith("```"):
            pipeline_str = pipeline_str[3:].strip()
        if pipeline_str.endswith("```"):
            pipeline_str = pipeline_str[:-3].strip()

        pipeline = ast.literal_eval(pipeline_str)
        if not isinstance(pipeline, list):
            raise ValueError("Pipeline is not a Python list")
    except Exception as e:
        print("🛑 Failed to parse pipeline:", e)
        print("Raw LLM output:\n", pipeline_str)
        return

    run_pipeline_and_print(db_uri, pipeline)

if __name__ == "__main__":
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print('Usage: python query_mongo.py "Your question here"')
        sys.exit(1)

    MONGO_URI = "mongodb://localhost:27017/"
    ask_question(MONGO_URI, sys.argv[1])