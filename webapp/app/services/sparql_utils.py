# webapp/app/services/sparql_utils.py

def sparql_json_to_rows(result: dict) -> list[dict]:
    """
    Convierte el JSON SPARQL a lista de filas:
    [
      {"n": "357"},
      {"name": "X", "date": "2024-01-01"}
    ]
    """
    rows = []

    bindings = result.get("results", {}).get("bindings", [])
    for b in bindings:
        row = {}
        for var, info in b.items():
            row[var] = info.get("value")
        rows.append(row)

    return rows
