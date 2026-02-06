import json
import os
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

# Ruta base: carpeta donde está ESTE archivo (graphrag_app/)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def load_index(
    index_path=None,
    meta_path=None
):
    if index_path is None:
        index_path = os.path.join(BASE_DIR, "index_content", "content.faiss")
    if meta_path is None:
        meta_path = os.path.join(BASE_DIR, "index_content", "content_meta.json")

    if not os.path.exists(index_path):
        raise FileNotFoundError(f"No existe el índice FAISS: {index_path}. Ejecuta: python -m graphrag_app.content_index")
    if not os.path.exists(meta_path):
        raise FileNotFoundError(f"No existe el meta JSON: {meta_path}. Ejecuta: python -m graphrag_app.content_index")

    index = faiss.read_index(index_path)
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    return index, meta

def retrieve_content(question: str, k: int = 5):
    index, meta = load_index()
    qvec = model.encode([question], normalize_embeddings=True)
    qvec = np.array(qvec, dtype="float32")
    scores, ids = index.search(qvec, k)

    out = []
    for score, idx in zip(scores[0], ids[0]):
        if idx == -1:
            continue
        item = dict(meta[idx])
        item["_score"] = float(score)
        out.append(item)
    return out
