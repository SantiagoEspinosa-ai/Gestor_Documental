# orquestador  (responsable: PERSONA_2)

Prepara cada documento para el motor de IA. Configuracion vigente:
[docs/motor_ia/SPEC_CONFIGURACION.md](../../../../docs/motor_ia/SPEC_CONFIGURACION.md).

## `modalidad.py`
Entrada: `detectar(contenido: bytes, nombre: str)`.
Salida: `Modalidad` (Contrato 3): `pdf_digital` | `pdf_escaneado` | `imagen`.

- El formato se decide por los primeros bytes (`%PDF-`, PNG, JPEG), no por la extension. Si no
  coinciden, manda el contenido y se registra un aviso sin el nombre del archivo.
- PDF: `pdf_digital` solo si **todas** las paginas tienen al menos `UMBRAL_CARACTERES_POR_PAGINA`
  (30) caracteres de texto extraible, sin contar espacios. Si alguna no llega (escaneado o mixto):
  `pdf_escaneado`.
- PNG y JPEG: `imagen`.
- Formato desconocido, archivo vacio, PDF corrupto, cifrado o sin paginas: `FormatoNoSoportado`.
- `caracteres_por_pagina(contenido)` devuelve el recuento por pagina; lo reutilizara el preparador.

Validar la extension contra `formatos_permitidos` de la ficha es tarea de `ingesta` (PERSONA_1).

## Pendiente
- `ocr.py`: `OCRProvider` + `TesseractOCR` (tarea 3).
- `preparador.py` y `servicio.py`: `preparar(bytes, nombre, tipo_declarado) -> DocumentoPreparado` (tarea 4).

Tests: `backend/tests/test_modalidad.py`.
