import sys
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_experimental.sql import SQLDatabaseChain
from langchain_ollama.llms import OllamaLLM

def ask_question(db_path: str, question: str) -> None:
    """
    Connects to the SQLite DB at db_path,
    runs the plain-English question through the SQLDatabaseChain,
    and prints the final answer.
    """
    # 1) Load the database
    db = SQLDatabase.from_uri(f"sqlite:///{db_path}")

    # 2) Wrap the Ollama model (zero temperature to avoid hallucinations)
    llm = OllamaLLM(model="llama3.2", temperature=0.0)

    # 3) Build the SQL Q&A chain, returning only the direct result
    chain = SQLDatabaseChain.from_llm(
        llm=llm,
        db=db,
        verbose=True,
        return_direct=True
    )

    # 4) Run the chain with the user question (returns a string)
    result_text = chain.run(question)

    # 5) Print the result
    print("Answer:", result_text)

if __name__ == "__main__":
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("Usage: python query_db.py \"Your question here\"")
        sys.exit(1)

    db_file = "test.db"
    user_question = sys.argv[1]
    ask_question(db_file, user_question)
