# fixtures (responsable: PERSONA_3)

Documentos FICTICIOS de prueba para el pipeline de ingesta, OCR y extraccion, y para los e2e.

## Por que no se suben
`fixtures/generados/` esta en `.gitignore`. El script es la fuente de verdad: las fechas son
relativas a `--hoy` (los casos no caducan) y con el mismo `--hoy` los ficheros salen identicos byte a
byte. Cada persona los genera en local.

## Como generarlos
```
python scripts/generar_fixtures.py                    # --hoy = fecha de hoy
python scripts/generar_fixtures.py --hoy 2026-09-30   # la de los mocks del frontend (DUP-001 contra ellos)
```
Necesita PyMuPDF, Pillow y PyYAML (`backend/requirements.txt`). Tarda unos segundos y genera 42
ficheros e `INDICE.md`: 3 casos x 3 tipos x 3 modalidades (27), las 3 copias del caso `duplicado`
(solo la credencial) y 12 de dificultad.

## Casos
| Caso | Persona | Que tiene |
|---|---|---|
| `sano` | 1 | Los tres documentos coinciden y estan vigentes |
| `vencido` | 2 | Pasaporte vencido hace 30 dias |
| `domicilio_distinto` | 1 | El comprobante lleva otro domicilio que la credencial |
| `duplicado` | 1 | Copia byte a byte de `credencial_elector_sano_*` (mismo SHA-256) |

## Modalidades
- `_digital.pdf`: PDF con capa de texto real.
- `_escaneado.pdf`: imagen a 200 dpi en gris, con ruido y rotacion ligera, sin capa de texto.
- `_foto.jpg`: foto simulada con perspectiva, sombra y luz desigual.

## Niveles de dificultad
Para que PERSONA_2 decida cuando el motor pasa del OCR al modelo de vision, el caso `sano` de los
3 tipos tiene ademas escaneado y foto en dos niveles mas degradados (12 ficheros):

| Nivel | Escaneado | Foto | OCR esperado |
|---|---|---|---|
| `normal` (sin sufijo) | 200 dpi, rotacion 0,4-1,2 grados, ruido 0,06, JPEG 80 | 150 dpi, perspectiva 3-6 %, JPEG 88 | ~100 % de los campos |
| `dificil` | 150 dpi, rotacion 2-3 grados, ruido 0,18, desenfoque 1,1 px, JPEG 40 | 130 dpi, perspectiva 8-10 %, rotacion 2-3 grados, ruido 0,18, desenfoque 1,3 px, JPEG 40 | 50-80 % |
| `extremo` | 105 dpi, rotacion 4-6 grados, ruido 0,22, desenfoque 1,3 px, JPEG 30 | 115 dpi, perspectiva 12-15 %, rotacion 4-6 grados, ruido 0,21, desenfoque 1,45 px, JPEG 30 | < 30 %, pero legible para una persona |

- Valores esperados: los del caso `sano`. `INDICE.md` los repite en "Fixtures de dificultad", con los
  parametros aplicados a cada fichero (angulo y perspectiva concretos) y su SHA-256.
- No forman parte de ningun folio de prueba ni de los mocks.
- Los parametros (`PARAMETROS` en el generador) se ajustaron con `verificar_ocr_fixtures.py`. El OCR
  cae de golpe al bajar la resolucion: en la foto extrema, 115 dpi da 12 % y 118 dpi da 0 %. Tras
  tocarlos, vuelve a verificar.
- El nivel `normal` no cambia: sus SHA-256 estan fijados en
  `backend/tests/sha256_fixtures_existentes.txt`, porque de ellos dependen
  `frontend/public/mock-originales` y los mocks. El fichero guarda tambien las versiones de PyMuPDF y
  Pillow con las que se generaron: los bytes dependen de ellas y `requirements.txt` usa `>=`, asi que
  con otras versiones los tests que comparan hashes se omiten (`pytest.skip`, con las versiones
  esperadas y las instaladas) en vez de fallar (`backend/tests/versiones_fixtures.py`).

## Nombres
`{tipo}_{caso}_{modalidad}.{pdf|jpg}`, con `tipo` = `pasaporte`, `credencial_elector` o
`comprobante_domicilio`. Ejemplo: `pasaporte_vencido_escaneado.pdf`.
Niveles de dificultad: `{tipo}_sano_{modalidad}_{nivel}.{pdf|jpg}`, por ejemplo
`pasaporte_sano_foto_dificil.jpg`.

## INDICE.md
`fixtures/generados/INDICE.md` es la verdad de referencia para los tests: archivos y SHA-256, valores
esperados por campo (fechas en ISO 8601) y alertas esperadas por folio de prueba, con codigo,
severidad y si van en el documento o en `alertas_expediente`:

| Folio de prueba | Documentos | Alertas esperadas |
|---|---|---|
| `sano` | los 3 de `sano` | ninguna |
| `vencido` | los 3 de `vencido` | `REG-vigencia_documento` (bloqueante) y `REG-vigencia_proxima` (preventiva) en el pasaporte |
| `domicilio_distinto` | los 3 de `domicilio_distinto` | `CMP-001` de `domicilio` en `alertas_expediente` |
| `duplicado` | credencial sano + su copia + comprobante sano | `DUP-001` en la copia |
| `falta_requerido` | pasaporte y credencial de `sano` | `EXP-001` (campo `comprobante_domicilio`) en `alertas_expediente` |

Solo lista alertas deterministas: `VAL-002`, `CLS-002` y `VIS-xxx` dependen del modelo.
Al final, la seccion "Fixtures de dificultad" (ver "Niveles de dificultad").

## Legibilidad OCR
Tras cambiar el generador, comprueba que Tesseract los lee (contenedor del backend, PowerShell,
desde la raiz del repo):
```
docker compose run --rm --no-deps -v "${PWD}\fixtures:/fixtures" -v "${PWD}\scripts:/scripts:ro" `
    backend python /scripts/verificar_ocr_fixtures.py --control
```
Deja la tabla en `fixtures/generados/resultado_ocr.md`, agrupada por nivel. Referencia (2026-10-01):

| Nivel | Ficheros | Campos encontrados |
|---|---|---|
| control (render del digital) | 9 | 50/51 (98 %) |
| normal | 18 | 100/102 (98 %) |
| dificil | 6 | 24/34 (71 %) |
| extremo | 6 | 5/34 (15 %) |
| especimen (fotos reales de los impresos) | 5 | 23/27 (85 %) |

Los fallos de los niveles control y normal (sexo "M" suelto y Z/2 en la MRZ de `pasaporte_vencido`)
ocurren tambien en el control digital y se dejan a proposito porque son realistas.

## Especimenes impresos
`fixtures/especimenes/` tiene fotos de movil de los documentos del caso `sano` impresos (con
`--hoy 2026-09-30`), sin metadatos. A diferencia de `generados/`, **si se sube a git**. Se preparan
con `scripts/procesar_especimenes.py` y el verificador OCR las incluye como nivel `especimen`. Ver
`fixtures/especimenes/README.md` (valores esperados y fechas a partir de las que dan alertas).

## Pendientes
- Especimenes: repetir o recortar las 4 fotos descartadas (`pasaporte` inclinada y dificil,
  `credencial_elector` inclinada y `comprobante_domicilio` inclinada); ver
  `fixtures/especimenes/README.md`.
- Etapa 2: e2e reales con los folios de prueba de `INDICE.md` sobre `docker compose` y Ollama.

## Prohibido
Nunca anadas aqui (ni en `generados/`, ni en el bucket S3, ni en capturas) documentos, nombres,
CURP, domicilios ni fotos de personas reales. Solo `PERSONAS_FICTICIAS` del generador, sin escudos,
logotipos ni nombres de organismos reales.
