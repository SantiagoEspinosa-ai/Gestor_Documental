"""Tests del cargador de fichas YAML (modulo configuracion). Sin BD, S3 ni modelo."""
import copy

import pytest
import yaml

from app.modulos.configuracion import servicio
from app.modulos.configuracion.servicio import ErrorConfiguracion, TipoNoEncontrado, TipoRegla, cargar


def ficha_base(nombre: str = "tipo_a") -> dict:
    """Ficha minima valida con datos inventados."""
    return {
        "nombre": nombre,
        "nombre_visible": "Tipo A",
        "categoria": "identificacion",
        "descripcion": "Documento de prueba",
        "caracteristicas_esperadas": ["Titulo"],
        "formatos_permitidos": ["PDF", ".png"],
        "campos": {
            "numero": {"tipo": "texto", "obligatorio": True, "patron": "^[A-Z0-9]{8}$"},
            "fecha_vencimiento": {"tipo": "fecha", "obligatorio": True},
        },
        "confianza_minima_clasificacion": 0.8,
        "confianza_minima_campo": 0.7,
        "reglas": [
            {"id": "formato_numero", "tipo": "patron", "campo": "numero",
             "severidad": "critica", "mensaje": "Numero invalido"},
            {"id": "vigencia_proxima", "tipo": "fecha_posterior_a_hoy_mas_dias", "campo": "fecha_vencimiento",
             "dias": 90, "severidad": "preventiva", "mensaje": "Vence pronto"},
        ],
    }


@pytest.fixture
def config(tmp_path):
    """Devuelve una funcion que escribe fichas en <tmp>/tipos y carga el directorio."""
    (tmp_path / "tipos").mkdir()

    def escribir_y_cargar(*fichas: dict, crudo: dict[str, str] | None = None):
        for ficha in fichas:
            (tmp_path / "tipos" / f"{ficha['nombre']}.yaml").write_text(yaml.safe_dump(ficha), encoding="utf-8")
        for nombre_fichero, texto in (crudo or {}).items():
            (tmp_path / "tipos" / nombre_fichero).write_text(texto, encoding="utf-8")
        return cargar(tmp_path)

    yield escribir_y_cargar
    servicio._tipos = None  # que la cache no arrastre la config temporal a otros tests


def errores_de(config, *fichas, **kwargs) -> str:
    with pytest.raises(ErrorConfiguracion) as exc:
        config(*fichas, **kwargs)
    return str(exc.value)


# --- Configuracion real del repo ---

def test_carga_las_fichas_reales_del_repo():
    tipos = cargar()
    assert {"credencial_elector", "pasaporte", "comprobante_domicilio"} <= tipos.keys()
    pasaporte = servicio.obtener("pasaporte")
    assert pasaporte.campos["numero_pasaporte"].obligatorio
    assert {r.id for r in pasaporte.reglas} == {"vigencia_documento", "vigencia_proxima", "formato_numero"}
    assert len(servicio.listar()) == len(tipos)


def test_ejemplos_referencia_apuntan_a_fixtures_generados_del_caso_sano():
    # Los ficheros no estan en git (fixtures/generados/ se genera con scripts/generar_fixtures.py):
    # se comprueba el nombre, no que existan.
    for ficha in cargar().values():
        assert ficha.ejemplos_referencia, ficha.nombre
        for ruta in ficha.ejemplos_referencia:
            carpeta, _, archivo = ruta.rpartition("/")
            base, _, extension = archivo.rpartition(".")
            assert carpeta == "fixtures/generados", ruta
            assert base.startswith(f"{ficha.nombre}_sano_"), ruta
            assert base.removeprefix(f"{ficha.nombre}_sano_") in {"digital", "escaneado", "foto"}, ruta
            assert extension in ficha.formatos_permitidos, ruta


def test_obtener_tipo_inexistente():
    cargar()
    with pytest.raises(TipoNoEncontrado):
        servicio.obtener("no_existe")


# --- Casos validos ---

def test_ficha_minima_valida_y_formatos_normalizados(config):
    tipos = config(ficha_base())
    ficha = tipos["tipo_a"]
    assert ficha.formatos_permitidos == ["pdf", "png"]
    assert ficha.reglas[1].tipo is TipoRegla.fecha_posterior_a_hoy_mas_dias
    assert ficha.reglas[1].dias == 90


def test_comparaciones_validas_entre_fichas(config):
    a, b = ficha_base("tipo_a"), ficha_base("tipo_b")
    a["comparaciones"] = {"tipo_b": ["numero"]}
    assert set(config(a, b)) == {"tipo_a", "tipo_b"}


# --- Casos invalidos ---

def test_yaml_con_sintaxis_rota(config):
    assert "roto.yaml: YAML mal formado" in errores_de(config, crudo={"roto.yaml": "nombre: [sin cerrar\n"})


def test_ficha_que_no_es_diccionario(config):
    assert "lista.yaml: la ficha debe ser un diccionario" in errores_de(config, crudo={"lista.yaml": "- a\n- b\n"})


def test_carpeta_sin_fichas(config):
    assert "no hay fichas YAML" in errores_de(config)


def test_falta_clave_obligatoria(config):
    ficha = ficha_base()
    del ficha["descripcion"]
    assert "tipo_a.yaml: descripcion:" in errores_de(config, ficha)


def test_clave_desconocida_por_errata(config):
    ficha = ficha_base()
    ficha["campos"]["numero"]["obligatoro"] = True
    assert "campos.numero.obligatoro" in errores_de(config, ficha)


def test_confianza_fuera_de_rango(config):
    ficha = ficha_base()
    ficha["confianza_minima_campo"] = 1.5
    assert "confianza_minima_campo" in errores_de(config, ficha)


def test_severidad_inexistente(config):
    ficha = ficha_base()
    ficha["reglas"][0]["severidad"] = "gravisima"
    assert "reglas.0.severidad" in errores_de(config, ficha)


def test_tipo_de_regla_inexistente(config):
    ficha = ficha_base()
    ficha["reglas"][0]["tipo"] = "adivinar"
    assert "reglas.0.tipo" in errores_de(config, ficha)


def test_tipo_de_campo_inexistente(config):
    ficha = ficha_base()
    ficha["campos"]["numero"]["tipo"] = "color"
    assert "campos.numero.tipo" in errores_de(config, ficha)


def test_regla_apunta_a_campo_inexistente(config):
    ficha = ficha_base()
    ficha["reglas"][1]["campo"] = "fecha_inventada"
    assert "campo inexistente 'fecha_inventada'" in errores_de(config, ficha)


def test_regla_de_dias_sin_dias(config):
    ficha = ficha_base()
    del ficha["reglas"][1]["dias"]
    assert "necesita 'dias'" in errores_de(config, ficha)


def test_regla_de_dias_con_dias_no_positivos(config):
    ficha = ficha_base()
    ficha["reglas"][1]["dias"] = 0
    assert "reglas.1.dias" in errores_de(config, ficha)


def test_patron_con_expresion_regular_invalida(config):
    ficha = ficha_base()
    ficha["campos"]["numero"]["patron"] = "^[A-Z"
    assert "expresion regular invalida" in errores_de(config, ficha)


def test_regla_patron_sobre_campo_sin_patron(config):
    ficha = ficha_base()
    del ficha["campos"]["numero"]["patron"]
    assert "no tiene patron" in errores_de(config, ficha)


def test_nombre_distinto_del_fichero(config):
    ficha = ficha_base()
    texto = yaml.safe_dump({**ficha, "nombre": "otro_nombre"})
    assert "no coincide con el nombre del fichero" in errores_de(config, crudo={"tipo_a.yaml": texto})


def test_ids_de_regla_repetidos(config):
    ficha = ficha_base()
    ficha["reglas"][1]["id"] = "formato_numero"
    assert "ids de regla repetidos: formato_numero" in errores_de(config, ficha)


def test_sin_campos(config):
    ficha = ficha_base()
    ficha["campos"] = {}
    ficha["reglas"] = []
    assert "tipo_a.yaml: campos:" in errores_de(config, ficha)


def test_comparacion_con_tipo_inexistente(config):
    ficha = ficha_base()
    ficha["comparaciones"] = {"tipo_fantasma": ["numero"]}
    assert "comparaciones.tipo_fantasma: tipo documental inexistente" in errores_de(config, ficha)


def test_comparacion_con_campo_que_no_existe_en_la_otra_ficha(config):
    a, b = ficha_base("tipo_a"), ficha_base("tipo_b")
    a["comparaciones"] = {"tipo_b": ["numero"]}
    b["campos"] = copy.deepcopy(b["campos"])
    del b["campos"]["numero"]
    b["reglas"] = [b["reglas"][1]]
    assert "el campo 'numero' no existe en ambas fichas" in errores_de(config, a, b)


def test_se_informan_todos_los_errores_a_la_vez(config):
    a, b = ficha_base("tipo_a"), ficha_base("tipo_b")
    a["confianza_minima_campo"] = 2
    b["reglas"][0]["severidad"] = "gravisima"
    with pytest.raises(ErrorConfiguracion) as exc:
        config(a, b)
    assert len(exc.value.errores) == 2
    assert any(e.startswith("tipo_a.yaml") for e in exc.value.errores)
    assert any(e.startswith("tipo_b.yaml") for e in exc.value.errores)


# --- ADR-009: nombre reservado ---

def test_ninguna_ficha_puede_llamarse_desconocido(config):
    assert "reservado" in errores_de(config, ficha_base("desconocido"))


def test_nombre_reservado_coincide_con_el_del_motor():
    from app.modulos.motor_ia.proveedores.base import DESCONOCIDO
    assert servicio.NOMBRE_RESERVADO == DESCONOCIDO


# --- ADR-007: marcadores de clasificacion ---

def test_marcadores_opcionales_y_validos(config):
    sin = config(ficha_base("tipo_a"))
    assert sin["tipo_a"].marcadores_clasificacion == []
    ficha = ficha_base("tipo_b")
    ficha["marcadores_clasificacion"] = [r"^P<[A-Z<]{3}", r"FECHA\s*(DE\s*)?EXPEDICION"]
    assert config(ficha)["tipo_b"].marcadores_clasificacion == ficha["marcadores_clasificacion"]


def test_marcador_con_expresion_regular_invalida(config):
    ficha = ficha_base()
    ficha["marcadores_clasificacion"] = ["VALIDO", "(sin cerrar"]
    assert "marcador 1" in errores_de(config, ficha)


def test_marcadores_repetidos(config):
    ficha = ficha_base()
    ficha["marcadores_clasificacion"] = ["CURP", "CURP"]
    assert "marcadores repetidos" in errores_de(config, ficha)


def test_las_fichas_reales_declaran_marcadores():
    for ficha in cargar().values():
        assert len(ficha.marcadores_clasificacion) >= 5, ficha.nombre


def test_marcadores_fuera_de_model_dump_y_de_tipos_documentales():
    # Son internos del motor: GET /tipos-documentales (Contrato 2) no los expone, tampoco cuando la API
    # serialice las fichas con model_dump() de configuracion.servicio.listar() (ADR-006 1.5).
    from app.modulos.api.tipos_documentales import TipoDocumental as RespuestaTipo
    for ficha in cargar().values():
        assert ficha.marcadores_clasificacion                       # el motor si los tiene
        volcado = ficha.model_dump(mode="json")
        assert "marcadores_clasificacion" not in volcado
        respuesta = RespuestaTipo.model_validate(volcado).model_dump(exclude_unset=True)
        assert "marcadores_clasificacion" not in respuesta


# --- Reglas de coherencia (etapa 2) ---

def _coherencia(**extra):
    return {"id": "coherente", "tipo": "fecha_anterior_a_campo", "campo": "fecha_vencimiento",
            "severidad": "critica", "mensaje": "Fechas incoherentes", **extra}


def test_regla_de_coherencia_valida(config):
    ficha = ficha_base()
    ficha["campos"]["fecha_expedicion"] = {"tipo": "fecha"}
    ficha["reglas"].append(_coherencia(campo="fecha_expedicion", campo_relacionado="fecha_vencimiento"))
    assert config(ficha)["tipo_a"].reglas[-1].campo_relacionado == "fecha_vencimiento"


def test_regla_de_coherencia_sin_campo_relacionado(config):
    ficha = ficha_base()
    ficha["reglas"].append(_coherencia())
    assert "campo_relacionado" in errores_de(config, ficha)


def test_campo_relacionado_en_una_regla_que_no_es_de_coherencia(config):
    ficha = ficha_base()
    ficha["reglas"][0]["campo_relacionado"] = "fecha_vencimiento"
    assert "campo_relacionado" in errores_de(config, ficha)


def test_campo_relacionado_inexistente(config):
    ficha = ficha_base()
    ficha["reglas"].append(_coherencia(campo_relacionado="no_existe"))
    assert "campo_relacionado inexistente" in errores_de(config, ficha)


def test_regla_de_coherencia_con_campos_de_otro_tipo(config):
    ficha = ficha_base()
    ficha["reglas"].append(_coherencia(campo="numero", campo_relacionado="fecha_vencimiento"))
    assert "necesita campos de tipo fecha y fecha" in errores_de(config, ficha)
