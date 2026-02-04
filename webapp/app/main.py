import os
import sys


from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from webapp.app.services.text2sparql import question_to_sparql
from webapp.app.services.fuseki_client import run_select
from webapp.app.services.sparql_utils import sparql_json_to_rows

app = FastAPI()

BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class ChatRequest(BaseModel):
    message: str


@app.get("/")
def home():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.post("/chat")
def chat(req: ChatRequest):
    question = req.message.strip()
    if not question:
        return {"answer": "Escribe una pregunta 🙂"}

    try:
        # 1️⃣ LLM → SPARQL
        sparql = question_to_sparql(question)

        if not sparql.upper().lstrip().startswith(("SELECT", "ASK")):
            return {"answer": "No puedo ejecutar consultas que no sean SELECT/ASK."}

        # 2️⃣ SPARQL → Fuseki
        result = run_select(sparql)

        # 3️⃣ JSON SPARQL → filas simples
        rows = sparql_json_to_rows(result)

        # 4️⃣ Respuesta en lenguaje natural (simple)
        if not rows:
            answer = "No he encontrado resultados."
        elif len(rows) == 1 and len(rows[0]) == 1:
            answer = f"El resultado es {list(rows[0].values())[0]}."
        else:
            answer = f"He encontrado {len(rows)} resultados."

        return {"answer": answer}

    except Exception as e:
        import traceback
        print("ERROR /chat:", repr(e))
        traceback.print_exc()
        return {"answer": "Ha ocurrido un error procesando la consulta."}

