import re
import pandas as pd
from rdflib import Graph, Namespace, Literal, RDF, URIRef
from rdflib.namespace import XSD

def slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-z0-9_]", "", s)
    return s or "x"

def normalize_date(value) -> str:
    """
    Devuelve fecha en formato ISO YYYY-MM-DD.
    Acepta:
      - datetime de Excel (pandas Timestamp)
      - "DD/MM/YYYY"
      - "YYYY-MM-DD"
      - "YYYY-MM" (se convierte a YYYY-MM-01)
    """
    if value is None:
        return ""

    # Si viene como datetime / Timestamp de pandas
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")

    s = str(value).strip()
    if not s or s.lower() == "nan":
        return ""

    # DD/MM/YYYY
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", s)
    if m:
        dd, mm, yyyy = m.groups()
        return f"{yyyy}-{mm}-{dd}"

    # YYYY-MM
    if re.fullmatch(r"\d{4}-\d{2}", s):
        return s + "-01"

    # Asumimos YYYY-MM-DD
    return s

def safe_int(value):
    try:
        if value is None:
            return None
        s = str(value).strip()
        if not s or s.lower() == "nan":
            return None
        return int(float(s))
    except Exception:
        return None

def safe_float(value):
    try:
        if value is None:
            return None
        s = str(value).strip().replace(",", ".")
        if not s or s.lower() == "nan":
            return None
        return float(s)
    except Exception:
        return None

# ========= CONFIG =========
XLSX_PATH = r"C:\Users\oiher\Desktop\Excel_TFG\unibasq_protocolo_2025.xlsx"
OUT_TTL   = r"C:\Users\oiher\Desktop\tfg-unibasq\rdf\unibasq_protocolo_2025.ttl"

BASE = Namespace("http://example.org/unibasq/")
U    = Namespace("http://example.org/unibasq/ontology#")

g = Graph()
g.bind("u", U)
g.bind("base", BASE)

# ========= CLASES =========
Documento = U.Documento
Figura = U.Figura
UmbralPuntuacion = U.UmbralPuntuacion
Requisito = U.Requisito
Apartado = U.ApartadoEvaluacion

# ========= PROPIEDADES =========
p_titulo = U.titulo
p_organismo = U.organismo
p_fecha = U.fecha
p_url = U.url

p_nombre = U.nombre

p_tipo = U.tipo
p_apartado = U.apartado
p_descripcion = U.descripcion
p_valor = U.valor
p_unidad = U.unidad
p_pagina = U.pagina
p_fuente = U.fuenteDocumento

p_tiene_requisito = U.tieneRequisito
p_tiene_umbral = U.tieneUmbral

# ========= CARGA EXCEL =========
xls = pd.ExcelFile(XLSX_PATH)
docs = pd.read_excel(xls, "Documentos").fillna("")
figs = pd.read_excel(xls, "Figuras").fillna("")
cr   = pd.read_excel(xls, "Criterios_y_Requisitos").fillna("")

# ========= DOCUMENTOS =========
doc_uri_by_id = {}
for _, row in docs.iterrows():
    doc_id = slug(str(row.get("document_id", "")))
    if not doc_id:
        continue

    doc_uri = BASE[f"doc/{doc_id}"]
    doc_uri_by_id[doc_id] = doc_uri

    g.add((doc_uri, RDF.type, Documento))

    titulo = str(row.get("titulo", "")).strip()
    if titulo:
        g.add((doc_uri, p_titulo, Literal(titulo)))

    organismo = str(row.get("organismo", "")).strip()
    if organismo:
        g.add((doc_uri, p_organismo, Literal(organismo)))

    fecha = normalize_date(row.get("fecha"))
    if fecha:
        g.add((doc_uri, p_fecha, Literal(fecha, datatype=XSD.date)))

    url = str(row.get("url", "")).strip()
    if url:
        g.add((doc_uri, p_url, Literal(url, datatype=XSD.anyURI)))

# ========= FIGURAS =========
fig_uri_by_id = {}
for _, row in figs.iterrows():
    fig_id = slug(str(row.get("figura_id", "")))
    if not fig_id:
        continue

    fig_uri = BASE[f"fig/{fig_id}"]
    fig_uri_by_id[fig_id] = fig_uri

    g.add((fig_uri, RDF.type, Figura))

    nombre = str(row.get("nombre", "")).strip()
    if nombre:
        g.add((fig_uri, p_nombre, Literal(nombre)))

# ========= APARTADOS (ENTIDADES) =========
apartado_uri = {}

def get_apartado_uri(nombre: str) -> URIRef:
    nombre = (nombre or "").strip()
    if not nombre:
        nombre = "total"
    ap_id = slug(nombre)

    if ap_id not in apartado_uri:
        uri = BASE[f"apartado/{ap_id}"]
        apartado_uri[ap_id] = uri
        g.add((uri, RDF.type, Apartado))
        g.add((uri, p_nombre, Literal(nombre)))
    return apartado_uri[ap_id]

# ========= CRITERIOS Y REQUISITOS =========
for idx, row in cr.iterrows():
    fig_id = slug(str(row.get("figura_id", "")))
    tipo = slug(str(row.get("tipo", "")))

    apartado = str(row.get("apartado", "")).strip()
    desc = str(row.get("descripcion", "")).strip()
    unidad = str(row.get("unidad", "")).strip()

    pagina = safe_int(row.get("pagina"))
    val = safe_float(row.get("valor"))

    doc_id = slug(str(row.get("document_id", "")))

    if fig_id not in fig_uri_by_id:
        continue

    fig_uri = fig_uri_by_id[fig_id]
    doc_uri = doc_uri_by_id.get(doc_id)

    # ---- REQUISITOS CUALITATIVOS ----
    if tipo == "requisito":
        req_uri = BASE[f"req/{fig_id}_{idx}"]
        g.add((req_uri, RDF.type, Requisito))

        if desc:
            g.add((req_uri, p_descripcion, Literal(desc)))
        if pagina is not None:
            g.add((req_uri, p_pagina, Literal(pagina, datatype=XSD.integer)))
        if doc_uri:
            g.add((req_uri, p_fuente, doc_uri))

        g.add((fig_uri, p_tiene_requisito, req_uri))
        continue

    # ---- UMBRALES ----
    umbral_uri = BASE[f"umbral/{fig_id}_{tipo}_{slug(apartado) or 'na'}_{idx}"]
    g.add((umbral_uri, RDF.type, UmbralPuntuacion))
    if tipo:
        g.add((umbral_uri, p_tipo, Literal(tipo)))

    # Apartado como ENTIDAD
    g.add((umbral_uri, p_apartado, get_apartado_uri(apartado if apartado else "total")))

    if desc:
        g.add((umbral_uri, p_descripcion, Literal(desc)))
    if val is not None:
        g.add((umbral_uri, p_valor, Literal(val, datatype=XSD.decimal)))
    if unidad:
        g.add((umbral_uri, p_unidad, Literal(unidad)))
    if pagina is not None:
        g.add((umbral_uri, p_pagina, Literal(pagina, datatype=XSD.integer)))
    if doc_uri:
        g.add((umbral_uri, p_fuente, doc_uri))

    g.add((fig_uri, p_tiene_umbral, umbral_uri))

# ========= EXPORT =========
g.serialize(destination=OUT_TTL, format="turtle")
print(f"OK: generado {OUT_TTL} con {len(g)} triples")
