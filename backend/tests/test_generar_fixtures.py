"""Tests de scripts/generar_fixtures.py (PERSONA_3). Solo datos ficticios."""
import copy
import importlib.util
from datetime import date, timedelta
from pathlib import Path

import pytest

RAIZ_REPO = Path(__file__).resolve().parents[2]
RUTA_SCRIPT = RAIZ_REPO / "scripts" / "generar_fixtures.py"
DIR_TIPOS = RAIZ_REPO / "config" / "tipos"
# El contenedor del backend solo monta ./backend, ./config en /config y ./prompts: sin el script
# (o sin config/tipos junto a el) estos tests no aplican. Se ejecutan desde la raiz del repo.
if not RUTA_SCRIPT.is_file() or not DIR_TIPOS.is_dir():
    pytest.skip(f"Tests del generador de fixtures omitidos: no se encuentra {RUTA_SCRIPT} o {DIR_TIPOS} "
                "(normal dentro del contenedor del backend; ejecutalos desde el repo completo)",
                allow_module_level=True)

import pymupdf  # noqa: E402
from PIL import Image  # noqa: E402

_spec = importlib.util.spec_from_file_location("generar_fixtures", RUTA_SCRIPT)
gf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gf)

HOY = date(2026, 9, 30)
TIPOS = ("pasaporte", "credencial_elector", "comprobante_domicilio")


@pytest.fixture(scope="module")
def fichas():
    return gf.cargar_fichas()


@pytest.fixture(scope="module")
def generado(tmp_path_factory):
    """Una generacion completa compartida por los tests que solo leen ficheros."""
    salida = tmp_path_factory.mktemp("fixtures")
    return salida, gf.generar(HOY, salida)


def alertas_de(folio, fichas):
    documentos = {}
    for caso, definicion in gf.CASOS.items():
        for tipo in TIPOS:
            documentos[(caso, tipo)] = {"valores": gf.valores_documento(
                tipo, gf.PERSONAS_FICTICIAS[definicion["persona"]], caso, HOY)}
    for caso, (origen, tipo) in gf.DUPLICADOS.items():
        documentos[(caso, tipo)] = documentos[(origen, tipo)]
    # Hashes simulados: iguales solo para el duplicado y su original
    hashes = {gf.nombre_archivo(t, c, "digital"): f"{c}/{t}" for (c, t) in documentos}
    hashes[gf.nombre_archivo("credencial_elector", "duplicado", "digital")] = "sano/credencial_elector"
    return gf.alertas_folio(folio, documentos, hashes, fichas, gf.cargar_proceso(), HOY)


# ---------------------------------------------------------------- MRZ, CURP y validaciones

def test_digito_control_con_el_ejemplo_de_la_norma_oaci():
    # Especimen publico de la norma OACI 9303 (Utopia)
    assert gf.digito_control("L898902C3") == "6"
    assert gf.digito_control("740812") == "2"
    assert gf.digito_control("120415") == "9"
    assert gf.digito_control("<<<<<<<<<<<<<<") == "0"


def test_mrz_de_cada_persona_es_valida_y_coherente_con_la_curp():
    for persona in gf.PERSONAS_FICTICIAS:
        valores = gf.valores_documento("pasaporte", persona, "sano", HOY)
        linea1, linea2 = gf.generar_mrz(valores)
        gf.validar_mrz(linea1, linea2, valores)
        nacimiento, sexo = gf.datos_de_curp(persona["curp"])
        assert linea1.startswith("P<UTO") and len(linea1) == len(linea2) == 44
        assert linea2[13:19] == nacimiento.strftime("%y%m%d") and linea2[20] == sexo


def test_mrz_con_digito_alterado_falla():
    valores = gf.valores_documento("pasaporte", gf.PERSONAS_FICTICIAS[0], "sano", HOY)
    linea1, linea2 = gf.generar_mrz(valores)
    alterada = linea2[:9] + str((int(linea2[9]) + 1) % 10) + linea2[10:]
    with pytest.raises(gf.ErrorFixture, match="control"):
        gf.validar_mrz(linea1, alterada, valores)


def test_datos_de_curp():
    assert gf.datos_de_curp("AEPA900101MDFXXX01") == (date(1990, 1, 1), "F")
    assert gf.datos_de_curp("DEPL850615HDFXXX02") == (date(1985, 6, 15), "M")
    assert gf.datos_de_curp("ZZZZ050315HDFXXXA1") == (date(2005, 3, 15), "M")  # letra -> 2000+


def test_personas_ficticias_son_coherentes(fichas):
    for persona in gf.PERSONAS_FICTICIAS:
        gf.validar_persona(persona, fichas)


@pytest.mark.parametrize("campo, valor, mensaje", [
    ("sexo", "M", "sexo"),
    ("fecha_nacimiento", "1990-01-02", "fecha_nacimiento"),
    ("clave_elector", "EJPRAN90010109M101", "clave_elector"),  # estado 09 en vez de 99
    ("curp", "AEPA900101XDFXXX01", "patron"),
])
def test_persona_incoherente_con_la_curp_falla(fichas, campo, valor, mensaje):
    persona = copy.deepcopy(gf.PERSONAS_FICTICIAS[0])
    persona[campo] = valor
    with pytest.raises(gf.ErrorFixture, match=mensaje):
        gf.validar_persona(persona, fichas)


def test_campo_nuevo_en_el_yaml_sin_valor_falla(fichas):
    ficha = copy.deepcopy(fichas["pasaporte"])
    ficha["campos"]["lugar_nacimiento"] = {"tipo": "texto", "obligatorio": False}
    valores = gf.valores_documento("pasaporte", gf.PERSONAS_FICTICIAS[0], "sano", HOY)
    with pytest.raises(gf.ErrorFixture, match="lugar_nacimiento"):
        gf.validar_valores("pasaporte", valores, ficha)


def test_valor_que_no_cumple_el_patron_falla(fichas):
    valores = gf.valores_documento("pasaporte", gf.PERSONAS_FICTICIAS[0], "sano", HOY)
    valores["numero_pasaporte"] = "ZX-01"
    with pytest.raises(gf.ErrorFixture, match="patron"):
        gf.validar_valores("pasaporte", valores, fichas["pasaporte"])


def test_fechas_relativas_a_hoy():
    ana, luis = gf.PERSONAS_FICTICIAS
    assert gf.valores_documento("pasaporte", ana, "sano", HOY)["fecha_vencimiento"] == date(2031, 9, 30)
    assert gf.valores_documento("pasaporte", luis, "vencido", HOY)["fecha_vencimiento"] == HOY - timedelta(days=30)
    assert gf.valores_documento("pasaporte", ana, "sano", HOY)["fecha_expedicion"] == date(2021, 9, 30)
    assert gf.valores_documento("credencial_elector", ana, "sano", HOY)["vigencia"] == 2029
    assert gf.valores_documento("comprobante_domicilio", ana, "sano", HOY)["fecha_emision"] == date(2026, 9, 15)


def test_domicilio_distinto_solo_cambia_el_comprobante():
    ana = gf.PERSONAS_FICTICIAS[0]
    credencial = gf.valores_documento("credencial_elector", ana, "domicilio_distinto", HOY)
    comprobante = gf.valores_documento("comprobante_domicilio", ana, "domicilio_distinto", HOY)
    assert credencial["domicilio"] == ana["domicilio"].upper()
    assert comprobante["domicilio"] == gf.DOMICILIO_ALTERNATIVO.upper() != credencial["domicilio"]


def test_sumar_anios_desde_29_de_febrero():
    assert gf.sumar_anios(date(2028, 2, 29), 5) == date(2033, 2, 28)
    assert gf.sumar_anios(date(2028, 2, 29), 4) == date(2032, 2, 29)


# ---------------------------------------------------------------- reglas y alertas esperadas

def test_regla_de_tipo_desconocido_falla(fichas):
    ficha = copy.deepcopy(fichas["pasaporte"])
    ficha["reglas"].append({"id": "x", "tipo": "regla_nueva", "campo": "sexo", "severidad": "critica",
                            "mensaje": "x"})
    valores = gf.valores_documento("pasaporte", gf.PERSONAS_FICTICIAS[0], "sano", HOY)
    with pytest.raises(gf.ErrorFixture, match="desconocido"):
        gf.evaluar_reglas(ficha, valores, HOY)


def test_fecha_en_la_frontera_de_una_regla_falla(fichas):
    valores = gf.valores_documento("pasaporte", gf.PERSONAS_FICTICIAS[0], "sano", HOY)
    valores["fecha_vencimiento"] = HOY
    with pytest.raises(gf.ErrorFixture, match="frontera"):
        gf.evaluar_reglas(fichas["pasaporte"], valores, HOY)


def test_alertas_sano(fichas):
    assert alertas_de("sano", fichas) == []


def test_alertas_vencido_listan_las_dos_reglas_del_pasaporte(fichas):
    alertas = alertas_de("vencido", fichas)
    assert [(a["codigo"], a["severidad"], a["donde"]) for a in alertas] == [
        ("REG-vigencia_documento", "bloqueante", "documento `pasaporte_vencido_*`"),
        ("REG-vigencia_proxima", "preventiva", "documento `pasaporte_vencido_*`"),
    ]


def test_alertas_domicilio_distinto_un_solo_cmp_en_el_expediente(fichas):
    alertas = alertas_de("domicilio_distinto", fichas)
    assert [(a["codigo"], a["severidad"], a["donde"], a["campo"]) for a in alertas] == [
        ("CMP-001", "critica", "alertas_expediente", "domicilio")]


def test_alertas_duplicado_en_el_segundo_documento(fichas):
    alertas = alertas_de("duplicado", fichas)
    assert [(a["codigo"], a["severidad"], a["donde"]) for a in alertas] == [
        ("DUP-001", "critica", "documento `credencial_elector_duplicado_*`")]


def test_alertas_falta_requerido(fichas):
    alertas = alertas_de("falta_requerido", fichas)
    assert [(a["codigo"], a["severidad"], a["donde"], a["campo"]) for a in alertas] == [
        ("EXP-001", "bloqueante", "alertas_expediente", "comprobante_domicilio")]
    assert "comprobante_domicilio" in alertas[0]["motivo"]


def test_codigos_reg_coinciden_con_el_catalogo(fichas):
    catalogo = (RAIZ_REPO / "docs" / "contratos" / "codigos_alertas.md").read_text(encoding="utf-8")
    assert "`REG-{id}`" in catalogo and "REG-vigencia_documento" in catalogo
    for alerta in alertas_de("vencido", fichas):
        regla = alerta["codigo"].removeprefix("REG-")
        assert regla in {r["id"] for r in fichas["pasaporte"]["reglas"]}


# ---------------------------------------------------------------- ficheros generados

def test_se_generan_todos_los_ficheros(generado):
    salida, hashes = generado
    esperados = {gf.nombre_archivo(t, c, m) for c in gf.CASOS for t in TIPOS for m in gf.MODALIDADES}
    esperados |= {gf.nombre_archivo("credencial_elector", "duplicado", m) for m in gf.MODALIDADES}
    assert set(hashes) == esperados and len(esperados) == 30
    assert all((salida / nombre).is_file() for nombre in esperados)
    assert (salida / "INDICE.md").is_file()


def test_capa_de_texto_de_los_digitales(generado):
    salida, _ = generado
    with pymupdf.open(salida / "pasaporte_vencido_digital.pdf") as doc:
        contenido = doc[0].get_text()
    assert "LUIS DEMO PRUEBAS" in contenido and "31/08/2026" in contenido and "P<UTODEMO<PRUEBAS<<LUIS" in contenido


def test_escaneados_sin_capa_de_texto(generado):
    salida, _ = generado
    for caso in gf.CASOS:
        for tipo in TIPOS:
            with pymupdf.open(salida / gf.nombre_archivo(tipo, caso, "escaneado")) as doc:
                assert doc.page_count == 1
                assert doc[0].get_text() == ""
                assert len(doc[0].get_images()) == 1


def test_fotos_son_jpg_rgb_sin_exif(generado):
    salida, _ = generado
    for caso in gf.CASOS:
        for tipo in TIPOS:
            with Image.open(salida / gf.nombre_archivo(tipo, caso, "foto")) as foto:
                assert foto.format == "JPEG" and foto.mode == "RGB"
                assert min(foto.size) >= 900 and "exif" not in foto.info


def test_duplicado_tiene_el_mismo_sha256_que_el_original(generado):
    _, hashes = generado
    for modalidad in gf.MODALIDADES:
        assert (hashes[gf.nombre_archivo("credencial_elector", "duplicado", modalidad)]
                == hashes[gf.nombre_archivo("credencial_elector", "sano", modalidad)])
    # Ningun otro par de ficheros coincide: DUP-001 solo aparece donde se busca
    assert len(set(hashes.values())) == len(hashes) - len(gf.MODALIDADES)


def test_indice_contiene_fecha_valores_y_alertas(generado):
    salida, _ = generado
    indice = (salida / "INDICE.md").read_text(encoding="utf-8")
    assert "--hoy 2026-09-30" in indice and "No se sube a git" in indice
    assert "| `fecha_vencimiento` | 2026-08-31 |" in indice
    for codigo in ("REG-vigencia_documento", "REG-vigencia_proxima", "CMP-001", "DUP-001", "EXP-001"):
        assert f"`{codigo}`" in indice
    assert "Alertas esperadas: ninguna." in indice.split("### Folio `sano`")[1].split("### Folio")[0]


def test_determinismo_byte_a_byte_con_el_mismo_hoy(generado, tmp_path):
    salida, hashes = generado
    otra = gf.generar(HOY, tmp_path)  # incluye PDF escaneados y JPG
    assert otra == hashes
    assert (tmp_path / "INDICE.md").read_bytes() == (salida / "INDICE.md").read_bytes()


def test_otro_hoy_cambia_los_ficheros(generado, tmp_path):
    _, hashes = generado
    otra = gf.generar(HOY + timedelta(days=1), tmp_path)
    assert set(otra) == set(hashes)
    assert all(otra[n] != hashes[n] for n in hashes if "_digital" in n)
