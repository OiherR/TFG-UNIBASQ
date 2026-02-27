import os
import requests
from typing import Optional

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

def ollama_generate(
    prompt: str,
    temperature: float = 0.0,
    system: Optional[str] = None,
    model: Optional[str] = None,
    timeout: int = 600,
) -> str:
    """
    Wrapper simple para /api/generate.
    Si 'system' viene, lo inyectamos arriba del prompt (compatible con tu enfoque actual).
    """
    final_prompt = prompt
    if system:
        final_prompt = f"SISTEMA:\n{system.strip()}\n\nUSUARIO:\n{prompt.strip()}\n"

    payload = {
        "model": model or OLLAMA_MODEL,
        "prompt": final_prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }

    r = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()["response"].strip()