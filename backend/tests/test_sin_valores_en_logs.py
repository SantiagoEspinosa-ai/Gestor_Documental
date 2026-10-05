"""ADR-010 (A5, H15): los logs del motor y datos_auditoria no llevan valores de los campos, ni sensibles ni otros.
Sin BD ni modelo: preparar y el proveedor son falsos. Datos ficticios."""
import json
import logging

import pytest

from app.modulos.motor_ia.proveedores.base import ErrorProveedor, ErrorRespuestaInvalida
from tests.test_procesar_documento import procesar
from tests.test_servicio_motor import DATOS_PASAPORTE, MRZ, TEXTO_PASAPORTE, ProveedorFalso

VALORES = [v for v in DATOS_PASAPORTE.values() if len(str(v)) > 2]  # "F" de sexo aparece en cualquier texto
SENSIBLES = ["X1234567P"]                                           # numero_pasaporte (sensible: true)


def _sin_valores(texto: str):
    for valor in VALORES + SENSIBLES:
        assert str(valor) not in texto, f"valor de un campo en la salida: {valor!r}"


@pytest.mark.parametrize("proveedor", [
    ProveedorFalso("ollama"),
    ProveedorFalso("ollama", falla_extraer=ErrorProveedor("caido")),
    ProveedorFalso("ollama", falla_extraer=ErrorRespuestaInvalida("json roto")),
    ProveedorFalso("ollama", datos={**DATOS_PASAPORTE, "sexo": None}),  # sexo desde la MRZ
], ids=["normal", "proveedor_caido", "json_invalido", "mrz"])
def test_logs_y_datos_auditoria_sin_valores(proveedor, monkeypatch, caplog):
    from app.modulos.motor_ia.interfaces import DocumentoPreparado, Modalidad, Pagina
    from app.modulos.orquestador import procesamiento
    monkeypatch.setattr(procesamiento, "preparar", lambda contenido, nombre, tipo=None, *, identificador=None, ocr=None:
                        DocumentoPreparado(identificador, Modalidad.pdf_digital,
                                           [Pagina(1, f"{TEXTO_PASAPORTE}\n{MRZ}")], tipo))
    with caplog.at_level(logging.DEBUG):
        resultado, auditoria = procesar(proveedor)
    _sin_valores(json.dumps(auditoria, ensure_ascii=False))
    _sin_valores("\n".join(r.getMessage() for r in caplog.records))
    assert resultado.datos_extraidos or resultado.estado_analisis.value == "error"  # el valor si esta en el resultado
