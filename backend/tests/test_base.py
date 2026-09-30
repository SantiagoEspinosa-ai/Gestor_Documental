"""
Tests de la etapa 0: la app arranca, la configuracion es coherente entre ficheros y el Contrato 1
acepta el ejemplo de la diapositiva 7. No necesitan BD, S3 ni modelo.
"""
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.resultado import ResultadoDocumento, ResultadoExpediente

CONFIG = Path(__file__).resolve().parents[2] / "config"
TIPOS = {p.stem: yaml.safe_load(p.read_text(encoding="utf-8")) for p in (CONFIG / "tipos").glob("*.yaml")}


def test_salud():
    assert TestClient(app).get("/salud").json() == {"estado": "ok"}


def test_mvp_tiene_al_menos_tres_tipos_documentales():  # diapositiva 13
    assert len(TIPOS) >= 3


def test_cada_ficha_tiene_lo_que_pide_la_diapositiva_4():
    requeridas = {"nombre", "categoria", "descripcion", "caracteristicas_esperadas", "formatos_permitidos",
                  "campos", "confianza_minima_clasificacion", "confianza_minima_campo", "reglas"}
    for nombre, ficha in TIPOS.items():
        assert requeridas <= ficha.keys(), nombre
        assert ficha["nombre"] == nombre, "el nombre debe coincidir con el fichero"


def test_reglas_y_comparaciones_apuntan_a_campos_y_tipos_que_existen():
    for nombre, ficha in TIPOS.items():
        for regla in ficha["reglas"]:
            assert regla["campo"] in ficha["campos"], f"{nombre}: regla {regla['id']}"
        for otro, campos in (ficha.get("comparaciones") or {}).items():
            assert otro in TIPOS, f"{nombre}: compara con tipo inexistente {otro}"
            for campo in campos:
                assert campo in ficha["campos"] and campo in TIPOS[otro]["campos"], f"{nombre}<->{otro}: {campo}"


def test_procesos_usan_tipos_configurados():
    procesos = yaml.safe_load((CONFIG / "procesos.yaml").read_text(encoding="utf-8"))["procesos"]
    for nombre, proceso in procesos.items():
        for tipo in proceso["tipos_requeridos"] + proceso["tipos_opcionales"]:
            assert tipo in TIPOS, f"{nombre}: {tipo}"


def test_al_menos_dos_modelos_configurables_y_tareas_coherentes():  # diapositiva 13
    modelos = yaml.safe_load((CONFIG / "modelos.yaml").read_text(encoding="utf-8"))
    proveedores = modelos["proveedores"]
    assert len(proveedores) >= 2
    for tarea, asignacion in modelos["tareas"].items():
        assert asignacion["principal"] in proveedores, tarea
        assert asignacion["respaldo"] in (None, *proveedores), tarea
    for proveedor in proveedores.values():
        assert not any("key" in k and not k.endswith("_env") for k in proveedor), "claves solo por variable de entorno"


def test_contrato_1_acepta_el_ejemplo_de_la_diapositiva_7():
    documento = ResultadoDocumento.model_validate({
        "folio_solicitud": "ONB-2026-000001",
        "identificador_unico_documento": "00000000-0000-4000-8000-000000000001",
        "tipo_documental_declarado": "credencial_elector",
        "tipo_documental_detectado": "credencial_elector",
        "confianza_clasificacion": 0.97,
        "datos_extraidos": {"nombre_completo": "ANA EJEMPLO PRUEBA", "fecha_nacimiento": "1990-01-01"},
        "nivel_confianza_por_campo": {"nombre_completo": 0.98, "fecha_nacimiento": 0.93},
        "evidencia_por_campo": {"nombre_completo": "pagina_1", "fecha_nacimiento": "pagina_1"},
        "reglas_cumplidas_e_incumplidas": {"cumplidas": ["formato_curp_valido"], "incumplidas": ["vigencia_documento"]},
        "alertas_encontradas": [{"codigo": "REG-vigencia_documento", "mensaje": "La credencial esta vencida",
                                 "severidad": "bloqueante", "confianza": 0.9, "campo": "vigencia"}],
        "recomendacion": "revision_manual",
        "estado_analisis": "completado",
        "fecha_y_modelo_utilizado": {"fecha_analisis": "2026-09-29T10:00:00Z", "proveedor": "ollama",
                                     "modelo": "llama3.2-vision:11b", "version_prompt": "extraccion@v1"},
        "referencia_archivo_original": {"nombre_archivo": "credencial_sano_digital.pdf",
                                        "ruta": "onboarding/2026/000001/originales/x.pdf", "hash": "0" * 64},
    })
    expediente = ResultadoExpediente(folio="ONB-2026-000001", proceso="onboarding",
                                     estado_general="en_revision", documentos=[documento])
    assert expediente.documentos[0].alertas_encontradas[0].severidad.value == "bloqueante"
