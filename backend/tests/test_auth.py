"""Tests de /api/v1/auth, de los manejadores globales de errores y de core/auditoria.py.

SQLite temporal y datos ficticios. TestClient(app) sin `with`: no se ejecuta el lifespan.
"""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core import auditoria, db
from app.core.config import get_settings
from app.core.db import Base
from app.core.errores import registrar_manejadores
from app.core.modelos import Auditoria
from app.main import app
from app.modulos.api import auth

SECRETO = "clave-ficticia-de-test-de-32-caracteres"
CONTRASENA = "contrasena-ficticia"
LOGIN = "/api/v1/auth/login"

_spec = importlib.util.spec_from_file_location(
    "crear_usuario", Path(__file__).resolve().parents[2] / "scripts" / "crear_usuario.py")
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)


@pytest.fixture
def sesion(monkeypatch, tmp_path):
    for nombre, valor in {
        "SECRET_KEY": SECRETO,
        "DATABASE_URL": f"sqlite:///{tmp_path / 'test.db'}",
        "AWS_ACCESS_KEY_ID": SECRETO,
        "AWS_SECRET_ACCESS_KEY": SECRETO,
        "S3_BUCKET": "bucket-de-test",
        "WEBHOOK_SECRET_HMAC": SECRETO,
    }.items():
        monkeypatch.setenv(nombre, valor)
    get_settings.cache_clear()
    db.get_engine.cache_clear()
    Base.metadata.create_all(db.get_engine())
    with Session(db.get_engine()) as s:
        script.crear_usuario(s, "revisor_ficticio", "revisor", CONTRASENA)
        yield s
    db.get_engine().dispose()
    get_settings.cache_clear()
    db.get_engine.cache_clear()


@pytest.fixture
def cliente(sesion):
    return TestClient(app)


def _logins(sesion) -> list[tuple[str, str]]:
    sesion.expire_all()
    filas = sesion.scalars(select(Auditoria).where(Auditoria.accion == "login").order_by(Auditoria.id))
    return [(f.usuario, f.detalle["resultado"]) for f in filas]


def test_login_correcto_y_token_valido_en_yo(cliente):
    r = cliente.post(LOGIN, json={"usuario": "revisor_ficticio", "contrasena": CONTRASENA})
    assert r.status_code == 200
    cuerpo = r.json()
    assert set(cuerpo) == {"access_token", "rol", "expires_in"}
    assert (cuerpo["rol"], cuerpo["expires_in"]) == ("revisor", 480 * 60)

    yo = cliente.get("/api/v1/auth/yo", headers={"Authorization": f"Bearer {cuerpo['access_token']}"})
    assert yo.status_code == 200
    assert yo.json() == {"usuario": "revisor_ficticio", "rol": "revisor"}


def test_contrasena_mala_y_usuario_inexistente_responden_igual(cliente, monkeypatch):
    llamadas = []
    original = auth.verificar_contrasena

    def espia(texto, hash_guardado):
        llamadas.append(hash_guardado)
        return original(texto, hash_guardado)

    monkeypatch.setattr(auth, "verificar_contrasena", espia)
    mala = cliente.post(LOGIN, json={"usuario": "revisor_ficticio", "contrasena": "otra-contrasena"})
    inexistente = cliente.post(LOGIN, json={"usuario": "nadie_ficticio", "contrasena": "otra-contrasena"})

    assert mala.status_code == inexistente.status_code == 401
    assert mala.json() == inexistente.json() == {"codigo": "CREDENCIALES_INVALIDAS",
                                                  "mensaje": "Usuario o contrasena incorrectos"}
    assert mala.headers["www-authenticate"] == inexistente.headers["www-authenticate"] == "Bearer"
    assert len(llamadas) == 2  # tambien se verifica contra el hash ficticio
    assert llamadas[1] == auth._hash_ficticio()


def test_contrasena_de_80_bytes_da_401(cliente):
    r = cliente.post(LOGIN, json={"usuario": "revisor_ficticio", "contrasena": "x" * 80})
    assert (r.status_code, r.json()["codigo"]) == (401, "CREDENCIALES_INVALIDAS")


def test_falta_la_contrasena_422_sin_valores(cliente):
    r = cliente.post(LOGIN, json={"usuario": "valor-que-no-debe-salir"})
    assert r.status_code == 422
    assert r.json()["codigo"] == "PETICION_INVALIDA"
    assert "contrasena" in r.json()["mensaje"]
    assert "valor-que-no-debe-salir" not in r.text


def test_campo_extra_422(cliente):
    r = cliente.post(LOGIN, json={"usuario": "revisor_ficticio", "contrasena": CONTRASENA,
                                  "token_type": "bearer"})
    assert (r.status_code, r.json()["codigo"]) == (422, "PETICION_INVALIDA")
    assert "token_type" in r.json()["mensaje"]


def test_yo_sin_token(cliente):
    r = cliente.get("/api/v1/auth/yo")
    assert (r.status_code, r.json()["codigo"]) == (401, "NO_AUTENTICADO")
    assert r.headers["www-authenticate"] == "Bearer"


def test_ruta_inexistente_404(cliente):
    r = cliente.get("/api/v1/no-existe")
    assert r.status_code == 404
    assert r.json() == {"codigo": "RUTA_NO_ENCONTRADA", "mensaje": "Ruta no encontrada"}


def test_metodo_no_permitido_405(cliente):
    r = cliente.get(LOGIN)
    assert (r.status_code, r.json()["codigo"]) == (405, "METODO_NO_PERMITIDO")


def test_error_no_controlado_500_sin_detalles():
    mini = FastAPI()
    registrar_manejadores(mini)

    @mini.get("/rompe")
    def rompe():
        raise RuntimeError("detalle interno secreto")

    r = TestClient(mini, raise_server_exceptions=False).get("/rompe")
    assert r.status_code == 500
    assert r.json() == {"codigo": "ERROR_INTERNO", "mensaje": "Error interno"}
    assert "detalle interno secreto" not in r.text


def test_una_fila_de_auditoria_por_intento(cliente, sesion):
    cliente.post(LOGIN, json={"usuario": "revisor_ficticio", "contrasena": CONTRASENA})
    cliente.post(LOGIN, json={"usuario": "revisor_ficticio", "contrasena": "otra-contrasena"})
    cliente.post(LOGIN, json={"usuario": "nadie_ficticio", "contrasena": "otra-contrasena"})
    assert _logins(sesion) == [("revisor_ficticio", "ok"), ("revisor_ficticio", "fallido"),
                               ("nadie_ficticio", "fallido")]
    for fila in sesion.scalars(select(Auditoria)):
        assert CONTRASENA not in str(fila.detalle)


def test_registrar_accion_desconocida(sesion):
    with pytest.raises(ValueError, match="desconocida"):
        auditoria.registrar(sesion, "borrar_todo")


# --- limite de intentos (ADR-011): 5 fallidos en 15 minutos, contados en la auditoria ---

def _intento(cliente, contrasena="otra-contrasena", usuario="revisor_ficticio"):
    return cliente.post(LOGIN, json={"usuario": usuario, "contrasena": contrasena})


def _fallar(cliente, veces, usuario="revisor_ficticio"):
    for _ in range(veces):
        assert _intento(cliente, usuario=usuario).status_code == 401


def _atrasar_logins(sesion, minutos):
    """Mueve al pasado todos los login de la auditoria (simula que pasa el tiempo)."""
    sesion.execute(update(Auditoria).where(Auditoria.accion == "login")
                   .values(creado_en=datetime.now(timezone.utc) - timedelta(minutes=minutos)))
    sesion.commit()


def test_cinco_fallidos_dan_429_con_retry_after_sin_comprobar_la_contrasena(cliente, sesion, monkeypatch):
    _fallar(cliente, 5)
    llamadas = []
    monkeypatch.setattr(auth, "verificar_contrasena", lambda *a: llamadas.append(a) or True)
    r = _intento(cliente, CONTRASENA)  # ni siquiera la correcta entra
    assert r.status_code == 429
    assert r.json() == {"codigo": "DEMASIADOS_INTENTOS",
                        "mensaje": "Demasiados intentos fallidos; vuelve a intentarlo mas tarde"}
    assert 0 < int(r.headers["retry-after"]) <= 15 * 60
    assert llamadas == []
    assert _logins(sesion)[-1] == ("revisor_ficticio", "bloqueado")


def test_retry_after_segun_el_fallido_que_libera(cliente, sesion):
    _fallar(cliente, 5)
    _atrasar_logins(sesion, 10)  # los 5 hace 10 minutos: quedan unos 5 minutos
    assert 290 <= int(_intento(cliente).headers["retry-after"]) <= 300


def test_el_bloqueado_se_audita_y_no_alarga_el_bloqueo(cliente, sesion):
    _fallar(cliente, 5)
    _atrasar_logins(sesion, 16)  # los fallidos ya fuera de la ventana...
    _fallar(cliente, 4)
    assert _intento(cliente).status_code == 401  # 5 fallidos en la ventana
    for _ in range(3):
        assert _intento(cliente).status_code == 429
    assert [r for _, r in _logins(sesion)].count("bloqueado") == 3
    # ...y los bloqueados no cuentan: al salir los 5 fallidos, vuelve a entrar aunque los bloqueados sean recientes
    sesion.execute(update(Auditoria).where(Auditoria.accion == "login",
                                           Auditoria.detalle["resultado"].as_string() == "fallido")
                   .values(creado_en=datetime.now(timezone.utc) - timedelta(minutes=16)))
    sesion.commit()
    assert _intento(cliente, CONTRASENA).status_code == 200


def test_pasada_la_ventana_vuelve_a_dejar_entrar(cliente, sesion):
    _fallar(cliente, 5)
    assert _intento(cliente, CONTRASENA).status_code == 429
    _atrasar_logins(sesion, 16)
    assert _intento(cliente, CONTRASENA).status_code == 200


def test_un_ok_reinicia_la_cuenta(cliente):
    _fallar(cliente, 4)
    assert _intento(cliente, CONTRASENA).status_code == 200  # antes del limite, el correcto entra
    _fallar(cliente, 4)  # 8 fallidos en la ventana, pero solo 4 despues del ok
    assert _intento(cliente, CONTRASENA).status_code == 200


def test_usuario_inexistente_igual_que_uno_existente(cliente, sesion):
    _fallar(cliente, 5, "revisor_ficticio")
    _fallar(cliente, 5, "nadie_ficticio")
    existente = _intento(cliente, usuario="revisor_ficticio")
    inexistente = _intento(cliente, usuario="nadie_ficticio")
    assert existente.status_code == inexistente.status_code == 429
    assert existente.json() == inexistente.json()
    assert existente.headers.keys() == inexistente.headers.keys()
    assert _logins(sesion)[-2:] == [("revisor_ficticio", "bloqueado"), ("nadie_ficticio", "bloqueado")]


def test_el_limite_es_por_usuario(cliente):
    _fallar(cliente, 5, "nadie_ficticio")
    assert _intento(cliente, CONTRASENA).status_code == 200


def test_limite_configurable(cliente, monkeypatch):
    monkeypatch.setenv("LOGIN_MAX_FALLIDOS", "2")
    get_settings.cache_clear()
    _fallar(cliente, 2)
    assert _intento(cliente, CONTRASENA).status_code == 429
