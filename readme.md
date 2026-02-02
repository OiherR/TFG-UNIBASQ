# TFG – Asistente de carrera académica basado en Grafos y LLMs

Este repositorio contiene el trabajo desarrollado para el TFG sobre un asistente
de carrera académica basado en grafos de conocimiento (RDF/SPARQL) y modelos de
lenguaje.

## Estructura
- `scripts/`: scripts Python para transformar Excel a RDF
- `rdf/`: grafo RDF generado (formato Turtle)
- `sparql/`: consultas SPARQL de validación
- `docs/`: preguntas del asistente y documentación

## Flujo de trabajo
1. Extracción manual del PDF oficial a Excel
2. Transformación automática Excel → RDF
3. Carga del RDF en Apache Jena Fuseki
4. Validación mediante consultas SPARQL
