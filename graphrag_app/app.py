#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from typing import List, Optional, Dict, Any

from graphrag_app.fuseki import sparql_select
from graphrag_app.ollama_client import ollama_generate

# Intenta usar tu retriever nuevo (content.index) y si no, cae al antiguo
try:
    from graphrag_app.retriever import retrieve as _retrieve

    def retrieve_content_hits(q: str, k: int = 8):
        return _retrieve(q, kind="content", k=max(20, k), final_k=k, min_score=None)
except Exception:
    from graphrag_app.content_retriever import retrieve_content as _retrieve

    def retrieve_content_hits(q: str, k: int = 8):
        return _retrieve(q, k=k)

U = "http://example.org/academic-career/ontology#"

SYSTEM_PROMPT = (
    "Eres un experto en acreditaciones de UNIBASQ. Responde SIEMPRE en español.\n"
    "Reglas:\n"
    "1) Si la pregunta pide un dato exacto (umbral / mínimo / máximo / puntuación / requisitos), usa primero la ontología.\n"
    "2) Si puedes devolver un único número (p. ej., mínimo total), devuelve SOLO el número.\n"
    "3) Si no hay dato exacto en ontología pero hay evidencia textual, muestra evidencia.\n"
    "4) En preguntas abiertas, apóyate en la evidencia y no inventes.\n"
    "5) Responde únicamente usando la evidencia proporcionada.\n"
    "6) Si la evidencia no contiene información suficiente, responde exactamente:\n"
    "'No hay evidencia suficiente en el grafo cargado.'\n"
)

# ======== Alias de figuras (para detectar en la pregunta) ========
FIGURE_ALIASES = {
    "profesorado pleno": [r"\bpleno\b", r"\bprofesorado pleno\b", r"\bprofesor pleno\b"],
    "profesorado agregado": [r"\bagregado\b", r"\bprofesorado agregado\b", r"\bprofesor agregado\b"],
    "profesorado de investigación": [r"\bprofesorado de investigaci[oó]n\b", r"\bprofesorado investigaci[oó]n\b"],
    "doctor investigador": [r"\bdoctor investigador\b"],
}

SECTION_ALIASES = {
    "indice": [r"\bíndice\b", r"\bindice\b", r"\baurkibidea\b"],
    "introduccion": [r"\bintroducci[oó]n\b", r"\bintroduccion\b", r"\bsarrera\b"],
    "procedimiento": [r"\bprocedimiento\b", r"\bizapidetzea\b"],
    "recurso": [r"\brecurso\b", r"\brecursos\b", r"\berrekurtsoak\b", r"\berrekurtsoa\b"],
    "requisitos": [r"\brequisito\b", r"\brequisitos\b"],
    "plazos": [r"\bplazo\b", r"\bplazos\b", r"\bepeak\b"],
    "notificacion": [r"\bnotificaci[oó]n\b", r"\bnotificacion\b", r"\bjakinarazpen\b"],
    "tasas": [r"\btasa\b", r"\btasas\b", r"\bordainketa\b"],
    "evaluacion": [r"\bevaluaci[oó]n\b", r"\bevaluacion\b", r"\bebaluazioa\b"],
    "otro": [r"\botro\b"],
}

SECTION_QUERY_HINTS = [
    "sección", "seccion", "apartado", "índice", "indice", "introducción", "introduccion",
    "aurkibidea", "sarrera",
]

# Mapping “Apartado N” -> individuo en tu ontología
# (según tu TTL: investigacion/docencia/formacion/gestion)
APARTADO_NUM_TO_URI = {
    1: f"{U}apartado_investigacion",
    2: f"{U}apartado_docencia",
    3: f"{U}apartado_formacion",
    4: f"{U}apartado_gestion",
}


# =========================
# Helpers de routing / intent
# =========================

def detect_figures(question: str) -> List[str]:
    q = (question or "").lower()
    found = []
    for fig_name, pats in FIGURE_ALIASES.items():
        if any(re.search(p, q) for p in pats):
            found.append(fig_name)
    return found


def detect_sections(question: str) -> List[str]:
    q = (question or "").lower()
    found = []
    for sec_name, pats in SECTION_ALIASES.items():
        if any(re.search(p, q) for p in pats):
            found.append(sec_name)
    return found


def is_searchy(q: str) -> bool:
    ql = (q or "").lower()
    return any(
        w in ql
        for w in [
            "dónde", "donde", "menciona", "mencione", "aparece", "habla de", "texto",
            "fragmento", "muéstrame", "muestrame", "enséñame", "enseñame", "qué pone",
            "que pone", "qué dice", "que dice", "sección", "seccion", "apartado",
        ]
    )


def is_exacty(q: str) -> bool:
    ql = (q or "").lower()
    return any(
        w in ql
        for w in [
            "umbral", "mínim", "minim", "máxim", "maxim", "puntuación", "puntuacion",
            "puntos", "requisito",
        ]
    )


def is_section_query(q: str) -> bool:
    ql = (q or "").lower()
    return bool(detect_sections(ql)) or any(w in ql for w in SECTION_QUERY_HINTS)


def route_intent(q: str) -> str:
    if is_exacty(q):
        return "EXACT"
    if is_section_query(q) or is_searchy(q):
        return "SEARCH"
    return "OPEN"


def evidence_strength(hits: List[Dict[str, Any]]) -> int:
    total = 0
    for h in hits or []:
        t = (h.get("text") or h.get("TEXTO") or h.get("CONTEXTO") or "").strip()
        total += len(t)
    return total


def _fmt_num(x: str) -> str:
    s = str(x).strip()
    try:
        f = float(s)
        if abs(f - round(f)) < 1e-9:
            return str(int(round(f)))
        return str(f)
    except Exception:
        return s


def format_evidence(hits: List[Dict[str, Any]], k: int = 6) -> str:
    out = []
    for h in (hits or [])[:k]:
        kind = h.get("kind") or h.get("_kind_norm") or "hit"
        pag = h.get("pagina") or h.get("page") or h.get("PAGINA") or "n/a"
        txt = (h.get("text") or h.get("TEXTO") or h.get("CONTEXTO") or "").strip()
        preview = txt.replace("\n", " ")
        if len(preview) > 350:
            preview = preview[:350] + "…"
        out.append(f"- ({kind}, pág. {pag}) {preview}")
    return "\n".join(out) if out else "—"


def _escape_sparql_literal(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace('"', '\\"')


def _rows_to_section_hits(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    hits = []
    for r in rows or []:
        texto = r.get("texto", {}).get("value", "").strip()
        pagina = r.get("pagina", {}).get("value", "n/a")
        titulo = r.get("titulo", {}).get("value", "")
        sec = r.get("secNombre", {}).get("value", "")
        text = (
            f"TIPO: Fragmento\n"
            f"DOC: {titulo}\n"
            f"SECCION: {sec}\n"
            f"PAGINA: {pagina}\n"
            f"TEXTO: {texto}"
        )
        hits.append({
            "kind": "frag",
            "pagina": pagina,
            "doc_titulo": titulo,
            "seccion": sec,
            "text": text,
        })
    return hits


def query_fragments_by_section(section_name: str, limit: int = 6) -> List[Dict[str, Any]]:
    section_name = (section_name or "").strip().lower()
    if not section_name:
        return []

    aliases = {
        "indice": ["indice", "índice", "aurkibidea"],
        "introduccion": ["introduccion", "introducción", "sarrera"],
        "procedimiento": ["procedimiento", "izapidetzea"],
        "recurso": ["recurso", "recursos", "errekurtsoa", "errekurtsoak"],
        "requisitos": ["requisito", "requisitos"],
        "plazos": ["plazo", "plazos", "epeak"],
        "notificacion": ["notificacion", "notificación", "jakinarazpen"],
        "tasas": ["tasa", "tasas", "ordainketa"],
        "evaluacion": ["evaluacion", "evaluación", "ebaluazioa"],
        "otro": ["otro"],
    }
    vals = aliases.get(section_name, [section_name])
    values_clause = " ".join(f'\"{_escape_sparql_literal(v.lower())}\"' for v in vals)

    query = f"""
    PREFIX u: <{U}>
    SELECT ?frag ?texto ?pagina ?titulo ?secNombre WHERE {{
      VALUES ?wanted {{ {values_clause} }}
      ?frag a u:Fragmento ;
            u:textoFuente ?texto ;
            u:enSeccion ?sec .
      OPTIONAL {{ ?frag u:pagina ?pagina . }}
      OPTIONAL {{
        ?frag u:fuenteDocumento ?doc .
        OPTIONAL {{ ?doc u:titulo ?titulo . }}
      }}
      OPTIONAL {{ ?sec u:nombre ?secNombre . }}
      FILTER(BOUND(?secNombre))
      FILTER(LCASE(STR(?secNombre)) = ?wanted)
    }}
    LIMIT {max(1, int(limit))}
    """
    rows = sparql_select(query)
    return _rows_to_section_hits(rows)


def retrieve_section_hits(q: str, k: int = 6) -> List[Dict[str, Any]]:
    sections = detect_sections(q)
    hits: List[Dict[str, Any]] = []

    for sec in sections:
        hits.extend(query_fragments_by_section(sec, limit=max(2, k)))

    if evidence_strength(hits) >= 120:
        return hits[:k]

    boosted_q = q
    if sections:
        boosted_q = q + " " + " ".join(f"seccion {s}" for s in sections)
    return retrieve_content_hits(boosted_q, k=k)


# =========================
# SPARQL: Figura -> Umbrales
# =========================

def _resolve_figure_uri_by_name(fig_name: str) -> Optional[str]:
    """
    Busca una Figura por u:nombre (case-insensitive contains).
    """
    name = (fig_name or "").strip().lower()
    if not name:
        return None

    query = f"""
    PREFIX u: <{U}>
    SELECT ?fig WHERE {{
      ?fig a u:Figura ;
           u:nombre ?n .
      FILTER(CONTAINS(LCASE(STR(?n)), "{name}"))
    }}
    LIMIT 1
    """
    rows = sparql_select(query)
    if not rows:
        return None
    return rows[0]["fig"]["value"]


def sparql_total_min_for_figure(fig_uri: str) -> Optional[str]:
    """
    Devuelve el umbral total mínimo (1 número) para una figura:
    figura u:tieneUmbral ?u .
    ?u u:apartado u:apartado_total ; u:minmax "total_min" ; u:valor ?v .
    """
    query = f"""
    PREFIX u: <{U}>
    SELECT ?v WHERE {{
      <{fig_uri}> u:tieneUmbral ?umb .
      ?umb a u:UmbralPuntuacion ;
           u:valor ?v ;
           u:apartado u:apartado_total ;
           u:minmax ?mm .
      FILTER(STR(?mm) = "total_min")
    }}
    LIMIT 1
    """
    rows = sparql_select(query)
    if not rows:
        return None
    return _fmt_num(rows[0]["v"]["value"])


def sparql_apartado_min_for_figure(fig_uri: str, apartado_uri: str) -> Optional[str]:
    """
    Devuelve el umbral mínimo de un apartado concreto (1 número) para una figura:
    ?umb u:apartado <apartado_uri> ; u:minmax "apartado_min" ; u:valor ?v
    """
    query = f"""
    PREFIX u: <{U}>
    SELECT ?v WHERE {{
      <{fig_uri}> u:tieneUmbral ?umb .
      ?umb a u:UmbralPuntuacion ;
           u:valor ?v ;
           u:apartado <{apartado_uri}> ;
           u:minmax ?mm .
      FILTER(STR(?mm) = "apartado_min")
    }}
    LIMIT 1
    """
    rows = sparql_select(query)
    if not rows:
        return None
    return _fmt_num(rows[0]["v"]["value"])


def build_exact_context(q: str) -> str:
    """
    Contexto “exacto” para cuando NO hay fast-path numérico.
    Devuelve una lista de umbrales relevantes por figura(s).
    """
    figs = detect_figures(q)
    if not figs:
        return ""

    blocks = []
    for fig in figs:
        fig_uri = _resolve_figure_uri_by_name(fig)
        if not fig_uri:
            continue

        query = f"""
        PREFIX u: <{U}>
        SELECT ?v ?mm ?ap ?p WHERE {{
          <{fig_uri}> u:tieneUmbral ?umb .
          ?umb a u:UmbralPuntuacion ;
               u:valor ?v ;
               u:minmax ?mm ;
               u:apartado ?ap ;
               u:provieneDe ?frag .
          OPTIONAL {{ ?frag u:pagina ?p . }}
        }}
        ORDER BY ?mm ?ap
        """
        rows = sparql_select(query)
        if not rows:
            continue

        lines = [f"Figura: {fig}"]
        for r in rows:
            v = _fmt_num(r["v"]["value"])
            mm = r["mm"]["value"]
            ap = r["ap"]["value"]
            p = r.get("p", {}).get("value", "n/a")
            lines.append(f"- {mm} | {ap} = {v} (pág. {p})")
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def extract_apartado_number(q: str) -> Optional[int]:
    m = re.search(r"\bapartado\s+(\d+)\b", (q or "").lower())
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def wants_total_min_only(q: str) -> bool:
    ql = (q or "").lower()
    return ("total" in ql) and (("mínim" in ql) or ("minim" in ql))


# =========================
# text2sparql bridge (STRUCTURED)
# =========================

def try_text2sparql(q: str) -> Optional[str]:
    """
    IMPORT flexible:
    - si lo mueves a graphrag_app/text2sparql.py -> OK
    - si lo dejas en webapp (raíz) -> intenta import directo
    """
    for mod in ("graphrag_app.text2sparql", "text2sparql"):
        try:
            m = __import__(mod, fromlist=["safe_run_question"])
            fn = getattr(m, "safe_run_question", None)
            if callable(fn):
                out = fn(q)
                if out and str(out).strip():
                    return str(out).strip()
        except Exception:
            continue
    return None


# =========================
# Orquestador principal
# =========================
def extract_direct_answer_from_hit(hit: dict) -> str | None:
    if not hit:
        return None

    text = (
        hit.get("text")
        or hit.get("TEXTO")
        or hit.get("CONTEXTO")
        or hit.get("descripcion")
        or ""
    ).strip()

    if not text or "Respuesta:" not in text:
        return None

    answer = text.split("Respuesta:", 1)[1].strip()

    if answer.startswith("TEXTO:"):
        answer = answer[len("TEXTO:"):].strip()

    answer = (
        answer.replace("DOC:", "")
              .replace("SECCION:", "")
              .replace("PAGINA:", "")
              .strip()
    )

    return answer or None
def answer_question(question: str, debug: bool = False) -> str:
    q = (question or "").strip()
    if not q:
        return "Por favor, escribe una pregunta."

    intent = route_intent(q)

    # ---------- EXACT ----------
    if intent == "EXACT":
        figs = detect_figures(q)

        if figs and wants_total_min_only(q):
            fig_uri = _resolve_figure_uri_by_name(figs[0])
            if fig_uri:
                val = sparql_total_min_for_figure(fig_uri)
                if val is not None:
                    return f"La puntuación mínima total para {figs[0]} es de {val} puntos."

        ap_n = extract_apartado_number(q)
        if figs and ap_n in APARTADO_NUM_TO_URI:
            fig_uri = _resolve_figure_uri_by_name(figs[0])
            if fig_uri:
                val = sparql_apartado_min_for_figure(fig_uri, APARTADO_NUM_TO_URI[ap_n])
                if val is not None:
                    return f"La puntuación mínima requerida en el apartado {ap_n} para {figs[0]} es de {val} puntos."

        if figs and ("investigación" in q.lower() or "investigacion" in q.lower()):
            fig_uri = _resolve_figure_uri_by_name(figs[0])
            if fig_uri:
                val = sparql_apartado_min_for_figure(fig_uri, f"{U}apartado_investigacion")
                if val is not None:
                    return f"La puntuación mínima requerida en el apartado de investigación para {figs[0]} es de {val} puntos."

        structured = try_text2sparql(q)
        if structured:
            return structured

        ctx_exact = build_exact_context(q)
        if ctx_exact:
            user_prompt = f"""
DATOS_ONTOLOGIA:
{ctx_exact}

PREGUNTA:
{q}

Instrucciones:
Responde de forma clara y breve.
No muestres URIs ni datos técnicos internos.
Usa únicamente los datos de la ontología.
""".strip()
            return ollama_generate(user_prompt, system=SYSTEM_PROMPT)

        hits = retrieve_content_hits(q, k=6)
        if evidence_strength(hits) < 180:
            return "No aparece en el grafo cargado."

        ctx_faiss = "\n\n".join(
            (h.get("text") or h.get("TEXTO") or h.get("CONTEXTO") or "").strip()
            for h in hits
            if (h.get("text") or h.get("TEXTO") or h.get("CONTEXTO") or "").strip()
        )

        user_prompt = f"""
TEXTO_EVIDENCIA:
{ctx_faiss}

PREGUNTA:
{q}

Instrucciones:
Responde de forma clara y breve usando solo la evidencia.
No muestres fragmentos brutos ni URIs.
""".strip()

        return ollama_generate(user_prompt, system=SYSTEM_PROMPT)

    # ---------- SEARCH ----------
    if intent == "SEARCH":
        hits = retrieve_section_hits(q, k=6) if is_section_query(q) else retrieve_content_hits(q, k=6)

        if evidence_strength(hits) < 180:
            return "No aparece en el grafo cargado."

        direct_answer = extract_direct_answer_from_hit(hits[0]) if hits else None
        if direct_answer:
            return direct_answer

        ctx_faiss = "\n\n".join(
            (h.get("text") or h.get("TEXTO") or h.get("CONTEXTO") or "").strip()
            for h in hits
            if (h.get("text") or h.get("TEXTO") or h.get("CONTEXTO") or "").strip()
        )

        user_prompt = f"""
TEXTO_EVIDENCIA:
{ctx_faiss}

PREGUNTA:
{q}

Instrucciones:
Responde de forma clara, breve y natural usando solo la evidencia.
No muestres fragmentos brutos.
No muestres URIs.
No digas "he encontrado fragmentos".
Si la evidencia no permite responder con precisión, indica que no hay información suficiente.
""".strip()

        ans = ollama_generate(user_prompt, system=SYSTEM_PROMPT)

        if debug:
            return (
                "--- DEBUG ---\n"
                f"intent={intent}\n"
                f"hits={len(hits)}\n"
                f"evidence_chars={evidence_strength(hits)}\n"
                "-------------\n"
                + ans
            )

        return ans

    # ---------- OPEN ----------
    user_prompt = f"""
PREGUNTA:
{q}

Instrucciones:
Responde de forma clara, breve y bien estructurada.
No inventes datos concretos, puntuaciones, fechas ni requisitos.
Si la pregunta requiere información normativa exacta y no se ha recuperado evidencia, responde de forma general indicando que sería necesario consultar la normativa cargada.
""".strip()

    ans = ollama_generate(user_prompt, system=SYSTEM_PROMPT)

    if debug:
        return (
            "--- DEBUG ---\n"
            f"intent={intent}\n"
            f"figs={detect_figures(q)}\n"
            f"sections={detect_sections(q)}\n"
            f"apartado_n={extract_apartado_number(q)}\n"
            "-------------\n"
            + ans
        )

    return ans
# =========================
# Modo Terminal
# =========================
if __name__ == "__main__":
    print("\n🚀 GraphRAG (Router: EXACT | STRUCTURED | SEARCH | OPEN)\n")

    while True:
        try:
            user_q = input("> ").strip()
            if user_q.lower() in ["salir", "exit", "quit"]:
                break
            print("\n" + answer_question(user_q) + "\n")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n❌ Error crítico: {e}\n")
