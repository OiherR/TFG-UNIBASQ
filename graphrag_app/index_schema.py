import json
import os
import re
from typing import List, Dict, Tuple
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from graphrag_app.fuseki import sparql_select

ONT_NS = "http://example.org/academic-career/ontology#"

PREFIXES = f"""
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX u:    <{ONT_NS}>
"""

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

def local_name(uri: str) -> str:
    return re.split(r"[#/]", uri.rstrip("/"))[-1]

def embed_texts(texts: List[str]) -> np.ndarray:
    vectors = model.encode(texts, normalize_embeddings=True)
    return np.array(vectors, dtype="float32")

def fetch_schema_cards(limit: int = 5000) -> List[Dict]:
    # Clases declaradas (TBox)
    q_classes_decl = PREFIXES + f"""
    SELECT DISTINCT ?uri WHERE {{
      ?uri a owl:Class .
      FILTER(STRSTARTS(STR(?uri), "{ONT_NS}"))
    }}
    LIMIT {limit}
    """

    # Tipos usados en instancias (ABox) - útil como complemento
    q_classes_used = PREFIXES + f"""
    SELECT DISTINCT ?uri WHERE {{
      ?s a ?uri .
      FILTER(STRSTARTS(STR(?uri), "{ONT_NS}"))
    }}
    LIMIT {limit}
    """

    # Propiedades declaradas (TBox)
    q_props_decl = PREFIXES + f"""
    SELECT DISTINCT ?uri WHERE {{
      ?uri a rdf:Property .
      FILTER(STRSTARTS(STR(?uri), "{ONT_NS}"))
    }}
    LIMIT {limit}
    """

    # Predicados usados (ABox) - complemento
    q_props_used = PREFIXES + f"""
    SELECT DISTINCT ?uri WHERE {{
      ?s ?uri ?o .
      FILTER(?uri != rdf:type)
      FILTER(STRSTARTS(STR(?uri), "{ONT_NS}"))
    }}
    LIMIT {limit}
    """

    classes = []
    for q in (q_classes_decl, q_classes_used):
        classes += sparql_select(q)["results"]["bindings"]

    props = []
    for q in (q_props_decl, q_props_used):
        props += sparql_select(q)["results"]["bindings"]

    # dedupe
    seen = set()
    cards = []

    for b in classes:
        uri = b["uri"]["value"]
        if uri in seen: 
            continue
        seen.add(uri)
        label = local_name(uri).replace("_", " ")
        cards.append({"kind": "class", "uri": uri, "label": label, "text": f"CLASE: {label}\nURI: {uri}"})

    for b in props:
        uri = b["uri"]["value"]
        if uri in seen:
            continue
        seen.add(uri)
        label = local_name(uri).replace("_", " ")
        cards.append({"kind": "property", "uri": uri, "label": label, "text": f"PROPIEDAD: {label}\nURI: {uri}"})

    return cards

def build_faiss_index(cards: List[Dict], out_dir: str = None) -> Tuple[str, str]:
    if out_dir is None:
        out_dir = os.path.join("graphrag_app", "index_schema")

    os.makedirs(out_dir, exist_ok=True)
    if not cards:
        return "", ""

    vectors = embed_texts([c["text"] for c in cards])
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)

    i_path = os.path.join(out_dir, "schema.faiss")
    m_path = os.path.join(out_dir, "schema_meta.json")
    faiss.write_index(index, i_path)
    with open(m_path, "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)
    return i_path, m_path

if __name__ == "__main__":
    cards = fetch_schema_cards()
    ip, mp = build_faiss_index(cards)
    print(f"✅ Esquema actualizado: {len(cards)} elementos en {ip}")
