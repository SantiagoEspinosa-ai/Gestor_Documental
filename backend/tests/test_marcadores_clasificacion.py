"""Marcadores de clasificacion del comprobante (ADR-007): las alternativas del 2026-10-08 (FECHA LIMITE DE PAGO,
SERVICIO, CONSUMO) no bajan la confianza de ningun comprobante, no suben la de los otros tipos y no cambian el
tipo que dan los marcadores en ningun fixture. Con los fixtures ficticios y el Tesseract real (como
test_fixtures_ocr.py); sin ellos, se salta. El tipo detectado por el modelo tampoco puede cambiar: los
marcadores no van en el prompt (formatear_tipos solo usa descripcion y caracteristicas)."""
import re
import shutil

import pytest

from app.modulos.configuracion import servicio as configuracion
from app.modulos.configuracion.servicio import FLAGS_MARCADORES
from app.modulos.motor_ia.confianza import confianza_clasificacion, texto_del_documento
from app.modulos.orquestador.preparador import preparar
from tests.test_fixtures_ocr import FIXTURES

# Los del comprobante antes del 2026-10-08
MARCADORES_ANTES = [
    r"COMPROBANTE\s*(DE\s*)?DOMICILIO|\bRECIBO\b|ESTADO\s*DE\s*CUENTA",
    r"FECHA\s*(DE\s*)?EMISION|\bPERIODO\b",
    r"\bDOMICILIO\b",
    r"\bTOTAL\b|\bIMPORTE\b",
    r"\bTITULAR\b",
]

pytestmark = [
    pytest.mark.skipif(not (FIXTURES / "INDICE.md").is_file(), reason="sin fixtures generados"),
    pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract no instalado"),
]


def _confianza(marcadores: list[str], texto: str) -> float:
    return round(sum(re.search(m, texto, FLAGS_MARCADORES) is not None for m in marcadores) / len(marcadores), 3)


@pytest.fixture(scope="module")
def textos() -> dict[str, str]:
    archivos = sorted(p for p in FIXTURES.iterdir() if p.suffix.lower() in (".pdf", ".jpg", ".png"))
    return {p.name: texto_del_documento(preparar(p.read_bytes(), p.name).paginas) for p in archivos}


def test_se_conservan_los_marcadores_de_antes_como_alternativas():
    nuevos = configuracion.obtener("comprobante_domicilio").marcadores_clasificacion
    assert len(nuevos) == len(MARCADORES_ANTES)  # alternativas dentro, no marcadores nuevos
    for antes, ahora in zip(MARCADORES_ANTES, nuevos):
        assert ahora == antes or ahora.startswith(antes + "|")


def test_ningun_comprobante_baja_y_ningun_otro_tipo_sube(textos):
    ficha = configuracion.obtener("comprobante_domicilio")
    bajan, suben = [], []
    for archivo, texto in textos.items():
        antes, ahora = _confianza(MARCADORES_ANTES, texto), confianza_clasificacion(ficha, texto)
        if archivo.startswith("comprobante_domicilio") and ahora < antes:
            bajan.append((archivo, antes, ahora))
        if not archivo.startswith("comprobante_domicilio") and ahora > antes:
            suben.append((archivo, antes, ahora))
    assert bajan == [] and suben == []


def test_ningun_fixture_cambia_de_tipo_por_marcadores(textos):
    fichas = {f.nombre: f for f in configuracion.listar()}

    def tipo(texto: str, antes: bool) -> str:
        def valor(nombre: str) -> float:
            if antes and nombre == "comprobante_domicilio":
                return _confianza(MARCADORES_ANTES, texto)
            return confianza_clasificacion(fichas[nombre], texto)
        return max(sorted(fichas), key=valor)

    cambian = [a for a, texto in textos.items() if tipo(texto, antes=True) != tipo(texto, antes=False)]
    assert cambian == []


def test_un_recibo_sin_recibo_ni_comprobante_ya_cumple_los_marcadores():
    ficha = configuracion.obtener("comprobante_domicilio")
    texto = ("SERVICIOS DE EJEMPLO S.A. - AVISO DE SERVICIO\nNOMBRE TITULAR\nANA EJEMPLO PRUEBA\nDOMICILIO\n"
             "CALLE FICTICIA 123\nFECHA LIMITE DE PAGO\n30/09/2026\nCONSUMO DEL PERIODO\nTOTAL 100.00")
    assert _confianza(MARCADORES_ANTES, texto) == 0.8
    assert confianza_clasificacion(ficha, texto) == 1.0
