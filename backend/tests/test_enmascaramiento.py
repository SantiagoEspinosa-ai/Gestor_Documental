"""Tests de core/enmascaramiento.py (ADR-010 A2 y A5). Todos los datos son ficticios."""
from datetime import datetime, timezone

from app.core.enmascaramiento import enmascarar_expediente, enmascarar_resultado, enmascarar_texto, mascara
from app.schemas.resultado import (ComparacionCampo, Correccion, ReferenciaArchivoOriginal, ResultadoDocumento,
                                   ResultadoExpediente)

CURP = "XEXX010101HNEXXXA4"            # ficticia
CURP_LEIDA = "XEXX010101HNEXXXA9"      # el OCR leyo mal el ultimo caracter
PASAPORTE = "G12345678"                # ficticio
MRZ_1 = "P<MEXEJEMPLO<<ANA<<<<<<<<<<<<<<<<<<<<<<<<<<<"
MRZ_2 = "G12345678<0MEX8001014F3001017<<<<<<<<<<<<<<02"
FECHA = datetime(2026, 10, 1, tzinfo=timezone.utc)
REFERENCIA = ReferenciaArchivoOriginal(nombre_archivo="x.pdf", ruta="x/y.pdf", hash="0" * 64)


def _documento(identificador="d1", **extra) -> ResultadoDocumento:
    base = dict(folio_solicitud="ONB-2026-000001", identificador_unico_documento=identificador,
                tipo_documental_declarado="credencial_elector", tipo_documental_detectado="credencial_elector",
                estado_analisis="completado", referencia_archivo_original=REFERENCIA)
    return ResultadoDocumento(**(base | extra))


def test_mascara():
    assert mascara("ABCDEFGH1234") == "****1234"
    assert mascara("12345") == "****2345"
    assert mascara("1234") == "****"
    assert mascara("") == "****"
    assert mascara(None) is None
    assert mascara(123456) == "****3456"  # no str -> str()


def test_datos_sensibles_enmascarados_y_el_resto_intacto():
    doc = _documento(datos_extraidos={"curp": CURP, "clave_elector": None, "nombre_completo": "Ana Ejemplo"})
    salida = enmascarar_resultado(doc, {"curp", "clave_elector"})
    assert salida.datos_extraidos == {"curp": "****XXA4", "clave_elector": None, "nombre_completo": "Ana Ejemplo"}


def test_no_muta_la_entrada():
    doc = _documento(datos_extraidos={"curp": CURP}, evidencia_por_campo={"curp": "pagina_1", "otro": CURP},
                     correcciones=[Correccion(campo="curp", valor_anterior=CURP_LEIDA, valor_nuevo=CURP,
                                              usuario="revisor.demo", fecha=FECHA)])
    antes = doc.model_dump()
    salida = enmascarar_resultado(doc, {"curp"})
    assert doc.model_dump() == antes
    assert salida is not doc and salida.correcciones[0] is not doc.correcciones[0]


def test_evidencia_de_un_campo_sensible_se_conserva_si_es_una_ubicacion():
    doc = _documento(datos_extraidos={"curp": CURP, "clave_elector": "ABCDEF01234567H890"},
                     evidencia_por_campo={"curp": "pagina_1", "clave_elector": "pagina_2:seccion_superior"})
    assert enmascarar_resultado(doc, {"curp", "clave_elector"}).evidencia_por_campo == {
        "curp": "pagina_1", "clave_elector": "pagina_2:seccion_superior"}
    corregido = _documento(datos_extraidos={"curp": CURP}, evidencia_por_campo={"curp": "correccion_revisor"})
    assert enmascarar_resultado(corregido, {"curp"}).evidencia_por_campo == {"curp": "correccion_revisor"}


def test_evidencia_de_un_campo_sensible_que_no_es_una_ubicacion_se_tapa_entera():
    doc = _documento(datos_extraidos={"curp": CURP}, evidencia_por_campo={"curp": f"texto: CURP {CURP} y mas"})
    assert enmascarar_resultado(doc, {"curp"}).evidencia_por_campo == {"curp": "****"}


def test_en_todas_las_evidencias_se_tapa_el_valor_leido_y_el_corregido():
    doc = _documento(
        datos_extraidos={"curp": CURP, "domicilio": "Calle Uno"},
        evidencia_por_campo={"domicilio": f"pagina_1: junto a {CURP_LEIDA}", "nombre": f"pagina_1:{CURP}"},
        correcciones=[Correccion(campo="curp", valor_anterior=CURP_LEIDA, valor_nuevo=CURP,
                                 usuario="revisor.demo", fecha=FECHA)])
    evidencias = enmascarar_resultado(doc, {"curp"}).evidencia_por_campo
    assert evidencias == {"domicilio": "pagina_1: junto a ****XXA9", "nombre": "pagina_1:****XXA4"}


def test_correcciones_de_campos_sensibles_enmascaradas():
    doc = _documento(
        datos_extraidos={"curp": CURP, "domicilio": "Calle Dos"},
        correcciones=[Correccion(campo="curp", valor_anterior=CURP_LEIDA, valor_nuevo=CURP, usuario="r", fecha=FECHA),
                      Correccion(campo="curp", valor_anterior=None, valor_nuevo=CURP, usuario="r", fecha=FECHA),
                      Correccion(campo="domicilio", valor_anterior="Calle Uno", valor_nuevo="Calle Dos",
                                 usuario="r", fecha=FECHA)])
    correcciones = enmascarar_resultado(doc, {"curp"}).correcciones
    assert [(c.valor_anterior, c.valor_nuevo) for c in correcciones] == [
        ("****XXA9", "****XXA4"), (None, "****XXA4"), ("Calle Uno", "Calle Dos")]


def test_pasaporte_con_mrz():
    doc = _documento(
        tipo_documental_declarado="pasaporte",
        datos_extraidos={"numero_pasaporte": PASAPORTE, "sexo": "F"},
        evidencia_por_campo={"numero_pasaporte": "pagina_1", "sexo": f"pagina_1:\n{MRZ_1}\n{MRZ_2}"})
    salida = enmascarar_resultado(doc, {"numero_pasaporte"})
    assert salida.datos_extraidos == {"numero_pasaporte": "****5678", "sexo": "F"}
    assert salida.evidencia_por_campo["sexo"] == f"pagina_1:\n{MRZ_1}\n****"  # la linea 1 se queda
    assert PASAPORTE not in salida.model_dump_json()


def test_la_linea_2_de_la_mrz_se_tapa_aunque_no_coincida_con_el_valor_y_sin_campos_sensibles():
    otra_linea_2 = "X98765432<1MEX9001014M3001017<<<<<<<<<<<<<<04"  # numero mal leido: no es el valor
    doc = _documento(datos_extraidos={"numero_pasaporte": PASAPORTE},
                     evidencia_por_campo={"fecha": f"pagina_1:{otra_linea_2}"})
    assert enmascarar_resultado(doc, set()).evidencia_por_campo == {"fecha": "pagina_1:****"}


def test_un_texto_corto_de_mayusculas_no_es_mrz():
    doc = _documento(evidencia_por_campo={"x": "pagina_1:SECCION_SUPERIOR", "y": "pagina_1:ABC<<DEF"})
    assert enmascarar_resultado(doc, set()).evidencia_por_campo == doc.evidencia_por_campo


def test_expediente_documentos_y_comparaciones():
    credencial = _documento("d1", datos_extraidos={"curp": CURP, "domicilio": "Calle Uno"})
    otro = _documento("d2", tipo_documental_declarado="comprobante_domicilio",
                      datos_extraidos={"curp": CURP, "domicilio": "Calle Uno"})
    expediente = ResultadoExpediente(
        folio="ONB-2026-000001", proceso="onboarding", estado_general="en_revision", documentos=[credencial, otro],
        comparaciones=[ComparacionCampo(campo="curp", coincide=True, valores={"d1": CURP, "d2": CURP}),
                       ComparacionCampo(campo="domicilio", coincide=True, valores={"d1": "Calle Uno", "d2": "Calle Uno"})])
    antes = expediente.model_dump()
    # La curp solo es sensible en la ficha de d1: en la comparacion se tapan todos sus valores
    salida = enmascarar_expediente(expediente, {"d1": {"curp"}})
    assert expediente.model_dump() == antes
    assert salida.documentos[0].datos_extraidos["curp"] == "****XXA4"
    assert salida.documentos[1].datos_extraidos["curp"] == CURP  # en d2 no es sensible
    assert salida.comparaciones[0].valores == {"d1": "****XXA4", "d2": "****XXA4"}
    assert salida.comparaciones[1].valores == {"d1": "Calle Uno", "d2": "Calle Uno"}


def test_enmascarar_texto_literales_del_documento_y_la_barrera_de_los_logs():
    # Un literal sin forma de dato sensible solo se tapa por ser del documento (mascara, con su cola);
    # lo que tiene forma de CURP se tapa siempre, con **** sin cola (logs.tapar)
    texto = "Clave ab12cd34 y CURP XAXX020202MDFYYYA5; URGENTE"
    assert enmascarar_texto(texto, ["ab12cd34"]) == "Clave ****cd34 y CURP ****; URGENTE"
    assert enmascarar_texto("texto normal", []) == "texto normal"
    # Sin distinguir mayusculas: el literal del documento y la barrera de los logs
    assert enmascarar_texto("clave AB12CD34 y curp xaxx020202mdfyyya5, urgente", ["ab12cd34"]) ==         "clave ****cd34 y curp ****, urgente"
