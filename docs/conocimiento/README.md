# Base de conocimiento (RAG)

Ficheros `.md` que `modulos/rag` trocea, vectoriza (`OLLAMA_MODELO_EMBEDDINGS`) y guarda en pgvector.
El motor de IA inyecta los fragmentos relevantes en `DocumentoPreparado.contexto_rag`.
Responsable de la indexacion: PERSONA_2 (etapa 3).

Categorias (diapositiva 9) y un fichero por categoria como minimo:

| Categoria | Fichero | Lo usa |
|---|---|---|
| Criterios de clasificacion | `criterios_clasificacion.md` | prompt de clasificacion |
| Estructuras de extraccion | `estructuras_extraccion.md` | prompt de extraccion |
| Politicas y reglas de negocio | `politicas_onboarding.md` | validacion y resumen |
| Definiciones | (anadir segun se necesite) | todos |
| Ejemplos | (anadir segun se necesite) | clasificacion |

Reglas:
- Solo contenido generico o inventado. Nunca datos personales ni documentos reales.
- Un encabezado `##` por tema: el troceado corta por encabezados.
- Lo que sea una regla **determinista** va en `config/tipos/*.yaml`, no aqui. Aqui va el contexto que
  ayuda al modelo a interpretar, no lo que se comprueba con codigo.
