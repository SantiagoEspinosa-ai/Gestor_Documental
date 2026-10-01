"""
Integracion con los fixtures ficticios de PERSONA_3 y el Tesseract real: preparar() no debe quedar por
debajo de la linea base (150/153 campos) y la MRZ debe dar el sexo y detectar lecturas erroneas.
Solo se usan los casos y el nivel conocidos (normal: digital, escaneado y foto de sano, vencido y
domicilio_distinto): si PERSONA_3 anade fixtures o niveles nuevos, este test no cambia.
Se salta si no hay fixtures (no estan en git). Ejecucion: docs/motor_ia/SPEC_CONFIGURACION.md, seccion 8.
"""
import os
import re
import shutil
import unicodedata
from pathlib import Path

import pytest

from app.modulos.orquestador.mrz import buscar_mrz, validar_digitos
from app.modulos.orquestador.preparador import preparar

# Linea base: 150 de 153 campos (scripts/verificar_ocr_fixtures.py de PERSONA_3, 2026-09-30), es decir, como
# mucho 3 campos sin encontrar en los casos conocidos.
MAX_NO_ENCONTRADOS = 3
CASOS_CONOCIDOS = {"sano", "vencido", "domicilio_distinto"}
NIVEL_NORMAL = re.compile(r".+_(digital|escaneado|foto)\.(pdf|jpg)")  # sin sufijo _dificil / _extremo


def _dir_fixtures() -> Path:
    candidatos = [os.environ.get("FIXTURES_DIR"), "/fixtures/generados",
                  Path(__file__).resolve().parents[2] / "fixtures" / "generados"]
    return next((Path(c) for c in candidatos if c and (Path(c) / "INDICE.md").is_file()), Path("/no-hay-fixtures"))


FIXTURES = _dir_fixtures()
pytestmark = [
    pytest.mark.skipif(not (FIXTURES / "INDICE.md").is_file(), reason="sin fixtures generados"),
    pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract no instalado"),
]


def _normalizar(texto: str) -> str:
    plano = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(plano.upper().split())


def _contiene(esperado: str, texto: str) -> bool:
    return re.search(rf"(?<![A-Z0-9]){re.escape(esperado)}(?![A-Z0-9])", texto) is not None


def _indice() -> dict[str, dict]:
    """{archivo: {caso, tipo, campos (como aparecen en el documento), mrz}} a partir de INDICE.md."""
    documentos, actual, en_mrz = {}, None, False
    for linea in (FIXTURES / "INDICE.md").read_text(encoding="utf-8").splitlines():
        if m := re.match(r"^### (\S+) / (\S+)$", linea):
            actual, en_mrz = {"caso": m[1], "tipo": m[2], "campos": {}, "mrz": []}, False
        elif linea.startswith("## "):
            actual = None
        elif actual is None:
            continue
        elif "Archivos:" in linea:
            for archivo in re.findall(r"`([^`]+)`", linea.split("Archivos:")[1]):
                documentos[archivo] = actual
        elif m := re.match(r"^\| `(\w+)` \| (.+) \|$", linea):
            valor = m[2].strip()
            if f := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", valor):
                valor = f"{f[3]}/{f[2]}/{f[1]}"  # en el documento: DD/MM/AAAA
            actual["campos"][m[1]] = valor
        elif linea == "```":
            en_mrz = not en_mrz
        elif en_mrz:
            actual["mrz"].append(linea)
    return {a: d for a, d in documentos.items() if d["caso"] in CASOS_CONOCIDOS and NIVEL_NORMAL.fullmatch(a)}


@pytest.fixture(scope="module")
def preparados():
    return {archivo: (datos, preparar((FIXTURES / archivo).read_bytes(), archivo))
            for archivo, datos in _indice().items()}


def test_no_baja_de_la_linea_base(preparados):
    encontrados, total, fallos = 0, 0, []
    for archivo, (datos, doc) in preparados.items():
        texto = _normalizar("\n".join(p.texto or "" for p in doc.paginas))
        for campo, valor in datos["campos"].items():
            total += 1
            if _contiene(_normalizar(valor), texto):
                encontrados += 1
            else:
                fallos.append(f"{archivo}:{campo}")
    assert len(preparados) == 3 * 3 * len(CASOS_CONOCIDOS) and total > 0   # 3 tipos x 3 modalidades por caso
    assert total - encontrados <= MAX_NO_ENCONTRADOS, f"{encontrados}/{total}; no encontrados: {fallos}"


def test_modalidades_de_los_fixtures(preparados):
    for archivo, (_, doc) in preparados.items():
        esperada = {"digital": "pdf_digital", "escaneado": "pdf_escaneado", "foto": "imagen"}[
            re.search(r"_(digital|escaneado|foto)\.", archivo)[1]]
        assert doc.modalidad.value == esperada, archivo
        assert all(p.imagen_png for p in doc.paginas), archivo


def test_mrz_de_los_pasaportes(preparados):
    for archivo, (datos, doc) in preparados.items():
        if datos["tipo"] != "pasaporte":
            continue
        mrz = buscar_mrz("\n".join(p.texto or "" for p in doc.paginas))
        assert mrz is not None, archivo
        digitos_ok = all(validar_digitos(mrz).values())
        if [mrz.linea1, mrz.linea2] == datos["mrz"]:
            assert digitos_ok, archivo           # lectura correcta -> digitos correctos
        else:
            assert not digitos_ok, archivo       # lectura erronea (p. ej. Z/2) -> se detecta
        if mrz.linea2[20] == datos["mrz"][1][20]:
            assert mrz.sexo == datos["campos"]["sexo"], archivo


def test_sexo_de_pasaporte_vencido_se_recupera_de_la_mrz(preparados):
    # La zona visual no da el sexo "M" suelto (fallo conocido de la linea base); la MRZ si.
    vencidos = [doc for archivo, (_, doc) in preparados.items() if archivo.startswith("pasaporte_vencido_")]
    assert len(vencidos) == 3
    sexos = [buscar_mrz("\n".join(p.texto or "" for p in doc.paginas)).sexo for doc in vencidos]
    assert sexos.count("M") >= 2, sexos
