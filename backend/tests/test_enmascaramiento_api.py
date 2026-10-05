"""ADR-010 A3 y A5, transversal: ninguna respuesta de la API (los 3 roles), ni el resumen.md ni el cuerpo
de los webhooks llevan el valor completo de un campo sensible. Por dentro (BD, comparaciones, reglas) sigue
el valor real. SQLite temporal + moto, motor falso, receptor de webhooks falso. Datos ficticios."""
import importlib.util
import json
from pathlib import Path

import boto3
import httpx
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import db, webhooks
from app.core.almacenamiento import AlmacenamientoS3
from app.core.config import get_settings
from app.core.db import Base
from app.core.modelos import AlertaBD, Correccion, Proceso
from app.core.seguridad import crear_token
from app.main import app
from app.modulos.expediente import servicio as expediente
from app.modulos.ingesta import motor_stub, procesamiento
from app.modulos.ingesta import servicio as ingesta
from app.modulos.ingesta.servicio import ingestar

SECRETO = "clave-ficticia-de-test"
BUCKET = "bucket-de-test"
REGION = "us-east-1"
URL = "https://receptor.ejemplo.test/hooks"

CURP_LEIDA = "XEXX010101HNEXXXA9"  # ficticia, como la leyo el OCR (mal el ultimo caracter)
CURP = "XEXX010101HNEXXXA4"        # ficticia, la que escribe el revisor
CLAVE_ELECTOR = "XEXXXX01010199H123"
PASAPORTE = "G12345678"
MRZ_1 = "P<MEXEJEMPLO<<ANA<<<<<<<<<<<<<<<<<<<<<<<<<<<"
MRZ_2 = "G12345678<0MEX0101014F3001017<<<<<<<<<<<<<<02"
SENSIBLES = (CURP_LEIDA, CURP, CLAVE_ELECTOR, PASAPORTE, MRZ_2)

_spec = importlib.util.spec_from_file_location(
    "crear_usuario", Path(__file__).resolve().parents[2] / "scripts" / "crear_usuario.py")
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)


def _analizar(contenido, **kwargs):
    """Motor falso: el stub con datos y evidencias sensibles segun el tipo declarado."""
    resultado, datos = motor_stub.procesar_documento(contenido, **kwargs)
    if kwargs["tipo_declarado"] == "pasaporte":
        extraidos = {"nombre_completo": "Ana Ejemplo Prueba", "numero_pasaporte": PASAPORTE,
                     "fecha_nacimiento": "2001-01-01", "fecha_vencimiento": "2030-01-01", "sexo": "F"}
        evidencias = {"numero_pasaporte": "pagina_1", "sexo": f"pagina_1:{MRZ_1}\n{MRZ_2}"}
    else:
        extraidos = {"nombre_completo": "Ana Ejemplo Prueba", "curp": CURP_LEIDA, "clave_elector": CLAVE_ELECTOR,
                     "fecha_nacimiento": "2001-01-01"}
        evidencias = {"curp": "pagina_1", "clave_elector": "pagina_1", "nombre_completo": f"pagina_1:{CURP_LEIDA}"}
    return resultado.model_copy(update={"datos_extraidos": extraidos, "evidencia_por_campo": evidencias,
                                        "nivel_confianza_por_campo": {c: 0.99 for c in extraidos}}), datos


@pytest.fixture
def entorno(monkeypatch, tmp_path):
    for nombre, valor in {
        "SECRET_KEY": SECRETO, "DATABASE_URL": f"sqlite:///{tmp_path / 'test.db'}",
        "AWS_ACCESS_KEY_ID": "clave-ficticia", "AWS_SECRET_ACCESS_KEY": SECRETO, "S3_BUCKET": BUCKET,
        "WEBHOOK_SECRET_HMAC": SECRETO, "APP_ENV": "dev",
    }.items():
        monkeypatch.setenv(nombre, valor)
    for nombre in ("CONFIG_DIR", "TAMANO_MAXIMO_ARCHIVO_MB"):
        monkeypatch.delenv(nombre, raising=False)
    get_settings.cache_clear()
    db.get_engine.cache_clear()
    monkeypatch.setattr(webhooks, "_esperar", lambda segundos: None)
    monkeypatch.setattr(webhooks, "_lanzar", lambda funcion: funcion())
    peticiones: list[httpx.Request] = []
    monkeypatch.setattr(webhooks, "_transporte",
                        httpx.MockTransport(lambda p: peticiones.append(p) or httpx.Response(200)))
    monkeypatch.setattr(procesamiento, "analizar", _analizar)
    Base.metadata.create_all(db.get_engine())
    with mock_aws():
        boto3.client("s3", region_name=REGION).create_bucket(Bucket=BUCKET)
        s3 = AlmacenamientoS3(bucket=BUCKET, region=REGION, access_key="clave-ficticia", secret_key=SECRETO,
                              segundos_url=60)
        monkeypatch.setattr(procesamiento, "get_almacenamiento", lambda: s3)
        with Session(db.get_engine()) as sesion:
            sesion.add(Proceso(nombre="onboarding", prefijo_folio="ONB", tipos_requeridos=["credencial_elector"],
                               tipos_opcionales=["pasaporte"], permitir_antecedentes=False,
                               caducidad_antecedentes_dias=30, webhook_url=URL))
            for rol in ("admin", "revisor", "integrador"):
                script.crear_usuario(sesion, f"{rol}_ficticio", rol, "contrasena-ficticia")
            sesion.commit()
            yield sesion, s3, peticiones
    db.get_engine().dispose()
    db.get_engine.cache_clear()
    get_settings.cache_clear()


def _cliente(rol: str) -> TestClient:
    cliente = TestClient(app)
    cliente.headers["Authorization"] = f"Bearer {crear_token(f'{rol}_ficticio', rol)[0]}"
    return cliente


def _sin_sensibles(texto: str, donde: str) -> None:
    for valor in SENSIBLES:
        assert valor not in texto, f"{donde} lleva un valor sensible en claro"


def test_ningun_valor_sensible_sale_en_claro(entorno):
    sesion, s3, peticiones = entorno
    folio = expediente.crear_folio(sesion, "onboarding", "CLI-000101", "x").folio
    credencial = ingestar(sesion, s3, folio, "c.pdf", b"%PDF-1.4 credencial", "credencial_elector", "x")
    pasaporte = ingestar(sesion, s3, folio, "p.pdf", b"%PDF-1.4 pasaporte", "pasaporte", "x")
    procesamiento.procesar(credencial.id)
    procesamiento.procesar(pasaporte.id)
    revisor = _cliente("revisor")
    respuestas = []

    # Acciones del revisor: todas sus respuestas, tambien la del PATCH que acaba de escribir el valor
    patch = revisor.patch(f"/api/v1/documentos/{credencial.id}/datos", json={"curp": CURP})
    assert patch.status_code == 200, patch.text
    assert patch.json()["datos_extraidos"]["curp"] == "****XXA4"
    respuestas.append(patch)
    respuestas.append(revisor.post(f"/api/v1/documentos/{credencial.id}/confirmar-clasificacion",
                                   json={"tipo_documental": "credencial_elector"}))
    alerta = sesion.scalars(select(AlertaBD).where(AlertaBD.documento_id == pasaporte.id)).first()
    if alerta is not None:
        respuestas.append(revisor.post(f"/api/v1/documentos/{pasaporte.id}/alertas/{alerta.id}/resolver",
                                       json={"aplica": False}))

    # Consultas, con los 3 roles
    for rol in ("admin", "revisor", "integrador"):
        cliente = _cliente(rol)
        for documento in (credencial, pasaporte):
            respuestas.append(cliente.get(f"/api/v1/documentos/{documento.id}"))
        respuestas.append(cliente.get(f"/api/v1/folios/{folio}"))
        respuestas.append(cliente.get(f"/api/v1/folios/{folio}/resumen.md"))
    for rol in ("admin", "revisor"):
        respuestas.append(_cliente(rol).get("/api/v1/folios"))
    respuestas.append(_cliente("admin").get("/api/v1/auditoria"))
    respuestas.append(revisor.post(f"/api/v1/folios/{folio}/decision", json={"decision": "rechazar"}))

    for respuesta in respuestas:
        assert respuesta.status_code == 200, (respuesta.request.url, respuesta.text)
        _sin_sensibles(respuesta.text, str(respuesta.request.url))

    folio_json = _cliente("integrador").get(f"/api/v1/folios/{folio}").json()
    [doc_c] = [d for d in folio_json["documentos"] if d["identificador_unico_documento"] == str(credencial.id)]
    assert doc_c["datos_extraidos"]["clave_elector"] == "****H123"
    assert doc_c["evidencia_por_campo"]["curp"] == "correccion_revisor"  # ubicacion: se conserva
    assert doc_c["evidencia_por_campo"]["nombre_completo"] == "pagina_1:****XXA9"  # el valor leido, tapado
    assert doc_c["correcciones"][0]["valor_anterior"] == "****XXA9"
    [doc_p] = [d for d in folio_json["documentos"] if d["identificador_unico_documento"] == str(pasaporte.id)]
    assert doc_p["evidencia_por_campo"]["sexo"] == f"pagina_1:{MRZ_1}\n****"

    # Webhooks: documento.completado de los dos y folio.estado_cambiado
    eventos = [json.loads(p.content)["evento"] for p in peticiones]
    assert eventos.count("documento.completado") == 2 and "folio.estado_cambiado" in eventos
    for peticion in peticiones:
        _sin_sensibles(peticion.content.decode("utf-8"), "el webhook")

    # Por dentro, el valor real: la correccion en BD y el resultado interno sin enmascarar
    sesion.expire_all()
    assert sesion.scalar(select(Correccion.valor_nuevo).where(Correccion.documento_id == credencial.id)) == CURP
    interno = ingesta.construir_resultado(sesion, credencial)
    assert interno.datos_extraidos["curp"] == CURP and interno.correcciones[0].valor_anterior == CURP_LEIDA


def test_resolver_alerta_de_expediente_enmascarado(entorno):
    sesion, s3, _ = entorno
    folio = expediente.crear_folio(sesion, "onboarding", None, "x").folio
    credencial = ingestar(sesion, s3, folio, "c.pdf", b"%PDF-1.4 credencial", "credencial_elector", "x")
    procesamiento.procesar(credencial.id)
    # Una alerta de expediente cualquiera (EXP-001 de un tipo que falta) para resolverla
    alerta = AlertaBD(folio=folio, documento_id=None, codigo="EXP-001", severidad="bloqueante", confianza=1.0,
                      campo="pasaporte", mensaje="Falta el documento requerido: Pasaporte")
    sesion.add(alerta)
    sesion.commit()
    respuesta = _cliente("revisor").post(f"/api/v1/folios/{folio}/alertas/{alerta.id}/resolver",
                                         json={"aplica": False})
    assert respuesta.status_code == 200
    _sin_sensibles(respuesta.text, "resolver alerta de expediente")
    assert respuesta.json()["documentos"][0]["datos_extraidos"]["curp"] == "****XXA9"


def test_tras_confirmar_otro_tipo_los_datos_de_la_ficha_anterior_siguen_tapados(entorno, monkeypatch):
    # Sin reproceso (lo lanzaria la BackgroundTask): el resultado vigente es aun el de la credencial
    sesion, s3, _ = entorno
    monkeypatch.setattr(ingesta, "procesar_documento", lambda *a, **k: None)
    folio = expediente.crear_folio(sesion, "onboarding", None, "x").folio
    credencial = ingestar(sesion, s3, folio, "c.pdf", b"%PDF-1.4 credencial", "credencial_elector", "x")
    procesamiento.procesar(credencial.id)
    respuesta = _cliente("revisor").post(f"/api/v1/documentos/{credencial.id}/confirmar-clasificacion",
                                         json={"tipo_documental": "pasaporte"})
    assert respuesta.status_code == 200
    assert respuesta.json()["datos_extraidos"]["curp"] == "****XXA9"
    _sin_sensibles(_cliente("integrador").get(f"/api/v1/documentos/{credencial.id}").text, "GET documento")
