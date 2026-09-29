# ADR-002: Contratos congelados

Fecha: 2026-09-29. Estado: aceptado.

## Decision
Tres contratos se congelan el dia 1 y solo cambian con un nuevo ADR y aviso al equipo:
1. `backend/app/schemas/resultado.py` - JSON de resultado por documento y expediente.
2. `docs/contratos/endpoints.md` - API REST y webhook.
3. `backend/app/modulos/motor_ia/interfaces.py` - interfaz del orquestador, proveedores y enrutador.

Convenciones: snake_case en espanol; folio `{PREFIJO}-{AAAA}-{NNNNNN}`; severidades
informativa | preventiva | critica | bloqueante; recomendacion aprobar | revision_manual | rechazar.

## Motivo
Permite que tres personas trabajen en paralelo contra mocks e integren sin sorpresas.
