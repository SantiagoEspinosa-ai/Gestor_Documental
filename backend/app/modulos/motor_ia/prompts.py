"""
Carga y renderizado de los prompts versionados de `prompts/<id>_<version>.md` (regla 5 de CLAUDE.md).
Cada fichero empieza con un frontmatter YAML (`id`, `version`, `salida`) entre lineas `---`.
"""
from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import jinja2
import yaml

from app.modulos.configuracion.servicio import TipoDocumental
from app.modulos.motor_ia.interfaces import Pagina

# Version en uso de cada prompt. Cambiarla es una decision de configuracion: anotarla en la spec.
VERSIONES_VIGENTES = {"clasificacion": "v2", "extraccion": "v3", "correccion_json": "v1"}

# backend/app/modulos/motor_ia/prompts.py -> raiz del repo
_RAIZ_REPO = Path(__file__).resolve().parents[4]
_CLAVES_FRONTMATTER = ("id", "version", "salida")

# StrictUndefined: una variable que falta es un error, no un hueco vacio en el prompt.
# Los valores (p. ej. el texto del documento) se insertan tal cual: nunca se interpretan como plantilla.
_JINJA = jinja2.Environment(undefined=jinja2.StrictUndefined, autoescape=False)


class ErrorPrompt(Exception):
    """Prompt inexistente, mal formado o renderizado con variables que faltan."""


@dataclass(frozen=True)
class Prompt:
    id: str
    version: str
    salida: str
    plantilla: str


def directorio_prompts() -> Path:
    """`PROMPTS_DIR` si esta definida (en Docker, /prompts); si no, `prompts/` en la raiz del repo."""
    return Path(os.environ.get("PROMPTS_DIR") or _RAIZ_REPO / "prompts")


@lru_cache
def _leer(ruta: Path) -> Prompt:
    if not ruta.is_file():
        raise ErrorPrompt(f"no existe el prompt {ruta.name}")
    texto = ruta.read_text(encoding="utf-8").replace("\r\n", "\n")
    if not texto.startswith("---\n") or "\n---\n" not in texto:
        raise ErrorPrompt(f"{ruta.name}: falta el frontmatter entre lineas '---'")
    cabecera, cuerpo = texto[4:].split("\n---\n", 1)
    try:
        meta = yaml.safe_load(cabecera)
    except yaml.YAMLError as e:
        raise ErrorPrompt(f"{ruta.name}: frontmatter YAML mal formado: {e}") from e
    if not isinstance(meta, dict) or any(not meta.get(c) for c in _CLAVES_FRONTMATTER):
        raise ErrorPrompt(f"{ruta.name}: el frontmatter debe tener {', '.join(_CLAVES_FRONTMATTER)}")
    meta = {c: str(meta[c]) for c in _CLAVES_FRONTMATTER}
    if f"{meta['id']}_{meta['version']}" != ruta.stem:
        raise ErrorPrompt(f"{ruta.name}: id '{meta['id']}' y version '{meta['version']}' no coinciden con el fichero")
    return Prompt(meta["id"], meta["version"], meta["salida"], cuerpo.strip())


def cargar(id_prompt: str, version: str | None = None) -> Prompt:
    """Lee `<PROMPTS_DIR>/<id>_<version>.md`. Sin version, usa la de VERSIONES_VIGENTES."""
    version = version or VERSIONES_VIGENTES.get(id_prompt)
    if version is None:
        raise ErrorPrompt(f"no hay version vigente para el prompt '{id_prompt}'")
    return _leer(directorio_prompts() / f"{id_prompt}_{version}.md")


def version_prompt(prompt: Prompt, tipo_documental: str | None = None) -> str:
    """Valor de `FechaYModelo.version_prompt`: `extraccion_pasaporte@v3`, o `clasificacion@v2` sin tipo."""
    nombre = f"{prompt.id}_{tipo_documental}" if tipo_documental else prompt.id
    return f"{nombre}@{prompt.version}"


def renderizar(id_prompt: str, version: str | None = None, *, tipo_documental: str | None = None,
               **variables) -> tuple[str, str]:
    """Devuelve `(texto, version_prompt)`. `tipo_documental`, si se pasa, tambien es variable del prompt."""
    prompt = cargar(id_prompt, version)
    if tipo_documental is not None:
        variables["tipo_documental"] = tipo_documental
    try:
        texto = _JINJA.from_string(prompt.plantilla).render(**variables)
    except jinja2.UndefinedError as e:
        raise ErrorPrompt(f"{id_prompt}_{prompt.version}: falta una variable: {e.message}") from e
    except jinja2.TemplateError as e:
        raise ErrorPrompt(f"{id_prompt}_{prompt.version}: plantilla invalida: {e}") from e
    return texto.strip(), version_prompt(prompt, tipo_documental)


# --- Formato comun de las variables, para que todos los prompts muestren los datos igual ---

def formatear_contenido(paginas: Iterable[Pagina]) -> str:
    """Texto por pagina con cabecera `--- pagina_<n> ---`, en el orden recibido."""
    bloques = [f"--- pagina_{p.numero} ---\n{(p.texto or '').strip() or '(sin texto extraido)'}" for p in paginas]
    return "\n\n".join(bloques) or "(sin texto extraido)"


def formatear_tipos(fichas: Iterable[TipoDocumental]) -> str:
    return "\n".join(
        f"- {f.nombre}: {f.descripcion} Caracteristicas: {'; '.join(f.caracteristicas_esperadas)}" for f in fichas
    )


def formatear_esquema(ficha: TipoDocumental) -> str:
    return "\n".join(
        f"- {nombre}: {campo.tipo.value}, {'obligatorio' if campo.obligatorio else 'opcional'}"
        for nombre, campo in ficha.campos.items()
    )


def formatear_contexto_rag(fragmentos: Iterable[str]) -> str:
    return "\n\n".join(f.strip() for f in fragmentos if f.strip()) or "(sin contexto)"
