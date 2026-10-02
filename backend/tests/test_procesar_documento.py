"""Tests de orquestador.procesar_documento (etapa 2): preparar -> motor_ia -> MRZ -> reglas -> recomendacion.
Sin BD, S3 ni modelo: preparar y el proveedor son falsos. Datos ficticios."""
import ast
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.modulos.motor_ia.interfaces import DocumentoPreparado, Modalidad, Pagina
from app.modulos.motor_ia.proveedores.base import ErrorProveedor
from app.modulos.orquestador import procesamiento
from app.modulos.orquestador import servicio as orquestador
from app.schemas.resultado import EstadoAnalisis, Recomendacion, ReferenciaArchivoOriginal, ResultadoDocumento
from tests.test_servicio_motor import DATOS_PASAPORTE, MRZ, TEXTO_PASAPORTE, EnrutadorFalso, ProveedorFalso

REFERENCIA = ReferenciaArchivoOriginal(nombre_archivo="pasaporte.pdf", ruta="s3://bucket/pasaporte.pdf", hash="0" * 64)
AHORA = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
ID = "00000000-0000-4000-8000-000000000009"


@pytest.fixture
def documento(monkeypatch):
    """Sustituye preparar(): el texto del documento lo fija cada test."""
    estado = {"texto": TEXTO_PASAPORTE}

    def preparar(contenido, nombre, tipo_declarado=None, *, identificador=None, ocr=None):
        return DocumentoPreparado(identificador, Modalidad.pdf_digital, [Pagina(1, estado["texto"])], tipo_declarado)
    monkeypatch.setattr(procesamiento, "preparar", preparar)
    return estado


def procesar(proveedor, tipo_declarado="pasaporte", **kwargs):
    resultado, auditoria = orquestador.procesar_documento(
        b"%PDF-ficticio", identificador=ID, nombre_archivo="pasaporte.pdf", tipo_declarado=tipo_declarado,
        folio="ONB-2026-000001", referencia=REFERENCIA, enrutador=EnrutadorFalso(proveedor), ahora=AHORA, **kwargs)
    ResultadoDocumento.model_validate(resultado.model_dump())
    return resultado, auditoria


def codigos(r):
    return [(a.codigo, a.campo) for a in r.alertas_encontradas]


def test_caso_normal_reglas_recomendacion_y_auditoria(documento):
    r, auditoria = procesar(ProveedorFalso("ollama"))
    assert (r.estado_analisis, r.recomendacion) == (EstadoAnalisis.completado, Recomendacion.aprobar)
    assert (r.identificador_unico_documento, r.folio_solicitud) == (ID, "ONB-2026-000001")
    assert r.alertas_encontradas == []
    assert "vigencia_documento" in r.reglas_cumplidas_e_incumplidas.cumplidas
    json.dumps(auditoria)  # la plataforma lo guarda en detalle (JSON)
    assert auditoria["modelo"] == "ollama-modelo-real-extraccion"
    assert auditoria["version_prompt"] == "extraccion_pasaporte@v3"
    assert auditoria["version_prompt_clasificacion"] == "clasificacion@v2"
    assert auditoria["respaldo_usado"] is False
    assert auditoria["confianzas_modelo"]["clasificacion"] == 0.93       # la del modelo, solo aqui (ADR-007)
    assert len(auditoria["llamadas"]) == 2 and auditoria["modalidad"] == "pdf_digital"
    assert {"tiempos", "tokens", "proveedor", "paginas"} <= set(auditoria)


def test_reglas_y_val_se_anaden_sin_repetir(documento):
    datos = {**DATOS_PASAPORTE, "fecha_vencimiento": "2026-01-01", "nacionalidad": None}
    documento["texto"] = TEXTO_PASAPORTE.replace("09/05/2034", "01/01/2026")
    r, _ = procesar(ProveedorFalso("ollama", datos=datos))
    assert ("REG-vigencia_documento", "fecha_vencimiento") in codigos(r)
    assert ("VAL-004", "nacionalidad") in codigos(r)
    assert len(codigos(r)) == len(set(codigos(r)))
    assert r.recomendacion is Recomendacion.revision_manual                # bloqueante, nunca rechazar (D1)


def test_hoy_sale_del_reloj_de_la_plataforma(documento, monkeypatch):
    llamadas = []
    monkeypatch.setattr(procesamiento.reloj, "hoy", lambda ahora=None: llamadas.append(ahora) or AHORA.date())
    procesar(ProveedorFalso("ollama"))
    assert llamadas == [AHORA]


# --- MRZ: el orquestador completa el sexo (VAL-003) ---

def test_sexo_desde_la_mrz_val_003(documento):
    documento["texto"] = TEXTO_PASAPORTE.replace("SEXO\nF\n", "") + "\n" + MRZ
    r, _ = procesar(ProveedorFalso("ollama", datos={**DATOS_PASAPORTE, "sexo": None}))
    assert (r.datos_extraidos["sexo"], r.nivel_confianza_por_campo["sexo"], r.evidencia_por_campo["sexo"]) == (
        "F", 1.0, "pagina_1")
    assert ("VAL-003", "sexo") in codigos(r) and ("VAL-004", "sexo") not in codigos(r)


def test_sexo_desde_la_mrz_con_digitos_fallidos(documento):
    documento["texto"] = TEXTO_PASAPORTE.replace("SEXO\nF\n", "") + "\n" + MRZ[:-1] + "9"
    r, _ = procesar(ProveedorFalso("ollama", datos={**DATOS_PASAPORTE, "sexo": None}))
    assert r.datos_extraidos["sexo"] == "F" and r.nivel_confianza_por_campo["sexo"] <= 0.5
    assert ("VAL-002", "sexo") in codigos(r)


def test_sexo_leido_no_se_sustituye_por_la_mrz(documento):
    documento["texto"] = TEXTO_PASAPORTE + "\n" + MRZ
    r, _ = procesar(ProveedorFalso("ollama", datos={**DATOS_PASAPORTE, "sexo": "M"}))
    assert r.datos_extraidos["sexo"] == "M" and ("VAL-003", "sexo") not in codigos(r)


# --- Tipo confirmado, desconocido y errores ---

def test_tipo_confirmado_sin_clasificar_y_recomendacion_d2(documento):
    r, auditoria = procesar(ProveedorFalso("ollama", tipo="credencial_elector"), tipo_declarado="credencial_elector",
                            tipo_confirmado="pasaporte")
    assert (r.tipo_documental_detectado, r.confianza_clasificacion) == (None, None)   # ADR-009, como el stub
    assert r.recomendacion is Recomendacion.aprobar                                   # D2: None cuenta como 1,0
    assert auditoria["version_prompt_clasificacion"] is None


def test_desconocido_sin_declarado_no_evalua_reglas(documento):
    r, _ = procesar(ProveedorFalso("ollama", tipo="desconocido"), tipo_declarado=None)
    assert r.datos_extraidos == {} and r.reglas_cumplidas_e_incumplidas.cumplidas == []
    assert r.recomendacion is Recomendacion.revision_manual


def test_proveedor_caido_error_sys_001_sin_reglas(documento):
    r, auditoria = procesar(ProveedorFalso("ollama", falla_clasificar=ErrorProveedor("caido")))
    assert r.estado_analisis is EstadoAnalisis.error and codigos(r) == [("SYS-001", None)]
    assert r.recomendacion is Recomendacion.revision_manual
    assert r.reglas_cumplidas_e_incumplidas.cumplidas == [] and auditoria["modelo"] is None
    json.dumps(auditoria)


def test_formato_no_soportado_lanza():
    with pytest.raises(orquestador.FormatoNoSoportado):
        orquestador.procesar_documento(b"no es un documento", identificador=ID, nombre_archivo="x.txt",
                                       tipo_declarado="pasaporte", folio="ONB-2026-000001", referencia=REFERENCIA,
                                       enrutador=EnrutadorFalso(ProveedorFalso("ollama")))


def test_misma_firma_que_el_stub_de_la_ingesta():
    import inspect

    from app.modulos.ingesta import motor_stub
    stub = inspect.signature(motor_stub.procesar_documento).parameters
    real = inspect.signature(orquestador.procesar_documento).parameters
    assert list(stub) == list(real)[:len(stub)]
    assert all(real[n].kind == p.kind and real[n].default == p.default for n, p in stub.items())


# --- Dependencias en un solo sentido (spec, seccion 11) ---

def test_motor_ia_no_importa_orquestador_salvo_el_cli():
    carpeta = Path(__file__).resolve().parents[1] / "app" / "modulos" / "motor_ia"
    for fichero in carpeta.rglob("*.py"):
        if fichero.name == "cli.py":
            continue  # punto de entrada: ningun modulo lo importa
        arbol = ast.parse(fichero.read_text(encoding="utf-8"))
        importados = [n.module or "" for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom)]
        importados += [a.name for n in ast.walk(arbol) if isinstance(n, ast.Import) for a in n.names]
        assert not any("orquestador" in m for m in importados), fichero.name
