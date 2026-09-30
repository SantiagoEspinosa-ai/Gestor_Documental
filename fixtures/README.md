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
Necesita PyMuPDF, Pillow y PyYAML (`backend/requirements.txt`). Tarda unos segundos.

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

## Nombres
`{tipo}_{caso}_{modalidad}.{pdf|jpg}`, con `tipo` = `pasaporte`, `credencial_elector` o
`comprobante_domicilio`. Ejemplo: `pasaporte_vencido_escaneado.pdf`.

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

## Legibilidad OCR
Tras cambiar el generador, comprueba que Tesseract los lee (contenedor del backend, PowerShell,
desde la raiz del repo):
```
docker compose run --rm --no-deps -v "${PWD}\fixtures:/fixtures" -v "${PWD}\scripts:/scripts:ro" `
    backend python /scripts/verificar_ocr_fixtures.py --control
```
Deja la tabla en `fixtures/generados/resultado_ocr.md`. Referencia: 150/153 campos. Los fallos
(sexo "M" suelto y Z/2 en la MRZ de `pasaporte_vencido`) ocurren tambien en el control digital y
se dejan a proposito porque son realistas.

## Prohibido
Nunca anadas aqui (ni en `generados/`, ni en el bucket S3, ni en capturas) documentos, nombres,
CURP, domicilios ni fotos de personas reales. Solo `PERSONAS_FICTICIAS` del generador, sin escudos,
logotipos ni nombres de organismos reales.
