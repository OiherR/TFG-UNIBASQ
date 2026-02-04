from graphrag_app.fuseki import sparql_select

class FusekiError(RuntimeError):
    pass

def _is_allowed(query: str) -> bool:
    q = query.strip().upper()
    # Permitimos PREFIX delante
    if q.startswith("PREFIX"):
        # si hay PREFIX, comprobamos que en algún punto sea SELECT/ASK
        return ("SELECT" in q) or ("ASK" in q)
    return q.startswith("SELECT") or q.startswith("ASK")

def run_select(query: str, timeout: int = 30) -> dict:
    """
    Ejecuta consulta en Fuseki (solo SELECT/ASK).
    Devuelve JSON estándar SPARQL.
    """
    if not _is_allowed(query):
        raise FusekiError("Consulta no permitida: solo SELECT/ASK (y PREFIX).")

    try:
        return sparql_select(query, timeout=timeout)
    except Exception as e:
        # re-lanzamos con un error más controlado
        raise FusekiError(str(e)) from e
