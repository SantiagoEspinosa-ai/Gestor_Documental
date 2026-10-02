"""Tests del CLI del motor IA con proveedores falsos: sin Ollama. Datos inventados."""
import hashlib
import json
import os

import pymupdf
import pytest

from app.modulos.motor_ia import cli
from app.modulos.motor_ia.proveedores.base import ErrorProveedor
from app.schemas.resultado import ResultadoDocumento
from tests.test_servicio_motor import EnrutadorFalso, ProveedorFalso

VARIABLES_OLLAMA = ("OLLAMA_BASE_URL", "OLLAMA_MODELO_TEXTO", "OLLAMA_MODELO_VISION")


@pytest.fixture
def pdf(tmp_path):
    documento = pymupdf.open()
    pagina = documento.new_page()
    for i, linea in enumerate(["PASAPORTE DE MUESTRA SIN VALIDEZ", "ANA EJEMPLO PRUEBA", "X1234567P"]):
        pagina.insert_text((72, 72 + 20 * i), linea)
    ruta = tmp_path / "pasaporte_de_prueba.pdf"
    documento.save(ruta)
    documento.close()
    return ruta


@pytest.fixture
def sin_env(tmp_path):
    return tmp_path / "no_existe.env"


def ejecutar(argv, proveedor=None, sin_env=None):
    enrutador = EnrutadorFalso(proveedor or ProveedorFalso("ollama"))
    return cli.ejecutar(argv, enrutador=enrutador, ruta_env=sin_env)


def test_caso_normal(pdf, sin_env, capsys):
    assert ejecutar([str(pdf), "--tipo", "pasaporte"], sin_env=sin_env) == cli.SALIDA_OK
    salida = capsys.readouterr()
    resultado = ResultadoDocumento.model_validate_json(salida.out)  # stdout: solo el Contrato 1
    assert resultado.folio_solicitud == "CLI-2026-000000"
    referencia = resultado.referencia_archivo_original
    assert referencia.nombre_archivo == "pasaporte_de_prueba.pdf"
    assert referencia.ruta == "local://pasaporte_de_prueba.pdf"  # sin rutas personales
    assert referencia.hash == hashlib.sha256(pdf.read_bytes()).hexdigest()
    assert "modalidad: pdf_digital" in salida.err and "estado: completado" in salida.err
    assert "ANA EJEMPLO PRUEBA" not in salida.err  # los datos solo van en el JSON
    assert str(pdf.parent) not in salida.out


def test_folio_y_tipo_confirmado(pdf, sin_env, capsys):
    proveedor = ProveedorFalso("ollama")
    assert ejecutar([str(pdf), "--folio", "ONB-2026-000123", "--tipo-confirmado", "pasaporte"], proveedor,
                    sin_env) == cli.SALIDA_OK
    resultado = json.loads(capsys.readouterr().out)
    assert resultado["folio_solicitud"] == "ONB-2026-000123"
    assert resultado["tipo_documental_confirmado"] == "pasaporte"
    assert [t for t, _ in proveedor.prompts] == ["extraccion"]


def test_salida_a_fichero(pdf, sin_env, tmp_path, capsys):
    destino = tmp_path / "resultado.json"
    assert ejecutar([str(pdf), "--tipo", "pasaporte", "--salida", str(destino)], sin_env=sin_env) == cli.SALIDA_OK
    assert capsys.readouterr().out == ""
    ResultadoDocumento.model_validate_json(destino.read_text(encoding="utf-8"))


def test_estado_error_sale_con_1_e_imprime_el_json(pdf, sin_env, capsys):
    proveedor = ProveedorFalso("ollama", falla_clasificar=ErrorProveedor("caido"))
    assert ejecutar([str(pdf), "--tipo", "pasaporte"], proveedor, sin_env) == cli.SALIDA_ERROR_ANALISIS
    resultado = json.loads(capsys.readouterr().out)
    assert resultado["estado_analisis"] == "error" and resultado["alertas_encontradas"][0]["codigo"] == "SYS-001"


@pytest.mark.parametrize("argv, mensaje", [
    (["no_existe.pdf"], "no existe el archivo"),
    (["{pdf}", "--tipo", "factura"], "tipo documental desconocido 'factura'"),
    (["{pdf}", "--tipo-confirmado", "factura"], "--tipo-confirmado"),
    (["{txt}"], "formato no soportado"),
])
def test_errores_de_entrada_salen_con_2(pdf, sin_env, tmp_path, capsys, argv, mensaje):
    txt = tmp_path / "notas.txt"
    txt.write_text("texto plano", encoding="utf-8")
    argv = [a.format(pdf=pdf, txt=txt) for a in argv]
    assert ejecutar(argv, sin_env=sin_env) == cli.SALIDA_ERROR_ENTRADA
    salida = capsys.readouterr()
    assert mensaje in salida.err and salida.out == ""


def test_sin_variables_de_ollama_sale_con_2(pdf, sin_env, monkeypatch, capsys):
    for variable in VARIABLES_OLLAMA:
        monkeypatch.delenv(variable, raising=False)
    assert cli.ejecutar([str(pdf)], ruta_env=sin_env) == cli.SALIDA_ERROR_ENTRADA
    assert "falta la variable de entorno OLLAMA_" in capsys.readouterr().err


def test_ruta_relativa_a_la_raiz_del_repo(tmp_path, monkeypatch, pdf):
    # Como el comando del entregable: se lanza desde backend/ con una ruta relativa a la raiz del repo.
    monkeypatch.setattr(cli, "RAIZ_REPO", tmp_path)
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "fixtures" / "doc.pdf").write_bytes(pdf.read_bytes())
    (tmp_path / "backend").mkdir()
    monkeypatch.chdir(tmp_path / "backend")
    assert cli.resolver_ruta("fixtures/doc.pdf") == tmp_path / "fixtures" / "doc.pdf"
    monkeypatch.chdir(tmp_path)
    assert cli.resolver_ruta("fixtures/doc.pdf") == tmp_path / "fixtures" / "doc.pdf"  # desde la carpeta actual


def test_el_entorno_real_gana_al_env(tmp_path, monkeypatch):
    fichero = tmp_path / ".env"
    fichero.write_text("OLLAMA_MODELO_TEXTO=desde-el-env\nVARIABLE_SOLO_EN_ENV_DE_PRUEBA=si\n", encoding="utf-8")
    monkeypatch.setenv("OLLAMA_MODELO_TEXTO", "desde-el-entorno")
    monkeypatch.delenv("VARIABLE_SOLO_EN_ENV_DE_PRUEBA", raising=False)
    cli.cargar_entorno(fichero)
    assert os.environ["OLLAMA_MODELO_TEXTO"] == "desde-el-entorno"
    assert os.environ["VARIABLE_SOLO_EN_ENV_DE_PRUEBA"] == "si"
    monkeypatch.delenv("VARIABLE_SOLO_EN_ENV_DE_PRUEBA")
