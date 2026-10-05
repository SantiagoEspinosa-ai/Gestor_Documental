"""Fixtures comunes a todos los tests.

MOTOR_ANALISIS=stub en todos (H10): ningun test llama al motor real ni a Ollama sin querer. Los que prueban
el motor real lo cambian y sustituyen el orquestador por uno falso.

`expediente.servicio` regenera el resumen.md en S3 despues de cada cambio (etapa 3). Para que ningun
test llame a AWS sin querer, su almacenamiento se sustituye en cada test por uno en memoria. Solo ese
punto: la ingesta (subidas y descargas de originales) y los tests que usan moto no cambian. Un test que
quiera el resumen en moto, o un almacenamiento roto, vuelve a parchear `expediente.servicio._almacenamiento`.
"""
import pytest

from app.core.almacenamiento import ObjetoNoEncontrado
from app.modulos.expediente import servicio as expediente


class AlmacenamientoEnMemoria:
    """Lo minimo que usa expediente.servicio: subir_derivado y descargar."""

    def __init__(self):
        self.objetos: dict[str, tuple[bytes, str]] = {}

    def subir_derivado(self, datos: bytes, clave: str, tipo_contenido: str) -> None:
        self.objetos[clave] = (datos, tipo_contenido)

    def descargar(self, clave: str) -> bytes:
        if clave not in self.objetos:
            raise ObjetoNoEncontrado(f"No existe el objeto '{clave}'")
        return self.objetos[clave][0]


@pytest.fixture(autouse=True)
def motor_stub(monkeypatch):
    monkeypatch.setenv("MOTOR_ANALISIS", "stub")


@pytest.fixture(autouse=True)
def almacenamiento_resumen(monkeypatch) -> AlmacenamientoEnMemoria:
    memoria = AlmacenamientoEnMemoria()
    monkeypatch.setattr(expediente, "_almacenamiento", lambda: memoria)
    return memoria
