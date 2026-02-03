import json
import os
import re
from typing import List, Dict, Tuple

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

from fuseki import sparql_select

PREFIXES = """
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""

# Modelo GRATIS y local
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

def local_name(uri: str) -> str:
    return re.split(r"[#/]", uri.rstrip("/"))[-1]

def embed_texts(texts: List[str]) -> np.ndarray:
    vectors = model.encode(texts, normalize_embeddings=True)
    return np.array(vectors, dtype="float32")

def fetch_schema_cards(limit: int = 300) -> List[Dict]:
    q_classes = PREFIXES + f"""
    SELECT ?uri (SAMPLE(?lbl) AS ?label)
    WHERE {{
      ?s a ?uri .
      OPTIONAL {{ ?uri rdfs:label ?lbl }}
    }}
    GROUP BY ?uri
    LIMIT {limit}
    """

    q_props = PREFIXES + f"""
    SELECT ?uri (SAMPLE(?lbl) AS ?label)
    WHERE {{
      ?s ?uri ?o .
      OPTIONAL {{ ?uri rdfs:label ?lbl }}
      FILTER(?uri != rdf:type)
    }}
    GROUP BY ?uri
    LIMIT {limit}
    """

    classes = sparql_select(q_classes)["results"]["bindings"]
    props   = sparql_select(q_props)["results"]["bindings"]

    cards = []

    for b in classes:
        uri = b["uri"]["value"]
        label = b.get("label", {}).get("value") or local_name(uri)
        cards.append({
            "kind": "class",
            "uri": uri,
            "label": label,
            "text": f"CLASE\nuri: {uri}\nlabel: {label}"
        })

    for b in props:
        uri = b["uri"]["value"]
        label = b.get("label", {}).get("value") or local_name(uri)
        cards.append({
            "kind": "property",
            "uri": uri,
            "label": label,
            "text": f"PROPIEDAD\nuri: {uri}\nlabel: {label}"
        })

    return cards

def build_faiss_index(cards: List[Dict], out_dir: str = "index") -> Tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)

    texts = [c["text"] for c in cards]
    vectors = embed_texts(texts)

    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)

    index_path = os.path.join(out_dir, "schema.faiss")
    meta_path  = os.path.join(out_dir, "schema_meta.json")

    faiss.write_index(index, index_path)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)

    return index_path, meta_path

if __name__ == "__main__":
    cards = fetch_schema_cards()
    ip, mp = build_faiss_index(cards)
    print("OK índice creado")
    print(" -", ip)
    print(" -", mp)
    print("cards:", len(cards))
