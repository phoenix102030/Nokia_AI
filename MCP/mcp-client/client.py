# mcp-client/client.py
# This script uses a local LLM to process natural language and call tools
# on the running FastMCP server.

import asyncio
import os
import sys
import json
import re
import ast  # Import the Abstract Syntax Tree module for safe parsing
from dotenv import load_dotenv
from fastmcp.client import Client
from mcp.types import TextContent
from openai import OpenAI

# Allow importing from the parent directory to access the 'shared' folder
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "shared"))
from tools import AVAILABLE_TOOLS_SCHEMA, TOOL_IMPLEMENTATIONS

# --- Configuration ---
load_dotenv()
FMC_SERVER_URL = os.getenv("MCP_SERVER_URL")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

if not all([FMC_SERVER_URL, OLLAMA_BASE_URL, OLLAMA_MODEL]):
    raise ValueError(
        "Please check MCP_SERVER_URL, OLLAMA_BASE_URL, and OLLAMA_MODEL in your .env file."
    )

# --- System Prompt (Modified for Clarity and Reliability) ---
SYSTEM_PROMPT = f"""
You are an expert agent that translates a user's natural language request into a specific tool call OR provides a direct answer.

- If the user’s request can be answered directly (e.g., a greeting, asking about your capabilities), your response should be **only the natural language answer itself**.
- Otherwise, your response must be **only a single tool call** in the format: tool_name(argument_name="argument_value", ...)

**Do not include any other text, think, explanation, or markdown formatting in your response.**

--- AVAILABLE TOOLS ---
{json.dumps(AVAILABLE_TOOLS_SCHEMA, indent=2, ensure_ascii=False)}

--- EXAMPLES ---
User request: "hi, what can you do?"
Your response: I can list MongoDB databases, collections or query documents on your behalf. Just ask me a query.

User request: "how many collections are in the traffic_data database?"
Your response: list_collections(database_name="traffic_data")

User request: "count the records in the lane_data collection in the traffic_data database"
Your response: find(database_name="traffic_data", collection_name="lane_data", filter={{}}, limit=0)
--- END EXAMPLES ---
"""


# --- Client Initialization ---
fastmcp_client = Client(FMC_SERVER_URL)
ollama_client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")


def parse_llm_tool_call(response_str: str) -> dict:
    try:
        match = re.match(r"(\w+)\((.*)\)", response_str.strip())
        if not match:
            return {
                "tool_name": "error",
                "arguments": {"message": "Invalid tool call format from LLM."},
            }

        tool_name = match.group(1)
        args_str = match.group(2)
        arguments = {}

        if args_str:
            # This regex correctly finds key=value pairs, even with nested structures.
            arg_pairs = re.findall(
                r'(\w+)\s*=\s*({.*?}|".*?"|\'.*?\'|[\d.-]+)', args_str
            )
            for key, value in arg_pairs:
                # ast.literal_eval safely converts the string representation of a Python
                # literal into the actual object.
                arguments[key.strip()] = ast.literal_eval(value)

        return {"tool_name": tool_name, "arguments": arguments}
    except Exception as e:
        return {
            "tool_name": "error",
            "arguments": {
                "message": f"Failed to parse tool call string: '{response_str}'. Error: {e}"
            },
        }


def get_clean_response(response: list) -> str:
    if not response or not isinstance(response[0], TextContent):
        return "Received an unexpected response format."
    content = response[0].text
    try:
        parsed_json = json.loads(content)
        return json.dumps(parsed_json, indent=2, ensure_ascii=False)
    except json.JSONDecodeError:
        return content


async def process_natural_language_query(user_query: str):
    print("\n🧠 Asking AI Agent to decide which tool to use...")
    try:
        response = ollama_client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_query},
            ],
            temperature=0.0,
        )
        full_llm_output = response.choices[0].message.content.strip()
        print(f"💡 LLM raw output:\n{full_llm_output}")

        cleaned_output = re.sub(
            r"<think>.*?</think>", "", full_llm_output, flags=re.DOTALL
        ).strip()

        # Try to find a tool call anywhere in the response
        tool_call_match = re.search(r"\w+\(.*\)", full_llm_output, re.DOTALL)

        # *** MODIFIED LOGIC: Handle both direct answers and tool calls ***
        if not tool_call_match:
            # If no tool call is found, assume it's a direct answer and print it.
            print(f"🤖 Agent Response:\n{cleaned_output}")
            return  # Successfully handled, so we exit the function.

        # If a tool call WAS found, proceed with extraction and execution.
        tool_call_str = tool_call_match.group(0)
        print(f"✅ Extracted tool call: {tool_call_str}")

        tool_call = parse_llm_tool_call(tool_call_str)
        tool_name = tool_call.get("tool_name")
        arguments = tool_call.get("arguments", {})

        if not tool_name or tool_name == "error":
            error_message = arguments.get(
                "message", "Could not decide which tool to use or failed to parse arguments."
            )
            print(f"🤖 Agent Response: {error_message}")
            return

        if tool_name == "no_op":
            no_op_response = await TOOL_IMPLEMENTATIONS["no_op"](**arguments)
            clean_result = get_clean_response([TextContent(text=no_op_response)])
            print(f"🤖 Agent Response:\n{clean_result}")
        elif tool_name in TOOL_IMPLEMENTATIONS:
            print(f"🛠️ Executing tool '{tool_name}' on FastMCP server...")
            server_response = await fastmcp_client.call_tool(tool_name, arguments)
            clean_result = get_clean_response(server_response)
            print(f"🤖 Final Result:\n{clean_result}")
        else:
            print(
                f"🤖 Agent Response: The LLM chose a tool ('{tool_name}') that is not implemented."
            )

    except Exception as e:
        print(f"\n❌ An error occurred during processing: {e}")


async def main():
    """Runs the interactive chat loop."""
    print("--- MCP Database Agent Client ---")
    print(f"Using '{OLLAMA_MODEL}' as the agent. Type 'exit' or 'quit' to end.")
    print("-" * 40)
    try:
        async with fastmcp_client:
            print("✅ Successfully connected to the MCP server.")
            while True:
                user_input = await asyncio.to_thread(input, "\n💬 You: ")
                if user_input.lower() in ["exit", "quit"]:
                    print("\n👋 Exiting. Goodbye!")
                    break
                await process_natural_language_query(user_input)
    except Exception as e:
        print(f"\n❌ A connection error occurred: {e}")
        print("   Please ensure your FastMCP server and Ollama are running.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Session ended by user.")