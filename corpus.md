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

ANECA:  
https://www.aneca.es

BOE:  
https://www.boe.es

1. Archivo procesado:
    - guia_noti.ttl
    Fuente:  
    https://www.unibasq.eus/eu/irakasle-eta-ikertzaileak-osagarriak/    

2. Archivo procesado:
    - guia_osagarriak.ttl
    Fuente:  
    https://www.unibasq.eus/eu/irakasle-eta-ikertzaileak-osagarriak/

3. Archivo procesado:
    - COM.18Protokoloa.ttl
    Fuente:  
    https://www.unibasq.eus/eu/irakasle-eta-ikertzaileak-osagarriak/

4. Archivo procesado:
    - protocolo_2025.ttl
    Fuente:  
    https://www.unibasq.eus/es/profesorado-acreditacion-del-pdi/

5. Archivo procesado:
    - tasak.ttl
    Fuente:  
    https://www.unibasq.eus/eu/irakasle-eta-ikertzaileak-osagarriak/

6. Archivo procesado:
    - noti_de_resultados.ttl
    Fuente:  
    https://www.unibasq.eus/es/profesorado-acreditacion-del-pdi/

7. Archivo procesado:
    - Decreto_209_2006.ttl
    Fuente:  
    https://www.unibasq.eus/eu/irakasle-eta-ikertzaileak-osagarriak/

8. Archivo procesado:
    - Decreto_64_2011.ttl
    Fuente:  
    https://www.unibasq.eus/eu/irakasle-eta-ikertzaileak-osagarriak/

9. Archivo procesado:
    - base.ttl
    Fuente:  
    https://www.unibasq.eus/es/profesorado-acreditacion-del-pdi/

10. Archivo procesado:
    - galdera_ohikoak.ttl
    Fuente:  
    https://www.unibasq.eus/eu/irakasle-eta-ikertzaileak-osagarriak/

11. Archivo procesado:
    - preguntas_frequentes.ttl  
    Fuente:  
    https://www.unibasq.eus/eu/irakasle-eta-ikertzaileak-osagarriak/

12. Archivo procesado:
    - tasas.ttl  
    Fuente:  
    https://www.unibasq.eus/eu/irakasle-eta-ikertzaileak-osagarriak/

13. Archivo procesado:
    - BOE-A-2023-19027-consolidado.ttl  
    Fuente:  
    https://www.boe.es/eli/es/rd/2023/07/18/678

14. Archivo procesado:
    - academia_adicional_procedimiento.ttl  
    Fuente:  
    https://www.aneca.es/documents/20123/0/PROCEDIMIENTO+ACREDITACION+ACADEMIA+2024.pdf

15. Archivo procesado:
    - Criterios200324_anexos_2.ttl  
    Fuente:  
    https://www.aneca.es/documents/20123/0/CRITERIOS+ACREDITACION+PROFESORADO+2024.pdf

16. Archivo procesado:
    - BOE_A_2023_consolidado.ttl  
    Fuente:  
    https://www.boe.es/eli/es/lo/2023/03/22/2

17. Archivo procesado:
    - Programa_DOCENTIA.ttl  
    Fuente:  
    https://www.aneca.es/documents/20123/0/DOCENTIA+2025.pdf

18. Archivo procesado:
    - BOE-A-2021-15781.ttl  
    Fuente:  
    https://www.boe.es/eli/es/rd/2021/09/28/822

19. Archivo procesado:
    - ESG_Español.ttl  
    Fuente:  
    https://www.aneca.es/documents/20123/81037/ESG_Espa%C3%B1ol.pdf

Este archivo define el modelo semántico utilizado en el sistema, incluyendo
las clases y propiedades principales como:

- Documento
- Fragmento
- Requisito
- UmbralPuntuacion
- Seccion
- Figura
- Normativa
- CriterioEvaluacion
- Procedimiento
- ProgramaEvaluacion
- FuenteOficial

---

Total de documentos RDF procesados: **19**

---

# Uso en el sistema

Los documentos del corpus se utilizan para:

- Construir el grafo semántico en **Apache Fuseki**
- Generar índices vectoriales para recuperación semántica
- Soportar el sistema **GraphRAG** desarrollado en este proyecto