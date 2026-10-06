"""
Memoria de folios (H14, ADR-010 C4): guarda el resumen.md de cada folio y extrae un fragmento para los
antecedentes. Sin embeddings ni modelo (spec, seccion 16): C4 solo pide un trozo del resumen del folio, y los
folios relacionados los elige la plataforma con SQL.

El resumen llega ya enmascarado (ADR-010 A5). El fragmento, ademas, no copia los valores de los datos ni de las
comparaciones ni el comentario libre de la decision: solo cabecera, decision, estado de cada documento y alertas.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.db import SesionLocal, get_engine
from app.modulos.rag.modelos import MemoriaFolio

log = logging.getLogger(__name__)

LIMITE_FRAGMENTO = 800  # caracteres; se corta en un final de linea
_RECORTADO = "..."


def extraer_fragmento(resumen_md: str, limite: int = LIMITE_FRAGMENTO) -> str:
    """Fragmento determinista del resumen.md (formato de expediente/plantillas/resumen.md.j2):
    - cabecera: titulo y lineas `- Clave: valor` (referencia opaca, proceso, fecha, estado, recomendacion);
    - decision: todas sus lineas salvo `- Comentario:` (texto libre);
    - por documento: su titulo, el estado del analisis y sus alertas (codigo, campo y mensaje), sin `Datos:`;
    - alertas del expediente. Nunca las comparaciones (llevan valores) ni "Generado el".
    Se corta en un final de linea antes de `limite` caracteres, marcando el corte con "..."."""
    lineas: list[str] = []
    seccion, bloque = "cabecera", None
    for cruda in resumen_md.splitlines():
        linea = cruda.rstrip()
        if not linea.strip():
            continue
        if linea.startswith("# "):
            lineas.append(linea)
            continue
        if linea.startswith("## "):
            seccion, bloque = linea[3:].strip().lower(), None
            if seccion in ("decision", "alertas del expediente"):
                lineas.append(linea)
            continue
        if linea.startswith("### "):
            bloque = "documento"
            lineas.append(linea)
            continue
        if seccion == "cabecera":
            if linea.startswith("- "):
                lineas.append(linea)
        elif seccion == "decision":
            if linea.startswith("- ") and not linea.startswith("- Comentario:"):
                lineas.append(linea)
        elif seccion in ("documentos", "alertas del expediente"):
            if linea.startswith("- Estado del analisis:"):
                lineas.append(linea)
            elif linea == "Datos:":
                bloque = "datos"
            elif linea.endswith(":") and not linea.startswith("- "):
                bloque = "alertas"  # titulo de un grupo de alertas (p. ej. "Criticas:")
                lineas.append(linea)
            elif bloque == "alertas" and linea.startswith("- "):
                lineas.append(linea)
    return _recortar(lineas, limite)


def _recortar(lineas: list[str], limite: int) -> str:
    salida, total = [], 0
    for linea in lineas:
        if total + len(linea) + 1 > limite - len(_RECORTADO) - 1:
            salida.append(_RECORTADO)
            break
        salida.append(linea)
        total += len(linea) + 1
    return "\n".join(salida)


def indexar_resumen(folio: str, resumen_md: str, *, sesion: Session | None = None,
                    ahora: datetime | None = None) -> None:
    """Guarda (o sustituye) el resumen del folio y su fragmento. **Nunca lanza**: se llama despues de regenerar el
    resumen, y un fallo aqui no debe romper la accion del revisor. Si falla, se registra solo el folio y el tipo de
    error (nunca el contenido) y el siguiente cambio lo reindexa."""
    propia = sesion is None
    sesion = sesion or SesionLocal(bind=get_engine())
    try:
        fila = sesion.get(MemoriaFolio, folio)
        datos = {"resumen_md": resumen_md, "fragmento": extraer_fragmento(resumen_md),
                 "actualizado_en": ahora or datetime.now(timezone.utc)}
        if fila is None:
            sesion.add(MemoriaFolio(folio=folio, **datos))
        else:
            for clave, valor in datos.items():
                setattr(fila, clave, valor)
        sesion.commit()
    except Exception as e:  # noqa: BLE001 - nunca lanza (ver docstring)
        sesion.rollback()
        log.warning("No se pudo indexar el resumen del folio %s: %s", folio, type(e).__name__)
    finally:
        if propia:
            sesion.close()


def fragmento_resumen(folio: str, *, sesion: Session | None = None) -> str | None:
    """El fragmento del resumen del folio (ya enmascarado), o None si el folio no esta indexado."""
    propia = sesion is None
    sesion = sesion or SesionLocal(bind=get_engine())
    try:
        fila = sesion.get(MemoriaFolio, folio)
        return fila.fragmento if fila is not None else None
    finally:
        if propia:
            sesion.close()
