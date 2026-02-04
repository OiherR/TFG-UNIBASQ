# TFG – GraphRAG sobre Knowledge Graph en Apache Jena Fuseki

Este repositorio contiene el desarrollo de un sistema **GraphRAG (Graph Retrieval-Augmented Generation)** aplicado a un **Knowledge Graph RDF** almacenado en **Apache Jena Fuseki**, como parte de un Trabajo de Fin de Grado.

El objetivo es permitir **consultas en lenguaje natural** sobre un grafo RDF, combinando:
- recuperación vectorial,
- modelos de lenguaje (LLM),
- y generación dinámica de consultas SPARQL.

---

## Estructura del repositorio

El proyecto se organiza en tres módulos principales:
1- ingestion/
Pipeline de **ingesta de datos** para la construcción del Knowledge Graph.
Flujo:
Excel / fuentes estructuradas -->RDF / OWL-->Apache Jena Fuseki
Este módulo se encarga de:
- transformar los datos originales a RDF,
- definir el esquema del grafo,
- cargar los triples en un dataset de Fuseki.

2.Núcleo lógico del sistema **GraphRAG**.

Incluye:
- **Retrieval vectorial** mediante FAISS y embeddings locales (`sentence-transformers`)
- **Modelo de lenguaje local** usando Ollama
- **Generación dinámica de SPARQL** a partir de preguntas en lenguaje natural
- Acceso al endpoint SPARQL de Fuseki

Componentes principales:
- `retriever.py` → recuperación de contexto desde FAISS
- `app.py` → construcción del prompt Text-to-SPARQL
- `fuseki.py` → cliente de consultas SPARQL
- `prompts.py` → definición de prompts
- `vector_index.py` → creación del índice FAISS

3-Webapp
Interfaz web y backend del sistema.

- **Backend**: FastAPI
- **Frontend**: HTML + CSS + JavaScript
- **Arquitectura**: separación clara entre UI, servicios y lógica GraphRAG

Funcionalidades:
- Chat web para preguntas en lenguaje natural
- Endpoint `/chat` que:
  1. recibe la pregunta del usuario,
  2. recupera contexto mediante GraphRAG,
  3. genera SPARQL con un LLM,
  4. consulta Fuseki,
  5. devuelve una respuesta en lenguaje natural.
------------------------------------------
▶️ Ejecución del sistema
 # Requisitos
- Python 3.10+
- Apache Jena Fuseki
- Ollama (con un modelo local instalado)
- FAISS

# Variables de entorno
Crear un archivo `.env` en la raíz del proyecto:
```env
FUSEKI_QUERY_URL=http://localhost:3030/<dataset>/query

 Arrancar Fuseki
Path + .\fuseki-server.bat
Abrir en el navegador http://localhost:3030

# Arrancar pagina web 
Desde la raiz del repositorio
python -m uvicorn webapp.app.main:app --reload
Abrir en el anvegador http://127.0.0.1:8000
