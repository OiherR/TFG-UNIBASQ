from fuseki import sparql_select

PREFIXES = """
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""

def get_top_classes(limit: int = 30):
    q = PREFIXES + f"""
    SELECT ?class (COUNT(?s) AS ?n)
    WHERE {{
      ?s rdf:type ?class .
    }}
    GROUP BY ?class
    ORDER BY DESC(?n)
    LIMIT {limit}
    """
    return sparql_select(q)

def get_top_properties(limit: int = 50):
    q = PREFIXES + f"""
    SELECT ?p (COUNT(*) AS ?n)
    WHERE {{
      ?s ?p ?o .
    }}
    GROUP BY ?p
    ORDER BY DESC(?n)
    LIMIT {limit}
    """
    return sparql_select(q)

def schema_summary_text() -> str:
    classes = get_top_classes()
    props = get_top_properties()

    def bindings_to_lines(res, var):
        lines = []
        for b in res["results"]["bindings"]:
            lines.append(b[var]["value"])
        return lines

    class_lines = bindings_to_lines(classes, "class")
    prop_lines  = bindings_to_lines(props, "p")

    # Esto se enseña al LLM
    text = "CLASES (top):\n" + "\n".join(f"- {c}" for c in class_lines)
    text += "\n\nPROPIEDADES (top):\n" + "\n".join(f"- {p}" for p in prop_lines)
    return text