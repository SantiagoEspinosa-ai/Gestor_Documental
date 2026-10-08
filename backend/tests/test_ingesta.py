"""Tests de modulos/ingesta (servicio, procesamiento y stub del motor). SQLite temporal y moto; datos ficticios."""
import inspect
import re
import threading
import time
import uuid

import boto3
import pytest
from moto import mock_aws
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import db
from app.core.almacenamiento import AlmacenamientoS3, ErrorAlmacenamiento
from app.core.config import get_settings
from app.core.db import Base
from app.core.errores import ErrorApi
from app.core.modelos import AlertaBD, Auditoria, Documento, Proceso, Resultado
from app.modulos.expediente import servicio as expediente
from app.modulos.ingesta import motor_stub, procesamiento
from app.modulos.ingesta.procesamiento import procesar
from app.modulos.ingesta.servicio import ingestar, obtener_resultado
from app.schemas.resultado import Alerta, EstadoAnalisis, ReferenciaArchivoOriginal, ResultadoDocumento

SECRETO = "clave-ficticia-de-test-de-32-caracteres"
BUCKET = "bucket-de-test"
REGION = "us-east-1"
PDF = b"%PDF-1.4 documento ficticio"
JPG = b"\xff\xd8\xff\xe0 imagen ficticia"
PNG = b"\x89PNG\r\n\x1a\n imagen ficticia"


@pytest.fixture
def sesion(monkeypatch, tmp_path):
    for nombre, valor in {
        "SECRET_KEY": SECRETO,
        "DATABASE_URL": f"sqlite:///{tmp_path / 'test.db'}",
        "AWS_ACCESS_KEY_ID": "clave-ficticia",
        "AWS_SECRET_ACCESS_KEY": SECRETO,
        "S3_BUCKET": BUCKET,
        "WEBHOOK_SECRET_HMAC": SECRETO,
    }.items():
        monkeypatch.setenv(nombre, valor)
    for nombre in ("CONFIG_DIR", "TAMANO_MAXIMO_ARCHIVO_MB"):
        monkeypatch.delenv(nombre, raising=False)
    get_settings.cache_clear()
    db.get_engine.cache_clear()
    Base.metadata.create_all(db.get_engine())
    with Session(db.get_engine()) as s:
        s.add(Proceso(nombre="onboarding", prefijo_folio="ONB", tipos_requeridos=["credencial_elector"],
                      tipos_opcionales=[], permitir_antecedentes=True, caducidad_antecedentes_dias=365))
        s.commit()
        yield s
    db.get_engine().dispose()
    get_settings.cache_clear()
    db.get_engine.cache_clear()


@pytest.fixture
def s3():
    with mock_aws():
        boto3.client("s3", region_name=REGION).create_bucket(Bucket=BUCKET)
        yield AlmacenamientoS3(bucket=BUCKET, region=REGION, access_key="clave-ficticia",
                               secret_key=SECRETO, segundos_url=60)


@pytest.fixture
def folio(sesion):
    return expediente.crear_folio(sesion, "onboarding", None, "integrador_ficticio")


def _subir(sesion, s3, folio, nombre="credencial_ficticia.pdf", datos=PDF, tipo="credencial_elector"):
    return ingestar(sesion, s3, folio.folio, nombre, datos, tipo, "integrador_ficticio")


def _codigo(e: pytest.ExceptionInfo) -> tuple[int, str]:
    return e.value.http, e.value.codigo


# --- ingestar ---

def test_subida_valida(sesion, s3, folio):
    doc = _subir(sesion, s3, folio)
    fila = sesion.get(Documento, doc.id)
    assert fila.estado_analisis == "pendiente"
    assert fila.nombre_archivo == "credencial_ficticia.pdf"
    assert re.fullmatch(rf"onboarding/{folio.anio}/{folio.secuencia:06d}/{doc.id}\.pdf", fila.ruta_s3)
    assert s3.descargar(fila.ruta_s3) == PDF

    registro = sesion.scalar(select(Auditoria).where(Auditoria.accion == "documento_subido"))
    assert registro.documento_id == doc.id
    assert registro.detalle == {"hash_sha256": fila.hash_sha256, "tamano_bytes": len(PDF), "duplicado": False}
    assert "credencial_ficticia" not in str(registro.detalle)


def test_folio_inexistente(sesion, s3):
    with pytest.raises(ErrorApi) as e:
        ingestar(sesion, s3, "ONB-2026-999999", "a.pdf", PDF, None, "x")
    assert _codigo(e) == (404, "FOLIO_NO_ENCONTRADO")


def test_folio_cerrado(sesion, s3, folio):
    folio.estado_general = "aprobado"
    sesion.commit()
    with pytest.raises(ErrorApi) as e:
        _subir(sesion, s3, folio)
    assert _codigo(e) == (409, "FOLIO_CERRADO")


def test_archivo_demasiado_grande(sesion, s3, folio):
    with pytest.raises(ErrorApi) as e:
        _subir(sesion, s3, folio, datos=b"x" * (20 * 1024 * 1024 + 1))
    assert _codigo(e) == (413, "ARCHIVO_DEMASIADO_GRANDE")


def test_archivo_vacio(sesion, s3, folio):
    with pytest.raises(ErrorApi) as e:
        _subir(sesion, s3, folio, datos=b"")
    assert _codigo(e) == (422, "PETICION_INVALIDA")


@pytest.mark.parametrize("nombre", ["documento.exe", "documento.docx", "sin_extension"])
def test_formato_no_permitido(sesion, s3, folio, nombre):
    with pytest.raises(ErrorApi) as e:
        _subir(sesion, s3, folio, nombre=nombre)
    assert _codigo(e) == (415, "FORMATO_NO_PERMITIDO")


def test_tipo_declarado_desconocido(sesion, s3, folio):
    with pytest.raises(ErrorApi, match="tipo_declarado no existe") as e:
        _subir(sesion, s3, folio, tipo="tipo_inventado")
    assert _codigo(e) == (422, "PETICION_INVALIDA")


@pytest.mark.parametrize("nombre,datos,tipo_contenido", [
    ("a.pdf", PDF, "application/pdf"),
    ("b.JPG", JPG, "image/jpeg"),
    ("c.png", PNG, "image/png"),
])
def test_sin_tipo_declarado_acepta_formatos_de_todos_los_tipos(sesion, s3, folio, nombre, datos,
                                                               tipo_contenido):
    doc = _subir(sesion, s3, folio, nombre=nombre, datos=datos, tipo=None)
    assert doc.ruta_s3.endswith("." + nombre.rsplit(".", 1)[1].lower())
    cabecera = boto3.client("s3", region_name=REGION).head_object(Bucket=BUCKET, Key=doc.ruta_s3)
    assert cabecera["ContentType"] == tipo_contenido


@pytest.mark.parametrize("nombre,datos", [("a.pdf", PNG), ("b.png", PDF), ("c.jpg", b"texto plano")])
def test_contenido_que_no_corresponde_a_la_extension(sesion, s3, folio, nombre, datos):
    with pytest.raises(ErrorApi) as e:
        _subir(sesion, s3, folio, nombre=nombre, datos=datos, tipo=None)
    assert _codigo(e) == (415, "FORMATO_NO_PERMITIDO")


def test_nombre_sin_ruta_y_recortado(sesion, s3, folio):
    doc = _subir(sesion, s3, folio, nombre="C:\\carpeta\\sub/" + "n" * 300 + ".pdf")
    assert len(doc.nombre_archivo) == 255
    assert doc.nombre_archivo.endswith(".pdf")
    assert "/" not in doc.nombre_archivo and "\\" not in doc.nombre_archivo


@pytest.mark.parametrize("nombre", ["", "   ", "/"])
def test_nombre_vacio(sesion, s3, folio, nombre):
    with pytest.raises(ErrorApi) as e:
        _subir(sesion, s3, folio, nombre=nombre)
    assert _codigo(e) == (422, "PETICION_INVALIDA")


def test_duplicado_no_bloquea_y_genera_dup_001(sesion, s3, folio):
    primero = _subir(sesion, s3, folio)
    segundo = _subir(sesion, s3, folio)
    assert primero.id != segundo.id
    assert primero.ruta_s3 != segundo.ruta_s3
    assert s3.descargar(primero.ruta_s3) == s3.descargar(segundo.ruta_s3) == PDF

    # Solo las de documento: el folio nace ademas con sus EXP-001 de expediente
    alertas = sesion.scalars(select(AlertaBD).where(AlertaBD.documento_id.is_not(None))).all()
    assert len(alertas) == 1
    assert sesion.scalar(select(func.count()).select_from(AlertaBD).where(AlertaBD.codigo == "DUP-001")) == 1
    assert (alertas[0].codigo, alertas[0].severidad, alertas[0].documento_id) == ("DUP-001", "critica", segundo.id)
    assert str(primero.id) in alertas[0].mensaje
    detalles = [a.detalle["duplicado"] for a in sesion.scalars(select(Auditoria).order_by(Auditoria.id))
                if a.accion == "documento_subido"]
    assert detalles == [False, True]


def test_fallo_al_subir_no_deja_rastro(sesion, folio):
    class AlmacenamientoRoto:
        def subir(self, datos, clave, tipo_contenido):
            raise ErrorAlmacenamiento("No se pudo completar 'subir' en el almacenamiento")

    with pytest.raises(ErrorApi) as e:
        _subir(sesion, AlmacenamientoRoto(), folio)
    assert _codigo(e) == (500, "ERROR_INTERNO")
    assert sesion.scalar(select(func.count()).select_from(Documento)) == 0
    assert sesion.scalar(select(func.count()).select_from(Auditoria)
                         .where(Auditoria.accion == "documento_subido")) == 0


# --- procesamiento con la interfaz acordada del motor ---

@pytest.fixture
def s3_en_procesamiento(s3, monkeypatch):
    """procesar() descarga con get_almacenamiento(): en los tests, el S3 de moto."""
    monkeypatch.setattr(procesamiento, "get_almacenamiento", lambda: s3)
    return s3


def _alerta(codigo: str, severidad: str = "preventiva") -> Alerta:
    return Alerta(codigo=codigo, mensaje=f"Alerta ficticia {codigo}", severidad=severidad, confianza=0.9,
                  campo="nombre_completo")


def _motor_falso(monkeypatch, alertas=(), estado=EstadoAnalisis.completado, identificador=None, datos=None):
    """Sustituye procesamiento.analizar por un motor que devuelve lo que se le diga."""
    def analizar(contenido, **kwargs):
        resultado, auditoria_stub = motor_stub.procesar_documento(contenido, **kwargs)
        resultado = resultado.model_copy(update={
            "alertas_encontradas": list(alertas), "estado_analisis": estado,
            "identificador_unico_documento": identificador or kwargs["identificador"]})
        return resultado, datos if datos is not None else auditoria_stub
    monkeypatch.setattr(procesamiento, "analizar", analizar)


def test_firma_del_motor_stub_es_la_acordada():
    firma = inspect.signature(motor_stub.procesar_documento)
    params = list(firma.parameters.values())
    assert [p.name for p in params] == ["contenido", "identificador", "nombre_archivo", "tipo_declarado",
                                        "folio", "referencia", "tipo_confirmado", "al_avanzar"]  # ADR-014
    assert params[0].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in params[1:])
    assert params[-2].default is None and params[-1].default is None
    assert all(p.default is inspect.Parameter.empty for p in params[:-2])


def test_motor_stub_devuelve_resultado_sin_alertas():
    ref = ReferenciaArchivoOriginal(nombre_archivo="a.pdf", ruta="r", hash="0" * 64)
    resultado, datos = motor_stub.procesar_documento(PDF, identificador="id-1", nombre_archivo="a.pdf",
                                                     tipo_declarado="pasaporte", folio="ONB-2026-000001",
                                                     referencia=ref)
    assert resultado.alertas_encontradas == []
    assert (resultado.identificador_unico_documento, resultado.folio_solicitud) == ("id-1", "ONB-2026-000001")
    assert datos == {"proveedor": "stub", "modelo": "stub", "version_prompt": "stub@v0", "respaldo_usado": False}


def test_procesar_con_su_propia_sesion_y_el_stub(sesion, s3_en_procesamiento, folio):
    doc = _subir(sesion, s3_en_procesamiento, folio)
    procesar(doc.id)  # sin pasarle sesion
    sesion.expire_all()
    assert sesion.get(Documento, doc.id).estado_analisis == "completado"
    fila = sesion.scalar(select(Resultado).where(Resultado.documento_id == doc.id))
    assert fila.version == 1
    resultado = ResultadoDocumento.model_validate(fila.json)
    assert resultado.tipo_documental_detectado == "credencial_elector"
    assert resultado.referencia_archivo_original.hash == doc.hash_sha256


def test_alertas_del_motor_con_version_e_id(sesion, s3_en_procesamiento, folio, monkeypatch):
    doc = _subir(sesion, s3_en_procesamiento, folio)
    _motor_falso(monkeypatch, alertas=[_alerta("VAL-001", "critica"), _alerta("REG-vigencia", "bloqueante")])
    procesar(doc.id)

    filas = sesion.scalars(select(AlertaBD).where(AlertaBD.documento_id == doc.id)
                           .order_by(AlertaBD.codigo)).all()
    assert [(a.codigo, a.version_resultado) for a in filas] == [("REG-vigencia", 1), ("VAL-001", 1)]
    visibles = obtener_resultado(sesion, str(doc.id)).alertas_encontradas
    assert {a.codigo for a in visibles} == {"VAL-001", "REG-vigencia"}
    assert all(uuid.UUID(a.id) for a in visibles)


def test_al_reprocesar_solo_se_ven_las_alertas_de_la_version_nueva(sesion, s3_en_procesamiento, folio,
                                                                    monkeypatch):
    _subir(sesion, s3_en_procesamiento, folio)
    doc = _subir(sesion, s3_en_procesamiento, folio)  # duplicado: DUP-001 de plataforma
    _motor_falso(monkeypatch, alertas=[_alerta("VAL-001")])
    procesar(doc.id)
    _motor_falso(monkeypatch, alertas=[_alerta("CLS-001"), _alerta("VAL-002")])
    procesar(doc.id)

    visibles = {a.codigo for a in obtener_resultado(sesion, str(doc.id)).alertas_encontradas}
    assert visibles == {"DUP-001", "CLS-001", "VAL-002"}
    # la de la version 1 sigue en BD, pero ya no se muestra
    assert sesion.scalar(select(AlertaBD.version_resultado).where(AlertaBD.codigo == "VAL-001")) == 1


def test_motor_con_error_y_sys_001(sesion, s3_en_procesamiento, folio, monkeypatch):
    doc = _subir(sesion, s3_en_procesamiento, folio)
    _motor_falso(monkeypatch, alertas=[_alerta("SYS-001", "critica")], estado=EstadoAnalisis.error)
    procesar(doc.id)
    sesion.expire_all()
    assert sesion.get(Documento, doc.id).estado_analisis == "error"
    assert sesion.scalar(select(func.count()).select_from(Resultado)) == 1
    resultado = obtener_resultado(sesion, str(doc.id))
    assert resultado.estado_analisis == EstadoAnalisis.error
    assert [a.codigo for a in resultado.alertas_encontradas] == ["SYS-001"]


def _falla_y_no_guarda(sesion, doc):
    procesar(doc.id)  # no relanza
    sesion.expire_all()
    assert sesion.get(Documento, doc.id).estado_analisis == "error"
    assert sesion.scalar(select(func.count()).select_from(Resultado)) == 0


def test_motor_que_lanza(sesion, s3_en_procesamiento, folio, monkeypatch):
    doc = _subir(sesion, s3_en_procesamiento, folio)

    def rompe(contenido, **kwargs):
        raise RuntimeError("fallo forzado")

    monkeypatch.setattr(procesamiento, "analizar", rompe)
    _falla_y_no_guarda(sesion, doc)


def test_identificador_que_no_coincide(sesion, s3_en_procesamiento, folio, monkeypatch):
    doc = _subir(sesion, s3_en_procesamiento, folio)
    _motor_falso(monkeypatch, identificador=str(uuid.uuid4()))
    _falla_y_no_guarda(sesion, doc)


def test_descargar_falla(sesion, s3, folio, monkeypatch):
    doc = _subir(sesion, s3, folio)

    class SinOriginal:
        def descargar(self, clave):
            raise ErrorAlmacenamiento("No se pudo completar 'descargar' en el almacenamiento")

    monkeypatch.setattr(procesamiento, "get_almacenamiento", lambda: SinOriginal())
    _falla_y_no_guarda(sesion, doc)


def test_auditoria_del_procesamiento(sesion, s3_en_procesamiento, folio, monkeypatch):
    doc = _subir(sesion, s3_en_procesamiento, folio)
    datos = {"proveedor": "ollama", "modelo": "modelo-ficticio", "version_prompt": "extraccion@v1",
             "respaldo_usado": True, "confianzas_modelo": {"nombre_completo": 0.7},
             "tiempos": {"total_ms": 1200}, "tokens": {"entrada": 10, "salida": 20},
             "no_serializable": object()}
    _motor_falso(monkeypatch, datos=datos)
    procesar(doc.id)

    registro = sesion.scalar(select(Auditoria).where(Auditoria.accion == "documento_procesado"))
    assert (registro.modelo, registro.version_prompt) == ("modelo-ficticio", "extraccion@v1")
    # sin modelo/version_prompt (van a sus columnas), sin lo no serializable y sin valores de campos
    assert registro.detalle == {"proveedor": "ollama", "respaldo_usado": True,
                                "confianzas_modelo": {"nombre_completo": 0.7},
                                "tiempos": {"total_ms": 1200}, "tokens": {"entrada": 10, "salida": 20}}


@pytest.mark.parametrize("maximo", [1, 2])
def test_procesamientos_simultaneos_limitados(sesion, s3_en_procesamiento, folio, monkeypatch, maximo):
    monkeypatch.setenv("MAX_PROCESAMIENTOS_SIMULTANEOS", str(maximo))
    get_settings.cache_clear()
    docs = [_subir(sesion, s3_en_procesamiento, folio, nombre=f"doc{i}.pdf", datos=PDF + str(i).encode())
            for i in range(2)]
    estado = {"dentro": 0, "maximo": 0}
    candado = threading.Lock()

    def motor_lento(contenido, **kwargs):
        with candado:
            estado["dentro"] += 1
            estado["maximo"] = max(estado["maximo"], estado["dentro"])
        time.sleep(0.3)
        with candado:
            estado["dentro"] -= 1
        return motor_stub.procesar_documento(contenido, **kwargs)

    monkeypatch.setattr(procesamiento, "analizar", motor_lento)
    salida = threading.Barrier(2)

    def lanzar(doc_id):
        salida.wait()
        procesar(doc_id)

    hilos = [threading.Thread(target=lanzar, args=(d.id,)) for d in docs]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert estado["maximo"] == maximo
    sesion.expire_all()
    assert all(sesion.get(Documento, d.id).estado_analisis == "completado" for d in docs)
