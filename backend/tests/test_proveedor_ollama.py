"""Tests de OllamaProvider contra un Ollama simulado (httpx.MockTransport). Nunca llama al modelo real."""
import base64
import io
import json
from pathlib import Path

import httpx
import pytest
from PIL import Image

from app.modulos.configuracion import servicio as configuracion
from app.modulos.motor_ia.interfaces import DocumentoPreparado, Modalidad, Pagina
from app.modulos.motor_ia.proveedores.base import (
    NUM_CTX,
    NUM_PREDICT,
    TIMEOUT_TEXTO_S,
    ErrorProveedor,
    ErrorRespuestaInvalida,
    timeout_vision,
)
from app.modulos.motor_ia.proveedores.ollama import OllamaProvider

RESPUESTAS = Path(__file__).parent / "respuestas_modelo"
TIPOS = ["comprobante_domicilio", "credencial_elector", "pasaporte"]
CAPACIDADES = {"gemma4:e2b": ["completion", "vision", "thinking"], "qwen2.5vl:3b": ["completion", "vision"]}


def guardada(nombre: str) -> dict:
    return json.loads((RESPUESTAS / f"{nombre}.json").read_text(encoding="utf-8"))


def respuesta(contenido: str) -> dict:
    return {"message": {"role": "assistant", "content": contenido}, "prompt_eval_count": 100, "eval_count": 20}


class OllamaFalso:
    """Responde /api/show con CAPACIDADES y /api/chat con las respuestas de la cola, en orden."""

    def __init__(self, *respuestas_chat, estado: int = 200, excepcion: Exception | None = None):
        self.cola = list(respuestas_chat)
        self.estado, self.excepcion = estado, excepcion
        self.chats: list[dict] = []
        self.timeouts: list[float] = []
        self.shows: list[str] = []

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        cuerpo = json.loads(peticion.content)
        if peticion.url.path == "/api/show":
            self.shows.append(cuerpo["model"])
            return httpx.Response(200, json={"capabilities": CAPACIDADES.get(cuerpo["model"], [])})
        if self.excepcion:
            raise self.excepcion
        self.chats.append(cuerpo)
        self.timeouts.append(peticion.extensions["timeout"]["read"])
        if self.estado != 200:
            return httpx.Response(self.estado, json={"error": "simulado"})
        siguiente = self.cola.pop(0)
        if isinstance(siguiente, int):  # un codigo HTTP de error para esta peticion concreta
            return httpx.Response(siguiente, json={"error": "simulado"})
        return httpx.Response(200, json=siguiente)


def proveedor(falso: OllamaFalso) -> OllamaProvider:
    cliente = httpx.Client(transport=httpx.MockTransport(falso))
    return OllamaProvider("http://ollama-falso:11434/", "gemma4:e2b", "qwen2.5vl:3b", cliente=cliente)


def png(ancho: int = 2000, alto: int = 1414) -> bytes:
    salida = io.BytesIO()
    Image.new("RGB", (ancho, alto), (210, 210, 210)).save(salida, format="PNG")
    return salida.getvalue()


# Texto suficiente (>= 30 caracteres sin espacios) para la regla del enrutador; datos inventados.
TEXTO_SUFICIENTE = "PASAPORTE DE MUESTRA SIN VALIDEZ ANA EJEMPLO PRUEBA X1234567P"


def documento(modalidad: Modalidad, n_paginas: int = 1, texto: str | None = None,
              con_imagenes: bool = True) -> DocumentoPreparado:
    """Por defecto: pdf_digital con texto suficiente; escaneado e imagen sin texto (OCR no disponible)."""
    if texto is None and modalidad is Modalidad.pdf_digital:
        texto = TEXTO_SUFICIENTE
    paginas = [Pagina(i, texto=texto, imagen_png=png() if con_imagenes else None) for i in range(1, n_paginas + 1)]
    return DocumentoPreparado("00000000-0000-4000-8000-000000000001", modalidad, paginas, "pasaporte")


def esquema() -> dict:
    return {n: c.model_dump(mode="json") for n, c in configuracion.cargar()["pasaporte"].campos.items()}


# --- Eleccion de modelo y cuerpo de la peticion ---

def test_pdf_digital_usa_el_modelo_de_texto_sin_imagenes():
    falso = OllamaFalso(guardada("texto_gemma4_extraccion_pasaporte_ok"))
    p = proveedor(falso)
    r = p.extraer(documento(Modalidad.pdf_digital), esquema(), "PROMPT DE PRUEBA")
    cuerpo = falso.chats[0]
    assert cuerpo["model"] == "gemma4:e2b" and "images" not in cuerpo["messages"][0]
    assert cuerpo["messages"][0]["content"] == "PROMPT DE PRUEBA"
    assert cuerpo["format"] == "json" and cuerpo["stream"] is False
    assert cuerpo["options"] == {"temperature": 0, "num_predict": NUM_PREDICT, "num_ctx": NUM_CTX}
    assert cuerpo["think"] is False  # gemma4 tiene la capacidad 'thinking'
    assert falso.timeouts == [TIMEOUT_TEXTO_S]
    assert r.datos_extraidos["fecha_vencimiento"] == "2034-05-09"
    assert p.ultima_llamada.modelo == "gemma4:e2b"


@pytest.mark.parametrize("modalidad", [Modalidad.imagen, Modalidad.pdf_escaneado])
def test_vision_usa_el_modelo_de_vision_con_imagenes_reducidas(modalidad):
    falso = OllamaFalso(guardada("vision_qwen_extraccion_fechas_tal_cual"))
    p = proveedor(falso)
    r = p.extraer(documento(modalidad), esquema(), "PROMPT")
    cuerpo = falso.chats[0]
    assert cuerpo["model"] == "qwen2.5vl:3b" and "think" not in cuerpo  # qwen no admite 'think'
    imagenes = [Image.open(io.BytesIO(base64.b64decode(i))) for i in cuerpo["messages"][0]["images"]]
    assert [i.size for i in imagenes] == [(1000, 707)]
    assert falso.timeouts == [timeout_vision(1)]
    assert r.datos_extraidos["fecha_expedicion"] == "2024-05-10"
    assert r.evidencia_por_campo["sexo"] == "pagina_1"


def test_capacidades_se_consultan_una_vez_por_modelo():
    falso = OllamaFalso(guardada("texto_gemma4_clasificacion_pasaporte"), guardada("texto_gemma4_extraccion_pasaporte_ok"))
    p = proveedor(falso)
    p.clasificar(documento(Modalidad.pdf_digital), TIPOS, "P")
    p.extraer(documento(Modalidad.pdf_digital), esquema(), "P")
    assert falso.shows == ["gemma4:e2b"]


# --- Lotes de vision ---

def test_vision_con_seis_paginas_va_en_dos_lotes_y_se_combina():
    lote2 = respuesta(json.dumps({
        "datos_extraidos": {"nombre_completo": "OTRO VALOR", "nacionalidad": "PAIS FICTICIO"},
        "nivel_confianza_por_campo": {"nombre_completo": 0.9, "nacionalidad": 0.9},
        "evidencia_por_campo": {"nombre_completo": "pagina_1", "nacionalidad": "pagina_2"},
    }))
    lote1 = respuesta(json.dumps({
        "datos_extraidos": {"nombre_completo": "ANA EJEMPLO PRUEBA", "nacionalidad": None},
        "nivel_confianza_por_campo": {"nombre_completo": 0.9},
        "evidencia_por_campo": {"nombre_completo": "pagina_3"},
    }))
    falso = OllamaFalso(lote1, lote2)
    p = proveedor(falso)
    r = p.extraer(documento(Modalidad.pdf_escaneado, 6), esquema(), "PROMPT")
    assert [len(c["messages"][0]["images"]) for c in falso.chats] == [4, 2]
    assert falso.timeouts == [timeout_vision(4), timeout_vision(2)]
    # nombre: pagina_3 (lote 1) frente a pagina_5 (lote 2, "pagina_1" relativa) -> la mas baja
    assert r.datos_extraidos["nombre_completo"] == "ANA EJEMPLO PRUEBA"
    assert r.evidencia_por_campo["nombre_completo"] == "pagina_3"
    # nacionalidad: solo en el lote 2, "pagina_2" relativa -> pagina_6
    assert r.evidencia_por_campo["nacionalidad"] == "pagina_6"
    assert p.ultima_llamada.lotes == 2 and p.ultima_llamada.peticiones == 2
    assert p.ultima_llamada.tokens_entrada == 200 and p.ultima_llamada.tokens_salida == 40


def test_clasificar_en_vision_solo_envia_el_primer_lote():
    falso = OllamaFalso(respuesta('{"tipo_documental_detectado": "pasaporte", "confianza": 0.9}'))
    r = proveedor(falso).clasificar(documento(Modalidad.imagen, 6), TIPOS, "P")
    assert len(falso.chats[0]["messages"][0]["images"]) == 4
    assert r.tipo_documental_detectado == "pasaporte"


# --- Reintento de correccion ---

def test_reintento_con_exito():
    falso = OllamaFalso(respuesta("esto no es JSON"), guardada("texto_gemma4_clasificacion_pasaporte"))
    p = proveedor(falso)
    r = p.clasificar(documento(Modalidad.imagen), TIPOS, "PROMPT ORIGINAL")
    assert r.tipo_documental_detectado == "pasaporte"
    reintento = falso.chats[1]["messages"]
    assert [m["role"] for m in reintento] == ["user", "assistant", "user"]
    assert reintento[1]["content"] == "esto no es JSON"
    assert "no es valida" in reintento[2]["content"] and "no es un JSON valido" in reintento[2]["content"]
    assert all("images" not in m for m in reintento)  # el reintento no reenvia las imagenes
    assert falso.timeouts[1] == TIMEOUT_TEXTO_S
    assert p.ultima_llamada.reintentos == 1 and p.ultima_llamada.peticiones == 2


def test_reintento_fallido_lanza_error_de_respuesta_invalida():
    falso = OllamaFalso(respuesta("mal"), respuesta('{"tipo_documental_detectado": "pasaporte"}'))
    with pytest.raises(ErrorRespuestaInvalida, match="tras el reintento"):
        proveedor(falso).clasificar(documento(Modalidad.pdf_digital), TIPOS, "P")


# --- Errores del servidor ---

@pytest.mark.parametrize("estado, mensaje", [(404, "ollama pull"), (429, "limite"), (500, "HTTP 500")])
def test_errores_http(estado, mensaje):
    with pytest.raises(ErrorProveedor, match=mensaje):
        proveedor(OllamaFalso(estado=estado)).extraer(documento(Modalidad.pdf_digital), esquema(), "P")


@pytest.mark.parametrize("excepcion, mensaje", [
    (httpx.ReadTimeout("simulado"), "no respondio"),
    (httpx.ConnectError("simulado"), "no se pudo conectar"),
])
def test_timeout_y_conexion(excepcion, mensaje):
    with pytest.raises(ErrorProveedor, match=mensaje):
        proveedor(OllamaFalso(excepcion=excepcion)).extraer(documento(Modalidad.pdf_digital), esquema(), "P")


def test_respuesta_sin_contenido():
    with pytest.raises(ErrorProveedor, match="sin message.content"):
        proveedor(OllamaFalso({"done": True})).extraer(documento(Modalidad.pdf_digital), esquema(), "P")


def test_protocolo_proveedor_llm():
    p = proveedor(OllamaFalso())
    assert (p.nombre, p.modelo, p.soporta_vision) == ("ollama", "gemma4:e2b", True)
    assert p.base_url == "http://ollama-falso:11434"


# --- Regla del enrutador: texto si todas las paginas tienen texto suficiente (capa del PDF u OCR) ---

def test_la_constante_coincide_con_el_umbral_de_modalidad():
    from app.modulos.motor_ia.proveedores.base import MIN_CARACTERES_TEXTO_POR_PAGINA
    from app.modulos.orquestador.modalidad import UMBRAL_CARACTERES_POR_PAGINA
    assert MIN_CARACTERES_TEXTO_POR_PAGINA == UMBRAL_CARACTERES_POR_PAGINA


@pytest.mark.parametrize("modalidad", [Modalidad.pdf_escaneado, Modalidad.imagen])
def test_escaneado_o_imagen_con_ocr_suficiente_usa_el_modelo_de_texto(modalidad):
    falso = OllamaFalso(guardada("texto_gemma4_extraccion_pasaporte_ok"))
    p = proveedor(falso)
    r = p.extraer(documento(modalidad, texto=TEXTO_SUFICIENTE), esquema(), "PROMPT")
    assert falso.chats[0]["model"] == "gemma4:e2b" and "images" not in falso.chats[0]["messages"][0]
    assert [i.entrada for i in p.ultimas_llamadas] == ["texto"] and p.ultima_llamada.motivo is None
    assert r.evidencia_por_campo["fecha_vencimiento"] == "pagina_1:Fecha de caducidad"  # con texto, con detalle


def test_si_una_pagina_no_tiene_texto_suficiente_va_a_vision():
    doc = documento(Modalidad.pdf_escaneado, n_paginas=2, texto=TEXTO_SUFICIENTE)
    doc.paginas[1].texto = "PAGINA 2"  # menos de 30 caracteres
    falso = OllamaFalso(guardada("vision_qwen_extraccion_foto_degradada"))
    p = proveedor(falso)
    p.extraer(doc, esquema(), "P")
    assert falso.chats[0]["model"] == "qwen2.5vl:3b" and len(falso.chats[0]["messages"][0]["images"]) == 2
    assert p.modelo_para(doc) == "qwen2.5vl:3b" and p.ultima_llamada.entrada == "vision"


def test_clasificar_con_texto_suficiente_no_envia_imagenes():
    falso = OllamaFalso(guardada("texto_gemma4_clasificacion_pasaporte"))
    p = proveedor(falso)
    p.clasificar(documento(Modalidad.imagen, texto=TEXTO_SUFICIENTE), TIPOS, "P")
    assert falso.chats[0]["model"] == "gemma4:e2b" and "images" not in falso.chats[0]["messages"][0]


# --- El reintento con vision lo decide el servicio; el proveedor solo expone extraer_con_vision ---

def _texto_incompleto() -> dict:
    # 3 de los 4 obligatorios del pasaporte a null
    datos = {"nombre_completo": "ANA EJEMPLO PRUEBA", "numero_pasaporte": None, "fecha_nacimiento": None,
             "fecha_vencimiento": None, "nacionalidad": "PAIS FICTICIO"}
    return respuesta(json.dumps({"datos_extraidos": datos, "nivel_confianza_por_campo": {c: 0.9 for c in datos},
                                 "evidencia_por_campo": {c: "pagina_1" for c in datos}}))


def test_extraer_no_reintenta_aunque_falten_obligatorios():
    falso = OllamaFalso(_texto_incompleto())
    p = proveedor(falso)
    r = p.extraer(documento(Modalidad.imagen, texto=TEXTO_SUFICIENTE), esquema(), "P")
    assert len(falso.chats) == 1 and falso.chats[0]["model"] == "gemma4:e2b"
    assert r.datos_extraidos["numero_pasaporte"] is None
    assert [i.entrada for i in p.ultimas_llamadas] == ["texto"]


def test_extraer_con_vision_usa_el_modelo_de_vision_y_registra_el_motivo():
    falso = OllamaFalso(guardada("vision_qwen_extraccion_fechas_tal_cual"))
    p = proveedor(falso)
    r = p.extraer_con_vision(documento(Modalidad.imagen, texto=TEXTO_SUFICIENTE), esquema(), "P",
                             "reintento con vision: 3/4 campos obligatorios vacios con texto")
    assert falso.chats[0]["model"] == "qwen2.5vl:3b" and len(falso.chats[0]["messages"][0]["images"]) == 1
    assert r.datos_extraidos["fecha_vencimiento"] == "2031-07-25"
    assert [(i.entrada, i.motivo) for i in p.ultimas_llamadas] == [
        ("vision", "reintento con vision: 3/4 campos obligatorios vacios con texto")]


def test_clasificar_con_vision_usa_el_modelo_de_vision_y_registra_el_motivo():
    falso = OllamaFalso(respuesta('{"tipo_documental_detectado": "pasaporte", "confianza": 0.9}'))
    p = proveedor(falso)
    r = p.clasificar_con_vision(documento(Modalidad.imagen, n_paginas=6, texto=TEXTO_SUFICIENTE), TIPOS, "P",
                                "reclasificacion con vision: la clasificacion con texto dio desconocido")
    assert falso.chats[0]["model"] == "qwen2.5vl:3b" and len(falso.chats[0]["messages"][0]["images"]) == 4
    assert r.tipo_documental_detectado == "pasaporte"
    assert [(i.entrada, i.motivo) for i in p.ultimas_llamadas] == [
        ("vision", "reclasificacion con vision: la clasificacion con texto dio desconocido")]
