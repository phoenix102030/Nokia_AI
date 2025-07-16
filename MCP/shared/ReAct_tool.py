# agent_client_multistep.py
# This script uses the correct low-level MCP client to connect to the server
# and implements a ReAct loop to allow for multi-step tool use.

import asyncio
import sys
import os
import json

# --- Step 1: Fix the ModuleNotFoundError ---
# This block adds the project's source code to Python's path so it can find the 'mcp' library.
try:
    # Get the directory where this script is located.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Construct the path to the root of the 'simuapi-main-tests-mcp' project folder.
    mcp_project_path = os.path.abspath(os.path.join(script_dir, '..', '..', 'simuapi-main-tests-mcp'))
    # Add this path to the front of the list Python searches for modules.
    sys.path.insert(0, mcp_project_path)
    
    # Print the path for debugging.
    print(f"DEBUG: Added project path to sys.path: {mcp_project_path}")
    
    # Now, import the correct client library and other necessary components.
    from src.mcp.client.streamable_http import streamablehttp_client
    from src.mcp.session import ClientSession
    # We import the tool schemas from your tools file to give them to the LLM
    from tools import AVAILABLE_TOOLS_SCHEMA
    print("✅ Successfully imported MCP client library and tools.")

except ImportError as e:
    print(f"❌ CRITICAL ERROR: Could not import the 'mcp' or 'tools' library: {e}")
    print("   Please ensure the path printed above is the correct path to the 'simuapi-main-tests-mcp' folder.")
    exit()
except Exception as e:
    print(f"❌ An unexpected error occurred during setup: {e}")
    exit()


# --- Step 2: Define the Connection Details ---
# The example you provided shows the URL format is /<server_name>/mcp
SERVER_NAME = "StatefulServer"
MCP_SERVER_URL = f"http://127.0.0.1:8000/{SERVER_NAME}/mcp"


# --- Step 3: Define the Main Client Logic ---
async def run_agent_conversation():
    """
    Manages the multi-step conversation with the LLM and tools.
    """
    print("\n--- Multi-Step AI Agent Initialized ---")
    print("This agent can perform multiple tool calls to answer complex questions.")
    print("Type 'exit' or 'quit' to end.")
    print("-" * 40)

    # We need a long-lived session with the MCP server
    try:
        async with streamablehttp_client(MCP_SERVER_URL) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                print("✅ Connected to MCP server.")

                while True:
                    user_input = input("💬 You: ")
                    if user_input.lower() in ["exit", "quit"]:
                        break

                    # The conversation history for this specific query
                    messages = [
                        {"role": "system", "content": "You are a helpful data analyst. You must use the provided tools to answer questions. Reason step-by-step about your plan. If you don't have enough information, call a tool to get it. When you have the final answer, provide it directly to the user."},
                        {"role": "user", "content": user_input}
                    ]

                    # --- The ReAct Loop ---
                    while True:
                        print("\n🧠 Thinking...")
                        
                        # This is a placeholder for the actual LLM call.
                        # In a real app, you would call your LLM (like Ollama) here.
                        # For this example, we will simulate the LLM's response based on the logic it would use.
                        
                        # --- SIMULATED LLM RESPONSE ---
                        llm_decision = None
                        if "typical morning peak speed" in user_input.lower() and len(messages) < 5:
                            if len(messages) == 2: # First turn
                                print("   -> LLM decides to first find peak periods.")
                                llm_decision = {"tool_name": "find_peak_periods", "tool_args": {"collection_name": "lane_data", "metric_field": "speed", "id_value": ":13445139_0", "threshold": 60}}
                            else: # Second turn
                                print("   -> LLM has peak times, now getting stats for those times.")
                                llm_decision = {"tool_name": "get_descriptive_stats", "tool_args": {"collection_name": "lane_data", "metric_field": "speed", "id_value": ":13445139_0", "start_time": "2024-02-14T07:00:00", "end_time": "2024-02-14T09:00:00"}}
                        else:
                            # For any other query, or after the second step, simulate a final answer
                            print("   -> LLM decides it has enough information.")
                            if messages[-1]["role"] == "tool":
                                final_answer = f"Based on the analysis, here is the result: {messages[-1]['content']}"
                            else:
                                final_answer = "I have analyzed the data as requested. What else can I help with?"
                            
                            print(f"🤖 Assistant: {final_answer}")
                            break # Exit the ReAct loop

                        # --- End of Simulated LLM Response ---
                        
                        print(f"   -> Calling tool: {llm_decision['tool_name']}")
                        tool_result_stream = await session.call_tool(llm_decision['tool_name'], llm_decision['tool_args'])
                        
                        final_tool_output = None
                        async for result in tool_result_stream:
                            if result.type == 'text':
                                final_tool_output = result.text
                        
                        print(f"   -> Tool Observation: {final_tool_output}")
                        
                        # Add the tool call and observation back to the message history for the next turn
                        messages.append({"role": "assistant", "content": None, "tool_calls": [{"id": "call_123", "type": "function", "function": {"name": llm_decision['tool_name'], "arguments": json.dumps(llm_decision['tool_args'])}}]})
                        messages.append({"tool_call_id": "call_123", "role": "tool", "name": llm_decision['tool_name'], "content": final_tool_output})

    except Exception as e:
        print(f"❌ An error occurred: {e}")
        print("   Please ensure the server_http.py script is running and accessible at {MCP_SERVER_URL}.")

if __name__ == "__main__":
    try:
        asyncio.run(run_agent_conversation())
    except KeyboardInterrupt:
        print("\nExiting agent client.")