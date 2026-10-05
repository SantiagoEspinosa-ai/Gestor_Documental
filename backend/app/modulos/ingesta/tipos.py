"""Fichas de tipos documentales que necesita la ingesta, desde `configuracion.servicio` (PERSONA_2).

Las fichas se cargan y validan una vez (`configuracion.servicio.cargar()` en el arranque de la app);
este modulo no lee YAML.
"""
from app.modulos.configuracion import servicio as configuracion


def existe_tipo(tipo: str) -> bool:
    try:
        configuracion.obtener(tipo)
    except configuracion.TipoNoEncontrado:
        return False
    return True


def formatos_permitidos(tipo: str | None) -> set[str]:
    """Extensiones (minusculas, sin punto) del tipo dado, o de todos los tipos si es None."""
    elegidas = [configuracion.obtener(tipo)] if tipo else configuracion.listar()
    return {f for ficha in elegidas for f in ficha.formatos_permitidos}


def _campo(campo: configuracion.Campo) -> dict:
    datos = {"tipo": campo.tipo.value, "obligatorio": campo.obligatorio, "sensible": campo.sensible}  # ADR-010 A6
    if campo.patron:
        datos["patron"] = campo.patron
    return datos


def _regla(regla: configuracion.Regla) -> dict:
    # Mismo orden de claves que las fichas YAML (campo_relacionado y dias, si los hay, tras campo)
    datos = {"id": regla.id, "tipo": regla.tipo.value, "campo": regla.campo}
    if regla.campo_relacionado is not None:
        datos["campo_relacionado"] = regla.campo_relacionado
    if regla.dias is not None:
        datos["dias"] = regla.dias
    datos["severidad"] = regla.severidad.value
    datos["mensaje"] = regla.mensaje
    return datos


def listar_fichas() -> list[dict]:
    """Fichas con la forma `TipoDocumental` de endpoints.md, ordenadas por nombre.

    El dict se arma a mano y no con `model_dump`: una clave de mas en el modelo de `configuracion`
    (p. ej. `caracteristicas_esperadas`) cambiaria el contrato.
    """
    return [
        {
            "nombre": ficha.nombre,
            "nombre_visible": ficha.nombre_visible,
            "categoria": ficha.categoria,
            "descripcion": ficha.descripcion,
            "formatos_permitidos": list(ficha.formatos_permitidos),  # el modelo ya los deja en minusculas y sin punto
            "campos": {nombre: _campo(campo) for nombre, campo in ficha.campos.items()},
            "confianza_minima_clasificacion": ficha.confianza_minima_clasificacion,
            "confianza_minima_campo": ficha.confianza_minima_campo,
            "reglas": [_regla(r) for r in ficha.reglas],
            "comparaciones": {otro: list(campos) for otro, campos in ficha.comparaciones.items()},
        }
        for ficha in sorted(configuracion.listar(), key=lambda f: f.nombre)
    ]


def campos_sensibles(*tipos: str | None) -> set[str]:
    """Campos con `sensible: true` (ADR-010 A1) en las fichas de esos tipos; los que no tienen ficha
    (None, "desconocido") no aportan ninguno."""
    sensibles = set()
    for tipo in tipos:
        if tipo and existe_tipo(tipo):
            sensibles |= {nombre for nombre, campo in configuracion.obtener(tipo).campos.items() if campo.sensible}
    return sensibles


def nombre_visible(tipo: str) -> str:
    """Nombre legible del tipo; si no hay ficha o no lo define, el nombre tecnico."""
    try:
        return configuracion.obtener(tipo).nombre_visible or tipo
    except Exception:  # noqa: BLE001  una ficha ilegible no debe impedir crear el folio
        return tipo
