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


# --- Variantes de lectura (2026-10-08, fuera de la linea base del hito): solo si estan generadas ---

def _variante(nombre: str):
    ruta = FIXTURES / nombre
    if not ruta.is_file():
        pytest.skip(f"sin la variante {nombre} (regenera los fixtures con scripts/generar_fixtures.py)")
    return preparar(ruta.read_bytes(), nombre)


@pytest.mark.parametrize("modalidad", ["digital", "escaneado"])
@pytest.mark.parametrize("variante", ["mes_abreviado", "mes_completo", "mes_anio_corto"])
def test_variante_fecha_con_el_mes_en_letras_se_lee(variante, modalidad):
    from app.modulos.motor_ia.confianza import _fechas_del_texto, texto_del_documento
    doc = _variante(f"comprobante_domicilio_sano_{modalidad}_{variante}.pdf")
    assert "2026-09-15" in _fechas_del_texto(texto_del_documento(doc.paginas))  # --hoy 2026-09-30, emision -15


def test_variante_recibo_sin_recibo_cumple_los_marcadores():
    from app.modulos.configuracion import servicio as configuracion
    from app.modulos.motor_ia.confianza import confianza_clasificacion, texto_del_documento
    doc = _variante("comprobante_domicilio_sano_digital_sin_recibo.pdf")
    assert confianza_clasificacion(configuracion.obtener("comprobante_domicilio"),
                                   texto_del_documento(doc.paginas)) == 1.0


@pytest.mark.parametrize("nombre", ["pasaporte_sano_digital_mrz_ruido.pdf", "pasaporte_sano_foto_mrz_ruido.jpg"])
def test_variante_mrz_con_ruido_solo_se_lee_reparandola(nombre):
    from app.modulos.orquestador import mrz as modulo_mrz
    doc = _variante(nombre)
    texto = "\n".join(p.texto or "" for p in doc.paginas)
    mrz = buscar_mrz(texto)
    assert mrz is not None and all(validar_digitos(mrz).values())
    # Sin la reparacion (solo la busqueda exacta de antes) no habria MRZ: el fixture de verdad la pone a prueba
    lineas = [re.sub(r"\s+", "", l).upper() for l in texto.splitlines() if l.strip()]
    exactas = [(a, b) for a, b in zip(lineas, lineas[1:])
               if a.startswith("P") and modulo_mrz._CARACTERES.match(a) and modulo_mrz._CARACTERES.match(b)]
    assert exactas == []
