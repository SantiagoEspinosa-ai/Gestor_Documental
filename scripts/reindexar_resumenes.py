"""
Regenera el resumen.md de cada folio y lo indexa en la memoria de folios (H14). De un solo uso, tras
desplegar la memoria: los folios anteriores no tienen fila en `memoria_folios` hasta su siguiente cambio.
Responsable: PERSONA_1.

Para cada folio llama a `expediente.servicio.regenerar_resumen`, que ya enmascara (ADR-010), sube a S3 e
indexa. Con --solo-cerrados, solo los folios con decision (los unicos que cuentan como antecedentes).
Usa la misma configuracion que la app (.env de la raiz o variables de entorno) y carga las fichas igual
que el arranque. Al final imprime cuantos folios se han procesado y los que fallaron (solo su id, nunca el
contenido). Un folio falla si su memoria no queda actualizada; un fallo de S3 no cuenta (la memoria se
indexa igual) y queda en el log del servicio.

Uso local, desde backend/ y con la BD migrada (`alembic upgrade head`):
    PYTHONPATH=. python ../scripts/reindexar_resumenes.py [--solo-cerrados]

Uso en Docker:
    docker compose run --rm -v ./scripts:/scripts -e PYTHONPATH=/app backend \\
        python /scripts/reindexar_resumenes.py --solo-cerrados
"""
import argparse
import sys
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SesionLocal, get_engine
from app.core.modelos import Folio
from app.modulos.configuracion import servicio as configuracion
from app.modulos.expediente import servicio as expediente
from app.modulos.rag.modelos import MemoriaFolio


def reindexar(sesion: Session, solo_cerrados: bool = False) -> tuple[int, list[str]]:
    """Regenera e indexa cada folio. Devuelve (procesados, ids de los que fallaron)."""
    consulta = select(Folio.folio).order_by(Folio.folio)
    if solo_cerrados:
        consulta = consulta.where(Folio.decision.is_not(None))
    folios = list(sesion.scalars(consulta))
    fallidos = []
    for folio in folios:
        inicio = datetime.now(timezone.utc)
        expediente.regenerar_resumen(sesion, folio)  # nunca lanza
        sesion.expire_all()
        fila = sesion.get(MemoriaFolio, folio)
        actualizado = fila.actualizado_en if fila is not None else None
        if actualizado is not None and actualizado.tzinfo is None:  # SQLite no guarda la zona
            actualizado = actualizado.replace(tzinfo=timezone.utc)
        if actualizado is None or actualizado < inicio:
            fallidos.append(folio)
    return len(folios), fallidos


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenera e indexa el resumen.md de cada folio (H14).")
    parser.add_argument("--solo-cerrados", action="store_true", help="solo los folios con decision")
    args = parser.parse_args()

    configuracion.cargar(get_settings().config_dir)  # las fichas, como el arranque de la app
    with SesionLocal(bind=get_engine()) as sesion:
        procesados, fallidos = reindexar(sesion, args.solo_cerrados)
    print(f"Folios procesados: {procesados}")
    print(f"Fallidos: {len(fallidos)}" + (f" ({', '.join(fallidos)})" if fallidos else ""))
    return 1 if fallidos else 0


if __name__ == "__main__":
    sys.exit(main())
