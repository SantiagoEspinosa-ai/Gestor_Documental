"""Tests de tests/versiones_fixtures.py: lectura de sha256_fixtures_existentes.txt y mensaje de omision."""
from tests.versiones_fixtures import leer_referencia, motivo_versiones_distintas, versiones_instaladas


def test_la_referencia_registra_versiones_y_30_hashes():
    versiones, hashes = leer_referencia()
    assert set(versiones) == {"pymupdf", "pillow"}
    assert len(hashes) == 30 and all(len(sha) == 64 for sha in hashes.values())
    assert "credencial_elector_sano_digital.pdf" in hashes


def test_sin_motivo_si_las_versiones_coinciden(tmp_path):
    instaladas = versiones_instaladas(["pymupdf", "pillow"])
    ruta = tmp_path / "referencia.txt"
    ruta.write_text("# comentario\n" + "".join(f"{p}=={v}\n" for p, v in instaladas.items()) + "abc  x.pdf\n",
                    encoding="utf-8")
    assert motivo_versiones_distintas(ruta) is None


def test_motivo_dice_que_versiones_esperan_y_cuales_hay(tmp_path):
    ruta = tmp_path / "referencia.txt"
    ruta.write_text("pymupdf==0.0.1\npillow==0.0.2\nabc  x.pdf\n", encoding="utf-8")
    motivo = motivo_versiones_distintas(ruta)
    instaladas = versiones_instaladas(["pymupdf", "pillow"])
    assert "registrados con pymupdf 0.0.1, pillow 0.0.2" in motivo
    assert f"instaladas: pymupdf {instaladas['pymupdf']}, pillow {instaladas['pillow']}" in motivo


def test_paquete_no_instalado():
    assert versiones_instaladas(["paquete-que-no-existe-xyz"]) == {"paquete-que-no-existe-xyz": "no instalado"}
