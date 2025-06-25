from fastmcp_async import MCPApplication
from toolbox_async import _toolbox_registry 

DB_CONNECTION = 'mongodb://localhost:27017/'

server = MCPApplication(db_connection_string=DB_CONNECTION)

print("--- Registering Tools ---")
for tool_name, tool_data in _toolbox_registry.items():
    # The endpoint path is derived from the tool name from the registry
    endpoint = f"/{tool_name}"
    
    function_to_register = tool_data['function']
    
    server.tool(name=endpoint)(function_to_register)
    
    print(f"✅ Registered tool: '{tool_name}' at endpoint '/tools{endpoint}'")
print("-------------------------")

app = server.app
