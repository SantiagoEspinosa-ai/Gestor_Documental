"""
CLI del motor IA (entregable de la etapa 1): analiza un archivo local sin BD ni S3.

Uso (desde backend/, o en el contenedor del backend):
    python -m app.modulos.motor_ia.cli fixtures/generados/pasaporte_sano_digital.pdf --tipo pasaporte

- stdout: solo el ResultadoDocumento (Contrato 1) en JSON. stderr: resumen (modalidad, llamadas, alertas).
- Codigos de salida: 0 completado; 1 estado_analisis=error (el JSON se imprime igual);
  2 error de entrada o de configuracion.
- Lee el .env de la raiz del repo; las variables del entorno real tienen prioridad.
- La ruta se busca desde la carpeta actual y, si no existe, desde la raiz del repo.
Es un punto de entrada: ningun modulo lo importa (spec, seccion 12).
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from dotenv import load_dotenv

from app.modulos.configuracion import servicio as configuracion
from app.modulos.motor_ia.enrutador import ErrorEnrutador, crear_enrutador
from app.modulos.motor_ia.interfaces import Enrutador
from app.modulos.motor_ia.prompts import ErrorPrompt
from app.modulos.motor_ia.servicio import analizar
from app.modulos.orquestador import servicio as orquestador
from app.schemas.resultado import EstadoAnalisis, ReferenciaArchivoOriginal

# backend/app/modulos/motor_ia/cli.py -> raiz del repo (en el contenedor, "/")
RAIZ_REPO = Path(__file__).resolve().parents[4]
FOLIO_CLI = "CLI-2026-000000"
SALIDA_OK, SALIDA_ERROR_ANALISIS, SALIDA_ERROR_ENTRADA = 0, 1, 2


class ErrorEntrada(Exception):
    """Archivo, tipo o configuracion invalidos: salida 2."""


def cargar_entorno(ruta_env: Path | None = None) -> None:
    """Carga el .env sin sobrescribir las variables que ya existen en el entorno."""
    load_dotenv(ruta_env or RAIZ_REPO / ".env", override=False)


def resolver_ruta(archivo: str) -> Path:
    ruta = Path(archivo)
    if ruta.is_file():
        return ruta.resolve()
    if not ruta.is_absolute() and (RAIZ_REPO / ruta).is_file():
        return (RAIZ_REPO / ruta).resolve()
    raise ErrorEntrada(f"no existe el archivo {archivo} (ni desde la carpeta actual ni desde la raiz del repo)")


def _comprobar_tipo(tipo: str | None, opcion: str) -> None:
    if tipo is None:
        return
    try:
        configuracion.obtener(tipo)
    except configuracion.TipoNoEncontrado:
        disponibles = ", ".join(sorted(f.nombre for f in configuracion.listar()))
        raise ErrorEntrada(f"{opcion}: tipo documental desconocido '{tipo}' (disponibles: {disponibles})") from None


def _resumen(nombre: str, doc, analisis) -> str:
    r = analisis.resultado
    lineas = [f"archivo: {nombre} | modalidad: {doc.modalidad.value} | paginas: {len(doc.paginas)}"]
    for i, info in enumerate(analisis.llamadas, start=1):
        lineas.append(f"llamada {i}: {info.proveedor} {info.modelo} | {info.segundos} s | tokens "
                      f"{info.tokens_entrada} entrada / {info.tokens_salida} salida | peticiones {info.peticiones} "
                      f"| reintentos {info.reintentos} | lotes {info.lotes}")
    confianza = f" ({r.confianza_clasificacion:.2f})" if r.confianza_clasificacion is not None else ""
    alertas = ", ".join(f"{a.codigo} {a.severidad.value}" + (f" [{a.campo}]" if a.campo else "")
                        for a in r.alertas_encontradas) or "ninguna"
    lineas.append(f"estado: {r.estado_analisis.value} | declarado: {r.tipo_documental_declarado} | "
                  f"detectado: {r.tipo_documental_detectado}{confianza} | campos: {len(r.datos_extraidos)} | "
                  f"alertas: {alertas}")
    return "\n".join(lineas)


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m app.modulos.motor_ia.cli",
                                description="Analiza un documento local con el motor IA (sin BD ni S3).")
    p.add_argument("archivo", help="PDF, PNG o JPEG")
    p.add_argument("--tipo", help="tipo documental declarado (p. ej. pasaporte)")
    p.add_argument("--tipo-confirmado", help="tipo confirmado por el revisor: extrae con esa ficha sin clasificar")
    p.add_argument("--folio", default=FOLIO_CLI, help=f"folio del resultado (por defecto {FOLIO_CLI})")
    p.add_argument("--salida", type=Path, help="guarda el JSON en este fichero en lugar de imprimirlo")
    return p.parse_args(argv)


def ejecutar(argv: list[str] | None = None, *, enrutador: Enrutador | None = None,
             ruta_env: Path | None = None) -> int:
    args = _argumentos(argv)
    cargar_entorno(ruta_env)
    try:
        configuracion.cargar()
        _comprobar_tipo(args.tipo, "--tipo")
        _comprobar_tipo(args.tipo_confirmado, "--tipo-confirmado")
        ruta = resolver_ruta(args.archivo)
        enrutador = enrutador or crear_enrutador()
        contenido = ruta.read_bytes()
        referencia = ReferenciaArchivoOriginal(nombre_archivo=ruta.name, ruta=f"local://{ruta.name}",
                                               hash=hashlib.sha256(contenido).hexdigest())
        doc = orquestador.preparar(contenido, ruta.name, args.tipo)
        analisis = analizar(doc, folio=args.folio, referencia=referencia,
                            tipo_confirmado=args.tipo_confirmado, enrutador=enrutador)
    except (ErrorEntrada, orquestador.FormatoNoSoportado, configuracion.ErrorConfiguracion,
            ErrorEnrutador, ErrorPrompt) as e:
        print(f"error: {e}", file=sys.stderr)
        return SALIDA_ERROR_ENTRADA

    json_resultado = analisis.resultado.model_dump_json(indent=2)
    if args.salida:
        args.salida.write_text(json_resultado + "\n", encoding="utf-8")
    else:
        sys.stdout.write(json_resultado + "\n")
    print(_resumen(ruta.name, doc, analisis), file=sys.stderr)
    return SALIDA_OK if analisis.resultado.estado_analisis is EstadoAnalisis.completado else SALIDA_ERROR_ANALISIS


if __name__ == "__main__":
    sys.exit(ejecutar())
