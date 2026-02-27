import os
import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from functools import lru_cache
from typing import Optional

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_model = SentenceTransformer(MODEL_NAME)

BASE_DIR = os.path.dirname(__file__)

# Cambiado: usamos "base" en vez de "faiss" para aceptar .faiss o .index
INDEX_CONFIG = {
    "schema": {
        "dir": "index_schema",
        "base": "schema",
        "meta": "schema_meta.json",
    },
    "content": {
        "dir": "index_content",
        "base": "content",
        "meta": "content_meta.json",
    },
}

def _embed_one(text: str) -> np.ndarray:
    vec = _model.encode([text], normalize_embeddings=True)
    return np.asarray(vec, dtype="float32")  # (1, dim)

def _pick_index_path(index_dir: str, base_name: str) -> str:
    """
    Acepta índices FAISS guardados como:
      - {base_name}.faiss
      - {base_name}.index
    """
    p_faiss = os.path.join(index_dir, f"{base_name}.faiss")
    p_index = os.path.join(index_dir, f"{base_name}.index")

    if os.path.exists(p_faiss):
        return p_faiss
    if os.path.exists(p_index):
        return p_index

    # Devolvemos .faiss para que el error muestre el esperado,
    # pero indicaremos también el .index en el mensaje.
    return p_faiss

@lru_cache(maxsize=4)
def _load_index(kind: str):
    if kind not in INDEX_CONFIG:
        raise ValueError(f"kind inválido: {kind}. Usa 'schema' o 'content'.")

    cfg = INDEX_CONFIG[kind]
    index_dir = os.path.join(BASE_DIR, cfg["dir"])
    index_path = _pick_index_path(index_dir, cfg["base"])
    meta_path  = os.path.join(index_dir, cfg["meta"])

    # Si no existe el que devolvió _pick_index_path, comprobamos también el alternativo
    alt_path = index_path.replace(".faiss", ".index") if index_path.endswith(".faiss") else index_path.replace(".index", ".faiss")

    if not os.path.exists(index_path):
        # mensaje útil: qué rutas intentó
        raise FileNotFoundError(
            "No se encuentra el índice FAISS.\n"
            f"Probado:\n- {index_path}\n- {alt_path}\n"
            f"Directorio: {index_dir}"
        )

    if not os.path.exists(meta_path):
        raise FileNotFoundError(f"No se encuentra el meta JSON: {meta_path}")

    index = faiss.read_index(index_path)
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    if not isinstance(meta, list):
        raise ValueError(f"Meta JSON inválido en {meta_path}: se esperaba una lista de items.")

    return index, meta

def _normalize_kind(k: str) -> str:
    """
    Unifica nombres de kind entre scripts antiguos/nuevos:
    - frag / fragment -> fragment
    - req -> req
    - umbral -> umbral
    """
    k = (k or "").strip().lower()
    if k in ("frag", "fragmento", "fragment"):
        return "fragment"
    if k in ("req", "requisito"):
        return "req"
    if k in ("umbral",):
        return "umbral"
    return k

def _intent(question: str) -> str:
    """
    Heurística simple para priorizar tipos en el ranking.
    """
    q = (question or "").lower()
    if any(w in q for w in ["umbral", "mínimo", "minimo", "puntuación", "puntuacion", "puntos", "threshold"]):
        return "umbral"
    if any(w in q for w in ["requisito", "requisitos", "condición", "condiciones", "debe", "deberá", "debera"]):
        return "req"
    return "general"

def retrieve(
    question: str,
    kind: str = "content",
    k: int = 20,
    min_score: Optional[float] = None,
    final_k: int = 8,
    debug: bool = False,
):
    """
    kind='content' para texto del PDF / cards (req, umbral, fragment)
    kind='schema' para ontología/esquema (para ayudar a generar SPARQL)

    - Acepta índices .faiss o .index automáticamente.
    - Re-ranking según intención.
    - Normaliza kind.
    """
    index, meta = _load_index(kind)
    qvec = _embed_one(question)

    scores, ids = index.search(qvec, k)

    raw_results = []
    for score, idx in zip(scores[0], ids[0]):
        if idx == -1:
            continue

        score = float(score)

        if min_score is not None and score < min_score:
            continue

        item = dict(meta[idx])
        item["_score"] = score

        item_kind = item.get("kind", "")
        item["_kind_norm"] = _normalize_kind(item_kind)

        raw_results.append(item)

    intent = _intent(question)

    def bonus(it) -> float:
        k_norm = it.get("_kind_norm", "")
        if intent == "umbral":
            return 0.06 if k_norm == "umbral" else (0.02 if k_norm == "req" else 0.0)
        if intent == "req":
            return 0.06 if k_norm == "req" else (0.01 if k_norm == "umbral" else 0.0)
        return 0.0

    for it in raw_results:
        it["_score2"] = it["_score"] + bonus(it)

    raw_results.sort(key=lambda x: x["_score2"], reverse=True)

    results = raw_results[:max(1, final_k)]

    if debug:
        print("\n=== RETRIEVER DEBUG ===")
        print(f"kind_index={kind}  k={k}  min_score={min_score}  final_k={final_k}")
        print("Q:", question)
        for i, r in enumerate(results, start=1):
            preview = (r.get("text", "") or "")[:220].replace("\n", " ")
            print(
                f"{i:02d} score={r['_score']:.3f} score2={r['_score2']:.3f} "
                f"kind={r.get('kind')} kind_norm={r.get('_kind_norm')} "
                f"pagina={r.get('pagina','n/a')}  {preview}..."
            )
        print("=======================\n")

    return results