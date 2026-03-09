# Corpus documental

Este repositorio utiliza un conjunto de documentos oficiales relacionados con 
el procedimiento de evaluación y reconocimiento de complementos retributivos
del personal docente e investigador  gestionado por **UNIBASQ**.

Los documentos han sido procesados mediante un pipeline de extracción
semántica que transforma los PDFs originales en representaciones RDF (TTL),
que posteriormente se utilizan en el sistema GraphRAG para la recuperación
híbrida de información.

---

UNIBASQ:  
https://www.unibasq.eus

1. Archivo procesado:
    - guia_noti.ttl
    Fuente:  
    https://www.unibasq.eus/eu/irakasle-eta-ikertzaileak-osagarriak/    

2. Archivo procesado:
    -guia_osagarriak.ttl
    Fuente:  
    https://www.unibasq.eus/eu/irakasle-eta-ikertzaileak-osagarriak/

3. Archivo procesado:
    -COM.18Protokoloa.ttl
    Fuente:  
    https://www.unibasq.eus/eu/irakasle-eta-ikertzaileak-osagarriak/

4. Archivo procesado:
    -protocolo_2025.ttl
    Fuente:  
    https://www.unibasq.eus/es/profesorado-acreditacion-del-pdi/

5. Archivo procesado:
    -tasak.ttl
    Fuente:  
    https://www.unibasq.eus/eu/irakasle-eta-ikertzaileak-osagarriak/

6. Archivo procesado:
    -noti_de_resultados.ttl
    Fuente:  
    https://www.unibasq.eus/es/profesorado-acreditacion-del-pdi/

7. Archivo procesado:
    -Decreto_209_2006.ttl
    Fuente:  
    https://www.unibasq.eus/eu/irakasle-eta-ikertzaileak-osagarriak/

8. Archivo procesado:
    -Decreto_64_2011.ttl
    Fuente:  
    https://www.unibasq.eus/eu/irakasle-eta-ikertzaileak-osagarriak/

9. Archivo procesado:
    -base.ttl
    Fuente:  
    https://www.unibasq.eus/es/profesorado-acreditacion-del-pdi/

10. Archivo procesado:
    -galdera_ohikoak.ttl
    Fuente:  
    https://www.unibasq.eus/eu/irakasle-eta-ikertzaileak-osagarriak/

Este archivo define el modelo semántico utilizado en el sistema, incluyendo
las clases y propiedades principales como:

- Documento
- Fragmento
- Requisito
- UmbralPuntuacion
- Seccion
- Figura

---

Total de documentos RDF procesados: **10**

---

# Uso en el sistema

Los documentos del corpus se utilizan para:

- Construir el grafo semántico en **Apache Fuseki**
- Generar índices vectoriales para recuperación semántica
- Soportar el sistema **GraphRAG** desarrollado en este proyecto