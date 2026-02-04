import os
import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

# Modelo local y gratuito (el mismo que usaste al crear el índice)
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

# Rutas absolutas basadas en la ubicación de este archivo (graphrag_app/retriever.py)
BASE_DIR = os.path.dirname(__file__)                 # .../tfg-unibasq/graphrag_app
INDEX_DIR = os.path.join(BASE_DIR, "index")          # .../tfg-unibasq/graphrag_app/index

DEFAULT_INDEX_PATH = os.path.join(INDEX_DIR, "schema.faiss")
DEFAULT_META_PATH  = os.path.join(INDEX_DIR, "schema_meta.json")


def load_index(index_path: str = DEFAULT_INDEX_PATH, meta_path: str = DEFAULT_META_PATH):
    if not os.path.exists(index_path):
        raise FileNotFoundError(f"No se encuentra el índice FAISS: {index_path}")
    if not os.path.exists(meta_path):
        raise FileNotFoundError(f"No se encuentra el meta JSON: {meta_path}")

    index = faiss.read_index(index_path)
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    return index, meta


def embed_one(text: str) -> np.ndarray:
    vec = model.encode([text], normalize_embeddings=True)
    return np.array(vec, dtype="float32")


def retrieve(question: str, k: int = 8):
    index, meta = load_index()
    qvec = embed_one(question)

    scores, ids = index.search(qvec, k)

    results = []
    for score, idx in zip(scores[0], ids[0]):
        if idx == -1:
            continue
        item = dict(meta[idx])
        item["_score"] = float(score)
        results.append(item)

    return results
