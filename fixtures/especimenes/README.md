# Especimenes impresos (responsable: PERSONA_3)

Fotos de movil de los documentos FICTICIOS del caso `sano`, impresos en papel. Complementan a
`fixtures/generados/` (fotos simuladas por software) con fotos reales: papel, luz, sombras,
perspectiva y compresion de una camara de verdad. Sirven para probar el OCR, el paso a vision y los
e2e con algo parecido a lo que subira un usuario.

A diferencia de `fixtures/generados/`, esta carpeta **si se sube a git**: son ficheros fijos que no
se pueden regenerar.

## Como se hicieron
1. `python scripts/generar_fixtures.py --hoy 2026-09-30` y se imprimieron los
   `*_sano_digital.pdf` de los tres tipos (persona ficticia 1).
2. Se fotografiaron con un movil sobre una mesa o una moqueta, en tres condiciones:
   - `buena`: de frente, luz uniforme;
   - `inclinada`: con perspectiva;
   - `dificil`: sobre fondo con textura, con sombras y algo de angulo.
3. Se revisaron una a una: solo puede aparecer el documento ficticio, sin caras, manos, pantallas,
   otros papeles ni objetos personales. Las que no cumplian se descartaron (ver "Ficheros").
4. Se procesaron con `scripts/procesar_especimenes.py`:
   - comprueba la firma JPEG (no HEIC renombrado);
   - toma solo la imagen principal del MPO del movil;
   - aplica la orientacion EXIF y convierte a sRGB;
   - quita todos los metadatos (EXIF con GPS y modelo de camara, XMP, ICC, MPO);
   - reduce el lado largo a 2000 px y guarda en JPEG con calidad 85.

   Las fotos originales no se copian al repo.
   ```
   python scripts/procesar_especimenes.py <carpeta o fotos {tipo}_{condicion}.jpeg>
   ```

## Ficheros
Nombre: `{tipo}_sano_especimen_{condicion}.jpg`.

| Fichero | Tipo | Condicion |
|---|---|---|
| `pasaporte_sano_especimen_buena.jpg` | pasaporte | buena |
| `credencial_elector_sano_especimen_buena.jpg` | credencial_elector | buena |
| `credencial_elector_sano_especimen_dificil.jpg` | credencial_elector | dificil |
| `comprobante_domicilio_sano_especimen_buena.jpg` | comprobante_domicilio | buena |
| `comprobante_domicilio_sano_especimen_dificil.jpg` | comprobante_domicilio | dificil |

Faltan `pasaporte` (inclinada y dificil), `credencial_elector` (inclinada) y
`comprobante_domicilio` (inclinada). Esas fotos se descartaron en la revision porque salian otros
objetos en el encuadre (un vaso, cables, el borde de un portatil, la sombra de un pie o ropa).
**Pendiente:** repetirlas, o recortarlas para que solo quede el documento y volver a revisarlas antes
de procesarlas. Las originales no estan en el repo.

`backend/tests/test_especimenes.py` comprueba que ninguna foto tiene EXIF, GPS, XMP, ICC ni MPO,
que el lado largo no pasa de 2000 px y que ninguna supera 2 MB.

## Valores esperados (caso `sano` con `--hoy 2026-09-30`)
Los mismos que `sano / {tipo}` en `fixtures/generados/INDICE.md` generado con esa fecha. Todos son
ficticios.

### pasaporte
| Campo | Valor esperado |
|---|---|
| `nombre_completo` | ANA EJEMPLO PRUEBA |
| `numero_pasaporte` | ZX0000001 |
| `fecha_nacimiento` | 1990-01-01 |
| `fecha_expedicion` | 2021-09-30 |
| `fecha_vencimiento` | 2031-09-30 |
| `nacionalidad` | UTOPICA |
| `sexo` | F |

MRZ:
```
P<UTOEJEMPLO<PRUEBA<<ANA<<<<<<<<<<<<<<<<<<<<
ZX00000015UTO9001011F3109306<<<<<<<<<<<<<<06
```

### credencial_elector
| Campo | Valor esperado |
|---|---|
| `nombre_completo` | ANA EJEMPLO PRUEBA |
| `curp` | AEPA900101MDFXXX01 |
| `clave_elector` | EJPRAN90010199M101 |
| `fecha_nacimiento` | 1990-01-01 |
| `domicilio` | CALLE FICTICIA 123, COLONIA DEMO, CIUDAD EJEMPLO |
| `vigencia` | 2029 |

### comprobante_domicilio
| Campo | Valor esperado |
|---|---|
| `nombre_titular` | ANA EJEMPLO PRUEBA |
| `domicilio` | CALLE FICTICIA 123, COLONIA DEMO, CIUDAD EJEMPLO |
| `proveedor` | SERVICIOS DE EJEMPLO S.A. |
| `fecha_emision` | 2026-09-15 |

## Advertencia: las fechas impresas no se mueven
A diferencia de los fixtures generados, que se calculan desde `--hoy`, estas fotos llevan fechas
fijas. Con el tiempo empiezan a dar alertas que hoy no dan:

| Documento | Regla | Desde | Alerta |
|---|---|---|---|
| `comprobante_domicilio` | `antiguedad_maxima` (90 dias desde la emision) | **2026-12-14** (15/09/2026 + 90 dias; el 14 o el 15 de diciembre segun la regla compare con `>` o `>=`) | `REG-antiguedad_maxima`, critica |
| `pasaporte` | `vigencia_proxima` (vence en menos de 90 dias) | 2031-07-02 | `REG-vigencia_proxima`, preventiva |
| `credencial_elector` | `vigencia_documento` (anio de vigencia >= anio actual) | 2030 | `REG-vigencia_documento`, bloqueante |

A partir del 2026-12-14, un folio con estos especimenes ya no equivale al folio `sano` de
`INDICE.md`: el comprobante dara `REG-antiguedad_maxima`. Para tener un comprobante vigente hay que
volver a imprimirlo y fotografiarlo.

## Lectura OCR (referencia 2026-10-01)
Con `scripts/verificar_ocr_fixtures.py`, que los incluye como nivel `especimen`:

| Fichero | Campos leidos |
|---|---|
| `pasaporte_sano_especimen_buena.jpg` | 7/7 |
| `credencial_elector_sano_especimen_buena.jpg` | 6/6 |
| `credencial_elector_sano_especimen_dificil.jpg` | 6/6 |
| `comprobante_domicilio_sano_especimen_buena.jpg` | 4/4 |
| `comprobante_domicilio_sano_especimen_dificil.jpg` | 0/4 |

En total, 23/27 (85 %). El comprobante dificil no se lee: el A4 ocupa poco del encuadre y tiene
sombras. Es un buen caso para el paso a vision.

## Prohibido
Nunca anadas aqui fotos de documentos reales, ni propios ni ajenos, aunque se tapen datos. Tampoco
fotos en las que aparezcan personas (caras, manos), pantallas, otros papeles u objetos personales.
Solo especimenes impresos con `scripts/generar_fixtures.py` y procesados con
`scripts/procesar_especimenes.py`, que quita los metadatos (el GPS del movil incluido).
