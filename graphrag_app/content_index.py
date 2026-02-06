import json
import os
import re
from typing import List, Dict, Tuple

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from graphrag_app.fuseki import sparql_select

ONT = "http://example.org/unibasq/ontology#"

P = {
    "tieneRequisito": f"<{ONT}tieneRequisito>",
    "tieneUmbral": f"<{ONT}tieneUmbral>",
    "nombre": f"<{ONT}nombre>",
    "descripcion": f"<{ONT}descripcion>",
    "tipo": f"<{ONT}tipo>",
    "valor": f"<{ONT}valor>",
    "unidad": f"<{ONT}unidad>",
}

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

def embed_texts(texts: List[str]) -> np.ndarray:
    vectors = model.encode(texts, normalize_embeddings=True)
    return np.array(vectors, dtype="float32")

def build_requirement_cards(limit: int = 1000) -> List[Dict]:
    # Sacamos: Figura -> Requisito, y opcionalmente su Umbral
    q = f"""
    SELECT ?figura ?figName ?req ?reqDesc ?reqTipo ?umb ?valor ?unidad
    WHERE {{
      ?figura {P["tieneRequisito"]} ?req .
      OPTIONAL {{ ?figura {P["nombre"]} ?figName }}

      OPTIONAL {{ ?req {P["descripcion"]} ?reqDesc }}
      OPTIONAL {{ ?req {P["tipo"]} ?reqTipo }}

      OPTIONAL {{
        ?req {P["tieneUmbral"]} ?umb .
        OPTIONAL {{ ?umb {P["valor"]} ?valor }}
        OPTIONAL {{ ?umb {P["unidad"]} ?unidad }}
      }}
    }}
    LIMIT {limit}
    """
    res = sparql_select(q)["results"]["bindings"]

    cards: List[Dict] = []
    for b in res:
        figura = b["figura"]["value"]
        figName = b.get("figName", {}).get("value", "")
        req = b["req"]["value"]
        reqDesc = b.get("reqDesc", {}).get("value", "")
        reqTipo = b.get("reqTipo", {}).get("value", "")
        umb = b.get("umb", {}).get("value", "")
        valor = b.get("valor", {}).get("value", "")
        unidad = b.get("unidad", {}).get("value", "")

        text = "\n".join([
            "TIPO_CARD: requisito",
            f"FIGURA_URI: {figura}",
            f"FIGURA_NOMBRE: {figName}",
            f"REQ_URI: {req}",
            f"REQ_DESCRIPCION: {reqDesc}",
            f"REQ_TIPO: {reqTipo}",
            f"UMBRAL_URI: {umb}",
            f"VALOR: {valor}",
            f"UNIDAD: {unidad}",
        ]).strip()

        cards.append({
            "kind": "req",
            "figura_uri": figura,
            "figura_nombre": figName,
            "req_uri": req,
            "req_desc": reqDesc,
            "req_tipo": reqTipo,
            "umbral_uri": umb,
            "valor": valor,
            "unidad": unidad,
            "text": text,
        })

    return cards
def build_umbral_cards(limit: int = 5000) -> List[Dict]:
    q = f"""
    SELECT ?fig ?figName ?umb ?umbTipo ?valor ?unidad
    WHERE {{
      ?fig {P["tieneUmbral"]} ?umb .
      OPTIONAL {{ ?fig {P["nombre"]} ?figName }}
      OPTIONAL {{ ?umb {P["tipo"]} ?umbTipo }}
      OPTIONAL {{ ?umb {P["valor"]} ?valor }}
      OPTIONAL {{ ?umb {P["unidad"]} ?unidad }}
    }}
    LIMIT {limit}
    """
    res = sparql_select(q)["results"]["bindings"]

    cards: List[Dict] = []
    import re
    for b in res:
        fig = b["fig"]["value"]
        figName = b.get("figName", {}).get("value", "")
        umb = b["umb"]["value"]
        umb_l = umb.lower()
        # AREA: docencia / investigacion / formacion / gestion / total
        m_area = re.search(r"_(docencia|investigacion|formacion|gestion|total)_", umb_l)
        area = m_area.group(1) if m_area else ""

        # MINMAX: min / max (si aparece)
        m_mm = re.search(r"_(min|max)_", umb_l)
        minmax = m_mm.group(1) if m_mm else ""

        umbTipo = b.get("umbTipo", {}).get("value", "")
        valor = b.get("valor", {}).get("value", "")
        unidad = b.get("unidad", {}).get("value", "")

        text = "\n".join([
            "TIPO_CARD: umbral",
            f"FIGURA_URI: {fig}",
            f"FIGURA_NOMBRE: {figName}",
            f"UMBRAL_URI: {umb}",
            f"AREA: {area}",
            f"MINMAX: {minmax}",
            f"UMBRAL_TIPO: {umbTipo}",
            f"VALOR: {valor}",
            f"UNIDAD: {unidad}",
        ]).strip()


        cards.append({
            "kind": "umbral",
            "figura_uri": fig,
            "figura_nombre": figName,
            "umbral_uri": umb,
            "umbral_tipo": umbTipo,
            "area": area,
            "minmax": minmax,
            "valor": valor,
            "unidad": unidad,
            "text": text,
        })


    return cards



def build_faiss(cards: List[Dict], out_dir="index_content") -> Tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)

    texts = [c["text"] for c in cards]
    vectors = embed_texts(texts)

    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)

    index_path = os.path.join(out_dir, "content.faiss")
    meta_path = os.path.join(out_dir, "content_meta.json")

    faiss.write_index(index, index_path)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)

    return index_path, meta_path

if __name__ == "__main__":
    req_cards = build_requirement_cards()
    umb_cards = build_umbral_cards()

    print("DEBUG req:", len(req_cards))
    print("DEBUG umbrales:", len(umb_cards))
    if len(umb_cards) > 0:
        print("DEBUG primer umbral:", umb_cards[0])                                                                                                                                                             

    cards = req_cards + umb_cards

    ip, mp = build_faiss(cards)
    print("OK índice de contenido creado:")
    print(" -", ip)
    print(" -", mp)
    print("cards:", len(cards), "(req:", len(req_cards), "umbral:", len(umb_cards), ")")
