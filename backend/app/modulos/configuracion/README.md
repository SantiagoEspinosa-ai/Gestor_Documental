# configuracion  (responsable: PERSONA_2)

Carga y valida las fichas de tipos documentales. Los demas modulos solo importan `servicio.py`.

Entrada: `<CONFIG_DIR>/tipos/*.yaml`. `CONFIG_DIR` sale de la variable de entorno (en Docker `/config`);
si no esta definida, se usa `config/` en la raiz del repo.

Salida (`servicio.py`):
- `cargar(directorio=None) -> dict[str, TipoDocumental]`: lee y valida todas las fichas. Llamarlo al
  arrancar; si alguna es invalida lanza `ErrorConfiguracion` con una linea por problema
  (`fichero: ruta.del.campo: motivo`) de todos los ficheros a la vez.
- `obtener(nombre) -> TipoDocumental` (o `TipoNoEncontrado`) y `listar() -> list[TipoDocumental]`.
  Si nadie llamo a `cargar()`, cargan la primera vez y guardan el resultado en memoria.
- `directorio_config() -> Path`: `CONFIG_DIR` o `config/` de la raiz del repo (lo usa el enrutador de
  `motor_ia` para encontrar `modelos.yaml`).
- Modelos Pydantic: `TipoDocumental`, `Campo`, `Regla` y los enums `TipoCampo`, `TipoRegla`
  (`Regla.severidad` usa `Severidad` del Contrato 1).

Que se valida:
- Claves obligatorias; claves desconocidas son error (detecta erratas).
- Confianzas entre 0 y 1; `formatos_permitidos` se normaliza a minusculas sin punto.
- Ninguna ficha puede llamarse `desconocido` (`NOMBRE_RESERVADO`, ADR-009).
- `marcadores_clasificacion` (opcional, ADR-007): expresiones regulares que compilan (con `FLAGS_MARCADORES`)
  y sin repetidos. `motor_ia/confianza.py` las busca en el texto normalizado del documento.
  Son internos del motor: quedan fuera de `model_dump()` y de `GET /tipos-documentales` (Contrato 2 sin cambios).
- Tipos de campo (`texto`, `fecha`, `anio`) y de regla validos; severidad del Contrato 1.
- `patron` compila como expresion regular; una regla `patron` usa el patron de su campo.
- Reglas `*_mas_dias` / `*_menos_dias` llevan `dias > 0`; ids de regla unicos; cada regla apunta a
  un campo existente.
- `nombre` igual al nombre del fichero.
- `comparaciones` apunta a tipos existentes y a campos presentes en ambas fichas.
- No se comprueba que existan los ficheros de `ejemplos_referencia` ni la simetria de las comparaciones.
  `ejemplos_referencia` apunta a los fixtures del caso sano (`fixtures/generados/<tipo>_sano_<modalidad>.<ext>`),
  que no estan en git: se generan con `scripts/generar_fixtures.py`. Un test comprueba el formato del nombre.

Anadir un tipo documental = anadir un YAML en `config/tipos/`, sin tocar codigo. Anadir un tipo de
campo o de regla nuevo si requiere codigo (`TipoCampo`, `TipoRegla`).

Fuera de este modulo: `procesos.yaml` (plataforma, PERSONA_1) y `modelos.yaml` (lo valida
`motor_ia/enrutador.py`).

Tests: `backend/tests/test_configuracion.py` (`cd backend && python -m pytest -q`).
