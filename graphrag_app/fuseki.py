# graphrag_app/fuseki.py
import os
import requests
from dotenv import load_dotenv
load_dotenv()
FUSEKI_QUERY_URL = os.getenv("FUSEKI_QUERY_URL")  # debe acabar en /query
HEADERS_GET = {"Accept": "application/sparql-results+json"}
HEADERS_POST = {
    "Accept": "application/sparql-results+json",
    "Content-Type": "application/x-www-form-urlencoded",
}

def sparql_select(query: str, timeout: int = 30):
    if not FUSEKI_QUERY_URL:
        raise RuntimeError("FUSEKI_QUERY_URL no está definido en el entorno/.env")

    # 1) Intento GET (muchos Fuseki lo aceptan siempre)
    r = requests.get(
        FUSEKI_QUERY_URL,
        params={"query": query},
        headers=HEADERS_GET,
        timeout=timeout,
    )
    if r.status_code == 200:
        return r.json().get("results", {}).get("bindings", [])

    # 2) Si GET no vale, intento POST (algunos servidores lo exigen)
    r2 = requests.post(
        FUSEKI_QUERY_URL,
        data={"query": query},
        headers=HEADERS_POST,
        timeout=timeout,
    )
    if r2.status_code == 200:
        return r2.json().get("results", {}).get("bindings", [])

    # Si ambos fallan, muestra error útil
    raise RuntimeError(f"Fuseki {r.status_code}/{r2.status_code}: {r.text[:300]} | {r2.text[:300]}")