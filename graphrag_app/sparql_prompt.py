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
- No inventes URIs ni propiedades si no están apoyadas por las pistas del esquema o por patrones muy probables del grafo.
- Cuando pidas texto o evidencia, prioriza recuperar también página, documento y sección si existen.

PISTAS IMPORTANTES DEL MODELO DE DATOS:
- Los fragmentos de texto suelen estar en u:Fragmento.
- El texto del fragmento suele ir en u:textoFuente.
- La página suele ir en u:pagina.
- El documento fuente suele enlazarse con u:fuenteDocumento y su título con u:titulo.
- La sección del fragmento suele enlazarse con u:enSeccion.
- Las secciones pueden modelarse como individuos y su nombre humano suele venir en u:nombre.
- Si la pregunta menciona una sección concreta, filtra por la sección y su nombre.
- Ten especialmente en cuenta estas secciones nuevas del grafo:
  - índice / indice / aurkibidea  -> normalmente sección con u:nombre "indice"
  - introducción / introduccion / sarrera -> normalmente sección con u:nombre "introduccion"
- También pueden aparecer secciones como procedimiento, recurso, requisitos, plazos, notificacion, tasas, evaluacion u otro.

PATRONES ÚTILES:
- Para recuperar fragmentos por sección, un patrón frecuente es:
  ?frag a u:Fragmento ;
        u:textoFuente ?texto ;
        u:enSeccion ?sec .
  ?sec u:nombre ?secNombre .
- Para búsquedas bilingües, usa FILTER sobre LCASE(STR(?secNombre)) con variantes como:
  "indice", "introduccion", "aurkibidea", "sarrera".
- Si la pregunta pide “qué pone”, “enséñame”, “muéstrame” o “dónde aparece”, prioriza devolver fragmentos y evidencia textual, no solo conteos.
- Si la pregunta pide requisitos o umbrales exactos, prioriza los recursos estructurados del grafo antes que los fragmentos.

PISTAS DEL ESQUEMA (recuperadas):
{schema_text if schema_text else "(sin pistas de esquema)"}

PREGUNTA:
{question}

Devuelve la consulta entre:
```sparql
... """.strip()
