# TFG – GraphRAG sobre Knowledge Graph en Fuseki

Este repositorio contiene dos módulos:

## ingestion/
Pipeline de ingesta de datos:
Excel → RDF → Apache Jena Fuseki.

## graphrag-app/
Aplicación de preguntas en lenguaje natural sobre el Knowledge Graph:
- Retrieval vectorial (FAISS + embeddings locales)
- LLM local (Ollama)
- Generación dinámica de SPARQL