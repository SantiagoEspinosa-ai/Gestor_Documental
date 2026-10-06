"""Tests de core/logs.py: el filtro tapa datos sensibles en mensajes y trazas. Datos ficticios."""
import io
import logging
import sys
import uuid

import pytest

from app.core import logs
from app.core.logs import FiltroDatosSensibles, tapar

CURP = "XEXX010101HNEXXXA4"
CLAVE_ELECTOR = "XEXXXX01010199H123"
PASAPORTE = "G12345678"
MRZ_2 = "G12345678<0MEX0101014F3001017<<<<<<<<<<<<<<02"
FOLIO = "ONB-2026-000001"


@pytest.fixture
def salida():
    """Logger propio con un handler a memoria y el filtro, como queda tras instalar()."""
    texto = io.StringIO()
    handler = logging.StreamHandler(texto)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    handler.addFilter(FiltroDatosSensibles())
    logger = logging.getLogger("app.prueba_logs")
    logger.addHandler(handler)
    logger.propagate = False
    logger.setLevel(logging.INFO)
    yield logger, texto
    logger.removeHandler(handler)
    logger.propagate = True
    logger.setLevel(logging.NOTSET)


def test_tapar():
    assert tapar(f"curp={CURP}") == "curp=****"
    assert tapar(f"clave {CLAVE_ELECTOR}.") == "clave ****."
    assert tapar(f"pasaporte {PASAPORTE} y 1A2B3C4D5") == "pasaporte **** y ****"
    assert tapar(f"mrz\n{MRZ_2}") == "mrz\n****"


def test_info_con_una_curp_no_la_deja_pasar(salida):
    logger, texto = salida
    logger.info("Valor leido %s en el folio %s", CURP, FOLIO)
    assert CURP not in texto.getvalue()
    assert FOLIO in texto.getvalue()


def test_exception_con_una_curp_tapa_mensaje_y_traza(salida):
    logger, texto = salida
    try:
        raise ValueError(f"no cuadra la curp {CURP} ni el pasaporte {PASAPORTE}")
    except ValueError:
        logger.exception("Fallo con %s", CURP)
    escrito = texto.getvalue()
    assert "Traceback" in escrito and "ValueError: no cuadra la curp **** ni el pasaporte ****" in escrito
    assert CURP not in escrito and PASAPORTE not in escrito


def test_stack_info_tapado(salida):
    logger, texto = salida
    logger.warning("aviso", stack_info=True)
    logger.warning(f"en la pila {CURP}", stack_info=True)
    assert "Stack (most recent call last)" in texto.getvalue() and CURP not in texto.getvalue()


def test_mensajes_normales_intactos(salida):
    logger, texto = salida
    identificador = str(uuid.uuid4())
    normales = [f"Documento {identificador} del folio {FOLIO}", "Webhook documento.completado entregado (HTTP 200)",
                "Alerta VAL-001 en el campo curp", "SHA-256 0f3a9c", "intento 3 a https://receptor.ejemplo.test",
                "Error no controlado en POST /api/v1/documentos/x/revelar", "MOTOR_ANALISIS=stub AES256"]
    for mensaje in normales:
        logger.info(mensaje)
    assert texto.getvalue().splitlines() == [f"INFO {m}" for m in normales]


def test_argumentos_que_no_casan_no_rompen():
    # El filtro no lanza ni descarta: el handler informa del error de formato como siempre
    assert FiltroDatosSensibles().filter(logging.makeLogRecord({"msg": "%s %s", "args": ("x",)})) is True


def test_linea_de_acceso_de_uvicorn_formateada_y_tapada():
    """El AccessFormatter de uvicorn lee los args por posicion: el filtro no puede dejarlos en None."""
    from uvicorn.logging import AccessFormatter
    texto = io.StringIO()
    handler = logging.StreamHandler(texto)
    handler.setFormatter(AccessFormatter('%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
                                         use_colors=False))
    handler.addFilter(FiltroDatosSensibles())
    logger = logging.getLogger("app.prueba_logs.access")
    logger.addHandler(handler)
    logger.propagate = False
    logger.setLevel(logging.INFO)
    errores = io.StringIO()
    stderr, logging.raiseExceptions = sys.stderr, True
    sys.stderr = errores
    try:
        # Mismo formato y args que uvicorn/protocols/http/httptools_impl.py
        logger.info('%s - "%s %s HTTP/%s" %d', "172.18.0.1:47096", "GET", f"/api/v1/buscar/{CURP}", "1.1", 401)
    finally:
        sys.stderr = stderr
        logger.removeHandler(handler)
    assert "Logging error" not in errores.getvalue()
    # El AccessFormatter anade la frase del estado HTTP
    assert texto.getvalue().strip() == 'INFO:     172.18.0.1:47096 - "GET /api/v1/buscar/**** HTTP/1.1" 401 Unauthorized'


def test_args_en_dict_tapados(salida):
    logger, texto = salida
    logger.info("curp %(curp)s del folio %(folio)s", {"curp": CURP, "folio": FOLIO})
    assert texto.getvalue().strip() == f"INFO curp **** del folio {FOLIO}"


def test_numeros_y_objetos_conservan_su_formato(salida):
    logger, texto = salida

    class Valor:
        def __str__(self):
            return f"valor {CURP}"
    logger.info("intentos %d, tiempo %.1f s, ok %s, nada %s, objeto %s", 3, 2.25, True, None, Valor())
    assert texto.getvalue().strip() == "INFO intentos 3, tiempo 2.2 s, ok True, nada None, objeto valor ****"


def test_excepcion_como_argumento_tapada(salida):
    logger, texto = salida
    logger.warning("fallo: %s", ValueError(f"curp {CURP}"))
    assert texto.getvalue().strip() == "WARNING fallo: curp ****"


def test_el_filtro_no_rompe_si_un_argumento_falla_al_convertirse():
    class Roto:
        def __str__(self):
            raise RuntimeError("no se puede")
    registro = logging.makeLogRecord({"msg": f"curp {CURP} y %s", "args": (Roto(),)})
    assert FiltroDatosSensibles().filter(registro) is True
    assert registro.msg == "curp **** y %s"  # el mensaje se tapa aunque falle un argumento


def test_instalar_en_el_raiz_sus_handlers_y_last_resort(caplog):
    logs.instalar()
    logs.instalar()  # idempotente
    raiz = logging.getLogger()
    assert raiz.filters.count(logs._FILTRO) == 1
    assert all(h.filters.count(logs._FILTRO) == 1 for h in raiz.handlers)
    assert logs._FILTRO in logging.lastResort.filters
    with caplog.at_level(logging.INFO):
        logging.getLogger("app.otro_modulo").info("curp %s", CURP)  # llega por propagacion al handler de caplog
        try:
            raise RuntimeError(CURP)
        except RuntimeError:
            logging.getLogger("app.otro_modulo").exception("fallo")
    assert CURP not in caplog.text and "curp ****" in caplog.text


def test_main_lo_instala_al_arrancar(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    llamadas = []
    monkeypatch.setattr(main.logs, "instalar", lambda: llamadas.append(1))
    monkeypatch.setattr(main.configuracion, "cargar", lambda d: (_ for _ in ()).throw(RuntimeError("corta aqui")))
    with pytest.raises(RuntimeError, match="corta aqui"):
        with TestClient(main.app):
            pass
    assert llamadas == [1]
