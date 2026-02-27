import argparse
from pathlib import Path
import pdfplumber
import re

# =========================
# ARGUMENTOS
# =========================
def parse_args():
    parser = argparse.ArgumentParser(
        description="Extraer texto y tablas de PDF por páginas + normalización umbrales/apartados + figura profesorado"
    )
    parser.add_argument("--input_pdf", required=True, help="Ruta al PDF de entrada")
    parser.add_argument("--output_txt", required=True, help="Ruta al TXT de salida")
    return parser.parse_args()

# =========================
# UTILIDADES
# =========================
def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def to_float_str(num: str) -> str:
    return num.replace(",", ".")

# =========================
# 0) FIGURA (PROFESORADO)
# =========================
FIGURE_PATTERNS = [
    (r"PROFESORADO\s+PLENO", "profesorado_pleno"),
    (r"PROFESORADO\s+AGREGADO", "profesorado_agregado"),
    (r"PROFESORADO\s+DE\s+INVESTIGACI[ÓO]N", "profesorado_investigacion"),
    (r"PERSONAL\s+DOCTOR\s+INVESTIGADOR|DOCTOR\s+INVESTIGADOR|PERSONAL\s+INVESTIGADOR\s+CONTRATADO", "doctor_investigador"),
    (r"UNIVERSIDADES\s+PRIVADAS.*T[ÍI]TULO\s+DE\s+DOCTOR|PROFESORADO\s+DOCTOR\s+DE\s+UNIVERSIDAD\s+PRIVADA", "profesorado_privadas_doctor"),
]

def detect_figura(text: str):
    if not text:
        return None
    t = " ".join(text.split())
    for pat, figura in FIGURE_PATTERNS:
        if re.search(pat, t, flags=re.IGNORECASE):
            return figura
    return None

# =========================
# 1) UMBRALES DESDE TEXTO (enunciados)
# =========================
# Total mínimo: "Obtener al menos 65 puntos"
RE_TOTAL_MIN = re.compile(
    r"(?:obtener)\s+(?:al\s+menos)\s+(\d+(?:[.,]\d+)?)\s+puntos",
    re.IGNORECASE
)

# Caso 1: "un mínimo de 35 puntos en el apartado 2"
RE_AP_MIN_EXPLICIT = re.compile(
    r"m[ií]nimo\s+de\s+(\d+(?:[.,]\d+)?)\s+puntos\s+en\s+el\s+apartado\s+(\d+)",
    re.IGNORECASE
)

# Caso 2 (encadenado): "... y de 10 puntos en el apartado 3" (sin repetir "mínimo")
RE_AP_MIN_CHAIN = re.compile(
    r"(?:y|e)\s+de\s+(\d+(?:[.,]\d+)?)\s+puntos\s+en\s+el\s+apartado\s+(\d+)",
    re.IGNORECASE
)

def extract_thresholds_from_text(text: str):
    """
    Devuelve dict con:
      - total_min: str o None
      - apartados_min: { "2": "35", "3": "10", ... }
    Nota: no asume nada de TOTAL en tabla; solo lo que diga el texto.
    """
    out = {"total_min": None, "apartados_min": {}}
    if not text:
        return out

    t = " ".join(text.split())

    m = RE_TOTAL_MIN.search(t)
    if m:
        out["total_min"] = to_float_str(m.group(1))

    # 1) Captura los "mínimo de X ... apartado N"
    explicit_hits = list(RE_AP_MIN_EXPLICIT.finditer(t))
    for mm in explicit_hits:
        val = to_float_str(mm.group(1))
        ap = mm.group(2)
        out["apartados_min"][ap] = val

    # 2) Si hay un "mínimo..." y luego vienen "y de X ... apartado M", capturarlos también
    #    Para no capturar "y de ..." de otras frases, restringimos a la ventana tras el primer "mínimo"
    if explicit_hits:
        start = explicit_hits[0].start()
        window = t[start:start + 300]  # ventana razonable
        for mm in RE_AP_MIN_CHAIN.finditer(window):
            val = to_float_str(mm.group(1))
            ap = mm.group(2)
            # no sobreescribe si ya estaba
            out["apartados_min"].setdefault(ap, val)

    return out

# =========================
# 2) FORMATEO TABLAS + CANONIZACIÓN "APARTADOS"
# =========================
def format_table(table):
    lines = []
    for row in table:
        clean_row = [norm(cell) for cell in row]  # cell puede ser None
        lines.append(" | ".join(clean_row))
    return "\n".join(lines)

def looks_like_apartados_table(table):
    """
    Heurística: detecta si la tabla parece la de APARTADOS/PUNTUACIÓN...
    """
    if not table or len(table) < 3:
        return False
    blob = " ".join(norm(c) for r in table for c in r if c)
    blob_u = blob.upper()
    return ("APARTADOS" in blob_u and "PUNTUACIÓN" in blob_u) or ("APARTADO" in blob_u and "TOTAL" in blob_u)

RE_ROW_APARTADO = re.compile(r"^\s*(\d+)\s*[-.]\s*(.+)$", re.IGNORECASE)
RE_POINTS = re.compile(r"(\d+(?:[.,]\d+)?)\s*puntos?", re.IGNORECASE)

def canonize_apartados_table(table, thresholds_from_text):
    """
    Intenta convertir la tabla a filas: apartado -> max/min y TOTAL.
    - min: solo si viene en la tabla o del texto (TOTAL_MIN / APARTADO_N_MIN)
    - TOTAL: siempre neutro como valor_tabla; si existe TOTAL_MIN en texto, lo añade como min=...
    """
    total_min_text = thresholds_from_text.get("total_min")
    ap_min_text = thresholds_from_text.get("apartados_min", {})

    # Aplana tabla en líneas
    rows = []
    for r in table:
        row_cells = [norm(c) for c in r]
        row_cells = [c for c in row_cells if c != ""]
        if not row_cells:
            continue
        rows.append(" | ".join(row_cells))

    apartados = []
    total_line = None
    for line in rows:
        up = line.upper()
        if up.startswith("TOTAL"):
            total_line = line
            continue

        m = RE_ROW_APARTADO.search(line.split("|")[0].strip())
        if not m:
            # alternativa "APARTADO 2"
            mm = re.search(r"\bAPARTADO\s*(\d+)\b", up)
            if mm:
                num = mm.group(1)
                name = line
            else:
                continue
        else:
            num = m.group(1)
            name = m.group(2).strip()

        nums = [to_float_str(x) for x in RE_POINTS.findall(line)]
        maxv = nums[0] if len(nums) >= 1 else ""
        # min tabla si hay segundo número; si no, min del texto
        minv = nums[1] if len(nums) >= 2 else ap_min_text.get(num, "")

        apartados.append((num, name, maxv, minv))

    # TOTAL (neutro)
    total_nums = [to_float_str(x) for x in RE_POINTS.findall(total_line or "")]
    total_val = total_nums[0] if total_nums else ""
    total_min = total_min_text or ""

    out_lines = []
    out_lines.append("----- APARTADOS_CANON -----")
    for num, name, maxv, minv in apartados:
        out_lines.append(f"APARTADO {num} | nombre={name} | max={maxv} | min={minv}")

    # TOTAL: NO asumimos min/max por la tabla. Si el texto dice TOTAL_MIN, lo añadimos.
    if total_min:
        out_lines.append(f"TOTAL | min={total_min} | valor_tabla={total_val}")
    else:
        out_lines.append(f"TOTAL | valor_tabla={total_val}")

    return "\n".join(out_lines)

# =========================
# EXTRACCIÓN
# =========================
def extract_text_with_pages(pdf_path):
    output_parts = []
    last_figura = None  # arrastre de figura si el encabezado está en una sola página

    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            output_parts.append(f"\n================ PAGE {page_number} ================\n")

            text = (page.extract_text() or "").strip()

            # Figura
            figura = detect_figura(text)
            if figura:
                last_figura = figura
            if last_figura:
                output_parts.append(f"----- FIGURA ----- {last_figura}\n")

            # Umbrales de texto
            th = extract_thresholds_from_text(text)

            if text:
                output_parts.append("----- TEXT -----\n")
                output_parts.append(text)

                marks = []
                if th["total_min"]:
                    marks.append(f"TOTAL_MIN={th['total_min']}")
                for ap, val in sorted(th["apartados_min"].items(), key=lambda x: int(x[0])):
                    marks.append(f"APARTADO_{ap}_MIN={val}")
                if marks:
                    output_parts.append("\n----- UMBRAL_TEXTO -----\n" + "\n".join(marks) + "\n")

            # Tablas
            tables = page.extract_tables() or []
            if tables:
                for idx, table in enumerate(tables, start=1):
                    output_parts.append(f"\n----- TABLE {idx} -----\n")
                    output_parts.append(format_table(table))

                    if looks_like_apartados_table(table):
                        output_parts.append("\n" + canonize_apartados_table(table, th) + "\n")

    return "\n".join(output_parts)

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    args = parse_args()

    pdf_path = Path(args.input_pdf)
    out_path = Path(args.output_txt)

    if not pdf_path.exists():
        raise FileNotFoundError(f"No existe el PDF: {pdf_path}")

    text = extract_text_with_pages(pdf_path)
    out_path.write_text(text, encoding="utf-8")

    print(f"✅ Texto y tablas extraídos + normalización + figura en: {out_path}")