# TFG – Asistente de Carrera Académica basado en Grafos y LLMs

Este proyecto implementa un asistente inteligente para consultas sobre acreditaciones y evaluaciones académicas.

El sistema combina tecnologías semánticas (RDF, OWL, SPARQL) con modelos de lenguaje de gran tamaño (LLMs) para automatizar la interpretación de normativa oficial.

El objetivo es permitir que un usuario formule preguntas en lenguaje natural y obtenga respuestas estructuradas basadas en documentos oficiales.

# Flujo de Ejecución y Comandos

1. Generar Texto desde PDF

El primer paso es convertir el archivo PDF en texto estructurado y facilitar la creación de triples RDF, ejecutando el siguiente comando:

python ingestion/scripts/convert_pdf_to_text.py --input_pdf ingestion/data/[nombre_del_pdf].pdf --output_txt ingestion/data/[nombre_del_txt].txt

Este comando toma un archivo PDF de entrada y genera un archivo .txt con el texto extraído, listo para ser procesado.

2. Generar RDF desde Texto usando LLM

Arrancar Ollama: ollama serve

Verifica que el modelo esté disponible con:

ollama list

Si el modelo no está instalado, puedes obtenerlo con:

ollama pull llama3.1:8b 

Una vez que tienes el texto extraído del PDF y ollama preparado, utiliza el siguiente comando para generar un archivo RDF en formato .ttl:

python ingestion/scripts/extract_to_ttl.py --input_rdf ingestion/ontology/academic_career.rdf --input_txt ingestion/data/[nombre_del_txt].txt --prompt_file ingestion/prompts/extract_ttl.txt --fix_prompt_file ingestion/prompts/fix_turtle.txt --output_ttl ingestion/ttl/[nombre_del_ttl].ttl --model llama3.2:3b

Este comando hace lo siguiente:

Utiliza la ontología RDF academic_career.rdf. Este .rdf es el molde que  creado en protege y está guardado dentro de la carpeta ontology.

Utiliza los dos prompts creados. Extract_ttl.txt y fix_turtle.txt

Procesa el archivo .txt para generar triples RDF.

El modelo LLM especificado (en este caso llama3.2:3b) genera las instancias semánticas.

3. Abrir Fuseki y cargar los ttl

Ejecutar fuseki en la terminal con este comando: .\fuseki-server.bat   

Accede a Fuseki en http://localhost:3030

Selecciona el dataset correspondiente. Sino esta creado, lo creas llamandolo academic-career y selecciones la opcion de Persistent

En la sección "Add Data", subes el archivo o los archivos .ttl generado(s).

4. Compilar el Content_index

Instalar la librería sentence-transformers (si no la tienes instalada)

Si aún no tienes instalada la librería sentence-transformers, usa el siguiente comando para instalarla:

pip install sentence-transformers

Ejecutar el comando para generar el índice de contenido:

en el .env se debe tener la misma url que fuseki y que la del comando sino va a dar error

python -m graphrag_app.content_index --fuseki_query_url "http://localhost:3030/academic-career/query" --out_dir ./graphrag_app/index_content --embed_model "sentence-transformers/all-MiniLM-L6-v2"

En la carpeta index_content se guardaran el content.index y el content_meta.json

5. Compilar el index_schema

Ejecutar este comando : :python -m graphrag_app.index__schema

En la carpeta index_schema se guardaran el schema.faiss y el schema_meta.json


6. Arrancar la aplicación web:

Desde la raíz del repositorio:

python -m uvicorn webapp.app.main:app --reload

Una vez iniciado, accede a http://127.0.0.1:8000
 en tu navegador.

## Tecnologías utilizadas

- Ontologías OWL (Protégé)
- Generación automática de RDF desde PDFs usando LLMs (Ollama)
- Apache Jena Fuseki como base de datos RDF
- Generación automática de SPARQL desde lenguaje natural
- FAISS para recuperación semántica vectorial
- FastAPI + HTML/CSS/JS para la interfaz web

---

## Arquitectura del sistema

Flujo general del sistema:
PDF
↓
Extracción de texto
↓
LLM (Ollama)
↓
RDF (.ttl)
↓
Apache Jena Fuseki
↓
SPARQL
↓
WebApp

El sistema combina:

- Recuperación vectorial (FAISS)
- Consultas estructuradas SPARQL
- Generación dinámica mediante LLM

---

## Estructura del repositorio

El proyecto se organiza en tres módulos principales:

---

### 1️⃣ ingestion/

Pipeline de **ingesta y estructuración semántica de documentos** para la construcción automática del Knowledge Graph.

Flujo:
PDF → Texto → LLM → RDF → Fuseki

Responsabilidades:

- Extraer texto estructurado desde documentos PDF.
- Generar instancias RDF automáticamente mediante LLM.
- Aplicar una ontología OWL previamente definida en Protégé.
- Procesar documentos por bloques de páginas (chunking).
- Exportar los triples en formato `.ttl`.

Componentes principales:

1. convert_pdf_to_text.py:

Propósito: Este script convierte los archivos PDF en texto plano, extrayendo el contenido de cada página, incluidas las tablas, figuras, umbrales, y otros datos relevantes.

Roles: Extrae texto de los PDFs página por página. Normaliza los datos extraídos, como los umbrales y las figuras del profesorado, para un procesamiento posterior.

2. extract_to_ttl.py:

Propósito: Este script utiliza el texto extraído y genera los archivos TTL en base a la ontología definida. Convierte los requisitos, umbrales y otras entidades en triples RDF.

Roles: Procesa los datos extraídos y los convierte a triples RDF (TTL). Interactúa con el modelo para determinar las secciones y validaciones necesarias, convirtiéndolos en un formato estructurado en Turtle.

3. extract_ttl.txt:

Propósito: Este archivo es un archivo de plantilla que probablemente contiene instrucciones o un esquema para convertir los datos extraídos en TTL.

Roles: Guía la conversión de texto a triples RDF siguiendo el formato adecuado.

4. fix_turtle.txt:

Propósito: Archivo que se usa para corregir errores de sintaxis en los archivos Turtle generados.

Roles: Este archivo se utiliza en caso de que los archivos TTL generados tengan errores sintácticos, asegurándose de que el archivo final sea válido.

### 2️⃣ graph_rag/

Núcleo lógico del sistema basado en arquitectura **GraphRAG híbrida**.

Combina recuperación semántica vectorial y consultas estructuradas RDF.

Flujo de la arquitectura interna:

-Consulta del Usuario:
  El usuario realiza una pregunta, que es capturada por app.py.

-Clasificación de la Consulta:
  La pregunta se clasifica por tipo en app.py como "EXACTA", "BUSQUEDA", "ABIERTO", etc.

-Recuperación de Datos:
  Si la consulta es de tipo EXACTO o STRUCTURADO, se utiliza text2sparql.py y sparql_prompt.py para generar una consulta SPARQL y se ejecuta en fuseki_client.py para obtener resultados del grafo RDF.

  Si la consulta es de tipo BUSQUEDA, se usa retriever.py para recuperar fragmentos relevantes del índice FAISS creado en content_index.py.

-Generación de Respuestas:
  Los resultados SPARQL son procesados y formateados, o en su defecto, se usa el modelo de lenguaje de Ollama a través de ollama_client.py para generar respuestas contextuales basadas en el contenido recuperado.

-Devolución de la Respuesta:
  Finalmente, la respuesta generada es enviada de vuelta al usuario a través de app.py.

Componentes:

1. app.py:

Propósito: Es el archivo principal que gestiona las consultas y respuestas. Recibe preguntas, las clasifica en tipos de consulta (exacta, abierta, búsqueda), y las responde ya sea con datos extraídos de un grafo RDF usando SPARQL o mediante búsqueda en texto usando un índice FAISS.

Roles: Este archivo se encarga de orquestar la lógica de preguntas y respuestas, basándose en el tipo de consulta que se realiza.

2. content_index.py:

Propósito: Contiene la lógica para indexar fragmentos de contenido (texto) con un modelo de embeding (SentenceTransformers) y almacenarlos en un índice FAISS.

Roles: Realiza la indexación de contenido para consultas basadas en texto, optimizando la búsqueda y recuperación de datos a través de un índice eficiente.

3. fuseki.py:

Propósito: Se encarga de la interacción con Fuseki, un servidor SPARQL que gestiona el grafo RDF. Proporciona funciones para realizar consultas SPARQL al servidor.

Roles: Esta clase facilita la consulta del grafo RDF usando SPARQL. Es esencial para obtener datos estructurados desde la base de conocimiento.

4. fuseki_client.py:

Propósito: Implementa un cliente para ejecutar consultas SPARQL SELECT/ASK en el servidor Fuseki.

Roles: Facilita la ejecución de consultas SELECT/ASK sobre el endpoint de Fuseki, retornando los resultados en formato JSON.

5. index_schema.py:

Propósito: Gestiona el esquema de la ontología (clases, propiedades) y la creación de un índice FAISS basado en estos elementos.

Roles: Indiza los elementos del esquema de la ontología para que puedan ser recuperados de manera eficiente y facilitar la generación de consultas SPARQL.

6. ollama_client.py:

Propósito: Facilita la generación de respuestas mediante un modelo LLM (Large Language Model) alojado en Ollama.

Roles: Utiliza el modelo de lenguaje de Ollama para generar respuestas basadas en el contexto de la pregunta y las evidencias proporcionadas por el sistema.

7. prompts.py:

Propósito: Contiene los prompts que son usados por el modelo de lenguaje para generar respuestas. Establece las reglas y contexto bajo los cuales el modelo debe operar.

Roles: Define el formato y las reglas para interactuar con el modelo LLM de Ollama, lo que permite la generación de respuestas a preguntas abiertas o estructuradas.

8. retriever.py:

Propósito: Implementa un sistema de recuperación de información basado en un índice FAISS. Utiliza un modelo de lenguaje para realizar embeddings de texto.

Roles: Se encarga de la búsqueda de fragmentos relevantes en el índice FAISS, devolviendo aquellos que más se asemejan a la consulta del usuario.

9. sparql_prompt.py:

Propósito: Construye el prompt para generar consultas SPARQL a partir de la pregunta del usuario.

Roles: Crea dinámicamente una consulta SPARQL basada en el esquema de la ontología recuperada y la pregunta del usuario, para ser procesada en el servidor Fuseki.

10. text2sparql.py:

Propósito: Interpreta preguntas de lenguaje natural y las convierte en consultas SPARQL estructuradas para ser ejecutadas en el servidor Fuseki.

Roles: Actúa como un puente para convertir preguntas no estructuradas en consultas estructuradas (SPARQL), facilitando la interacción con el grafo RDF.

### 3️⃣ webapp/

Interfaz web del sistema.

Permite realizar preguntas en lenguaje natural y visualizar respuestas generadas dinámicamente.

-Interfaz del Usuario (Frontend):
  El usuario interactúa con la interfaz web que se encuentra en index.html. La página incluye un formulario para enviar preguntas y una vista de chat donde las respuestas del bot serán mostradas.

  El frontend está estilizado usando styles.css para asegurar una experiencia visual atractiva y fluida.

-Comunicación con el Backend:
  Cuando el usuario envía una pregunta, el archivo app.js maneja la solicitud y envía la pregunta al backend a través de una petición POST a la ruta /chat en el servidor FastAPI (definido en main.py).

  El backend recibe la pregunta en la ruta /chat, procesa la consulta usando la función answer_question (importada desde graphrag_app.app), y devuelve una respuesta.

-Respuesta y Actualización del Chat:
  La respuesta generada por el backend es luego presentada al usuario en la interfaz de chat. Si el servidor está procesando, se muestra un indicador de carga en el frontend.

  Además, app.js gestiona el historial de conversaciones, almacenando las consultas y respuestas para su recuperación en sesiones futuras.

-Historial de Conversaciones:
  Las conversaciones del usuario se guardan en el almacenamiento local (localStorage), lo que permite que el usuario vea y continúe con consultas anteriores, organizadas de manera intuitiva en la barra lateral.

Componentes: 

1. main.py:

Propósito: Este archivo es el servidor principal de la aplicación, gestionado con FastAPI. Configura el servidor web, sirviendo tanto los archivos estáticos (HTML, CSS, JS) como manejando las peticiones de chat (consultas del usuario).

Roles: Monta los archivos estáticos (CSS, JS, HTML) usando StaticFiles. Define las rutas principales, como la de la página principal (/) y la ruta para enviar y recibir mensajes de chat (/chat).Utiliza la función answer_question de graphrag_app para procesar las preguntas del usuario y generar respuestas, que luego se envían a la interfaz web.

Carpeta static:

Esta carpeta contiene los archivos relacionados con la interfaz de usuario (frontend), como los scripts de JavaScript, hojas de estilo CSS y el HTML.

2. app.js:

Propósito: Es el archivo JavaScript que maneja la lógica interactiva del frontend.

Roles:Gestiona el flujo de mensajes en el chat, permitiendo al usuario interactuar con la aplicación. Envía las consultas del usuario al servidor backend usando la ruta /chat mediante fetch. Muestra las respuestas del bot y maneja las actualizaciones de la conversación, incluyendo la creación de nuevas consultas y la visualización de conversaciones anteriores almacenadas en el almacenamiento local (localStorage). También maneja la visualización del estado de carga mientras se espera la respuesta del servidor.

3. index.html:

Propósito: Es la página principal de la interfaz web.

Roles: Proporciona la estructura de la página, incluyendo un chat interactivo y una barra lateral con opciones como "Nueva consulta" y "Limpiar historial".Se cargan y se muestran las respuestas del sistema dentro de un área de chat. Se conecta con el archivo app.js para gestionar la interacción entre el usuario y el bot.

4. styles.css:

Propósito: Contiene los estilos para la interfaz de usuario.

Roles: Define el diseño visual de la página web, incluyendo la disposición del chat, la barra lateral y los mensajes. Incluye estilos para elementos como el fondo, los botones, los mensajes de usuario y bot, la animación de carga, y la apariencia general de la interfaz. Hace que la interfaz sea responsiva para diferentes tamaños de pantalla, ajustando el diseño a dispositivos móviles.

## Ontología

La ontología OWL define las clases principales del dominio académico:

- Documento
- Figura
- UmbralPuntuacion
- Requisito
- ApartadoEvaluacion

Permite modelar:

- Requisitos mínimos y máximos
- Criterios de evaluación
- Relación entre figuras académicas y normativa

---

## 🔧 Requisitos

- Python 3.10+
- Apache Jena Fuseki
- Ollama (con modelo instalado, por ejemplo `llama3.1:8b`)
- FAISS
- Protégé

---
