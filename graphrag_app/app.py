import re
import unicodedata
from graphrag_app.fuseki import sparql_select
from graphrag_app.retriever import retrieve
from graphrag_app.ollama_client import ollama_generate
from graphrag_app.content_retriever import retrieve_content
from typing import Optional

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

def pick_best_threshold(hits, question: str):
    q = question.lower()

    want_pleno = "pleno" in q
    want_invest = "investig" in q
    want_min = ("min" in q) or ("mínim" in q)

    for h in hits:
        if h.get("kind") != "umbral":
            continue

        fig = (h.get("figura_nombre") or "").lower()
        area = (h.get("area") or "").lower()
        mm = (h.get("minmax") or "").lower()
        umb_tipo = (h.get("umbral_tipo") or "").lower()

        if want_pleno and "pleno" not in fig:
            continue
        if want_invest and area != "investigacion":
            continue
        if want_min and mm != "min":
            continue

        # extra guardarraíl: apartado_min
        if want_invest and want_min and "apartado_min" not in umb_tipo:
            continue

        if h.get("valor"):
            return h

    return None


def try_answer_threshold(question: str):
    q = question.lower()
    # Heurística simple: solo intentarlo si suena a umbral/puntuación
    if not any(w in q for w in ["nota", "puntu", "mínim", "minim", "min", "max", "puntos"]):
        return None

    hits = retrieve_content(question, k=25)
    best = pick_best_threshold(hits, question)
    if not best:
        return None

    valor = best["valor"]
    unidad = best.get("unidad", "puntos")
    figura = best.get("figura_nombre", "la figura indicada")
    area = best.get("area", "")

    if area:
        return f"Para {figura}, la puntuación mínima en {area} es {valor} {unidad}."
    return f"Para {figura}, el umbral mínimo es {valor} {unidad}."

def ask(question: str, max_retries: int = 2):
    direct = try_answer_threshold(question)
    if direct:
        return {"sparql": None, "answer": direct, "error": None}

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


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s

def answer_question(question: str) -> str:
    result = ask(question)

    if result.get("error"):
        # opcional: devuelve error amigable
        return "Ha ocurrido un error procesando la consulta."

    return result.get("answer") or "Ez dago erantzunik."

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


