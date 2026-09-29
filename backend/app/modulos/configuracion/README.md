# configuracion  (responsable: PERSONA_2)

Entrada: `CONFIG_DIR/tipos/*.yaml`, `procesos.yaml`, `modelos.yaml`.
Salida: `obtener(nombre) -> TipoDocumental`, `listar() -> list[TipoDocumental]` (modelos Pydantic
`TipoDocumental`, `Campo`, `Regla`). Un YAML mal formado impide arrancar, con el fichero y el campo
en el mensaje. Anadir un tipo = anadir un YAML, sin tocar codigo.
