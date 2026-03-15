import os
import json
import re
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from functools import lru_cache
from typing import Optional

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_model = SentenceTransformer(MODEL_NAME)

BASE_DIR = os.path.dirname(__file__)

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
    return np.asarray(vec, dtype="float32")


def _pick_index_path(index_dir: str, base_name: str) -> str:
    p_faiss = os.path.join(index_dir, f"{base_name}.faiss")
    p_index = os.path.join(index_dir, f"{base_name}.index")

    if os.path.exists(p_faiss):
        return p_faiss
    if os.path.exists(p_index):
        return p_index

    return p_faiss


@lru_cache(maxsize=4)
def _load_index(kind: str):
    if kind not in INDEX_CONFIG:
        raise ValueError(f"kind inválido: {kind}. Usa 'schema' o 'content'.")

    cfg = INDEX_CONFIG[kind]
    index_dir = os.path.join(BASE_DIR, cfg["dir"])
    index_path = _pick_index_path(index_dir, cfg["base"])
    meta_path = os.path.join(index_dir, cfg["meta"])

    alt_path = (
        index_path.replace(".faiss", ".index")
        if index_path.endswith(".faiss")
        else index_path.replace(".index", ".faiss")
    )

    if not os.path.exists(index_path):
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
    k = (k or "").strip().lower()
    if k in ("frag", "fragmento", "fragment"):
        return "fragment"
    if k in ("req", "requisito"):
        return "req"
    if k in ("umbral",):
        return "umbral"
    return k


def _intent(question: str) -> str:
    q = (question or "").lower()

    if any(w in q for w in ["umbral", "mínimo", "minimo", "puntuación", "puntuacion", "puntos", "threshold"]):
        return "umbral"

    if any(w in q for w in ["requisito", "requisitos", "condición", "condiciones", "debe", "deberá", "debera"]):
        return "req"

    if any(w in q for w in ["tasa", "tasas", "pago", "pagar", "cuánto cuesta", "cuanto cuesta", "ordain", "ordaindu"]):
        return "tasa"

    if any(w in q for w in ["plazo", "plazos", "cuándo", "cuando", "fecha", "fechas", "epe", "epeak", "convocatoria"]):
        return "plazo"

    if any(w in q for w in ["recurso", "recurrir", "reposición", "reposicion", "jurisdicción", "jurisdiccion", "errekurtso"]):
        return "recurso"

    if any(w in q for w in ["notificación", "notificacion", "notifica", "resolución", "resolucion", "jakinaraz"]):
        return "notificacion"

    if any(w in q for w in ["procedimiento", "tramitar", "tramitación", "tramitacion", "pasos", "solicitud", "izapidet"]):
        return "procedimiento"

    if any(w in q for w in ["evaluación", "evaluacion", "criterios", "méritos", "meritos", "ebalu"]):
        return "evaluacion"

    if any(w in q for w in ["índice", "indice", "aurkibidea"]):
        return "indice"

    if any(w in q for w in ["introducción", "introduccion", "sarrera"]):
        return "introduccion"

    return "general"


def _contains_number(text: str) -> bool:
    return bool(re.search(r"\b\d+(?:[.,]\d+)?\b", text or ""))


def _section_bonus(question: str, item: dict) -> float:
    q = (question or "").lower()
    sec = (item.get("seccion_nombre") or item.get("section") or "").lower()

    if not sec:
        return 0.0

    if any(w in q for w in ["índice", "indice", "aurkibidea"]) and sec == "indice":
        return 0.08

    if any(w in q for w in ["introducción", "introduccion", "sarrera"]) and sec == "introduccion":
        return 0.08

    if any(w in q for w in ["tasa", "tasas", "pago", "pagar", "ordain"]) and sec == "tasas":
        return 0.06

    if any(w in q for w in ["plazo", "plazos", "epe", "epeak", "convocatoria"]) and sec == "plazos":
        return 0.06

    if any(w in q for w in ["recurso", "recurrir", "reposicion", "reposición", "errekurtso"]) and sec == "recurso":
        return 0.06

    if any(w in q for w in ["notificación", "notificacion", "jakinaraz"]) and sec == "notificacion":
        return 0.06

    if any(w in q for w in ["procedimiento", "tramitar", "izapidet"]) and sec == "procedimiento":
        return 0.06

    if any(w in q for w in ["evaluación", "evaluacion", "criterios", "méritos", "meritos", "ebalu"]) and sec == "evaluacion":
        return 0.04

    return 0.0


def _noise_penalty(text: str) -> float:
    t = (text or "")
    penalty = 0.0
    if "----- TEXT -----" in t:
        penalty -= 0.03
    if "----- FIGURA -----" in t:
        penalty -= 0.02
    return penalty


def retrieve(
    question: str,
    kind: str = "content",
    k: int = 20,
    min_score: Optional[float] = None,
    final_k: int = 8,
    debug: bool = False,
):
    index, meta = _load_index(kind)
    qvec = _embed_one(question)

    # subimos un poco el recall inicial para que el re-ranking tenga margen
    search_k = max(k, final_k * 4, 30)
    scores, ids = index.search(qvec, search_k)

    raw_results = []
    for score, idx in zip(scores[0], ids[0]):
        if idx == -1:
            continue

        score = float(score)
        if min_score is not None and score < min_score:
            continue

        item = dict(meta[idx])
        item["_score"] = score
        item["_kind_norm"] = _normalize_kind(item.get("kind", ""))
        raw_results.append(item)

    intent = _intent(question)

    def bonus(it) -> float:
        text = (it.get("text") or it.get("contexto") or it.get("descripcion") or "")
        k_norm = it.get("_kind_norm", "")
        total = 0.0

        # boosts por tipo de card
        if intent == "umbral":
            total += 0.08 if k_norm == "umbral" else (0.02 if k_norm == "req" else 0.0)
            if _contains_number(text):
                total += 0.03

        elif intent == "req":
            total += 0.08 if k_norm == "req" else (0.02 if k_norm == "fragment" else 0.0)

        elif intent == "tasa":
            if "tasa" in text.lower() or "ordain" in text.lower() or "pago" in text.lower():
                total += 0.09
            if _contains_number(text):
                total += 0.04

        elif intent == "plazo":
            if any(w in text.lower() for w in ["plazo", "convocatoria", "fecha", "epe", "epeak"]):
                total += 0.08
            if _contains_number(text):
                total += 0.02

        elif intent == "recurso":
            if any(w in text.lower() for w in ["recurso", "reposición", "reposicion", "jurisdicción", "jurisdiccion", "errekurtso"]):
                total += 0.09

        elif intent == "notificacion":
            if any(w in text.lower() for w in ["notificación", "notificacion", "resolución", "resolucion", "jakinaraz"]):
                total += 0.08

        elif intent == "procedimiento":
            if any(w in text.lower() for w in ["procedimiento", "solicitud", "tramitar", "izapidet"]):
                total += 0.08

        elif intent == "evaluacion":
            if any(w in text.lower() for w in ["evaluación", "evaluacion", "criterios", "méritos", "meritos", "ebalu"]):
                total += 0.06

        elif intent == "indice":
            total += 0.10 if "índice" in text.lower() or "indice" in text.lower() or "aurkibidea" in text.lower() else 0.0

        elif intent == "introduccion":
            total += 0.10 if "introducción" in text.lower() or "introduccion" in text.lower() or "sarrera" in text.lower() else 0.0

        total += _section_bonus(question, it)
        total += _noise_penalty(text)
        return total

    for it in raw_results:
        it["_score2"] = it["_score"] + bonus(it)

    raw_results.sort(key=lambda x: x["_score2"], reverse=True)
    results = raw_results[:max(1, final_k)]

    if debug:
        print("\n=== RETRIEVER DEBUG ===")
        print(f"kind_index={kind}  k={k}  search_k={search_k}  min_score={min_score}  final_k={final_k}")
        print("Q:", question)
        print("INTENT:", intent)
        for i, r in enumerate(results, start=1):
            preview = (r.get("text") or r.get("contexto") or r.get("descripcion") or "")[:220].replace("\n", " ")
            print(
                f"{i:02d} score={r['_score']:.3f} score2={r['_score2']:.3f} "
                f"kind={r.get('kind')} kind_norm={r.get('_kind_norm')} "
                f"sec={r.get('seccion_nombre','')} pag={r.get('pagina','n/a')}  {preview}..."
            )
        print("=======================\n")

    return results