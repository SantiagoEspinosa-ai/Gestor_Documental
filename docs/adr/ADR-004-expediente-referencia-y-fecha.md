# ADR-004: Referencia y fecha de solicitud en ResultadoExpediente

Fecha: 2026-09-29. Estado: ACEPTADO el 2026-09-30 (revision del PR #1, junto con el ADR-006).
Aplicado en `backend/app/schemas/resultado.py`.

## Contexto
- Diapositiva 8: la cabecera del expediente muestra folio, **solicitante**, **fecha de solicitud** y
  estado general.
- Diapositiva 9: el resumen `.md` incluye "identidad o referencia de la persona" y "fecha y referencia
  del tramite".
- `POST /folios` ya recibe `referencia_externa` y la tabla `folios` guarda `creado_en`, pero
  `ResultadoExpediente` (Contrato 1) no expone ninguno de los dos. El frontend tendria que inventarlos
  y los integradores externos no los reciben.

## Decision propuesta
Anadir dos campos opcionales a `ResultadoExpediente` en `backend/app/schemas/resultado.py`:

```python
referencia_externa: str | None = None   # id del solicitante en el sistema integrador (nunca el nombre)
fecha_solicitud: datetime | None = None # = folios.creado_en
```

`referencia_externa` es un identificador opaco del sistema que integra (p. ej. `CLI-000123`), no el
nombre de la persona: el nombre sale de `datos_extraidos` y se enmascara en la UI (extra 1).

## Consecuencias
- Son opcionales: no rompen a nadie que ya consuma el contrato.
- PERSONA_1 los rellena en `GET /folios/{folio}`; PERSONA_3 los pinta en la cabecera y en los mocks;
  la plantilla del resumen `.md` los usa.
