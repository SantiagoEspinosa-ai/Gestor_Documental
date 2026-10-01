"""
Adaptador de Ollama (ADR-005): unico sitio donde se llama a la API HTTP de Ollama.
Implementa ProveedorLLM (Contrato 3). Regla del enrutador (spec, seccion 3): modelo de texto, sin
imagenes, si todas las paginas tienen texto suficiente (capa del PDF u OCR); vision en el resto, con las
paginas reducidas y por lotes. El reintento con vision lo decide el servicio (motor_ia/servicio.py),
que conoce la clasificacion; aqui solo se expone `extraer_con_vision`.
"""
from __future__ import annotations

import base64
import time
from collections.abc import Callable
from typing import Any

import httpx

from app.modulos.motor_ia.interfaces import (
    DocumentoPreparado,
    Modalidad,
    Pagina,
    ResultadoClasificacion,
    ResultadoExtraccion,
)
from app.modulos.motor_ia.prompts import renderizar
from app.modulos.motor_ia.proveedores.base import (
    KEEP_ALIVE,
    NUM_CTX,
    NUM_PREDICT,
    TEMPERATURA,
    TIMEOUT_TEXTO_S,
    ErrorProveedor,
    ErrorRespuestaInvalida,
    InfoLlamada,
    RespuestaNoValida,
    combinar_lotes,
    lotes_de_paginas,
    parsear_clasificacion,
    parsear_extraccion,
    postprocesar_clasificacion,
    postprocesar_extraccion,
    reducir_imagen,
    tiene_texto_suficiente,
    timeout_vision,
)

# Modalidad que se pasa al postprocesado solo para decidir el formato de la evidencia:
# con texto se conserva el detalle (`pagina_1:Fecha de caducidad`); con vision, solo `pagina_<n>`.
_EVIDENCIA_CON_DETALLE = Modalidad.pdf_digital
_EVIDENCIA_SOLO_PAGINA = Modalidad.imagen


class OllamaProvider:
    nombre = "ollama"
    soporta_vision = True

    def __init__(self, base_url: str, modelo_texto: str, modelo_vision: str, *, cliente: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.modelo_texto = modelo_texto
        self.modelo_vision = modelo_vision
        self.modelo = modelo_texto  # atributo del Protocol; el modelo real de cada llamada va en ultima_llamada
        self._cliente = cliente or httpx.Client()
        self._capacidades: dict[str, frozenset[str]] = {}
        self.ultima_llamada: InfoLlamada | None = None
        # Llamadas de la ultima operacion (clasificar, extraer o extraer_con_vision).
        self.ultimas_llamadas: list[InfoLlamada] = []

    # --- ProveedorLLM ---

    @staticmethod
    def usa_texto(doc: DocumentoPreparado) -> bool:
        return tiene_texto_suficiente(doc.paginas)

    def modelo_para(self, doc: DocumentoPreparado) -> str:
        return self.modelo_texto if self.usa_texto(doc) else self.modelo_vision

    def clasificar(self, doc: DocumentoPreparado, tipos_posibles: list[str], prompt: str) -> ResultadoClasificacion:
        self.ultimas_llamadas = []
        texto = self.usa_texto(doc)
        info = self._empezar(self.modelo_para(doc), "texto" if texto else "vision")
        lote = [] if texto else lotes_de_paginas(doc.paginas)[0]
        try:
            respuesta = self._pedir(info, prompt, lote, parsear_clasificacion)
        finally:
            self._terminar(info)
        return postprocesar_clasificacion(respuesta, tipos_posibles)

    def clasificar_con_vision(self, doc: DocumentoPreparado, tipos_posibles: list[str], prompt: str,
                              motivo: str | None = None) -> ResultadoClasificacion:
        """Clasificacion forzada con el modelo de vision (reclasificacion decidida por el servicio)."""
        self.ultimas_llamadas = []
        info = self._empezar(self.modelo_vision, "vision", motivo)
        try:
            respuesta = self._pedir(info, prompt, lotes_de_paginas(doc.paginas)[0], parsear_clasificacion)
        finally:
            self._terminar(info)
        return postprocesar_clasificacion(respuesta, tipos_posibles)

    def extraer(self, doc: DocumentoPreparado, esquema_campos: dict[str, Any], prompt: str) -> ResultadoExtraccion:
        """Texto si hay texto suficiente; vision si no. No reintenta: lo decide el servicio."""
        self.ultimas_llamadas = []
        if not self.usa_texto(doc):
            return self._extraer_vision(doc, esquema_campos, prompt)
        return self._extraer_texto(doc, esquema_campos, prompt)

    def extraer_con_vision(self, doc: DocumentoPreparado, esquema_campos: dict[str, Any], prompt: str,
                           motivo: str | None = None) -> ResultadoExtraccion:
        """Extraccion forzada con el modelo de vision (reintento decidido por el servicio). `motivo` queda en
        la llamada."""
        self.ultimas_llamadas = []
        return self._extraer_vision(doc, esquema_campos, prompt, motivo)

    # --- Internos ---

    def _extraer_texto(self, doc: DocumentoPreparado, esquema_campos: dict[str, Any], prompt: str) -> ResultadoExtraccion:
        info = self._empezar(self.modelo_texto, "texto")
        try:
            respuesta = self._pedir(info, prompt, [], parsear_extraccion)
        finally:
            self._terminar(info)
        return postprocesar_extraccion(respuesta, esquema_campos, _EVIDENCIA_CON_DETALLE, [p.numero for p in doc.paginas])

    def _extraer_vision(self, doc: DocumentoPreparado, esquema_campos: dict[str, Any], prompt: str,
                        motivo: str | None = None) -> ResultadoExtraccion:
        info = self._empezar(self.modelo_vision, "vision", motivo)
        try:
            lotes = lotes_de_paginas(doc.paginas)
            info.lotes = len(lotes)
            resultados = []
            for lote in lotes:
                respuesta = self._pedir(info, prompt, lote, parsear_extraccion)
                resultados.append(postprocesar_extraccion(respuesta, esquema_campos, _EVIDENCIA_SOLO_PAGINA,
                                                          [p.numero for p in lote]))
            return combinar_lotes(resultados)
        finally:
            self._terminar(info)

    def _empezar(self, modelo: str, entrada: str, motivo: str | None = None) -> InfoLlamada:
        info = InfoLlamada(proveedor=self.nombre, modelo=modelo, entrada=entrada, motivo=motivo)
        info.segundos = time.perf_counter()
        self.ultima_llamada = info
        self.ultimas_llamadas.append(info)
        return info

    @staticmethod
    def _terminar(info: InfoLlamada) -> None:
        info.segundos = round(time.perf_counter() - info.segundos, 2)

    def _pedir(self, info: InfoLlamada, prompt: str, lote: list[Pagina], parsear: Callable[[str], Any]):
        """Una peticion y, si la respuesta no es valida, un reintento con la instruccion de correccion
        (sin reenviar las imagenes: solo hay que corregir el formato)."""
        imagenes = [base64.b64encode(reducir_imagen(p.imagen_png)).decode() for p in lote]
        mensaje: dict[str, Any] = {"role": "user", "content": prompt}
        if imagenes:
            mensaje["images"] = imagenes
        contenido = self._chat(info, [mensaje], len(imagenes))
        try:
            return parsear(contenido)
        except RespuestaNoValida as error:
            info.reintentos += 1
            correccion, _ = renderizar("correccion_json", error=str(error))
            historial = [{"role": "user", "content": prompt},
                         {"role": "assistant", "content": contenido},
                         {"role": "user", "content": correccion}]
            contenido = self._chat(info, historial, 0)
            try:
                return parsear(contenido)
            except RespuestaNoValida as segundo:
                raise ErrorRespuestaInvalida(f"{info.modelo}: respuesta invalida tras el reintento: {segundo}") from segundo

    def _chat(self, info: InfoLlamada, mensajes: list[dict], n_imagenes: int) -> str:
        cuerpo: dict[str, Any] = {
            "model": info.modelo,
            "messages": mensajes,
            "format": "json",
            "stream": False,
            "keep_alive": KEEP_ALIVE,
            "options": {"temperature": TEMPERATURA, "num_predict": NUM_PREDICT, "num_ctx": NUM_CTX},
        }
        if "thinking" in self._capacidades_de(info.modelo):
            cuerpo["think"] = False
        timeout = timeout_vision(n_imagenes) if n_imagenes else TIMEOUT_TEXTO_S
        datos = self._post("/api/chat", cuerpo, timeout, info.modelo)
        info.peticiones += 1
        info.tokens_entrada += int(datos.get("prompt_eval_count") or 0)
        info.tokens_salida += int(datos.get("eval_count") or 0)
        contenido = (datos.get("message") or {}).get("content")
        if not isinstance(contenido, str):
            raise ErrorProveedor(f"{info.modelo}: respuesta de Ollama sin message.content")
        return contenido

    def _capacidades_de(self, modelo: str) -> frozenset[str]:
        """Capacidades del modelo (p. ej. 'vision', 'thinking') segun /api/show, consultadas una vez."""
        if modelo not in self._capacidades:
            datos = self._post("/api/show", {"model": modelo}, TIMEOUT_TEXTO_S, modelo)
            self._capacidades[modelo] = frozenset(datos.get("capabilities") or [])
        return self._capacidades[modelo]

    def _post(self, ruta: str, cuerpo: dict, timeout: float, modelo: str) -> dict:
        try:
            respuesta = self._cliente.post(f"{self.base_url}{ruta}", json=cuerpo, timeout=timeout)
        except httpx.TimeoutException as e:
            raise ErrorProveedor(f"{modelo}: Ollama no respondio en {timeout} s") from e
        except httpx.HTTPError as e:
            raise ErrorProveedor(f"{modelo}: no se pudo conectar con Ollama en {self.base_url}") from e
        if respuesta.status_code == 404:
            raise ErrorProveedor(f"modelo '{modelo}' no encontrado en Ollama (ollama pull {modelo})")
        if respuesta.status_code == 429:
            raise ErrorProveedor(f"{modelo}: Ollama rechazo la peticion por limite (429)")
        if respuesta.status_code >= 400:
            raise ErrorProveedor(f"{modelo}: Ollama respondio HTTP {respuesta.status_code}")
        try:
            return respuesta.json()
        except ValueError as e:
            raise ErrorProveedor(f"{modelo}: respuesta de Ollama que no es JSON") from e
