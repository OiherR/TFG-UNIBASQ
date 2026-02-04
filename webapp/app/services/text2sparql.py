import re
from graphrag_app.retriever import retrieve
from graphrag_app.ollama_client import ollama_generate
from graphrag_app.app import build_sparql_prompt


def extract_sparql(text: str) -> str:
    """
    Extrae la SPARQL si el modelo la devuelve entre ``` ``` (opcionalmente ```sparql).
    """
    m = re.search(r"```(?:sparql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else text.strip()


def question_to_sparql(question: str) -> str:
    ctx_items = retrieve(question)
    prompt = build_sparql_prompt(question, ctx_items)
    llm_output = ollama_generate(prompt)
    sparql = extract_sparql(llm_output)
    return sparql
