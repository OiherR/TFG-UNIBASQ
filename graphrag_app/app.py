import re
from fuseki import sparql_select
from retriever import retrieve
from ollama_client import ollama_generate


def extract_sparql(text: str) -> str:
    """
    Extrae SPARQL si viene entre ``` ``` y limpia asignaciones tipo: query = "..."
    """
    m = re.search(r"```(?:sparql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    sparql = (m.group(1).strip() if m else text.strip())

    # Si el modelo devuelve algo tipo: query = "SELECT ..."
    sparql = re.sub(r'^\s*query\s*=\s*', '', sparql, flags=re.IGNORECASE)

    # Si viene todo entre comillas "..."
    sparql = sparql.strip()
    if (sparql.startswith('"') and sparql.endswith('"')) or (sparql.startswith("'") and sparql.endswith("'")):
        sparql = sparql[1:-1].strip()

    # Quita posibles prefijos tipo "SPARQL:" al principio
    sparql = re.sub(r'^\s*SPARQL\s*:\s*', '', sparql, flags=re.IGNORECASE)

    return sparql.strip()


def build_sparql_prompt(question: str, ctx_items, last_error: str | None = None) -> str:
    ctx = "\n\n".join([f"{i+1}) {it['text']}" for i, it in enumerate(ctx_items)])

    prompt = f"""Eres un asistente experto en SPARQL y Apache Jena Fuseki.

REGLAS ESTRICTAS:
- Devuelve SOLO la consulta SPARQL (sin texto adicional).
- No uses ``` ni explicaciones.
- Usa únicamente URIs que aparezcan en el CONTEXTO.
- No inventes prefijos ni URIs.
- Usa SELECT (nunca ASK, CONSTRUCT, DESCRIBE).
- Prohibido usar GRAPH, FROM, FROM NAMED o SERVICE.
- Usa SIEMPRE el grafo por defecto.

EJEMPLO (IMPORTANTE):
Pregunta: ¿Cuántos triples hay en el grafo?
SPARQL:
SELECT (COUNT(*) AS ?n) WHERE {{ ?s ?p ?o }}

PREGUNTA DEL USUARIO:
{question}

CONTEXTO DEL KNOWLEDGE GRAPH:
{ctx}

Genera ahora SOLO la consulta SPARQL:
"""

    if last_error:
        prompt += f"""
La consulta anterior falló con este error:
{last_error}

Corrige la consulta SPARQL cumpliendo las reglas.
"""
    return prompt


def sanitize_sparql(question: str, sparql: str) -> str:
    """
    Guardarraíl duro:
    - Prohíbe GRAPH/FROM/SERVICE
    - Si la pregunta es conteo de triples, fuerza query segura
    """
    s_up = sparql.upper()

    forbidden = ["GRAPH", "FROM ", "FROM NAMED", "SERVICE "]
    if any(tok in s_up for tok in forbidden):
        q = question.lower()
        if ("cuánt" in q or "cuanto" in q) and "tripl" in q:
            return "SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }"
        raise ValueError("SPARQL contiene GRAPH/FROM/SERVICE. Debe usar el grafo por defecto.")

    # Evita que el modelo devuelva una asignación estilo código
    if re.search(r'^\s*query\s*=\s*', sparql, flags=re.IGNORECASE):
        sparql = re.sub(r'^\s*query\s*=\s*', '', sparql, flags=re.IGNORECASE).strip()

    # Si aun así se cuela un conteo mal formado, fuerza el seguro
    q = question.lower()
    if ("cuánt" in q or "cuanto" in q) and "tripl" in q:
        # Si no contiene COUNT, lo forzamos (por robustez)
        if "COUNT" not in s_up:
            return "SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }"

    return sparql.strip()


def verbalize_answer(question: str, sparql: str, data: dict) -> str:
    bindings = data.get("results", {}).get("bindings", [])
    preview = bindings[:10]

    prompt = f"""Responde en español de forma clara y concisa.

Pregunta:
{question}

Consulta SPARQL ejecutada:
{sparql}

Resultados (primeras filas):
{preview}

Si no hay resultados, indícalo claramente.
"""
    return ollama_generate(prompt, temperature=0.2)


def ask(question: str, max_retries: int = 2):
    ctx_items = retrieve(question, k=10)
    last_error = None
    sparql = ""

    for _ in range(max_retries + 1):
        prompt = build_sparql_prompt(question, ctx_items, last_error)
        sparql = extract_sparql(ollama_generate(prompt, temperature=0.0))

        try:
            sparql = sanitize_sparql(question, sparql)
            data = sparql_select(sparql)
            answer = verbalize_answer(question, sparql, data)
            return {"sparql": sparql, "answer": answer, "error": None}
        except Exception as e:
            last_error = str(e)

    return {"sparql": sparql, "answer": None, "error": last_error}


if __name__ == "__main__":
    question = input("Pregunta: ").strip()
    result = ask(question)

    print("\nSPARQL GENERADA:\n")
    print(result["sparql"])

    if result["error"]:
        print("\n❌ ERROR:\n")
        print(result["error"])
    else:
        print("\n✅ RESPUESTA:\n")
        print(result["answer"])
