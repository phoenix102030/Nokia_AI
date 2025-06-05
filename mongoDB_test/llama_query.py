import sys
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import AgentExecutor, create_tool_calling_agent

from toolbox import *

def main():
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print('"Your question here"')
        sys.exit(1)

    question = sys.argv[1]
    llm = ChatOllama(model="qwen2.5", temperature=0.0)
    tools = [
        get_busiest_lanes_by_occupancy,
        get_lanes_with_most_traffic,
        get_total_vehicles_entered,
        get_average_occupancy_by_hour,
        get_average_speed_for_sensor,
        get_sensors_with_highest_flow,
        get_sensor_data_in_time_range,
        get_peak_flow_time,
    ]

    # Define the system prompt, telling the model how to choose tools
    prompt = ChatPromptTemplate.from_messages([
        ("system", """
        You are an expert traffic data assistant. You have access to tools that query two MongoDB databases:

        1.  **traffic_db** (lane data). Use tools related to lanes, occupancy, and vehicle counts.
        2.  **measurements_db** (sensor data). Use tools related to sensors, speed, and flow.

        Depending on the user's question, choose exactly one tool and return a JSON function call.
        """),
        ("user", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    print(f"🗣️ Asking question: {question}")
    result = agent_executor.invoke({"input": question})

    print("\n✅ Final Answer:")
    print(result["output"])


if __name__ == "__main__":
    main()
