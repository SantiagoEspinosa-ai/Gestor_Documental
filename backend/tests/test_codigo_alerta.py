"""alertas.codigo admite los REG-{id_regla} largos (migracion 0009): antes era String(30) y en PostgreSQL un codigo
como REG-nacimiento_antes_de_expedicion (34) hacia fallar el guardado y el documento acababa en error. SQLite no
aplica la longitud de VARCHAR: el fallo real solo se ve en PostgreSQL (TEST_POSTGRES_URL). Datos ficticios."""
import os
from pathlib import Path

import pytest
import yaml
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from app.core.db import Base
from app.core.modelos import AlertaBD, Folio, Proceso

CODIGO_LARGO = "REG-nacimiento_antes_de_expedicion"  # 34 caracteres
LONGITUD = AlertaBD.__table__.c.codigo.type.length
FICHAS = Path(__file__).resolve().parents[2] / "config" / "tipos"


def test_la_columna_admite_los_codigos_de_las_reglas_de_las_fichas():
    assert LONGITUD == 64 and len(CODIGO_LARGO) == 34
    codigos = [f"REG-{regla['id']}" for ficha in sorted(FICHAS.glob("*.yaml"))
               for regla in (yaml.safe_load(ficha.read_text(encoding="utf-8")).get("reglas") or [])]
    assert codigos and max(map(len, codigos)) > 30  # hoy hay reglas de 34 y 35: con String(30) fallaban
    assert all(len(c) <= LONGITUD for c in codigos), [c for c in codigos if len(c) > LONGITUD]


def _guarda_y_lee(url: str) -> str:
    engine = create_engine(url)
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as s:
            s.execute(delete(AlertaBD).where(AlertaBD.folio == "CAL-2026-000001"))
            s.execute(delete(Folio).where(Folio.folio == "CAL-2026-000001"))
            s.execute(delete(Proceso).where(Proceso.nombre == "codigo_alerta_test"))
            s.add(Proceso(nombre="codigo_alerta_test", prefijo_folio="CAL", tipos_requeridos=[], tipos_opcionales=[],
                          permitir_antecedentes=False, caducidad_antecedentes_dias=1))
            s.flush()
            s.add(Folio(folio="CAL-2026-000001", proceso="codigo_alerta_test", anio=2026, secuencia=1))
            s.flush()
            s.add(AlertaBD(folio="CAL-2026-000001", codigo=CODIGO_LARGO, severidad="critica",
                           mensaje="Regla ficticia", confianza=1.0))
            s.commit()
            codigo = s.scalar(select(AlertaBD.codigo).where(AlertaBD.folio == "CAL-2026-000001"))
            # Limpieza: la BD de TEST_POSTGRES_URL la comparten otros tests
            s.execute(delete(AlertaBD).where(AlertaBD.folio == "CAL-2026-000001"))
            s.execute(delete(Folio).where(Folio.folio == "CAL-2026-000001"))
            s.execute(delete(Proceso).where(Proceso.nombre == "codigo_alerta_test"))
            s.commit()
            return codigo
    finally:
        engine.dispose()


def test_guarda_una_alerta_con_un_codigo_de_34_en_sqlite(tmp_path):
    assert _guarda_y_lee(f"sqlite:///{tmp_path / 'codigo.db'}") == CODIGO_LARGO


@pytest.mark.skipif(not os.environ.get("TEST_POSTGRES_URL"), reason="requiere TEST_POSTGRES_URL")
def test_guarda_una_alerta_con_un_codigo_de_34_en_postgres():
    # Con String(30), PostgreSQL rechazaba el INSERT (StringDataRightTruncation). La BD de pruebas tiene que
    # estar al dia con el modelo (create_all no altera una tabla que ya existe)
    assert _guarda_y_lee(os.environ["TEST_POSTGRES_URL"]) == CODIGO_LARGO
