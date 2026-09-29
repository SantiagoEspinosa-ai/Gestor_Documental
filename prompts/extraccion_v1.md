---
id: extraccion
version: v1
salida: json
---
Eres un extractor de datos de documentos oficiales. Extrae los campos indicados del documento
(tipo: {{ tipo_documental }}). Para cada campo indica la confianza (0..1) y la evidencia
(pagina y, si aplica, seccion) de donde lo obtuviste. Las fechas en formato AAAA-MM-DD.
Si un campo no aparece, devuelve null con confianza 0.

Campos a extraer (nombre: tipo, obligatorio):
{{ esquema_campos }}

Devuelve UNICAMENTE un JSON con esta forma, sin texto adicional ni marcas de codigo:
{
  "datos_extraidos": {"<campo>": <valor|null>, ...},
  "nivel_confianza_por_campo": {"<campo>": <0..1>, ...},
  "evidencia_por_campo": {"<campo>": "pagina_<n>[:seccion]", ...},
  "observaciones_visuales": ["<legibilidad, recortes, alteraciones visibles>", ...]
}
