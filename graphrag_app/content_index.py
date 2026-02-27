#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import requests


# ----------------------------
# Config
# ----------------------------

DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
DEFAULT_EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
# Cache global para SentenceTransformers (evita recargar el modelo por cada texto)
_ST_MODEL = None
_ST_MODEL_NAME = None

DEFAULT_FUSEKI_QUERY = os.getenv(
    "FUSEKI_QUERY_URL",
    "http://localhost:3030/academic-career/query" 
)

U = "http://example.org/academic-career/ontology#"


# ----------------------------
# Helpers
# ----------------------------

def sparql_select(endpoint: str, query: str, timeout: int = 60) -> List[dict]:
    r = requests.post(
        endpoint,
        data={"query": query},
        headers={"Accept": "application/sparql-results+json"},
        timeout=timeout,
    )
    r.raise_for_status()
    data = r.json()
    return data["results"]["bindings"]


def local_st_embed(model_name: str, text: str):
    """
    Embedding local con SentenceTransformers.
    Cachea el modelo en memoria para no recargarlo.
    """
    global _ST_MODEL, _ST_MODEL_NAME

    from sentence_transformers import SentenceTransformer

    if _ST_MODEL is None or _ST_MODEL_NAME != model_name:
        _ST_MODEL = SentenceTransformer(model_name)
        _ST_MODEL_NAME = model_name

    # normalize_embeddings=True ayuda mucho con cosine similarity / FAISS IP
    emb = _ST_MODEL.encode([text], normalize_embeddings=True)
    return emb[0]

def normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def short(s: str, n: int = 800) -> str:
    s = normalize_ws(s)
    return s if len(s) <= n else s[:n].rstrip() + "…"


# ----------------------------
# Data structures
# ----------------------------

@dataclass
class Fragmento:
    uri: str
    pagina: Optional[int]
    texto: str
    doc_uri: Optional[str] = None
    doc_titulo: Optional[str] = None
    seccion_uri: Optional[str] = None
    seccion_nombre: Optional[str] = None


@dataclass
class Requisito:
    uri: str
    descripcion: str
    proviene_de: Optional[str]  # frag URI
    pagina: Optional[int]
    doc_titulo: Optional[str]
    seccion_nombre: Optional[str]
    contexto: str


@dataclass
class Umbral:
    uri: str
    valor: Optional[str]
    minmax: Optional[str]
    apartado_uri: Optional[str]
    apartado_nombre: Optional[str]
    proviene_de: Optional[str]
    pagina: Optional[int]
    doc_titulo: Optional[str]
    seccion_nombre: Optional[str]
    contexto: str


# ----------------------------
# SPARQL queries
# ----------------------------

Q_FRAGS = f"""
PREFIX u: <{U}>
SELECT ?frag ?pagina ?texto ?doc ?titulo ?sec ?secNombre WHERE {{
  ?frag a u:Fragmento ;
        u:textoFuente ?texto ;
        u:pagina ?pagina ;
        u:fuenteDocumento ?doc .
  OPTIONAL {{ ?doc u:titulo ?titulo . }}
  OPTIONAL {{
    ?frag u:enSeccion ?sec .
    OPTIONAL {{ ?sec u:nombre ?secNombre . }}
  }}
}}
"""

Q_REQS = f"""
PREFIX u: <{U}>
SELECT ?req ?desc ?frag ?pagina ?titulo ?secNombre WHERE {{
  ?req a u:Requisito ;
       u:descripcion ?desc .
  OPTIONAL {{
    ?req u:provieneDe ?frag .
    OPTIONAL {{ ?frag u:pagina ?pagina . }}
    OPTIONAL {{
      ?frag u:fuenteDocumento ?doc .
      OPTIONAL {{ ?doc u:titulo ?titulo . }}
    }}
    OPTIONAL {{
      ?frag u:enSeccion ?sec .
      OPTIONAL {{ ?sec u:nombre ?secNombre . }}
    }}
  }}
}}
"""

Q_UMBRALES = f"""
PREFIX u: <{U}>
SELECT ?umb ?valor ?minmax ?apartado ?apartadoNombre ?frag ?pagina ?titulo ?secNombre WHERE {{
  ?umb a u:UmbralPuntuacion .
  OPTIONAL {{ ?umb u:valor ?valor . }}
  OPTIONAL {{ ?umb u:minmax ?minmax . }}
  OPTIONAL {{
    ?umb u:apartado ?apartado .
    OPTIONAL {{ ?apartado u:nombre ?apartadoNombre . }}
  }}
  OPTIONAL {{
    ?umb u:provieneDe ?frag .
    OPTIONAL {{ ?frag u:pagina ?pagina . }}
    OPTIONAL {{
      ?frag u:fuenteDocumento ?doc .
      OPTIONAL {{ ?doc u:titulo ?titulo . }}
    }}
    OPTIONAL {{
      ?frag u:enSeccion ?sec .
      OPTIONAL {{ ?sec u:nombre ?secNombre . }}
    }}
  }}
}}
"""


# ----------------------------
# Build content entries
# ----------------------------

def load_fragments(fuseki_query_url: str) -> Dict[str, Fragmento]:
    rows = sparql_select(fuseki_query_url, Q_FRAGS)
    frags: Dict[str, Fragmento] = {}

    for b in rows:
        uri = b["frag"]["value"]
        pagina = int(b["pagina"]["value"]) if "pagina" in b else None
        texto = b["texto"]["value"] if "texto" in b else ""
        doc_uri = b["doc"]["value"] if "doc" in b else None
        titulo = b["titulo"]["value"] if "titulo" in b else None
        sec_uri = b["sec"]["value"] if "sec" in b else None
        sec_nombre = b["secNombre"]["value"] if "secNombre" in b else None

        # Deduplicate by URI: keep the longer texto (usually better)
        if uri in frags:
            if len(texto) > len(frags[uri].texto):
                frags[uri].texto = texto
            continue

        frags[uri] = Fragmento(
            uri=uri,
            pagina=pagina,
            texto=texto,
            doc_uri=doc_uri,
            doc_titulo=titulo,
            seccion_uri=sec_uri,
            seccion_nombre=sec_nombre,
        )

    return frags


def load_requisitos(fuseki_query_url: str, frags: Dict[str, Fragmento]) -> List[Requisito]:
    rows = sparql_select(fuseki_query_url, Q_REQS)
    reqs: List[Requisito] = []

    for b in rows:
        uri = b["req"]["value"]
        desc = b["desc"]["value"]
        frag = b["frag"]["value"] if "frag" in b else None
        pagina = int(b["pagina"]["value"]) if "pagina" in b else None
        titulo = b["titulo"]["value"] if "titulo" in b else None
        sec_nombre = b["secNombre"]["value"] if "secNombre" in b else None

        contexto = ""
        if frag and frag in frags:
            contexto = short(frags[frag].texto, 900)

            # si no venía pagina/titulo/section del query por algún motivo, las cogemos del frag
            if pagina is None:
                pagina = frags[frag].pagina
            if not titulo:
                titulo = frags[frag].doc_titulo
            if not sec_nombre:
                sec_nombre = frags[frag].seccion_nombre

        reqs.append(
            Requisito(
                uri=uri,
                descripcion=desc,
                proviene_de=frag,
                pagina=pagina,
                doc_titulo=titulo,
                seccion_nombre=sec_nombre,
                contexto=contexto,
            )
        )

    return reqs


def load_umbrales(fuseki_query_url: str, frags: Dict[str, Fragmento]) -> List[Umbral]:
    rows = sparql_select(fuseki_query_url, Q_UMBRALES)
    umbs: List[Umbral] = []

    for b in rows:
        uri = b["umb"]["value"]
        valor = b["valor"]["value"] if "valor" in b else None
        minmax = b["minmax"]["value"] if "minmax" in b else None
        apartado_uri = b["apartado"]["value"] if "apartado" in b else None
        apartado_nombre = b["apartadoNombre"]["value"] if "apartadoNombre" in b else None
        frag = b["frag"]["value"] if "frag" in b else None
        pagina = int(b["pagina"]["value"]) if "pagina" in b else None
        titulo = b["titulo"]["value"] if "titulo" in b else None
        sec_nombre = b["secNombre"]["value"] if "secNombre" in b else None

        contexto = ""
        if frag and frag in frags:
            contexto = short(frags[frag].texto, 900)
            if pagina is None:
                pagina = frags[frag].pagina
            if not titulo:
                titulo = frags[frag].doc_titulo
            if not sec_nombre:
                sec_nombre = frags[frag].seccion_nombre

        umbs.append(
            Umbral(
                uri=uri,
                valor=valor,
                minmax=minmax,
                apartado_uri=apartado_uri,
                apartado_nombre=apartado_nombre,
                proviene_de=frag,
                pagina=pagina,
                doc_titulo=titulo,
                seccion_nombre=sec_nombre,
                contexto=contexto,
            )
        )

    return umbs


def build_content_meta(frags: Dict[str, Fragmento], reqs: List[Requisito], umbs: List[Umbral]) -> List[dict]:
    out: List[dict] = []

    # Fragments (optional but useful for fallback retrieval)
    for f in frags.values():
        doc = f.doc_titulo or ""
        sec = f.seccion_nombre or ""
        text = (
            "TIPO: Fragmento\n"
            f"DOC: {doc}\n"
            f"SECCION: {sec}\n"
            f"PAGINA: {f.pagina if f.pagina is not None else ''}\n"
            f"TEXTO: {short(f.texto, 1200)}"
        )
        out.append({
            "kind": "frag",
            "frag_uri": f.uri,
            "pagina": str(f.pagina) if f.pagina is not None else "",
            "doc_titulo": doc,
            "seccion": sec,
            "texto": f.texto,
            "text": text,
        })

    # Requisitos
    for r in reqs:
        doc = r.doc_titulo or ""
        sec = r.seccion_nombre or ""
        text = (
            "TIPO: Requisito\n"
            f"DOC: {doc}\n"
            f"SECCION: {sec}\n"
            f"DESCRIPCION: {normalize_ws(r.descripcion)}\n"
            f"PAGINA: {r.pagina if r.pagina is not None else ''}\n"
            f"CONTEXTO: {r.contexto}"
        )
        out.append({
            "kind": "req",
            "req_uri": r.uri,
            "req_desc": r.descripcion,
            "provieneDe": r.proviene_de,
            "pagina": str(r.pagina) if r.pagina is not None else "",
            "doc_titulo": doc,
            "seccion": sec,
            "text": text,
        })

    # Umbrales (aquí es donde antes te salía n/a)
    for u in umbs:
        doc = u.doc_titulo or ""
        sec = u.seccion_nombre or ""
        apartado = u.apartado_nombre or (u.apartado_uri or "")
        text = (
            "TIPO: Umbral\n"
            f"DOC: {doc}\n"
            f"SECCION: {sec}\n"
            f"APARTADO: {apartado}\n"
            f"VALOR: {u.valor or ''}\n"
            f"MINMAX: {u.minmax or ''}\n"
            f"PAGINA: {u.pagina if u.pagina is not None else ''}\n"
            f"CONTEXTO: {u.contexto}"
        )
        out.append({
            "kind": "umbral",
            "umbral_uri": u.uri,
            "valor": u.valor or "",
            "minmax": u.minmax or "",
            "apartado_uri": u.apartado_uri or "",
            "apartado": apartado,
            "provieneDe": u.proviene_de,
            "pagina": str(u.pagina) if u.pagina is not None else "",
            "doc_titulo": doc,
            "seccion": sec,
            "text": text,
        })

    return out


# ----------------------------
# Build FAISS
# ----------------------------

def build_faiss_index(
    items: List[dict],
    ollama_url: str,
    embed_model: str,
    out_index_path: str,
    out_meta_path: str,
    batch: int = 64,
) -> None:

    texts = [it["text"] for it in items]
    embs: List[List[float]] = []

    for i in range(0, len(texts), batch):
        chunk = texts[i:i + batch]
        for t in chunk:
            embs.append(local_st_embed(embed_model, t))

        if (i // batch) % 5 == 0:
            print(f"[embed] {min(i+batch, len(texts))}/{len(texts)}")

    X = np.array(embs, dtype="float32")
    dim = X.shape[1]
    index = faiss.IndexFlatIP(dim)
    faiss.normalize_L2(X)
    index.add(X)

    faiss.write_index(index, out_index_path)
    with open(out_meta_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"[ok] wrote {out_index_path}")
    print(f"[ok] wrote {out_meta_path}")


# ----------------------------
# Main
# ----------------------------

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fuseki_query_url", default=DEFAULT_FUSEKI_QUERY)
    ap.add_argument("--ollama_url", default=DEFAULT_OLLAMA_URL)
    ap.add_argument("--embed_model", default=DEFAULT_EMBED_MODEL)
    ap.add_argument("--out_dir", default=".")
    ap.add_argument("--index_name", default="content.index")
    ap.add_argument("--meta_name", default="content_meta.json")
    return ap.parse_args()


def main():
    args = parse_args()

    out_index = os.path.join(args.out_dir, args.index_name)
    out_meta = os.path.join(args.out_dir, args.meta_name)

    print("[1/4] loading fragments from Fuseki…")
    frags = load_fragments(args.fuseki_query_url)
    print(f"  fragments: {len(frags)}")

    print("[2/4] loading requisitos from Fuseki…")
    reqs = load_requisitos(args.fuseki_query_url, frags)
    print(f"  requisitos: {len(reqs)}")

    print("[3/4] loading umbrales from Fuseki…")
    umbs = load_umbrales(args.fuseki_query_url, frags)
    print(f"  umbrales: {len(umbs)}")

    print("[4/4] building content meta…")
    items = build_content_meta(frags, reqs, umbs)
    print(f"  total items: {len(items)}")

    print("[build] embeddings + faiss…")
    build_faiss_index(
        items=items,
        ollama_url=args.ollama_url,
        embed_model=args.embed_model,
        out_index_path=out_index,
        out_meta_path=out_meta,
    )


if __name__ == "__main__":
    main()
