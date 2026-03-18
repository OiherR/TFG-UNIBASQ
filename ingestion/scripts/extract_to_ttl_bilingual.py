import re
import json
import argparse
import requests
from pathlib import Path
from rdflib import Graph, RDF, RDFS, OWL
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ========= CONFIGURACIÓN DE RED ROBUSTA =========
session = requests.Session()
retries = Retry(
    total=3,
    connect=3,
    read=3,
    backoff_factor=1,
    status_forcelist=[500, 502, 503, 504],
    allowed_methods=["POST", "GET"],
)
session.mount("http://", HTTPAdapter(max_retries=retries))
session.mount("https://", HTTPAdapter(max_retries=retries))

OLLAMA_URL = "http://localhost:11434/api/generate"


# ========= CLI =========
def parse_args():
    parser = argparse.ArgumentParser(
        description="Extractor RAG-Ontology Blindado + Tablas/Umbrales + Figura dinámica + Apartados dinámicos"
    )
    parser.add_argument("--input_rdf", type=str, required=True)
    parser.add_argument("--input_txt", type=str, required=True)
    parser.add_argument("--prompt_file", type=str, required=True)
    parser.add_argument("--fix_prompt_file", type=str, required=True)
    parser.add_argument("--output_ttl", type=str, default="resultado_final.ttl")
    parser.add_argument("--model", type=str, default="qwen2.5:7b")
    parser.add_argument("--max_pages", type=int, default=0)
    parser.add_argument("--debug_comments", action="store_true")
    return parser.parse_args()


# ========= RDF / ONTOLOGÍA (Filtro Estricto) =========
def qname_or_local(g, uri):
    try:
        return g.namespace_manager.normalizeUri(uri)
    except Exception:
        s = str(uri)
        return s.split("#")[-1] if "#" in s else s.split("/")[-1]


def extract_ontology_schema(rdf_path: str) -> dict:
    g = Graph()
    ext = Path(rdf_path).suffix.lower().lstrip(".")
    fmt = {"ttl": "turtle", "rdf": "xml", "owl": "xml", "xml": "xml", "nt": "nt"}.get(ext, None)
    g.parse(rdf_path, format=fmt)

    ns_map = {p: str(ns) for p, ns in g.namespaces()}
    ctx = {"namespaces": ns_map, "classes": [], "properties": [], "individuals": []}

    def info(uri):
        label = next(g.objects(uri, RDFS.label), None)
        comment = next(g.objects(uri, RDFS.comment), None)
        return {
            "name": qname_or_local(g, uri),
            "label": str(label) if label else "",
            "comment": str(comment) if comment else ""
        }

    onto = next((uri for _p, uri in ns_map.items() if "academic-career/ontology" in uri), None)

    def is_in_onto(u):
        s = str(u)
        if onto:
            return s.startswith(onto)
        return "academic-career/ontology" in s

    for c in set(g.subjects(RDF.type, OWL.Class)):
        if is_in_onto(c):
            ctx["classes"].append(info(c))

    props = set(g.subjects(RDF.type, OWL.ObjectProperty)) | set(g.subjects(RDF.type, OWL.DatatypeProperty))
    for p in props:
        if is_in_onto(p):
            d = [qname_or_local(g, x) for x in g.objects(p, RDFS.domain)]
            r = [qname_or_local(g, x) for x in g.objects(p, RDFS.range)]
            item = info(p)
            item.update({"domain": d, "range": r})
            ctx["properties"].append(item)

    for i in set(g.subjects(RDF.type, OWL.NamedIndividual)):
        if is_in_onto(i):
            ctx["individuals"].append(info(i))

    return ctx


def build_forced_prefixes(ns_map: dict) -> str:
    onto = next(
        (uri for _p, uri in ns_map.items() if "academic-career/ontology" in uri),
        "http://example.org/academic-career/ontology#"
    )
    lines = [
        f"@prefix u: <{onto}> .",
        "@prefix base: <http://example.org/academic-career/> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> ."
    ]
    return "\n".join(lines) + "\n\n"


# ========= LIMPIEZA Y SEGURIDAD =========
def sanitize_ttl(raw: str) -> str:
    if not raw:
        return ""
    clean = re.sub(r"```(?:turtle|ttl)?", "", raw, flags=re.IGNORECASE).replace("```", "").strip()
    m = re.search(r"(@prefix|PREFIX|base:|u:)", clean, re.IGNORECASE)
    if m:
        clean = clean[m.start():]
    return clean.strip()


def remove_prefix_lines(ttl: str) -> str:
    out = []
    for ln in ttl.splitlines():
        s = ln.strip().lower()
        if s.startswith("@prefix") or s.startswith("prefix "):
            continue
        out.append(ln)
    return "\n".join(out)


def strip_doc_and_frag(ttl: str, doc_id: str, frag_uri: str) -> str:
    lines = []
    for ln in ttl.splitlines():
        s = ln.strip()
        if s.startswith(f"base:doc_{doc_id}") or s.startswith(frag_uri):
            continue
        lines.append(ln)
    return "\n".join(lines).strip()


def strip_any_fragment_blocks(ttl: str) -> str:
    out_lines = []
    skipping = False
    for ln in ttl.splitlines():
        if not skipping and re.search(r"\ba\s+u:Fragmento\b", ln):
            skipping = True
        if skipping:
            if re.search(r"\.\s*$", ln.strip()):
                skipping = False
            continue
        out_lines.append(ln)
    return "\n".join(out_lines).strip()


def normalize_minmax(ttl: str) -> str:
    return re.sub(r'(u:minmax\s+"[^"]+")\s*\^\^[^ ;]+', r"\1", ttl)


def validate_ttl(ttl_body: str, forced_prefixes: str) -> bool:
    g = Graph()
    try:
        g.parse(data=forced_prefixes + ttl_body, format="turtle")
        return True
    except Exception:
        return False


# ========= OLLAMA =========
def call_ollama(prompt, model):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.0, "num_ctx": 4096, "num_predict": 700},
        "keep_alive": "10m"
    }
    r = session.post(OLLAMA_URL, json=payload, timeout=2400)
    r.raise_for_status()
    return r.json().get("response", "").strip()


def split_pages(text: str) -> dict[int, str]:
    chunks = re.split(r"(?:\n)?(?:={3,}|-{3,})\s*PAGE\s*(\d+)\s*(?:={3,}|-{3,})(?:\n)?", text)
    if len(chunks) < 2:
        print(" OJO: No se han detectado marcadores de página. Procesando como página única.")
        return {1: text}
    pages = {}
    for i in range(1, len(chunks), 2):
        if i + 1 < len(chunks):
            page_num = int(chunks[i])
            pages[page_num] = chunks[i + 1]
    return pages


def clean_page_content(raw: str) -> str:
    """
    Limpia ruido típico del TXT intermedio:
      - marcadores ----- TEXT ----- / ----- TABLE n -----
      - espacios redundantes
    No elimina contenido semántico.
    """
    if not raw:
        return ""
    txt = raw.replace("\r", "")
    txt = re.sub(r"-----\s*TEXT\s*-----", " ", txt, flags=re.I)
    txt = re.sub(r"-----\s*TABLE\s*\d+\s*-----", " ", txt, flags=re.I)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt.strip()


def filter_bulletin_noise(raw: str) -> str:
    """
    En boletines oficiales a veces aparece ruido previo (anuncios, edictos, Metro Bilbao...).
    Si detectamos un decreto objetivo, recortamos el bloque desde el inicio real del decreto.
    """
    if not raw:
        return ""

    txt = raw.replace("\r", "")

    decree_patterns = [
        r"\b209\s*/\s*2006\s+DEKRETUA\b",
        r"\bDECRETO\s+209\s*/\s*2006\b",
        r"\b64\s*/\s*2011\s+DEKRETUA\b",
        r"\bDECRETO\s+64\s*/\s*2011\b",
    ]

    starts = []
    for pat in decree_patterns:
        m = re.search(pat, txt, flags=re.I)
        if m:
            starts.append(m.start())

    if starts:
        txt = txt[min(starts):]

    return txt.strip()


def llm_classify_section(text: str, model: str) -> str:
    allowed = ["indice", "introduccion", "requisitos", "procedimiento", "tasas", "notificacion", "plazos", "recurso", "evaluacion", "otro"]
    prompt = (
        f"Clasifica el siguiente texto administrativo en UNA sola categoría. "
        f"Devuelve SOLO UNA palabra de esta lista [{', '.join(allowed)}].\n"
        f"Puedes basarte tanto en castellano como en euskera.\n"
        f"Pistas útiles: aurkibidea->indice, sarrera->introduccion, "
        f"eskaera/izapidetzea->procedimiento, ordainketa/tasak->tasas, "
        f"jakinarazpen->notificacion, errekurtso->recurso, epe/plazo->plazos, "
        f"ebaluazio/irizpide/puntuazio->evaluacion.\n\n"
        f"TEXTO:\n{text[:1200]}"
    )
    out = call_ollama(prompt, model).strip().lower()
    out = re.sub(r"[^a-z_áéíóúñ]", "", out)
    return out if out in allowed else "otro"


def rulebased_section(content: str) -> str | None:
    """
    Clasificación determinista por keywords.
    Devuelve una de: requisitos, plazos, notificacion, tasas, procedimiento, recurso, evaluacion, otro
    (si None -> caerá a llm_classify_section)
    """
    t = (content or "").lower()

    # Normaliza rápido (sin cargarte URLs)
    t_compact = re.sub(r"\s+", " ", t)

    # 0) ÍNDICE / INTRODUCCIÓN (castellano + euskera)
    if re.search(r"(?:^|\n)\s*(ÍNDICE|AURKIBIDEA)\b", content, flags=re.I):
        return "indice"
    if (
        re.search(r"(?:^|\n)\s*1\.?\s*(Introducci[óo]n|Sarrera)\b", content, flags=re.I)
        or re.search(r"\bIntroducci[óo]n\b", t_compact)
        or re.search(r"\bSarrera\b", content, flags=re.I)
        or "helburua" in t_compact
    ):
        return "introduccion"

    # 1) NOTIFICACIÓN / JAKINARAZPENAK
    if (
        "notificación" in t_compact
        or "notificacion" in t_compact
        or "jakinarazpen" in t_compact
        or "tablón electrónico" in t_compact
        or "tablon electronico" in t_compact
        or "tablón de anuncios" in t_compact
        or "tablon de anuncios" in t_compact
        or "iragarki-taula" in t_compact
        or ("mi carpeta" in t_compact and "notific" in t_compact)
        or ("nire karpeta" in t_compact and "jakinaraz" in t_compact)
        or ("aviso" in t_compact and ("sms" in t_compact or "correo" in t_compact or "email" in t_compact))
        or ("ohar" in t_compact and ("sms" in t_compact or "posta" in t_compact or "email" in t_compact))
        or ("resolución" in t_compact and "notific" in t_compact)
        or ("ebazpen" in t_compact and "jakinaraz" in t_compact)
        or "notificación pendiente" in t_compact
    ):
        return "notificacion"

    # 2) TASAS / PAGO / ORDAINKETA
    # Evita falsos positivos: en algunas guías la palabra "tasa" aparece ya en introducción.
    # Para considerar sección "tasas" pedimos señales claras de pago/liquidación/pasarela/importe.
    if (
        "pago de la tasa" in t_compact
        or ("pago" in t_compact and "tasa" in t_compact)
        or "mi pago" in t_compact
        or ("pasarela" in t_compact and "pago" in t_compact)
        or "kutxabank" in t_compact
        or "carta de pago" in t_compact
        or "justificante de pago" in t_compact
        or "liquidación" in t_compact
        or "liquidacion" in t_compact
        or "ordainketa" in t_compact
        or "ordaindu" in t_compact
        or "ordainagiri" in t_compact
        or "ordainketa-gutuna" in t_compact
        or "tasak" in t_compact
        or re.search(r"\b49[,.]70\b", t_compact)
        or "c maila" in t_compact
    ):
        return "tasas"

    # 3) PLAZOS / EPEAK
    if (
        "plazo" in t_compact
        or "epe" in t_compact
        or re.search(r"\bdel\s+\d{1,2}\s+de\s+[a-záéíóúñ]+\s+de\s+\d{4}\s+al\s+\d{1,2}\s+de\s+[a-záéíóúñ]+\s+de\s+\d{4}\b", t_compact)
        or re.search(r"\ben\s+el\s+plazo\s+de\s+\d+\s+(d[ií]as|mes(es)?)\b", t_compact)
        or re.search(r"\bdentro\s+de\s+los?\s+\d+\s+(d[ií]as|mes(es)?)\b", t_compact)
        or re.search(r"\b\d+\s+mes(es)?\b", t_compact) and ("notific" in t_compact or "resoluc" in t_compact)
        or re.search(r"\b\d+\s+egun(?: baliodun)?\b", t_compact)
        or re.search(r"\b\d+\s+hilabete\b", t_compact)
    ):
        return "plazos"

    # 4) RECURSOS / ERREKURTSOAK
    if (
        "recurso" in t_compact
        or "reposicion" in t_compact
        or "reposición" in t_compact
        or "contencioso" in t_compact
        or "vía administrativa" in t_compact
        or "juzgados de lo contencioso" in t_compact
        or "errekurtso" in t_compact
        or "gora jotzeko" in t_compact
        or "administrazioarekiko auzi" in t_compact
    ):
        return "recurso"
    
    # 5) EVALUACIÓN / EBALUAZIOA
    if (
        "evaluación" in t_compact
        or "evaluacion" in t_compact
        or "criterios" in t_compact
        or "puntuación" in t_compact
        or "puntuacion" in t_compact
        or "ebaluazio" in t_compact
        or "irizpide" in t_compact
        or "gehienez" in t_compact
        or "tarte" in t_compact
        or "ikerketa" in t_compact
        or "irakaskuntza" in t_compact
        or "kudeaketa" in t_compact
        or "ezagutzaren transferentzia" in t_compact
        or "dibulgazio" in t_compact
        or "atalka betetzea" in t_compact
        or "a mailaren sartzea" in t_compact
    ):
        return "evaluacion"
    
    # 6) PROCEDIMIENTO / TRAMITACIÓN / IZAPIDETZEA
    if (
        "sede electrónica" in t_compact
        or "sede electronica" in t_compact
        or "registro telemático" in t_compact
        or "registro telematico" in t_compact
        or "firma electrónica" in t_compact
        or "firma electronica" in t_compact
        or ("certificado" in t_compact and ("firma" in t_compact or "electr" in t_compact))
        or "cumplimentación" in t_compact
        or "cumplimentacion" in t_compact
        or "formalización" in t_compact
        or "formalizacion" in t_compact
        or "representación voluntaria" in t_compact
        or "representacion voluntaria" in t_compact
        or "aplicación informática" in t_compact
        or "aplicacion informatica" in t_compact
        or "egiaztapena" in t_compact
        or "eskaera" in t_compact
        or "eskabidea" in t_compact
        or "izapidet" in t_compact
        or "sinadura elektroniko" in t_compact
        or "ziurtagiri" in t_compact
        or "egoitza elektroniko" in t_compact
        or "erregistro telematiko" in t_compact
        or "ordezkaritza" in t_compact
        or "aplikazio informatiko" in t_compact
    ):
        return "procedimiento"

    # 7) REQUISITOS / BALDINTZAK
    if (
        "serán requisitos imprescindibles" in t_compact
        or "seran requisitos imprescindibles" in t_compact
        or "betebehar" in t_compact
        or "baldintza" in t_compact
        or "ezinbesteko baldintza" in t_compact
    ):
        return "requisitos"

    if re.search(r"(?:^|\n)\s*▪\s+", content):
        if re.search(r"\bobtener\s+al\s+menos\s+\d+(?:[.,]\d+)?\s+puntos\b", t_compact):
            return "requisitos"
        if ("puntuación máxima" in t_compact or "puntuacion maxima" in t_compact) and ("puntuación mínima" in t_compact or "puntuacion minima" in t_compact):
            return "requisitos"

    if ("puntuación máxima" in t_compact or "puntuacion maxima" in t_compact) and ("apartados" in t_compact) and ("total" in t_compact):
        return "requisitos"



    return None

# =============================================================================
# HELPERS: SLUG
# =============================================================================
def _slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = (s.replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u").replace("ñ","n"))
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:80] if s else "x"


# =============================================================================
# FIGURA (DINÁMICA)
# =============================================================================
def detect_figura_from_marker(page_content: str) -> str | None:
    m = re.search(r"-----\s*FIGURA\s*-----\s*([a-z0-9_]+)", page_content, flags=re.I)
    return m.group(1).strip().lower() if m else None


def detect_figura_from_text(page_content: str) -> str | None:
    m_text = re.search(r"----- TEXT -----\n(.*?)(?=\n-----|\Z)", page_content, flags=re.S)
    text = (m_text.group(1) if m_text else page_content)
    t = re.sub(r"\s+", " ", text).strip()

    # patrón fuerte
    m = re.search(
        r"\bCRITERIOS\s+PARA\s+LA\s+EVALUACI[ÓO]N\b.*?\bDEL\b\s+(.+?)(?:\s+Ser[aá]n|\s+Seran|\s*$)",
        t, flags=re.I
    )
    if m:
        return m.group(1).strip()[:180]

    # patrón suelto
    m2 = re.search(r"\b(PROFESORADO\s+[A-ZÁÉÍÓÚÑ ]{3,120})\b", t, flags=re.I)
    if m2:
        return m2.group(1).strip()[:180]

    m3 = re.search(r"\b(PERSONAL\s+INVESTIGADOR\s+CONTRATADO\b.*?)(?:\s+Ser[aá]n|\s+Seran|\s*$)", t, flags=re.I)
    if m3:
        return m3.group(1).strip()[:180]

    return None


def ensure_figura(fig_label: str, doc_id: str, figuras_state: dict) -> tuple[str, str]:
    slug = _slugify(fig_label)
    if slug in figuras_state["by_slug"]:
        return figuras_state["by_slug"][slug], ""
    fig_uri = f"base:fig_{doc_id}_{slug}"
    figuras_state["by_slug"][slug] = fig_uri
    fig_ttl = (
        f"{fig_uri} a u:Figura ;\n"
        f"  u:nombre {json.dumps(fig_label, ensure_ascii=False)} .\n"
    )
    figuras_state["ttl"].append(fig_ttl)
    return fig_uri, fig_ttl


# =============================================================================
# APARTADOS (DINÁMICOS)
# =============================================================================
def ensure_apartado_dynamic(label: str, doc_id: str, apartados_state: dict) -> tuple[str, str]:
    """
    Crea individuos dinámicos de u:ApartadoEvaluacion en base:
      base:ap_{doc_id}_{slug} a u:ApartadoEvaluacion ; u:nombre "..." .
    Devuelve (uri, ttl_if_new)
    """
    slug = _slugify(label)
    key = f"{doc_id}::{slug}"
    if key in apartados_state["by_key"]:
        return apartados_state["by_key"][key], ""
    ap_uri = f"base:ap_{doc_id}_{slug}"
    apartados_state["by_key"][key] = ap_uri
    ap_ttl = (
        f"{ap_uri} a u:ApartadoEvaluacion ;\n"
        f"  u:nombre {json.dumps(label, ensure_ascii=False)} .\n"
    )
    apartados_state["ttl"].append(ap_ttl)
    return ap_uri, ap_ttl


def map_or_create_apartado_from_label(label: str, doc_id: str, apartados_state: dict) -> str:
    """
    Intenta mapear a individuos estándar SOLO si hay match fuerte por keywords.
    Si no, crea apartado dinámico con el label.
    """
    s = re.sub(r"\s+", " ", (label or "")).strip().lower()

    # matches fuertes
    if "investig" in s or "transferencia" in s:
        return "u:apartado_investigacion"
    if "docen" in s or "experiencia profesional" in s:
        return "u:apartado_docencia"
    if "gestión" in s or "gestion" in s:
        return "u:apartado_gestion"
    if "formación" in s or "formacion" in s:
        return "u:apartado_formacion"
    if s.startswith("total"):
        return "u:apartado_total"

    # si no, dinámico
    ap_uri, _ = ensure_apartado_dynamic(label, doc_id, apartados_state)
    return ap_uri


def map_or_create_apartado_from_number(num: str, doc_id: str, apartados_state: dict) -> str:
    """
    Para 'apartado 2' -> apartado dinámico "apartado 2" (no asumimos semántica).
    """
    label = f"apartado {num}"
    ap_uri, _ = ensure_apartado_dynamic(label, doc_id, apartados_state)
    return ap_uri


# =============================================================================
# TEXT/TABLES + extracción determinista
# =============================================================================
def split_text_and_tables(page_text: str) -> tuple[str, list[str]]:
    t = page_text.replace("\r", "")
    m_text = re.search(r"----- TEXT -----\n(.*?)(?=\n----- TABLE|\Z)", t, flags=re.S)
    text_block = m_text.group(1).strip() if m_text else ""
    tables = []
    for m in re.finditer(r"----- TABLE \d+ -----\n(.*?)(?=\n----- TABLE|\Z)", t, flags=re.S):
        tables.append(m.group(1).strip())
    if not text_block and not tables:
        return t.strip(), []
    return text_block, tables


def _normalize_spaces(s: str) -> str:
    s = s.replace("\t", " ")
    s = re.sub(r"[ ]{2,}", " ", s)
    s = re.sub(r"\s+\|\s+", " | ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_requisitos_rulebased(page_text: str) -> list[str]:
    text_block, _tables = split_text_and_tables(page_text)
    if not text_block:
        text_block = page_text

    cutoff = None
    for pat in [r"\bPUNTUACIÓN\b", r"\bAPARTADOS\b", r"\bTOTAL\b", r"^\s*1\.\s*ACTIVIDAD\b"]:
        m = re.search(pat, text_block, flags=re.I | re.M)
        if m:
            cutoff = m.start() if cutoff is None else min(cutoff, m.start())
    if cutoff is not None and cutoff > 0:
        text_block = text_block[:cutoff]

    chunks = []
    for m in re.finditer(r"(?:^|\n)\s*▪\s*(.*?)(?=(?:\n\s*▪\s)|\Z)", text_block, flags=re.S):
        chunk = m.group(1).strip()
        chunk = re.sub(r"\s*\n\s*", " ", chunk).strip()
        chunk = re.sub(r"\s{2,}", " ", chunk)
        if chunk:
            chunks.append(chunk)
    return chunks


def requisitos_to_ttl(reqs: list[str], doc_id: str, pg_num: int, frag_uri: str, section: str) -> tuple[str, list[str]]:
    sec_individual = f"u:sec_{section}" if section != "otro" else "u:sec_otro"
    out = []
    uris = []
    for idx, desc in enumerate(reqs, start=1):
        req_uri = f"base:req_{doc_id}_p{pg_num}_{idx}"
        uris.append(req_uri)
        out.append(
            f"{req_uri} a u:Requisito ;\n"
            f"  u:descripcion {json.dumps(desc, ensure_ascii=False)} ;\n"
            f"  u:pagina {pg_num} ;\n"
            f"  u:fuenteDocumento base:doc_{doc_id} ;\n"
            f"  u:enSeccion {sec_individual} ;\n"
            f"  u:provieneDe {frag_uri} .\n"
        )
    return "\n".join(out).strip(), uris


def _try_float(num: str):
    try:
        return float(num.replace(",", "."))
    except Exception:
        return None


def parse_puntos_table_robust(table_block: str) -> dict:
    raw_lines = [ln.rstrip() for ln in table_block.replace("\r", "").split("\n") if ln.strip()]
    if not raw_lines:
        return {"rows": [], "total": None}

    joined = " ".join(raw_lines).lower()
    if "apartados" not in joined or ("puntuación" not in joined and "puntuacion" not in joined):
        return {"rows": [], "total": None}

    lines = [_normalize_spaces(ln) for ln in raw_lines]
    start_row_re = re.compile(r"^(?:\d+\s*\.-|TOTAL)\b", flags=re.I)

    rows = []
    total_val = None
    buf = []

    def flush():
        nonlocal buf, rows, total_val
        if not buf:
            return
        row = " ".join(buf)
        row = re.sub(r"\s{2,}", " ", row).strip()

        if re.match(r"^TOTAL\b", row, flags=re.I):
            m = re.search(r"(\d+(?:[.,]\d+)?)\s*puntos", row, flags=re.I)
            if m:
                total_val = _try_float(m.group(1))
            buf = []
            return

        m_ap = re.match(r"^(\d+\s*\.-\s*.+?)(?:\s*\||\s{2,}|\s+\d)", row)
        apartado = m_ap.group(1).strip() if m_ap else None

        nums = re.findall(r"(\d+(?:[.,]\d+)?)\s*puntos", row, flags=re.I)
        if apartado and nums:
            max_v = _try_float(nums[0])
            min_v = _try_float(nums[1]) if len(nums) > 1 else None
            if max_v is not None:
                rows.append({"apartado": apartado, "max": max_v, "min": min_v})

        buf = []

    for ln in lines:
        if start_row_re.match(ln):
            flush()
            buf = [ln]
        else:
            buf.append(ln)
    flush()

    if total_val is None:
        for ln in lines[::-1]:
            if "total" in ln.lower():
                m = re.search(r"(\d+(?:[.,]\d+)?)\s*puntos", ln, flags=re.I)
                if m:
                    total_val = _try_float(m.group(1))
                    break

    return {"rows": rows, "total": total_val}


def umbrales_from_tables(page_text: str) -> dict:
    _text_block, tables = split_text_and_tables(page_text)
    best = {"rows": [], "total": None}
    for tb in tables:
        parsed = parse_puntos_table_robust(tb)
        if len(parsed["rows"]) > len(best["rows"]):
            best = parsed
        if best["rows"] and parsed.get("total") is not None:
            best["total"] = parsed["total"]
    return best


def umbrales_to_ttl(umbral_data: dict, doc_id: str, pg_num: int, frag_uri: str, section: str, apartados_state: dict) -> tuple[str, list[str]]:
    sec_individual = f"u:sec_{section}" if section != "otro" else "u:sec_otro"
    ttl_lines = []
    uris = []

    for i, row in enumerate(umbral_data.get("rows", []), start=1):
        apartado_txt = (row.get("apartado") or "").strip()
        max_v = row.get("max", None)
        min_v = row.get("min", None)

        apartado_obj = map_or_create_apartado_from_label(apartado_txt, doc_id, apartados_state)

        if apartado_txt and max_v is not None:
            u_uri = f"base:umbral_{doc_id}_p{pg_num}_a{i}_max"
            uris.append(u_uri)
            ttl_lines.append(
                f"{u_uri} a u:UmbralPuntuacion ;\n"
                f"  u:apartado {apartado_obj} ;\n"
                f"  u:valor {max_v} ;\n"
                f"  u:minmax \"apartado_max\" ;\n"
                f"  u:pagina {pg_num} ;\n"
                f"  u:fuenteDocumento base:doc_{doc_id} ;\n"
                f"  u:enSeccion {sec_individual} ;\n"
                f"  u:provieneDe {frag_uri} .\n"
            )

        if apartado_txt and min_v is not None:
            u_uri = f"base:umbral_{doc_id}_p{pg_num}_a{i}_min"
            uris.append(u_uri)
            ttl_lines.append(
                f"{u_uri} a u:UmbralPuntuacion ;\n"
                f"  u:apartado {apartado_obj} ;\n"
                f"  u:valor {min_v} ;\n"
                f"  u:minmax \"apartado_min\" ;\n"
                f"  u:pagina {pg_num} ;\n"
                f"  u:fuenteDocumento base:doc_{doc_id} ;\n"
                f"  u:enSeccion {sec_individual} ;\n"
                f"  u:provieneDe {frag_uri} .\n"
            )

    total = umbral_data.get("total", None)
    if total is not None:
        u_uri = f"base:umbral_{doc_id}_p{pg_num}_total_max"
        uris.append(u_uri)
        ttl_lines.append(
            f"{u_uri} a u:UmbralPuntuacion ;\n"
            f"  u:apartado u:apartado_total ;\n"
            f"  u:valor {total} ;\n"
            f"  u:minmax \"total_max\" ;\n"
            f"  u:pagina {pg_num} ;\n"
            f"  u:fuenteDocumento base:doc_{doc_id} ;\n"
            f"  u:enSeccion {sec_individual} ;\n"
            f"  u:provieneDe {frag_uri} .\n"
        )

    return "\n".join(ttl_lines).strip(), uris


def _to_decimal_str(n: str) -> str:
    n = n.strip().replace(",", ".")
    return n if "." in n else f"{n}.0"


def extract_umbral_from_text_and_tables(page_text: str, doc_id: str, apartados_state: dict) -> list[dict]:
    """
    General:
      - total_min: "Obtener al menos X puntos" -> u:apartado_total
      - mínimos por apartado: "mínimo de X puntos en el apartado N" -> apartado dinámico "apartado N"
    """
    umbrales: list[dict] = []
    t = page_text

    # TOTAL mínimo
    m = re.search(r"\bObtener\s+al\s+menos\s+(\d+(?:[.,]\d+)?)\s+puntos\b", t, flags=re.IGNORECASE)
    if m:
        umbrales.append({"apartado": "u:apartado_total", "valor": _to_decimal_str(m.group(1)), "minmax": "total_min"})

    # mínimos por apartado N (DINÁMICO)
    for mm in re.finditer(
        r"m[ií]nimo\s+de\s+(\d+(?:[.,]\d+)?)\s+puntos\s+en\s+el\s+apartado\s+(\d+)",
        t, flags=re.I
    ):
        val = _to_decimal_str(mm.group(1))
        apn = mm.group(2)
        apartado_uri = map_or_create_apartado_from_number(apn, doc_id, apartados_state)
        umbrales.append({"apartado": apartado_uri, "valor": val, "minmax": "apartado_min"})

    # TOTAL máximo solo si hay señales de tabla
    if re.search(r"\bAPARTADOS\b|\bPUNTUACIÓN\s+(MÁXIMA|MINIMA|MÍNIMA)\b|\bPOR\s+APARTADO\b", t, flags=re.IGNORECASE):
        m2 = re.search(r"\bTOTAL\s+(\d+(?:[.,]\d+)?)\s+puntos\b", t, flags=re.IGNORECASE)
        if m2:
            umbrales.append({"apartado": "u:apartado_total", "valor": _to_decimal_str(m2.group(1)), "minmax": "total_max"})

    # Dedup
    seen = set()
    out = []
    for u in umbrales:
        key = (u["apartado"], u["valor"], u["minmax"])
        if key in seen:
            continue
        seen.add(key)
        out.append(u)
    return out


def build_umbral_ttl(pg_num: int, frag_uri: str, doc_id: str, page_text: str, apartados_state: dict) -> tuple[str, list[str]]:
    umbrales = extract_umbral_from_text_and_tables(page_text, doc_id, apartados_state)
    if not umbrales:
        return "", []

    lines = []
    uris = []
    n = 1000
    for uobj in umbrales:
        subj = f"base:umbral_{doc_id}_p{pg_num}_{n}"
        uris.append(subj)
        n += 1
        lines.append(
            f"{subj} a u:UmbralPuntuacion ;\n"
            f"  u:valor {uobj['valor']} ;\n"
            f"  u:apartado {uobj['apartado']} ;\n"
            f"  u:minmax \"{uobj['minmax']}\" ;\n"
            f"  u:pagina {pg_num} ;\n"
            f"  u:fuenteDocumento base:doc_{doc_id} ;\n"
            f"  u:provieneDe {frag_uri} .\n"
        )
    return "\n".join(lines).strip(), uris


def extract_faq_pairs(page_text: str) -> list[tuple[str, str]]:
    """
    Extrae FAQs numeradas del tipo:
      1.- Pregunta?
      Respuesta...

      2.- Pregunta?
      Respuesta...
    """
    txt = (page_text or "").replace("\r", "").strip()
    if not txt:
        return []

    # Normaliza un poco, pero conserva saltos para segmentar mejor
    txt = re.sub(r"\n{2,}", "\n", txt)

    # Divide por inicio de pregunta numerada: 1.-  2.-  34.- ...
    blocks = re.split(r'(?=^\s*\d+\s*\.-\s*)', txt, flags=re.M)

    pairs: list[tuple[str, str]] = []

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Quita la numeración inicial
        block = re.sub(r'^\s*(\d+)\s*\.-\s*', '', block)

        # Compacta espacios dentro del bloque
        block = re.sub(r'\s+', ' ', block).strip()

        # Separa pregunta y respuesta en el primer ?
        m = re.match(r'(.+?\?)\s*(.+)', block)
        if not m:
            continue

        question = m.group(1).strip()
        answer = m.group(2).strip()

        # Limpieza mínima
        question = re.sub(r'\s+', ' ', question)
        answer = re.sub(r'\s+', ' ', answer)

        if len(question) >= 6 and len(answer) >= 8:
            pairs.append((question, answer))

    return pairs

# ========= MAIN =========
if __name__ == "__main__":
    args = parse_args()
    print("📖 Cargando ontología...")
    schema = extract_ontology_schema(args.input_rdf)
    forced_prefixes = build_forced_prefixes(schema["namespaces"])

    prompt_template = Path(args.prompt_file).read_text(encoding="utf-8")
    fix_template = Path(args.fix_prompt_file).read_text(encoding="utf-8")
    pages = split_pages(Path(args.input_txt).read_text(encoding="utf-8"))
    doc_id = Path(args.input_txt).stem

    # Estado figuras y apartados dinámicos
    figuras_state = {"by_slug": {}, "ttl": []}
    apartados_state = {"by_key": {}, "ttl": []}

    last_fig_uri = None  # arrastre de figura

    doc_title = Path(args.input_txt).stem.replace("_", " ")
    ttl_parts = [
        forced_prefixes,
        f'base:doc_{doc_id} a u:Documento ;\n  u:titulo {json.dumps(doc_title, ensure_ascii=False)} .\n'
    ]
    page_items = sorted(pages.items())[:args.max_pages] if args.max_pages > 0 else sorted(pages.items())
    is_faq_doc = "galdera_ohiko" in doc_id.lower() or "faq" in doc_id.lower()

    for pg_num, content in page_items:
        if not content.strip():
            continue

        content = filter_bulletin_noise(content)
        content = clean_page_content(content)
        if not content.strip():
            continue

        # FAQ: troceo pregunta-respuesta para evitar fragmentos gigantes
        if is_faq_doc:
            faq_pairs = extract_faq_pairs(content)
            if faq_pairs:
                faq_blocks = []
                for i, (question, answer) in enumerate(faq_pairs, start=1):
                    frag_uri = f"base:frag_{doc_id}_p{pg_num}_{i}"
                    qa_text = f"Pregunta: {question} Respuesta: {answer}"
                    faq_blocks.append(
                        f"{frag_uri} a u:Fragmento ;\n"
                        f"  u:pagina {pg_num} ;\n"
                        f"  u:fuenteDocumento base:doc_{doc_id} ;\n"
                        f"  u:enSeccion u:sec_otro ;\n"
                        f"  u:textoFuente {json.dumps(qa_text[:1000], ensure_ascii=False)} .\n"
                    )
                header = f"# --- PAG {pg_num} (faq) ---\n" if args.debug_comments else ""
                ttl_parts.append(header + "\n".join(faq_blocks) + "\n")
                continue

        # 0) Figura dinámica (marker > texto)
        fig_from_marker = detect_figura_from_marker(content)
        fig_label = None
        if fig_from_marker:
            fig_label = fig_from_marker.replace("_", " ").upper()
        else:
            fig_label = detect_figura_from_text(content)

        if fig_label:
            fig_uri, _ = ensure_figura(fig_label, doc_id, figuras_state)
            last_fig_uri = fig_uri

        # 1) Sección
        section_rb = rulebased_section(content)
        section = section_rb if section_rb else llm_classify_section(content, args.model)
        sec_individual = f"u:sec_{section}" if section != "otro" else "u:sec_otro"

        # 2) Fragmento
        norm_txt = re.sub(r"\s+", " ", content).strip()
        norm_txt = norm_txt.replace("----- TEXT -----", " ").strip()
        snippet = norm_txt[:1000] if len(norm_txt) > 1000 else norm_txt
        frag_uri = f"base:frag_{doc_id}_p{pg_num}"

        frag_ttl = (
            f"{frag_uri} a u:Fragmento ;\n"
            f"  u:pagina {pg_num} ;\n"
            f"  u:fuenteDocumento base:doc_{doc_id} ;\n"
            f"  u:enSeccion {sec_individual} ;\n"
            f"  u:textoFuente {json.dumps(snippet, ensure_ascii=False)} .\n"
        )

        print(f"📄 Página {pg_num} ({section})...")

        # ========= REQUISITOS =========
        if section == "requisitos":
            reqs = extract_requisitos_rulebased(content)
            reqs_ttl, req_uris = requisitos_to_ttl(reqs, doc_id, pg_num, frag_uri, section) if reqs else ("", [])

            umbrales_ttl_texto, umbral_text_uris = build_umbral_ttl(pg_num, frag_uri, doc_id, content, apartados_state)

            umbral_data = umbrales_from_tables(content)
            umbrales_ttl_tabla, umbral_table_uris = (
                umbrales_to_ttl(umbral_data, doc_id, pg_num, frag_uri, section, apartados_state)
                if (umbral_data.get("rows") or umbral_data.get("total") is not None)
                else ("", [])
            )

            # Enlaces figura -> requisitos/umbrales
            links = []
            if last_fig_uri:
                for ruri in req_uris:
                    links.append(f"{last_fig_uri} u:tieneRequisito {ruri} .")
                for uuri in (umbral_text_uris + umbral_table_uris):
                    links.append(f"{last_fig_uri} u:tieneUmbral {uuri} .")

            candidate = frag_ttl
            if reqs_ttl:
                candidate += "\n\n" + reqs_ttl
            if umbrales_ttl_texto:
                candidate += "\n\n" + umbrales_ttl_texto
            if umbrales_ttl_tabla:
                candidate += "\n\n" + umbrales_ttl_tabla
            if links:
                candidate += "\n\n" + "\n".join(links) + "\n"

            candidate = normalize_minmax(candidate)
            header = f"# --- PAG {pg_num} ({section}) ---\n" if args.debug_comments else ""
            ttl_parts.append(header + candidate + "\n")
            continue

        # ========= RESTO: LLM =========
        # ( no forzamos apartados aquí salvo umbrales deterministas)
        full_prompt = prompt_template.format(
            ONTOLOGIA="",
            TEXTO=content,
            PAGINA=pg_num,
            DOC_ID=doc_id,
            FRAG_URI=frag_uri,
            SECTION=section,
            FORCED_PREFIXES=forced_prefixes
        )

        try:
            raw_res = call_ollama(full_prompt, args.model)
            ttl_body = remove_prefix_lines(sanitize_ttl(raw_res))
            ttl_body = strip_doc_and_frag(ttl_body, doc_id, frag_uri)
            ttl_body = strip_any_fragment_blocks(ttl_body)

            det_umbral_ttl, det_umbral_uris = build_umbral_ttl(pg_num, frag_uri, doc_id, content, apartados_state)

            links = []
            if last_fig_uri:
                for uuri in det_umbral_uris:
                    links.append(f"{last_fig_uri} u:tieneUmbral {uuri} .")

            candidate = frag_ttl + "\n"
            if det_umbral_ttl:
                candidate += det_umbral_ttl + "\n\n"
            candidate += ttl_body
            if links:
                candidate += "\n\n" + "\n".join(links) + "\n"
            candidate = normalize_minmax(candidate)

            if not validate_ttl(candidate, forced_prefixes):
                print(f"⚠️ Reparando pág {pg_num}...")
                fix_prompt = fix_template.format(FORCED_PREFIXES=forced_prefixes, TTL=candidate)
                fixed = remove_prefix_lines(sanitize_ttl(call_ollama(fix_prompt, args.model)))
                fixed = strip_doc_and_frag(fixed, doc_id, frag_uri)
                fixed = strip_any_fragment_blocks(fixed)
                fixed = normalize_minmax(fixed)

                if validate_ttl(fixed, forced_prefixes):
                    candidate = fixed
                else:
                    candidate = frag_ttl

            header = f"# --- PAG {pg_num} ({section}) ---\n" if args.debug_comments else ""
            ttl_parts.append(header + candidate + "\n")

        except Exception as e:
            print(f"❌ Error pág {pg_num}: {e}")
            ttl_parts.append(frag_ttl + "\n")

    # Inserta definiciones dinámicas al principio
    inserts = []

    if figuras_state["ttl"]:
        inserts.append("\n# --- FIGURAS DETECTADAS (DINÁMICAS) ---\n" + "\n".join(figuras_state["ttl"]) + "\n")

    if apartados_state["ttl"]:
        inserts.append("\n# --- APARTADOS DETECTADOS (DINÁMICOS) ---\n" + "\n".join(apartados_state["ttl"]) + "\n")

    if inserts:
        ttl_parts.insert(2, "\n".join(inserts))

    Path(args.output_ttl).write_text("\n".join(ttl_parts), encoding="utf-8")
    print(f"✅ Proceso terminado: {args.output_ttl}")