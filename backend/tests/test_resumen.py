"""Tests de expediente/resumen.py (generacion pura del resumen.md). Datos ficticios."""
from datetime import datetime, timezone

from app.modulos.expediente import resumen
from app.modulos.expediente.resumen import escapar, generar
from app.schemas.resultado import (Alerta, ComparacionCampo, Correccion, ReferenciaArchivoOriginal,
                                   ResultadoDocumento, ResultadoExpediente)

GENERADO = datetime(2026, 10, 5, 8, 0, tzinfo=timezone.utc)
FICHAS = {"credencial_elector": {"nombre_visible": "Credencial de elector",
                                 "campos": {"nombre_completo": {}, "curp": {}, "domicilio": {}}}}
NOMBRE = "Ana Ejemplo Prueba"  # persona ficticia
REFERENCIA_FICHERO = ReferenciaArchivoOriginal(nombre_archivo="ana_ejemplo_credencial.pdf", ruta="x/y.pdf", hash="0" * 64)


def _documento(identificador, declarado, detectado, datos=None, **extra):
    return ResultadoDocumento(folio_solicitud="ONB-2026-000001", identificador_unico_documento=identificador,
                              tipo_documental_declarado=declarado, tipo_documental_detectado=detectado,
                              datos_extraidos=datos or {}, estado_analisis="completado",
                              referencia_archivo_original=REFERENCIA_FICHERO, **extra)


def _expediente(**cambios) -> ResultadoExpediente:
    credencial = _documento(
        "d1", "credencial_elector", "credencial_elector",
        {"nombre_completo": f"{NOMBRE} | Segundo\nrenglon", "curp": None},
        correcciones=[Correccion(campo="nombre_completo", valor_anterior="X", valor_nuevo=NOMBRE, usuario="revisor.demo",
                                 fecha=datetime(2026, 10, 1, tzinfo=timezone.utc))],
        alertas_encontradas=[Alerta(codigo="VAL-001", mensaje="Falta curp", severidad="critica", confianza=1.0,
                                    campo="curp")])
    desconocido = _documento("d2", None, "desconocido")
    base = dict(folio="ONB-2026-000001", proceso="onboarding", referencia_externa="CLI-000101",
                fecha_solicitud=datetime(2026, 10, 1, 9, 15, tzinfo=timezone.utc), estado_general="aprobado",
                documentos=[credencial, desconocido],
                comparaciones=[ComparacionCampo(campo="domicilio", coincide=False, valores={"d1": "Calle *Uno*", "d2": None})],
                alertas_expediente=[Alerta(codigo="EXP-001", mensaje="Falta el documento requerido: Pasaporte",
                                           severidad="bloqueante", confianza=1.0, campo="pasaporte", aplica=False)],
                recomendacion_global="revision_manual", decision_humana="aprobar", comentario_decision="Todo <b>ok</b>",
                usuario_decision="revisor.demo", fecha_decision=datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc))
    return ResultadoExpediente(**(base | cambios))


ESPERADO = """\
# Expediente ONB-2026-000001

- Referencia: CLI-000101
- Proceso: onboarding
- Fecha de solicitud: 2026-10-01 09:15 UTC
- Estado: Aprobado
- Recomendacion global: Revision manual

## Decision

- Decision: Aprobado
- Comentario: Todo \\<b\\>ok\\</b\\>
- Usuario: revisor.demo
- Fecha: 2026-10-02 12:00 UTC

## Documentos

### Documento 1: Credencial de elector

- Estado del analisis: Completado

| Campo | Valor | Nota |
| --- | --- | --- |
| Nombre completo | Ana Ejemplo Prueba \\| Segundo renglon | corregido por revisor |
| Curp | no detectado |  |
| Domicilio | no detectado |  |

Criticas:
- VAL-001 (curp): Falta curp (sin revisar)

### Documento 2: Tipo no reconocido

- Estado del analisis: Completado

Sin datos extraidos.

Sin alertas.

## Alertas del expediente

Bloqueantes:
- EXP-001 (pasaporte): Falta el documento requerido: Pasaporte (falso positivo)

## Comparaciones

| Campo | Coincide | Valores |
| --- | --- | --- |
| Domicilio | No | documento 1: Calle \\*Uno\\*; documento 2: no detectado |

Generado el 2026-10-05 08:00 UTC
"""


def test_salida_esperada_con_fecha_fija():
    assert generar(_expediente(), FICHAS, GENERADO) == ESPERADO


def test_es_determinista():
    assert generar(_expediente(), FICHAS, GENERADO) == generar(_expediente(), FICHAS, GENERADO)


def test_un_valor_con_barra_y_salto_de_linea_no_rompe_la_tabla():
    texto = generar(_expediente(), FICHAS, GENERADO)
    [fila] = [linea for linea in texto.splitlines() if linea.startswith("| Nombre completo")]
    # 4 separadores de columna sin escapar: la fila sigue teniendo 3 columnas
    assert fila.replace("\\|", "").count("|") == 4
    assert "Segundo renglon" in fila  # el salto de linea pasa a espacio, en la misma fila


def test_el_nombre_no_sale_en_la_cabecera_ni_el_fichero_en_ningun_sitio():
    texto = generar(_expediente(), FICHAS, GENERADO)
    cabecera = texto.split("## Documentos")[0]
    assert "Ana" not in cabecera
    assert cabecera.startswith("# Expediente ONB-2026-000001\n")
    assert "CLI-000101" in cabecera  # se identifica por la referencia
    assert "ana_ejemplo_credencial" not in texto


def test_desconocido_sale_como_tipo_no_reconocido_y_sin_tipo_si_no_hay():
    texto = generar(_expediente(), FICHAS, GENERADO)
    assert "### Documento 2: Tipo no reconocido" in texto
    assert "desconocido" not in texto
    sin_tipo = _expediente(documentos=[_documento("d3", None, None)], comparaciones=[])
    assert "### Documento 1: Sin tipo" in generar(sin_tipo, FICHAS, GENERADO)


def test_sin_referencia_sin_decision_y_sin_documentos():
    texto = generar(_expediente(referencia_externa=None, decision_humana=None, comentario_decision=None,
                                usuario_decision=None, fecha_decision=None, documentos=[], comparaciones=[],
                                alertas_expediente=[], estado_general="en_revision"), FICHAS, GENERADO)
    assert "- Referencia: sin referencia" in texto
    assert "## Decision" not in texto
    assert "Sin documentos." in texto
    assert "Sin alertas del expediente." in texto and "Sin comparaciones." in texto


def test_escapar():
    assert escapar("a|b`c*d_e[f]g<h>i\\j") == "a\\|b\\`c\\*d\\_e\\[f\\]g\\<h\\>i\\\\j"
    assert escapar("uno\ndos\r\ntres") == "uno dos tres"


def test_los_datos_pasan_por_enmascarar_para_resumen(monkeypatch):
    vistos = []

    def tapar(datos, ficha):
        vistos.append(dict(datos))
        return {campo: "****" if valor is not None else None for campo, valor in datos.items()}
    monkeypatch.setattr(resumen, "enmascarar_para_resumen", tapar)
    texto = generar(_expediente(), FICHAS, GENERADO)
    assert NOMBRE not in texto and "Calle" not in texto  # datos de los documentos y de las comparaciones
    assert vistos  # se ha llamado
