"""Tests de motor_ia/servicio.py con proveedores y enrutador falsos: sin red ni modelo. Datos inventados."""
from datetime import datetime, timezone

import pytest

from app.modulos.configuracion.servicio import TipoNoEncontrado
from app.modulos.motor_ia.interfaces import (
    DocumentoPreparado,
    Modalidad,
    Pagina,
    ResultadoClasificacion,
    ResultadoExtraccion,
    Tarea,
)
from app.modulos.motor_ia.proveedores.base import ErrorProveedor, ErrorRespuestaInvalida, InfoLlamada
from app.modulos.motor_ia.servicio import analizar
from app.schemas.resultado import EstadoAnalisis, ReferenciaArchivoOriginal, ResultadoDocumento

AHORA = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
REFERENCIA = ReferenciaArchivoOriginal(nombre_archivo="pasaporte_sano_digital.pdf",
                                       ruta="local://pasaporte_sano_digital.pdf", hash="0" * 64)
# MRZ del especimen publico de la OACI (datos ficticios), digitos de control correctos
MRZ = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<\nL898902C36UTO7408122F1204159ZE184226B<<<<<10"
DATOS_PASAPORTE = {"nombre_completo": "ANA EJEMPLO PRUEBA", "numero_pasaporte": "X1234567P",
                   "fecha_nacimiento": "1990-01-01", "fecha_expedicion": "2024-05-10",
                   "fecha_vencimiento": "2034-05-09", "nacionalidad": "PAIS FICTICIO", "sexo": "F"}


class ProveedorFalso:
    soporta_vision = True

    def __init__(self, nombre, tipo="pasaporte", datos=None, falla_clasificar=None, falla_extraer=None):
        self.nombre, self.modelo = nombre, f"{nombre}-protocolo"
        self.tipo, self.datos = tipo, dict(DATOS_PASAPORTE if datos is None else datos)
        self.falla_clasificar, self.falla_extraer = falla_clasificar, falla_extraer
        self.prompts: list[tuple[str, str]] = []
        self.ultima_llamada = None

    def _llamada(self, tarea, prompt):
        self.prompts.append((tarea, prompt))
        self.ultima_llamada = InfoLlamada(proveedor=self.nombre, modelo=f"{self.nombre}-modelo-real-{tarea}")

    def clasificar(self, doc, tipos_posibles, prompt):
        self._llamada("clasificacion", prompt)
        if self.falla_clasificar:
            raise self.falla_clasificar
        return ResultadoClasificacion(self.tipo, 0.93, "prueba")

    def extraer(self, doc, esquema_campos, prompt):
        self._llamada("extraccion", prompt)
        if self.falla_extraer:
            raise self.falla_extraer
        datos = {c: self.datos.get(c) for c in esquema_campos}
        return ResultadoExtraccion(datos, {c: 0.9 for c in datos if datos[c] is not None},
                                   {c: "pagina_1" for c in datos if datos[c] is not None})


class EnrutadorFalso:
    def __init__(self, principal, respaldo=None):
        self.principal, self._respaldo = principal, respaldo
        self.pedidos: list[tuple[Tarea, str | None]] = []

    def obtener(self, tarea, tipo_documental=None):
        self.pedidos.append((tarea, tipo_documental))
        return self.principal

    def respaldo(self, tarea, tipo_documental=None):
        return self._respaldo


def documento(declarado="pasaporte", texto="PASAPORTE\nANA EJEMPLO PRUEBA", n_paginas=1):
    paginas = [Pagina(i, texto=texto) for i in range(1, n_paginas + 1)]
    return DocumentoPreparado("00000000-0000-4000-8000-000000000001", Modalidad.pdf_digital, paginas, declarado)


def ejecutar(principal, respaldo=None, doc=None, **kwargs):
    enrutador = EnrutadorFalso(principal, respaldo)
    analisis = analizar(doc or documento(), folio="CLI-2026-000000", referencia=REFERENCIA,
                        enrutador=enrutador, ahora=AHORA, **kwargs)
    ResultadoDocumento.model_validate(analisis.resultado.model_dump())  # siempre un Contrato 1 valido
    return analisis, enrutador


def codigos(resultado):
    return [(a.codigo, a.severidad.value, a.campo) for a in resultado.alertas_encontradas]


# --- Caso normal ---

def test_caso_normal():
    p = ProveedorFalso("ollama")
    analisis, enrutador = ejecutar(p)
    r = analisis.resultado
    assert r.estado_analisis is EstadoAnalisis.completado
    assert (r.folio_solicitud, r.tipo_documental_declarado, r.tipo_documental_detectado) == (
        "CLI-2026-000000", "pasaporte", "pasaporte")
    assert r.confianza_clasificacion == 0.93 and r.datos_extraidos["numero_pasaporte"] == "X1234567P"
    assert r.alertas_encontradas == [] and r.recomendacion is None
    assert r.fecha_y_modelo_utilizado.model_dump() == {
        "fecha_analisis": AHORA, "proveedor": "ollama", "modelo": "ollama-modelo-real-extraccion",
        "version_prompt": "extraccion_pasaporte@v3"}
    assert enrutador.pedidos == [(Tarea.clasificacion, None), (Tarea.extraccion, "pasaporte")]
    assert [i.modelo for i in analisis.llamadas] == ["ollama-modelo-real-clasificacion", "ollama-modelo-real-extraccion"]
    clasificacion, extraccion = p.prompts
    assert "ANA EJEMPLO PRUEBA" in clasificacion[1] and "- pasaporte:" in clasificacion[1]
    assert "(tipo: pasaporte)" in extraccion[1] and "- numero_pasaporte: texto, obligatorio" in extraccion[1]


# --- Tipo documental (ADR-006, 2.5) ---

def test_tipo_distinto_del_declarado_cls_001_y_extrae_con_el_declarado():
    p = ProveedorFalso("ollama", tipo="credencial_elector")
    analisis, enrutador = ejecutar(p)
    r = analisis.resultado
    assert codigos(r) == [("CLS-001", "critica", None)]
    assert r.alertas_encontradas[0].confianza == 1.0
    assert enrutador.pedidos[1] == (Tarea.extraccion, "pasaporte")
    assert set(r.datos_extraidos) == set(DATOS_PASAPORTE)


def test_tipo_confirmado_no_clasifica():
    p = ProveedorFalso("ollama", tipo="credencial_elector")
    analisis, enrutador = ejecutar(p, tipo_confirmado="pasaporte", doc=documento(declarado="credencial_elector"))
    r = analisis.resultado
    assert [t for t, _ in p.prompts] == ["extraccion"]
    assert (r.tipo_documental_confirmado, r.tipo_documental_detectado, r.confianza_clasificacion) == ("pasaporte", None, None)
    assert codigos(r) == []
    assert r.fecha_y_modelo_utilizado.version_prompt == "extraccion_pasaporte@v3"


def test_sin_declarado_extrae_con_el_detectado():
    p = ProveedorFalso("ollama", tipo="credencial_elector", datos={"curp": "AEPA900101MDFXXX01"})
    analisis, enrutador = ejecutar(p, doc=documento(declarado=None))
    assert enrutador.pedidos[1] == (Tarea.extraccion, "credencial_elector")
    assert analisis.resultado.datos_extraidos["curp"] == "AEPA900101MDFXXX01"
    assert codigos(analisis.resultado) == []


def test_desconocido_sin_declarado_no_extrae_ni_alerta():
    p = ProveedorFalso("ollama", tipo="desconocido")
    analisis, _ = ejecutar(p, doc=documento(declarado=None))
    r = analisis.resultado
    assert [t for t, _ in p.prompts] == ["clasificacion"]
    assert r.estado_analisis is EstadoAnalisis.completado and r.datos_extraidos == {} and r.alertas_encontradas == []
    assert r.fecha_y_modelo_utilizado.version_prompt == "clasificacion@v2"


def test_desconocido_con_declarado_cls_001_y_extrae_con_el_declarado():
    analisis, _ = ejecutar(ProveedorFalso("ollama", tipo="desconocido"))
    assert codigos(analisis.resultado) == [("CLS-001", "critica", None)]
    assert analisis.resultado.datos_extraidos["sexo"] == "F"


def test_tipo_declarado_inexistente():
    with pytest.raises(TipoNoEncontrado):
        ejecutar(ProveedorFalso("ollama", tipo="factura"), doc=documento(declarado="factura"))


# --- Respaldo y errores ---

def test_respaldo_se_usa_si_falla_el_principal_sys_005():
    principal = ProveedorFalso("ollama", falla_extraer=ErrorProveedor("timeout simulado"))
    respaldo = ProveedorFalso("respaldo")
    analisis, _ = ejecutar(principal, respaldo)
    r = analisis.resultado
    assert r.estado_analisis is EstadoAnalisis.completado
    assert codigos(r) == [("SYS-005", "informativa", None)]
    assert r.fecha_y_modelo_utilizado.proveedor == "respaldo"
    assert [i.proveedor for i in analisis.llamadas] == ["ollama", "ollama", "respaldo"]


def test_sys_005_una_sola_vez_aunque_fallen_las_dos_tareas():
    principal = ProveedorFalso("ollama", falla_clasificar=ErrorProveedor("x"), falla_extraer=ErrorProveedor("x"))
    analisis, _ = ejecutar(principal, ProveedorFalso("respaldo"))
    assert codigos(analisis.resultado) == [("SYS-005", "informativa", None)]


def test_sin_respaldo_sys_001_y_estado_error():
    analisis, _ = ejecutar(ProveedorFalso("ollama", falla_clasificar=ErrorProveedor("caido")))
    r = analisis.resultado
    assert r.estado_analisis is EstadoAnalisis.error
    assert codigos(r) == [("SYS-001", "critica", None)]
    assert r.fecha_y_modelo_utilizado is None and r.datos_extraidos == {}


def test_falla_la_extraccion_conserva_la_clasificacion():
    analisis, _ = ejecutar(ProveedorFalso("ollama", falla_extraer=ErrorProveedor("caido")))
    r = analisis.resultado
    assert r.estado_analisis is EstadoAnalisis.error and r.tipo_documental_detectado == "pasaporte"
    assert r.fecha_y_modelo_utilizado.version_prompt == "clasificacion@v2"


def test_json_invalido_prueba_el_respaldo_y_si_falla_sys_002():
    principal = ProveedorFalso("ollama", falla_extraer=ErrorRespuestaInvalida("json roto"))
    respaldo = ProveedorFalso("respaldo", falla_extraer=ErrorRespuestaInvalida("json roto"))
    analisis, _ = ejecutar(principal, respaldo)
    assert [t for t, _ in respaldo.prompts] == ["extraccion"]  # se probo el respaldo
    assert codigos(analisis.resultado) == [("SYS-002", "critica", None)]
    assert analisis.resultado.estado_analisis is EstadoAnalisis.error


def test_json_invalido_sin_respaldo_sys_002():
    analisis, _ = ejecutar(ProveedorFalso("ollama", falla_clasificar=ErrorRespuestaInvalida("json roto")))
    assert codigos(analisis.resultado) == [("SYS-002", "critica", None)]


# --- Texto recortado ---

def test_texto_recortado_sys_003():
    p = ProveedorFalso("ollama")
    analisis, _ = ejecutar(p, doc=documento(texto="A" * 15000, n_paginas=2))
    assert codigos(analisis.resultado) == [("SYS-003", "preventiva", None)]
    assert "[texto recortado]" in p.prompts[0][1]


# --- Sexo desde la MRZ ---

def test_sexo_desde_la_mrz_val_003():
    datos = {**DATOS_PASAPORTE, "sexo": None}
    analisis, _ = ejecutar(ProveedorFalso("ollama", datos=datos),
                           doc=documento(texto="PASAPORTE\nANA EJEMPLO PRUEBA", n_paginas=1))
    assert analisis.resultado.datos_extraidos["sexo"] is None  # sin MRZ en el texto: no cambia

    doc = DocumentoPreparado("id", Modalidad.pdf_digital, [Pagina(1, "PASAPORTE"), Pagina(2, f"otros datos\n{MRZ}")],
                             "pasaporte")
    analisis, _ = ejecutar(ProveedorFalso("ollama", datos=datos), doc=doc)
    r = analisis.resultado
    assert (r.datos_extraidos["sexo"], r.nivel_confianza_por_campo["sexo"], r.evidencia_por_campo["sexo"]) == (
        "F", 1.0, "pagina_2")
    assert codigos(r) == [("VAL-003", "informativa", "sexo")]


def test_sexo_desde_la_mrz_con_digitos_fallidos():
    erronea = MRZ[:-1] + "9"  # digito compuesto incorrecto
    doc = DocumentoPreparado("id", Modalidad.pdf_digital, [Pagina(1, erronea)], "pasaporte")
    analisis, _ = ejecutar(ProveedorFalso("ollama", datos={**DATOS_PASAPORTE, "sexo": None}), doc=doc)
    assert analisis.resultado.nivel_confianza_por_campo["sexo"] == 0.5


def test_sexo_leido_no_se_sustituye_por_la_mrz():
    doc = DocumentoPreparado("id", Modalidad.pdf_digital, [Pagina(1, MRZ)], "pasaporte")
    analisis, _ = ejecutar(ProveedorFalso("ollama", datos={**DATOS_PASAPORTE, "sexo": "M"}), doc=doc)
    assert analisis.resultado.datos_extraidos["sexo"] == "M" and codigos(analisis.resultado) == []


def test_registra_todas_las_llamadas_de_una_operacion():
    # Con reintento de vision, el proveedor hace dos llamadas en una sola extraccion: se registran las dos.
    class ProveedorConReintento(ProveedorFalso):
        def clasificar(self, doc, tipos_posibles, prompt):
            self.ultimas_llamadas = []
            return super().clasificar(doc, tipos_posibles, prompt)

        def extraer(self, doc, esquema_campos, prompt):
            resultado = super().extraer(doc, esquema_campos, prompt)
            texto = InfoLlamada(proveedor="ollama", modelo="texto-real", entrada="texto")
            vision = InfoLlamada(proveedor="ollama", modelo="vision-real", entrada="vision",
                                 motivo="reintento con vision")
            self.ultimas_llamadas, self.ultima_llamada = [texto, vision], vision
            return resultado

    analisis, _ = ejecutar(ProveedorConReintento("ollama"))
    assert [(i.modelo, i.entrada) for i in analisis.llamadas][-2:] == [("texto-real", "texto"), ("vision-real", "vision")]
    assert analisis.resultado.fecha_y_modelo_utilizado.modelo == "vision-real"


# --- Reintento con vision decidido por el servicio (riesgo 2 del plan) ---

INCOMPLETOS = {"nombre_completo": "ANA EJEMPLO PRUEBA", "numero_pasaporte": None, "fecha_nacimiento": None,
               "fecha_expedicion": None, "fecha_vencimiento": None, "nacionalidad": "PAIS FICTICIO", "sexo": None}


class ProveedorConVision(ProveedorFalso):
    """Extrae con texto (entrada 'texto') y, si el servicio lo pide, con vision."""

    def __init__(self, *a, datos_vision=None, falla_vision=None, entrada_extraer="texto", **k):
        super().__init__(*a, **k)
        self.datos_vision = DATOS_PASAPORTE if datos_vision is None else datos_vision
        self.falla_vision, self.entrada_extraer = falla_vision, entrada_extraer
        self.pedidos_vision: list[str] = []

    def _nueva(self, modelo, entrada, motivo=None):
        self.ultima_llamada = InfoLlamada(proveedor=self.nombre, modelo=modelo, entrada=entrada, motivo=motivo)
        self.ultimas_llamadas = [self.ultima_llamada]

    def clasificar(self, doc, tipos_posibles, prompt):
        resultado = super().clasificar(doc, tipos_posibles, prompt)
        self._nueva("modelo-texto", "texto")
        return resultado

    def extraer(self, doc, esquema_campos, prompt):
        resultado = super().extraer(doc, esquema_campos, prompt)
        self._nueva("modelo-texto" if self.entrada_extraer == "texto" else "modelo-vision", self.entrada_extraer)
        return resultado

    def extraer_con_vision(self, doc, esquema_campos, prompt, motivo=None):
        self.pedidos_vision.append(motivo)
        self._nueva("modelo-vision", "vision", motivo)
        if self.falla_vision:
            raise self.falla_vision
        datos = {c: self.datos_vision.get(c) for c in esquema_campos}
        return ResultadoExtraccion(datos, {c: 0.8 for c in datos if datos[c] is not None},
                                   {c: "pagina_1" for c in datos if datos[c] is not None})


def doc_con_imagenes(declarado="pasaporte", con_imagenes=True):
    return DocumentoPreparado("id", Modalidad.imagen,
                              [Pagina(1, texto="PASAPORTE DE MUESTRA ANA EJEMPLO PRUEBA",
                                      imagen_png=b"png-ficticio" if con_imagenes else None)], declarado)


def test_reintenta_con_vision_si_faltan_la_mitad_o_mas_de_los_obligatorios():
    p = ProveedorConVision("ollama", datos=INCOMPLETOS, datos_vision={**DATOS_PASAPORTE, "nacionalidad": None})
    analisis, _ = ejecutar(p, doc=doc_con_imagenes())
    r = analisis.resultado
    assert p.pedidos_vision == ["reintento con vision: 3/4 campos obligatorios vacios con texto"]
    assert r.datos_extraidos["numero_pasaporte"] == "X1234567P"        # manda la vision
    assert r.datos_extraidos["nacionalidad"] == "PAIS FICTICIO"        # el texto rellena lo que la vision deja vacio
    assert [(i.entrada, i.motivo) for i in analisis.llamadas][-2:] == [
        ("texto", None), ("vision", "reintento con vision: 3/4 campos obligatorios vacios con texto")]
    assert r.fecha_y_modelo_utilizado.modelo == "modelo-vision"


def test_no_reintenta_si_salta_cls_001():
    p = ProveedorConVision("ollama", tipo="comprobante_domicilio", datos=INCOMPLETOS)
    analisis, _ = ejecutar(p, doc=doc_con_imagenes(declarado="pasaporte"))
    assert p.pedidos_vision == []
    assert ("CLS-001", "critica", None) in codigos(analisis.resultado)
    assert analisis.llamadas[-1].motivo == ("sin reintento con vision (3/4 campos obligatorios vacios): "
                                            "el tipo declarado no coincide con el detectado (CLS-001)")
    assert analisis.resultado.fecha_y_modelo_utilizado.modelo == "modelo-texto"


def test_con_tipo_confirmado_si_reintenta():
    p = ProveedorConVision("ollama", tipo="comprobante_domicilio", datos=INCOMPLETOS)
    analisis, _ = ejecutar(p, doc=doc_con_imagenes(declarado="comprobante_domicilio"), tipo_confirmado="pasaporte")
    assert len(p.pedidos_vision) == 1 and codigos(analisis.resultado) == []


def test_no_reintenta_si_falta_menos_de_la_mitad():
    p = ProveedorConVision("ollama", datos={**DATOS_PASAPORTE, "fecha_vencimiento": None})
    ejecutar(p, doc=doc_con_imagenes())
    assert p.pedidos_vision == []


def test_no_reintenta_sin_imagenes():
    p = ProveedorConVision("ollama", datos=INCOMPLETOS)
    analisis, _ = ejecutar(p, doc=doc_con_imagenes(con_imagenes=False))
    assert p.pedidos_vision == [] and analisis.resultado.datos_extraidos["numero_pasaporte"] is None


def test_no_reintenta_si_la_extraccion_ya_fue_con_vision():
    p = ProveedorConVision("ollama", datos=INCOMPLETOS, entrada_extraer="vision")
    ejecutar(p, doc=doc_con_imagenes())
    assert p.pedidos_vision == []


def test_si_el_reintento_falla_se_conserva_el_texto():
    p = ProveedorConVision("ollama", datos=INCOMPLETOS, falla_vision=ErrorProveedor("vision caida"))
    analisis, _ = ejecutar(p, doc=doc_con_imagenes())
    r = analisis.resultado
    assert r.estado_analisis is EstadoAnalisis.completado and r.datos_extraidos["nombre_completo"] == "ANA EJEMPLO PRUEBA"
    assert r.fecha_y_modelo_utilizado.modelo == "modelo-texto"
    assert "fallo (vision caida): se conserva el resultado con texto" in analisis.llamadas[-1].motivo


# --- OCR pobre: reclasificacion con vision (senal 2) y reintento por formato invalido (senal 4) ---

class ProveedorConReclasificacion(ProveedorConVision):
    """Clasifica con texto como `tipo` y, si el servicio lo pide, con vision como `tipo_vision`."""

    def __init__(self, *a, tipo_vision="pasaporte", falla_clasificar_vision=None, **k):
        super().__init__(*a, **k)
        self.tipo_vision, self.falla_clasificar_vision = tipo_vision, falla_clasificar_vision
        self.reclasificaciones: list[str] = []

    def clasificar_con_vision(self, doc, tipos_posibles, prompt, motivo=None):
        self.reclasificaciones.append(motivo)
        self._nueva("modelo-vision", "vision", motivo)
        if self.falla_clasificar_vision:
            raise self.falla_clasificar_vision
        return ResultadoClasificacion(self.tipo_vision, 0.9, "vision")


MOTIVO_RECLASIFICACION = "reclasificacion con vision: la clasificacion con texto dio desconocido"
MOTIVO_EXTRACCION_VISION = "extraccion con vision: OCR pobre (la clasificacion con texto dio desconocido)"


def motivos(analisis):
    return [(i.entrada, i.motivo) for i in analisis.llamadas]


def test_desconocido_con_texto_reclasifica_con_vision_y_extrae_con_vision():
    p = ProveedorConReclasificacion("ollama", tipo="desconocido", tipo_vision="pasaporte", datos=INCOMPLETOS)
    analisis, _ = ejecutar(p, doc=doc_con_imagenes(declarado="pasaporte"))
    r = analisis.resultado
    assert p.reclasificaciones == [MOTIVO_RECLASIFICACION]
    assert r.tipo_documental_detectado == "pasaporte" and codigos(r) == []      # la vision confirma: sin CLS-001
    assert p.pedidos_vision == [MOTIVO_EXTRACCION_VISION]                        # extraccion directa con vision
    assert [t for t, _ in p.prompts] == ["clasificacion"]                         # no se extrae con texto
    assert r.datos_extraidos["numero_pasaporte"] == "X1234567P"
    assert motivos(analisis) == [("texto", None), ("vision", MOTIVO_RECLASIFICACION),
                                 ("vision", MOTIVO_EXTRACCION_VISION)]
    assert r.fecha_y_modelo_utilizado.modelo == "modelo-vision"


def test_la_vision_detecta_otro_tipo_concreto_cls_001_y_sin_reintento():
    p = ProveedorConReclasificacion("ollama", tipo="desconocido", tipo_vision="credencial_elector", datos=INCOMPLETOS)
    analisis, _ = ejecutar(p, doc=doc_con_imagenes(declarado="pasaporte"))
    r = analisis.resultado
    assert r.tipo_documental_detectado == "credencial_elector"
    assert codigos(r) == [("CLS-001", "critica", None)]
    assert p.pedidos_vision == []                                                # ni extraccion con vision ni reintento
    assert [t for t, _ in p.prompts] == ["clasificacion", "extraccion"]          # extrae con texto y la ficha declarada
    assert "el tipo declarado no coincide con el detectado (CLS-001)" in analisis.llamadas[-1].motivo


def test_la_vision_tambien_da_desconocido_cls_001_y_extrae_con_vision_la_ficha_declarada():
    p = ProveedorConReclasificacion("ollama", tipo="desconocido", tipo_vision="desconocido", datos=INCOMPLETOS)
    analisis, _ = ejecutar(p, doc=doc_con_imagenes(declarado="pasaporte"))
    assert codigos(analisis.resultado) == [("CLS-001", "critica", None)]
    assert p.pedidos_vision == [MOTIVO_EXTRACCION_VISION]
    assert analisis.resultado.datos_extraidos["numero_pasaporte"] == "X1234567P"


def test_sin_declarado_la_vision_da_el_tipo_y_se_extrae_con_esa_ficha():
    p = ProveedorConReclasificacion("ollama", tipo="desconocido", tipo_vision="pasaporte", datos=INCOMPLETOS)
    analisis, enrutador = ejecutar(p, doc=doc_con_imagenes(declarado=None))
    assert enrutador.pedidos[-1] == (Tarea.extraccion, "pasaporte")
    assert p.pedidos_vision == [MOTIVO_EXTRACCION_VISION] and codigos(analisis.resultado) == []


def test_si_falla_la_reclasificacion_se_conserva_el_texto():
    p = ProveedorConReclasificacion("ollama", tipo="desconocido", datos=INCOMPLETOS,
                                    falla_clasificar_vision=ErrorProveedor("vision caida"))
    analisis, _ = ejecutar(p, doc=doc_con_imagenes(declarado="pasaporte"))
    r = analisis.resultado
    assert r.tipo_documental_detectado == "desconocido" and ("CLS-001", "critica", None) in codigos(r)
    assert any("fallo (vision caida): se conserva la clasificacion con texto" in (i.motivo or "") for i in analisis.llamadas)
    assert r.estado_analisis is EstadoAnalisis.completado


def test_sin_imagenes_no_se_reclasifica():
    p = ProveedorConReclasificacion("ollama", tipo="desconocido", datos=INCOMPLETOS)
    ejecutar(p, doc=doc_con_imagenes(declarado="pasaporte", con_imagenes=False))
    assert p.reclasificaciones == []


def test_reintento_por_formato_invalido():
    p = ProveedorConVision("ollama", datos={**DATOS_PASAPORTE, "numero_pasaporte": "X00000015UTO9001011F"})
    analisis, _ = ejecutar(p, doc=doc_con_imagenes())
    assert p.pedidos_vision == ["reintento con vision: formato invalido en numero_pasaporte con texto"]
    assert analisis.resultado.datos_extraidos["numero_pasaporte"] == "X1234567P"


def test_reintento_por_vacios_y_formato_a_la_vez():
    datos = {**INCOMPLETOS, "fecha_expedicion": "3009/2021"}
    p = ProveedorConVision("ollama", datos=datos)
    ejecutar(p, doc=doc_con_imagenes())
    assert p.pedidos_vision == ["reintento con vision: 3/4 campos obligatorios vacios; formato invalido en "
                                "fecha_expedicion con texto"]


def test_formato_invalido_con_cls_001_concreto_no_reintenta():
    p = ProveedorConVision("ollama", tipo="comprobante_domicilio",
                           datos={**DATOS_PASAPORTE, "numero_pasaporte": "X00000015UTO9001011F"})
    analisis, _ = ejecutar(p, doc=doc_con_imagenes(declarado="pasaporte"))
    assert p.pedidos_vision == []
    assert analisis.llamadas[-1].motivo == ("sin reintento con vision (formato invalido en numero_pasaporte): "
                                            "el tipo declarado no coincide con el detectado (CLS-001)")
