"""Tests de carga y renderizado de prompts (motor_ia). Sin modelo; datos inventados."""
import pytest

from app.modulos.configuracion import servicio as configuracion
from app.modulos.motor_ia import prompts
from app.modulos.motor_ia.interfaces import Pagina
from app.modulos.motor_ia.prompts import (
    VERSIONES_VIGENTES,
    ErrorPrompt,
    formatear_contenido,
    formatear_contexto_rag,
    formatear_campos,
    formatear_esquema,
    formatear_tipos,
    renderizar,
)


@pytest.fixture(autouse=True)
def _limpiar_cache():
    prompts._leer.cache_clear()
    yield
    prompts._leer.cache_clear()


@pytest.fixture
def carpeta(tmp_path, monkeypatch):
    """PROMPTS_DIR temporal; devuelve una funcion para escribir prompts en ella."""
    monkeypatch.setenv("PROMPTS_DIR", str(tmp_path))

    def escribir(nombre: str, texto: str):
        (tmp_path / nombre).write_text(texto, encoding="utf-8")

    return escribir


def variables_reales() -> dict:
    fichas = configuracion.cargar()
    return {
        "contenido": formatear_contenido([Pagina(numero=1, texto="PASAPORTE\nANA EJEMPLO PRUEBA")]),
        "tipos_posibles": formatear_tipos(fichas.values()),
        "contexto_rag": formatear_contexto_rag([]),
        "esquema_campos": formatear_esquema(fichas["pasaporte"]),
        "campos_a_extraer": formatear_campos(fichas["pasaporte"]),
    }


# --- Prompts reales del repo ---

def test_versiones_vigentes_existen_y_renderizan():
    v = variables_reales()
    texto, version = renderizar("clasificacion", contenido=v["contenido"], tipos_posibles=v["tipos_posibles"],
                                contexto_rag=v["contexto_rag"])
    assert version == f"clasificacion@{VERSIONES_VIGENTES['clasificacion']}"
    assert "ANA EJEMPLO PRUEBA" in texto and "- pasaporte:" in texto and "{{" not in texto

    texto, version = renderizar("extraccion", tipo_documental="pasaporte", contenido=v["contenido"],
                                esquema_campos=v["esquema_campos"], campos_a_extraer=v["campos_a_extraer"])
    assert version == f"extraccion_pasaporte@{VERSIONES_VIGENTES['extraccion']}"
    assert "(tipo: pasaporte)" in texto and "- numero_pasaporte: texto\n" in texto
    assert "opcional" not in texto and "obligatorio" not in texto   # v3: sin obligatoriedad (ver formatear_campos)
    assert "EXACTAMENTE como aparecen" in texto



def test_extraccion_v4_vigencia_de_la_credencial():
    fichas = configuracion.cargar()
    contenido = formatear_contenido([Pagina(numero=1, texto="CREDENCIAL PARA VOTAR\nEMISION 2019   VIGENCIA 2029")])
    texto, version = renderizar("extraccion", "v4", tipo_documental="credencial_elector", contenido=contenido,
                                campos_a_extraer=formatear_campos(fichas["credencial_elector"]))
    assert version == "extraccion_credencial_elector@v4"
    assert "junto a la palabra VIGENCIA" in texto and "Nunca el de EMISION" in texto
    assert "{%" not in texto


@pytest.mark.parametrize("tipo", ["pasaporte", "comprobante_domicilio"])
def test_extraccion_v4_igual_que_v3_en_los_demas_tipos(tipo):
    fichas = configuracion.cargar()
    variables = {"contenido": "x", "campos_a_extraer": formatear_campos(fichas[tipo])}
    v3, _ = renderizar("extraccion", "v3", tipo_documental=tipo, **variables)
    v4, version = renderizar("extraccion", "v4", tipo_documental=tipo, **variables)
    assert v4 == v3 and version == f"extraccion_{tipo}@v4"

def test_prompts_v1_siguen_disponibles():
    v = variables_reales()
    _, version = renderizar("clasificacion", "v1", tipos_posibles=v["tipos_posibles"], contexto_rag="(sin contexto)")
    assert version == "clasificacion@v1"
    _, version = renderizar("extraccion", "v1", tipo_documental="credencial_elector", esquema_campos="- curp: texto")
    assert version == "extraccion_credencial_elector@v1"


def test_el_frontmatter_no_llega_al_prompt():
    texto, _ = renderizar("extraccion", tipo_documental="pasaporte", contenido="x", esquema_campos="x",
                          campos_a_extraer="x")
    assert not texto.startswith("---") and "salida: json" not in texto


# --- Carpeta temporal ---

def test_prompts_dir_y_version_prompt(carpeta):
    carpeta("saludo_v3.md", "---\nid: saludo\nversion: v3\nsalida: texto\n---\nHola {{ nombre }}.\n")
    assert renderizar("saludo", "v3", nombre="EJEMPLO") == ("Hola EJEMPLO.", "saludo@v3")
    assert renderizar("saludo", "v3", tipo_documental="pasaporte", nombre="X")[1] == "saludo_pasaporte@v3"


def test_acepta_finales_de_linea_crlf(carpeta):
    carpeta("saludo_v1.md", "---\r\nid: saludo\r\nversion: v1\r\nsalida: texto\r\n---\r\nHola.\r\n")
    assert renderizar("saludo", "v1") == ("Hola.", "saludo@v1")


def test_falta_una_variable(carpeta):
    carpeta("saludo_v1.md", "---\nid: saludo\nversion: v1\nsalida: texto\n---\nHola {{ nombre }}.\n")
    with pytest.raises(ErrorPrompt, match="falta una variable"):
        renderizar("saludo", "v1")


def test_el_contenido_del_documento_no_se_interpreta_como_plantilla(carpeta):
    carpeta("eco_v1.md", "---\nid: eco\nversion: v1\nsalida: texto\n---\n{{ contenido }}\n")
    malicioso = "{{ 7*7 }} {% for x in range(3) %}X{% endfor %}"
    assert renderizar("eco", "v1", contenido=malicioso)[0] == malicioso


@pytest.mark.parametrize("nombre, texto, mensaje", [
    ("p_v1.md", "Sin frontmatter\n", "falta el frontmatter"),
    ("p_v1.md", "---\nid: p\nversion: v1\nsalida: texto\nSin cierre\n", "falta el frontmatter"),
    ("p_v1.md", "---\nid: [sin cerrar\n---\nx\n", "YAML mal formado"),
    ("p_v1.md", "---\nid: p\nversion: v1\n---\nx\n", "debe tener"),
    ("p_v1.md", "---\nid: otro\nversion: v1\nsalida: texto\n---\nx\n", "no coinciden"),
    ("p_v1.md", "---\nid: p\nversion: v9\nsalida: texto\n---\nx\n", "no coinciden"),
    ("p_v1.md", "---\nid: p\nversion: v1\nsalida: texto\n---\n{% if %}\n", "plantilla invalida"),
])
def test_prompts_mal_formados(carpeta, nombre, texto, mensaje):
    carpeta(nombre, texto)
    with pytest.raises(ErrorPrompt, match=mensaje):
        renderizar("p", "v1")


def test_prompt_inexistente(carpeta):
    with pytest.raises(ErrorPrompt, match="no existe"):
        renderizar("no_existe", "v1")


def test_sin_version_vigente(carpeta):
    with pytest.raises(ErrorPrompt, match="no hay version vigente"):
        renderizar("no_configurado")


# --- Formato de variables ---

def test_formatear_contenido():
    paginas = [Pagina(numero=1, texto="  Linea A \n"), Pagina(numero=2, texto=None), Pagina(numero=3, texto="   ")]
    assert formatear_contenido(paginas) == (
        "--- pagina_1 ---\nLinea A\n\n--- pagina_2 ---\n(sin texto extraido)\n\n--- pagina_3 ---\n(sin texto extraido)"
    )
    assert formatear_contenido([]) == "(sin texto extraido)"


def test_formatear_contexto_rag():
    assert formatear_contexto_rag([]) == "(sin contexto)"
    assert formatear_contexto_rag(["  uno ", "", "dos"]) == "uno\n\ndos"


def test_formatear_tipos_y_esquema():
    fichas = configuracion.cargar()
    tipos = formatear_tipos([fichas["pasaporte"]])
    assert tipos.startswith("- pasaporte: Pasaporte vigente") and "Caracteristicas: Fotografia del titular" in tipos
    esquema = formatear_esquema(fichas["pasaporte"]).splitlines()
    assert esquema[0] == "- nombre_completo: texto, obligatorio"
    assert "- nacionalidad: texto, opcional" in esquema
    assert formatear_campos(fichas["pasaporte"]).splitlines()[0] == "- nombre_completo: texto"


def test_extraccion_v2_sigue_con_la_obligatoriedad():
    v = variables_reales()
    texto, version = renderizar("extraccion", "v2", tipo_documental="pasaporte", contenido=v["contenido"],
                                esquema_campos=v["esquema_campos"])
    assert version == "extraccion_pasaporte@v2" and "- nacionalidad: texto, opcional" in texto
