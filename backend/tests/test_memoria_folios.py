"""Tests de la memoria de folios (rag, H14, ADR-010 C4). SQLite temporal; resumen.md de ejemplo ya enmascarado,
con el formato de expediente/plantillas/resumen.md.j2. Datos ficticios."""
import logging
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.core import db
from app.core.config import get_settings
from app.core.db import Base
from app.core.modelos import Folio, Proceso
from app.modulos.rag import memoria
from app.modulos.rag import servicio as rag
from app.modulos.rag.modelos import MemoriaFolio

SECRETO = "valor-de-test-no-real-de-32-caracteres"  # noqa: S105
FOLIO = "ONB-2026-000001"
AHORA = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)

RESUMEN = """# Expediente ONB-2026-000001

- Referencia: E2E-REF-0001
- Proceso: onboarding
- Fecha de solicitud: 2026-10-01
- Estado: cerrado
- Recomendacion global: revision_manual

## Decision

- Decision: rechazar
- Comentario: La persona ANA EJEMPLO PRUEBA aporto un pasaporte vencido
- Usuario: revisor_demo
- Fecha: 2026-10-02

## Documentos

### Documento 1: Pasaporte

- Estado del analisis: completado

Datos:
- nombre_completo: ANA EJEMPLO PRUEBA

- numero_pasaporte: ****0001

- fecha_vencimiento: 2026-01-01

Bloqueantes:
- REG-vigencia_documento (fecha_vencimiento): El pasaporte esta vencido (confirmada)

### Documento 2: Credencial de elector

- Estado del analisis: completado

Datos:
- curp: ****XX01

- domicilio: CALLE FICTICIA 123, COLONIA DEMO, CIUDAD EJEMPLO

Sin alertas.

## Alertas del expediente

Sin alertas del expediente.

## Comparaciones

- nombre_completo: si
  - Documento 1 (Pasaporte): ANA EJEMPLO PRUEBA
  - Documento 2 (Credencial de elector): ANA EJEMPLO PRUEBA

Generado el 2026-10-02 10:00
"""
# Valores de los datos y de las comparaciones (y el comentario libre): nunca en el fragmento
VALORES = ["ANA EJEMPLO PRUEBA", "****0001", "****XX01", "CALLE FICTICIA", "2026-01-01", "aporto un pasaporte"]


@pytest.fixture
def sesion(monkeypatch, tmp_path):
    for nombre, valor in {"SECRET_KEY": SECRETO, "DATABASE_URL": f"sqlite:///{tmp_path / 'test.db'}",
                          "AWS_ACCESS_KEY_ID": SECRETO, "AWS_SECRET_ACCESS_KEY": SECRETO,
                          "S3_BUCKET": "bucket-de-test", "WEBHOOK_SECRET_HMAC": SECRETO}.items():
        monkeypatch.setenv(nombre, valor)
    get_settings.cache_clear()
    db.get_engine.cache_clear()
    Base.metadata.create_all(db.get_engine())
    with Session(db.get_engine()) as s:
        s.add(Proceso(nombre="onboarding", prefijo_folio="ONB", tipos_requeridos=[], tipos_opcionales=[],
                      permitir_antecedentes=True, caducidad_antecedentes_dias=365, webhook_url=None))
        s.flush()  # el proceso antes que el folio (sin relationship, el orden de los INSERT no esta garantizado)
        s.add(Folio(folio=FOLIO, proceso="onboarding", anio=2026, secuencia=1))
        s.commit()
        yield s
    get_settings.cache_clear()
    db.get_engine.cache_clear()


# --- Fragmento (puro) ---

def test_fragmento_con_cabecera_decision_estado_y_alertas():
    f = memoria.extraer_fragmento(RESUMEN)
    assert f.splitlines()[0] == "# Expediente ONB-2026-000001"
    for esperado in ("- Referencia: E2E-REF-0001", "- Recomendacion global: revision_manual", "## Decision",
                     "- Decision: rechazar", "- Fecha: 2026-10-02", "### Documento 1: Pasaporte",
                     "- Estado del analisis: completado", "Bloqueantes:",
                     "- REG-vigencia_documento (fecha_vencimiento): El pasaporte esta vencido (confirmada)",
                     "### Documento 2: Credencial de elector", "## Alertas del expediente"):
        assert esperado in f.splitlines(), esperado


def test_fragmento_sin_valores_comparaciones_ni_comentario():
    f = memoria.extraer_fragmento(RESUMEN)
    for valor in VALORES:
        assert valor not in f, valor
    assert "Comparaciones" not in f and "Generado el" not in f and "Datos:" not in f


def test_fragmento_sin_decision_folio_abierto():
    abierto = RESUMEN.replace("- Estado: cerrado", "- Estado: en_revision")
    abierto = abierto[:abierto.index("## Decision")] + abierto[abierto.index("## Documentos"):]
    f = memoria.extraer_fragmento(abierto)
    assert "## Decision" not in f and "- Estado: en_revision" in f


def test_fragmento_se_corta_en_un_final_de_linea():
    largo = RESUMEN.replace("Bloqueantes:\n", "Bloqueantes:\n" + "".join(
        f"- REG-regla_{i} (campo): Mensaje de prueba numero {i} (sin revisar)\n" for i in range(60)))
    f = memoria.extraer_fragmento(largo)
    assert len(f) <= memoria.LIMITE_FRAGMENTO and f.endswith("\n...")
    assert all(linea in largo.splitlines() for linea in f.splitlines()[:-1])  # lineas enteras


def test_resumen_vacio():
    assert memoria.extraer_fragmento("") == ""


# --- indexar_resumen y fragmento_resumen (con BD) ---

def test_folio_sin_indexar_da_none(sesion):
    assert rag.fragmento_resumen(FOLIO) is None


def test_indexar_y_leer(sesion):
    rag.indexar_resumen(FOLIO, RESUMEN)
    assert rag.fragmento_resumen(FOLIO) == memoria.extraer_fragmento(RESUMEN)
    fila = sesion.get(MemoriaFolio, FOLIO)
    assert fila.resumen_md == RESUMEN


def test_reindexar_sustituye(sesion):
    rag.indexar_resumen(FOLIO, RESUMEN, ahora=AHORA)
    nuevo = RESUMEN.replace("- Decision: rechazar", "- Decision: aprobar")
    rag.indexar_resumen(FOLIO, nuevo)
    assert "- Decision: aprobar" in rag.fragmento_resumen(FOLIO)
    sesion.expire_all()
    assert sesion.query(MemoriaFolio).count() == 1


def test_indexar_nunca_lanza_y_no_registra_el_contenido(sesion, caplog):
    with caplog.at_level(logging.WARNING):
        rag.indexar_resumen("ONB-2026-999999", RESUMEN)   # folio que no existe: falla la clave ajena
    assert rag.fragmento_resumen("ONB-2026-999999") is None
    mensajes = "\n".join(r.getMessage() for r in caplog.records)
    assert "ONB-2026-999999" in mensajes
    for valor in VALORES + ["Expediente", "rechazar"]:
        assert valor not in mensajes, valor


def test_usa_la_sesion_que_le_pasan(sesion):
    rag.indexar_resumen(FOLIO, RESUMEN, sesion=sesion)
    assert rag.fragmento_resumen(FOLIO, sesion=sesion).startswith("# Expediente")


def test_api_publica():
    assert set(rag.__all__) == {"LIMITE_FRAGMENTO", "fragmento_resumen", "indexar_resumen"}
