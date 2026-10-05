# orquestador  (responsable: PERSONA_2)

Prepara cada documento y orquesta su analisis. Los demas modulos solo importan `servicio.py`
(`procesar_documento`, `preparar`, `detectar`, `FormatoNoSoportado`, `buscar_mrz`, `validar_digitos`, `Mrz`).

## `procesamiento.py`: `procesar_documento` (lo conecta la plataforma)
`procesar_documento(contenido, *, identificador, nombre_archivo, tipo_declarado, folio, referencia,
tipo_confirmado=None) -> (ResultadoDocumento, datos_auditoria)`. Sin BD ni S3. Pasos: `preparar` -> MRZ ->
`motor_ia.analizar` -> sexo desde la MRZ (`VAL-003`, `completar_mrz.py`) -> `validacion.evaluar_reglas` (con `hoy`
de `reloj.py`, zona `ZONA_HORARIA`) -> `validacion.recomendar_documento`. Proveedor caido: `error` + `SYS-001`; JSON
invalido: `error` + `SYS-002`; lo demas lanza. Detalle: spec, seccion 11. Configuracion vigente:
[docs/motor_ia/SPEC_CONFIGURACION.md](../../../../docs/motor_ia/SPEC_CONFIGURACION.md).

## `preparador.py`
Entrada: `preparar(contenido: bytes, nombre: str, tipo_declarado=None, *, identificador=None, ocr=None)`.
Salida: `DocumentoPreparado` (Contrato 3), con las paginas en orden y numeradas desde 1.

| Modalidad | Texto de cada pagina | Imagen de cada pagina |
|---|---|---|
| `pdf_digital` | capa de texto (PyMuPDF) | PNG a 150 dpi |
| `pdf_escaneado` | capa de texto si supera el umbral (PDF mixto); si no, OCR | PNG a 200 dpi |
| `imagen` | OCR | la propia imagen, orientada segun EXIF, en PNG |

- `identificador`: si no se pasa, un UUID4 (CLI). `ocr`: por defecto `TesseractOCR()`; los tests
  inyectan uno falso.
- Sin Tesseract (p. ej. Windows fuera de Docker): las paginas que necesitaban OCR quedan con
  `texto=None` y se avisa una vez en el log, sin el nombre del archivo. La vision sigue funcionando.
- Imagen corrupta: `FormatoNoSoportado`. Sin limite de paginas (el proveedor trabaja por lotes).

## `ocr.py`
`OCRProvider` (Protocol): `extraer_texto(imagen: bytes) -> str`. `TesseractOCR`: idiomas de
`TESSERACT_LANG` (por defecto `spa+eng`), preprocesado escala de grises + autocontraste, sin
enderezado. `ErrorOCR` si Tesseract no esta instalado o no puede leer la imagen. Unico sitio con
`pytesseract` (ADR-005).

## `mrz.py`
MRZ del pasaporte (TD3, dos lineas de 44 caracteres), funciones puras sobre el texto:
`buscar_mrz(texto) -> Mrz | None` (tolera espacios), `Mrz.sexo` (posicion 21 de la linea 2),
`validar_digitos(mrz)` (5 digitos de control, pesos 7-3-1). Se conecta en `motor_ia/servicio.py`
(tarea 9).

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
- `caracteres_por_pagina(contenido)` devuelve el recuento por pagina.

Validar la extension contra `formatos_permitidos` de la ficha es tarea de `ingesta` (PERSONA_1).

Tests: `test_modalidad.py`, `test_ocr.py`, `test_mrz.py`, `test_preparador.py` y, con los fixtures
montados, `test_fixtures_ocr.py`.
