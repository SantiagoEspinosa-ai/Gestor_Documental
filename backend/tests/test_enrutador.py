"""Tests del enrutador (motor_ia/enrutador.py). Entorno inyectado: sin variables reales, claves ni red."""
import logging

import pytest
import yaml

from app.modulos.motor_ia.enrutador import VARIABLE_PRIVACIDAD, ErrorEnrutador, crear_enrutador
from app.modulos.motor_ia.interfaces import Tarea
from app.modulos.motor_ia.proveedores.ollama import OllamaProvider

TIPOS = {"pasaporte", "credencial_elector", "comprobante_domicilio"}
SECRETO = "valor-secreto-de-prueba"
ENTORNO = {
    "OLLAMA_BASE_URL": "http://ollama-de-prueba:11434",
    "OLLAMA_MODELO_TEXTO": "modelo-texto-de-prueba",
    "OLLAMA_MODELO_VISION": "modelo-vision-de-prueba",
}
ENTORNO_COMERCIAL = {
    "PROVEEDOR_COMERCIAL_BASE_URL": "https://comercial-de-prueba/api/v1",
    "PROVEEDOR_COMERCIAL_MODELO": "modelo-de-prueba:free",
    "PROVEEDOR_COMERCIAL_API_KEY": SECRETO,
}


def config_base() -> dict:
    return {
        "proveedores": {
            "ollama": {"tipo": "ollama", "base_url_env": "OLLAMA_BASE_URL", "modelo_texto_env": "OLLAMA_MODELO_TEXTO",
                       "modelo_vision_env": "OLLAMA_MODELO_VISION", "soporta_vision": True, "privado": True},
            "otro_ollama": {"tipo": "ollama", "base_url_env": "OTRO_URL", "modelo_texto_env": "OTRO_TEXTO",
                            "modelo_vision_env": "OTRO_VISION", "soporta_vision": True, "privado": True},
            "comercial": {"tipo": "openrouter", "base_url_env": "PROVEEDOR_COMERCIAL_BASE_URL",
                          "api_key_env": "PROVEEDOR_COMERCIAL_API_KEY", "modelo_env": "PROVEEDOR_COMERCIAL_MODELO",
                          "soporta_vision": True, "privado": False},
        },
        "tareas": {
            "clasificacion": {"principal": "ollama", "respaldo": "otro_ollama"},
            "extraccion": {"principal": "ollama", "respaldo": "comercial", "por_tipo": None},
        },
    }


@pytest.fixture
def escribir(tmp_path):
    def _escribir(config: dict | str):
        texto = config if isinstance(config, str) else yaml.safe_dump(config)
        (tmp_path / "modelos.yaml").write_text(texto, encoding="utf-8")
        return tmp_path
    return _escribir


def enrutador(directorio, entorno=None):
    return crear_enrutador(directorio, ENTORNO if entorno is None else entorno, TIPOS)


def errores_de(directorio, entorno=None) -> str:
    with pytest.raises(ErrorEnrutador) as exc:
        enrutador(directorio, entorno)
    assert SECRETO not in str(exc.value)
    return str(exc.value)


# --- modelos.yaml real del repo ---

def test_modelos_yaml_real():
    e = crear_enrutador(entorno=ENTORNO)  # tipos documentales de configuracion
    proveedor = e.obtener(Tarea.extraccion, "pasaporte")
    assert isinstance(proveedor, OllamaProvider)
    assert (proveedor.base_url, proveedor.modelo_texto, proveedor.modelo_vision) == (
        "http://ollama-de-prueba:11434", "modelo-texto-de-prueba", "modelo-vision-de-prueba")
    assert e.obtener(Tarea.clasificacion) is proveedor  # una instancia por proveedor
    assert e.obtener(Tarea.validacion) is proveedor     # se acepta, aunque nadie la pide
    assert e.respaldo(Tarea.extraccion) is None         # comercial: no privado y openrouter sin implementar


# --- respaldo ---

def test_respaldo_privado_disponible(escribir):
    e = enrutador(escribir(config_base()), {**ENTORNO, "OTRO_URL": "http://otro:1", "OTRO_TEXTO": "t", "OTRO_VISION": "v"})
    respaldo = e.respaldo(Tarea.clasificacion)
    assert isinstance(respaldo, OllamaProvider) and respaldo is not e.obtener(Tarea.clasificacion)
    assert respaldo.base_url == "http://otro:1"


def test_respaldo_sin_variables_devuelve_none_y_avisa(escribir, caplog):
    caplog.set_level(logging.WARNING)
    e = enrutador(escribir(config_base()))
    assert e.respaldo(Tarea.clasificacion) is None
    assert "respaldo 'otro_ollama' no disponible" in caplog.text and "OTRO_URL" in caplog.text


def test_respaldo_no_privado_con_la_barrera_cerrada(escribir, caplog):
    caplog.set_level(logging.WARNING)
    e = enrutador(escribir(config_base()), {**ENTORNO, **ENTORNO_COMERCIAL})
    assert e.respaldo(Tarea.extraccion) is None
    assert f"no es privado y {VARIABLE_PRIVACIDAD} no esta activada" in caplog.text
    assert SECRETO not in caplog.text


def test_respaldo_no_privado_con_la_barrera_abierta_sigue_sin_implementar(escribir, caplog):
    caplog.set_level(logging.WARNING)
    e = enrutador(escribir(config_base()), {**ENTORNO, **ENTORNO_COMERCIAL, VARIABLE_PRIVACIDAD: "true"})
    assert e.respaldo(Tarea.extraccion) is None
    assert "el tipo 'openrouter' aun no esta implementado" in caplog.text
    assert SECRETO not in caplog.text


def test_valor_de_ejemplo_cuenta_como_no_configurado(escribir, caplog):
    caplog.set_level(logging.WARNING)
    config = config_base()
    config["tareas"]["clasificacion"]["respaldo"] = "otro_ollama"
    enrutador(escribir(config), {**ENTORNO, "OTRO_URL": "http://otro:1", "OTRO_TEXTO": "TU_MODELO_AQUI:free",
                                 "OTRO_VISION": "v"})
    assert "la variable de entorno OTRO_TEXTO tiene el valor de ejemplo" in caplog.text


# --- por_tipo ---

def test_por_tipo_cambia_el_principal(escribir):
    config = config_base()
    config["tareas"]["extraccion"] = {"principal": "ollama", "respaldo": "otro_ollama",
                                      "por_tipo": {"pasaporte": "otro_ollama"}}
    e = enrutador(escribir(config), {**ENTORNO, "OTRO_URL": "http://otro:1", "OTRO_TEXTO": "t", "OTRO_VISION": "v"})
    assert e.obtener(Tarea.extraccion, "pasaporte").base_url == "http://otro:1"
    assert e.obtener(Tarea.extraccion, "credencial_elector").base_url == "http://ollama-de-prueba:11434"
    assert e.respaldo(Tarea.extraccion, "pasaporte") is None  # el respaldo es el propio principal
    assert e.respaldo(Tarea.extraccion, "credencial_elector").base_url == "http://otro:1"


# --- errores al arrancar ---

def test_principal_sin_variable_de_entorno(escribir):
    mensaje = errores_de(escribir(config_base()), {"OLLAMA_BASE_URL": "http://x", "OLLAMA_MODELO_TEXTO": "t"})
    assert "proveedor principal 'ollama' no disponible: falta la variable de entorno OLLAMA_MODELO_VISION" in mensaje


def test_principal_no_privado_con_la_barrera_cerrada(escribir):
    config = config_base()
    config["tareas"]["clasificacion"]["principal"] = "comercial"
    mensaje = errores_de(escribir(config), {**ENTORNO, **ENTORNO_COMERCIAL})
    assert f"proveedor principal 'comercial': no es privado y {VARIABLE_PRIVACIDAD} no esta activada" in mensaje


def test_principal_de_tipo_no_implementado(escribir):
    config = config_base()
    config["tareas"]["clasificacion"]["principal"] = "comercial"
    mensaje = errores_de(escribir(config), {**ENTORNO, **ENTORNO_COMERCIAL, VARIABLE_PRIVACIDAD: "1"})
    assert "el tipo 'openrouter' aun no esta implementado" in mensaje


@pytest.mark.parametrize("cambio, mensaje", [
    (lambda c: c["tareas"]["clasificacion"].update(principal="fantasma"), "clasificacion.principal: proveedor inexistente 'fantasma'"),
    (lambda c: c["tareas"]["extraccion"].update(respaldo="fantasma"), "extraccion.respaldo: proveedor inexistente 'fantasma'"),
    (lambda c: c["tareas"]["extraccion"].update(por_tipo={"factura": "ollama"}), "tipo documental inexistente 'factura'"),
    (lambda c: c["tareas"]["extraccion"].update(por_tipo={"pasaporte": "fantasma"}), "por_tipo.pasaporte: proveedor inexistente"),
    (lambda c: c["tareas"].pop("extraccion"), "falta la tarea 'extraccion'"),
    (lambda c: c["tareas"].update(resumen={"principal": "ollama"}), "tareas.resumen"),
    (lambda c: c["proveedores"]["ollama"].update(privdo=True), "proveedores.ollama.privdo"),
    (lambda c: c["proveedores"]["ollama"].pop("modelo_vision_env"), "necesita modelo_vision_env"),
    (lambda c: c["proveedores"]["ollama"].update(tipo="gemini"), "proveedores.ollama.tipo"),
    (lambda c: c["proveedores"]["comercial"].pop("api_key_env"), "necesita api_key_env"),
])
def test_modelos_yaml_invalido(escribir, cambio, mensaje):
    config = config_base()
    cambio(config)
    assert mensaje in errores_de(escribir(config))


def test_varios_errores_a_la_vez(escribir):
    config = config_base()
    config["tareas"]["clasificacion"]["principal"] = "fantasma"
    config["tareas"]["extraccion"]["respaldo"] = "fantasma2"
    with pytest.raises(ErrorEnrutador) as exc:
        enrutador(escribir(config))
    assert len(exc.value.errores) == 2


@pytest.mark.parametrize("texto, mensaje", [("proveedores: [sin cerrar\n", "YAML mal formado"),
                                            ("- una\n- lista\n", "modelos.yaml")])
def test_yaml_mal_formado(escribir, texto, mensaje):
    assert mensaje in errores_de(escribir(texto))


def test_sin_modelos_yaml(tmp_path):
    assert "no existe" in errores_de(tmp_path)
