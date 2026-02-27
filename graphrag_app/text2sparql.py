import re
from graphrag_app.retriever import retrieve
from graphrag_app.ollama_client import ollama_generate
from graphrag_app.fuseki_client import run_select
from graphrag_app.sparql_utils import sparql_json_to_rows
from graphrag_app.sparql_prompt import build_sparql_prompt


def _extract_sparql(text: str) -> str:
    m = re.search(r"```(?:sparql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else text.strip()


def question_to_sparql(question: str) -> str:
    # Para generar SPARQL, el contexto correcto es el ESQUEMA, no el contenido
    schema_items = retrieve(question, kind="schema", k=25, min_score=None, final_k=16)
    prompt = build_sparql_prompt(question, schema_items, topk=16)
    llm_out = ollama_generate(prompt)
    return _extract_sparql(llm_out)


def safe_run_question(question: str) -> str:
    """
    Ejecuta: pregunta -> SPARQL -> Fuseki (solo SELECT/ASK) -> devuelve texto.
    Devuelve "" si no hay filas o falla (para que el router pruebe otras rutas).
    """
    try:
        sparql = question_to_sparql(question)
        res = run_select(sparql, timeout=60)  # run_select ya bloquea queries peligrosas
        rows = sparql_json_to_rows(res)
        if not rows:
            return ""

        cols = list(rows[0].keys())
        lines = []
        lines.append("Resultado (vía consulta estructurada SPARQL):")
        lines.append("Columnas: " + ", ".join(cols))

        for r in rows[:10]:
            lines.append("- " + " | ".join(str(r.get(c, "")) for c in cols))

        if len(rows) > 10:
            lines.append(f"(Mostrando 10 de {len(rows)} filas)")

        return "\n".join(lines).strip()
    except Exception:
        return ""