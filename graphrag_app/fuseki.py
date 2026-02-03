import os
import requests
from dotenv import load_dotenv

load_dotenv()
FUSEKI_QUERY_URL = os.getenv("FUSEKI_QUERY_URL")

def sparql_select(query: str, timeout: int = 30) -> dict:
    if not FUSEKI_QUERY_URL:
        raise RuntimeError("FUSEKI_QUERY_URL no está definido en .env")

    headers = {
        "Accept": "application/sparql-results+json",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {"query": query}

    r = requests.post(FUSEKI_QUERY_URL, data=data, headers=headers, timeout=timeout)

    if r.status_code >= 400:
        # Fuseki normalmente devuelve aquí el mensaje de parseo SPARQL
        raise RuntimeError(f"Fuseki {r.status_code}: {r.text}\n\nQUERY:\n{query}")

    return r.json()
