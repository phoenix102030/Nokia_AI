from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama.llms import OllamaLLM

# 1) Create a prompt template
template = "User: {question}\nAssistant:"
prompt = ChatPromptTemplate.from_template(template)

# 2) Point LangChain at your Ollama model
llm = OllamaLLM(model="llama3.2")

# 3) Wire them together
chain = prompt | llm

# 4) Run it
result = chain.invoke({"question": "What's the weather like today?"})
print(result)