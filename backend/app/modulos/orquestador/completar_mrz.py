"""
MRZ del pasaporte para el analisis: la verificacion que usa la confianza calculada (ADR-007) y el sexo cuando la
extraccion no lo trae (VAL-003). Vive en el orquestador para que motor_ia no lo importe (spec, seccion 11).
"""
from __future__ import annotations

from app.modulos.configuracion.servicio import TipoDocumental
from app.modulos.motor_ia import servicio as motor_ia
from app.modulos.motor_ia.interfaces import DocumentoPreparado
from app.modulos.orquestador.mrz import buscar_mrz, validar_digitos
from app.schemas.resultado import Alerta, ResultadoDocumento, Severidad


def verificacion_mrz(doc: DocumentoPreparado) -> motor_ia.VerificacionMrz | None:
    """La primera MRZ del documento: sus valores, sus digitos de control y la pagina donde esta."""
    for pagina in doc.paginas:
        mrz = buscar_mrz(pagina.texto)
        if mrz is not None:
            return motor_ia.VerificacionMrz(mrz.numero_documento, mrz.fecha_nacimiento, mrz.fecha_vencimiento,
                                            mrz.sexo, validar_digitos(mrz), pagina.numero)
    return None


def completar_sexo(resultado: ResultadoDocumento, doc: DocumentoPreparado, ficha: TipoDocumental,
                   mrz: motor_ia.VerificacionMrz | None) -> ResultadoDocumento:
    """Solo pasaporte y solo si `sexo` llega vacio: el de la MRZ (posicion 21 de la linea 2), evidencia
    `pagina_<n>`, VAL-003 (informativa) y su confianza calculada (1,0 si los digitos cuadran; como mucho 0,5 si no)."""
    if (ficha.nombre != "pasaporte" or "sexo" not in ficha.campos or mrz is None or mrz.sexo is None
            or resultado.datos_extraidos.get("sexo") is not None):
        return resultado
    datos = {**resultado.datos_extraidos, "sexo": mrz.sexo}
    confianza = motor_ia.confianzas_de_campos({"sexo": mrz.sexo}, ficha, motor_ia.texto_del_documento(doc.paginas),
                                              mrz)["sexo"]
    alertas = list(resultado.alertas_encontradas)
    if not any(a.codigo == "VAL-003" and a.campo == "sexo" for a in alertas):
        alertas.append(Alerta(codigo="VAL-003", severidad=Severidad.informativa, confianza=1.0, campo="sexo",
                              mensaje="El valor del campo se ha tomado de la MRZ porque no se leyo en la zona visual"))
    return resultado.model_copy(update={
        "datos_extraidos": datos,
        "nivel_confianza_por_campo": {**resultado.nivel_confianza_por_campo, "sexo": confianza},
        "evidencia_por_campo": {**resultado.evidencia_por_campo, "sexo": f"pagina_{mrz.pagina or 1}"},
        "alertas_encontradas": alertas,
    })
