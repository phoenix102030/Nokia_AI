import os
import json
import asyncio
from openai import OpenAI
from dotenv import load_dotenv
from api_tool_caller import call_api_tool

load_dotenv()
try:
    client = OpenAI(base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1"), api_key=os.getenv("OPENAI_API_KEY", "ollama"))
    MODEL = os.getenv("MODEL_NAME")
    if not MODEL: raise ValueError("MODEL_NAME not found in .env file.")
    print(f"✅ OpenAI client configured for Ollama model: {MODEL}")
except Exception as e:
    print(f"❌ Error initializing client: {e}"); exit()

# --- DYNAMIC TOOL DEFINITION ---
async def get_tools_from_server():
    print("🔎 Discovering available tools from the server...")
    try:
        tools_json_str = await call_api_tool(endpoint="/list_available_tools", tool_name="list_available_tools", params={})
        tools_raw = json.loads(tools_json_str)
        
        # --- Make descriptions even more explicit for the LLM ---
        for tool_info in tools_raw:
            if tool_info['name'] == 'get_lanes_by_metric':
                tool_info['description'] += " Valid metrics are: 'occupancy', 'density', 'speed', 'entered', 'waiting_time'."
            
        # Convert to OpenAI format
        formatted_tools = []
        for tool_info in tools_raw:
            properties = {p["name"]: {"type": "integer" if "int" in p.get("type", "") else "string", "description": f"Parameter '{p['name']}'. Default: {p.get('default', 'N/A')}"} for p in tool_info.get("parameters", [])}
            formatted_tools.append({"type": "function", "function": {"name": tool_info["name"], "description": tool_info["description"], "parameters": {"type": "object", "properties": properties, "required": [p["name"] for p in tool_info.get("parameters", []) if p.get("default") == "REQUIRED"]}}})
        
        print(f"✅ Successfully loaded and enhanced {len(formatted_tools)} tools.")
        return formatted_tools
    except Exception as e:
        print(f"❌ CRITICAL: Could not fetch tools from server. Is it running? Error: {e}")
        return None

# --- MAIN ASYNC APPLICATION LOGIC (The "Bulletproof" version is already robust) ---
async def main():
    tools_list = await get_tools_from_server()
    if not tools_list:
        print("Exiting due to tool loading failure."); return

    print("\n--- 🤖 AI Traffic Analyst is Ready (Robust v2) ---")
    print("I have loaded my capabilities from the server. Ask me anything!")
    
    system_prompt = (
        "You are a helpful and meticulous data analyst bot. Your goal is to answer user questions about traffic data. "
        "You MUST use the provided tools to answer questions. Do not make up answers. "
        "If the user asks what you can do or what tools you have, you MUST call the `list_available_tools` function."
    )
    
    messages = [{"role": "system", "content": system_prompt}]

    while True:
        user_input = await asyncio.to_thread(input, "\nYou: ")
        if user_input.lower() in ["exit", "quit"]: break
        
        messages.append({"role": "user", "content": user_input})
        print("🤖 Thinking...")
        response = client.chat.completions.create(model=MODEL, messages=messages, tools=tools_list, tool_choice="auto")
        response_message = response.choices[0].message
        messages.append(response_message)
        
        tool_calls_to_execute = []
        if response_message.tool_calls:
            print("🧠 Assistant used standard 'tool_calls' format.")
            tool_calls_to_execute = response_message.tool_calls
        elif response_message.content:
            try:
                potential_tool_call = json.loads(response_message.content)
                if "name" in potential_tool_call and "parameters" in potential_tool_call:
                    print("🧠 Assistant used plain-text JSON format. Parsing manually.")
                    class MockToolCall:
                        def __init__(self, name, args): self.id = f"call_{os.urandom(4).hex()}"; self.function = self.__class__.Function(name, json.dumps(args))
                        class Function:
                            def __init__(self, name, args): self.name, self.arguments = name, args
                    tool_calls_to_execute.append(MockToolCall(potential_tool_call['name'], potential_tool_call['parameters']))
            except (json.JSONDecodeError, TypeError): pass
        
        if tool_calls_to_execute:
            for tool_call in tool_calls_to_execute:
                function_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                function_response_str = await call_api_tool(endpoint=f"/{function_name}", tool_name=function_name, params=arguments)
                print(f"✅ Tool '{function_name}' executed.")
                messages.append({"tool_call_id": tool_call.id, "role": "tool", "name": function_name, "content": function_response_str})
            
            print("📝 Summarizing the result...")
            final_response = client.chat.completions.create(model=MODEL, messages=messages)
            final_answer = final_response.choices[0].message.content
            print(f"\nAssistant: {final_answer}")
            messages.append(final_response.choices[0].message)
        else:
            print(f"\nAssistant: {response_message.content}")

if __name__ == "__main__":
    asyncio.run(main())