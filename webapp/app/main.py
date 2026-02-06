import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from graphrag_app.app import answer_question

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
        answer = answer_question(question)
        return {"answer": answer}
    except Exception as e:
        print("ERROR /chat:", repr(e))
        return {"answer": "Ha ocurrido un error procesando la consulta."}
