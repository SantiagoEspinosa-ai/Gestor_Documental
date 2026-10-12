"""Comparacion del nombre entre documentos sin depender del orden (validacion/comparaciones.py, 2026-10-12).
Datos ficticios. El resto de campos se compara como antes."""
from app.modulos.configuracion import servicio as configuracion
from app.modulos.validacion import servicio as validacion
from app.modulos.validacion.comparaciones import DocumentoComparable


# --- 3. Comparacion del nombre entre documentos, sin depender del orden ---

FICHAS = [f.model_dump(mode="json") for f in configuracion.listar()]


def comparar_nombres(pasaporte: str, credencial: str, campo: str = "nombre_completo"):
    documentos = [DocumentoComparable("p", "pasaporte", {campo: pasaporte}),
                  DocumentoComparable("c", "credencial_elector", {campo: credencial})]
    return {c.campo: c.coincide for c in validacion.comparar(documentos, FICHAS)}[campo]


def test_el_mismo_nombre_en_distinto_orden_coincide():
    assert comparar_nombres("EJEMPLO PRUEBA ANA", "ANA EJEMPLO PRUEBA")
    assert comparar_nombres("Ejemplo-Prueba, Ana", "ÁNA EJEMPLO PRUEBA")  # sin signos ni acentos


def test_falta_un_apellido_o_cambia_una_palabra_no_coincide():
    assert not comparar_nombres("ANA EJEMPLO", "ANA EJEMPLO PRUEBA")
    assert not comparar_nombres("ANA EJEMPLO PRUEVA", "ANA EJEMPLO PRUEBA")
    assert not comparar_nombres("ANA ANA EJEMPLO", "ANA EJEMPLO")  # una palabra repetida no se pierde


def test_los_demas_campos_siguen_comparandose_como_antes():
    # El domicilio no se reordena: el mismo texto en otro orden NO coincide
    documentos = [DocumentoComparable("c", "credencial_elector", {"domicilio": "CALLE FICTICIA 123, COLONIA DEMO"}),
                  DocumentoComparable("d", "comprobante_domicilio", {"domicilio": "COLONIA DEMO, CALLE FICTICIA 123"})]
    assert {c.campo: c.coincide for c in validacion.comparar(documentos, FICHAS)}["domicilio"] is False
