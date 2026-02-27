# graphrag_app/sparql_prompt.py

U = "http://example.org/academic-career/ontology#"

def build_sparql_prompt(question: str, schema_items: list[dict], topk: int = 16) -> str:
    schema_text = "\n".join(
        f"- {it.get('text','')}".strip()
        for it in (schema_items or [])[:topk]
        if isinstance(it, dict) and (it.get("text") or "").strip()
    )

    return f"""
Eres un asistente que genera consultas SPARQL para Fuseki.

REGLAS:
- Devuelve SOLO una consulta SPARQL SELECT válida.
- Incluye: PREFIX u: <{U}>
- Prohibido: INSERT/DELETE/LOAD/CREATE/DROP.
- Usa LIMIT si procede (p.ej. LIMIT 50).
- Si faltan datos, genera igualmente una SELECT útil.

PISTAS DEL ESQUEMA (recuperadas):
{schema_text if schema_text else "(sin pistas de esquema)"}

PREGUNTA:
{question}

Devuelve la consulta entre:
```sparql
... """.strip()

