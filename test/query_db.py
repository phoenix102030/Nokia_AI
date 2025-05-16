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
    db = SQLDatabase.from_uri(f"sqlite:///{db_path}")
    llm = OllamaLLM(model="llama3.2", temperature=0.0)

    chain = SQLDatabaseChain.from_llm(
        llm=llm,
        db=db,
        verbose=True,
        return_direct=True
    )

    result_text = chain.run(question)
    print("Answer:", result_text)

if __name__ == "__main__":
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("Usage: python query_db.py \"Your question here\"")
        sys.exit(1)

    db_file = "test.db"
    user_question = sys.argv[1]
    ask_question(db_file, user_question)
