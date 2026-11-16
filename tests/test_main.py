import json

import main


def test_normalizar_texto_elimina_tildes_y_espacios():
    assert main.normalizar_texto("  Humedad   Relativa ") == "humedad relativa"


def test_desfuzzificacion_es_determinista_y_acotada():
    resultado = main.desfuzzificar_mamdani(0.0, 0.25, 0.4)
    assert 0.0 <= resultado <= 100.0
    assert resultado == main.desfuzzificar_mamdani(0.0, 0.25, 0.4)


def test_grounding_rechaza_numero_no_presentado():
    trazabilidad = {"modulo_3_prescripcion": {"viabilidad_calculada": 22.84}}
    assert main.explicacion_grounded_valida("Viabilidad: 22.84%.", trazabilidad)
    assert not main.explicacion_grounded_valida("Viabilidad: 99%.", trazabilidad)


def test_explicacion_grounding_rechaza_diagnostico_absoluto():
    trazabilidad = {"modulo_1_diagnostico": {"patologia_candidata": "Oídio"}}
    assert not main.explicacion_grounded_valida("Infección confirmada.", trazabilidad)


def test_extraccion_completa_claves_faltantes(monkeypatch):
    monkeypatch.setattr(
        main,
        "llamar_groq",
        lambda mensajes, modo_json=False: json.dumps({"intencion": "DIAGNOSTICO_LOTE"}),
    )
    resultado = main.llm_extraccion_unificada("hay oídio", {
        "patologias": ["Oídio"],
        "etapas": [],
        "quimicos": [],
        "lotes": [],
    })
    assert resultado["sintomas_reportados"] == []
    assert resultado["intencion"] == "DIAGNOSTICO_LOTE"
    assert resultado["_errores_extraccion"]


def test_pg3_diagnostico_cruza_diagnostico_y_riesgo():
    assert main.modulos_para_intencion("DIAGNOSTICO_LOTE") == [
        "DIAGNOSTICO_LOTE",
    ]


def test_pg3_prescripcion_cruza_tres_submodulos():
    assert main.modulos_para_intencion("PRESCRIPCION") == [
        "DIAGNOSTICO_LOTE",
        "RIESGO_BIOCLIMATICO",
        "PRESCRIPCION",
    ]


def test_pg3_fuera_de_dominio_no_ejecuta_submodulos():
    assert main.modulos_para_intencion("FUERA_DE_DOMINIO") == []


def test_datos_operativos_completan_clima_desde_diagnostico():
    datos = {"temperatura": None, "humedad_relativa": None, "patologia_mencionada": None}
    diagnostico = {
        "resultados": [{
            "temperatura_c": 25.5,
            "humedad_pct": 65,
            "patologia": "Oídio",
        }]
    }
    resultado = main.completar_datos_desde_diagnostico(datos, diagnostico)
    assert resultado["temperatura"] == 25.5
    assert resultado["humedad_relativa"] == 65
    assert resultado["patologia_mencionada"] == "Oídio"


def test_explicacion_solo_indica_modulos_ejecutados(monkeypatch):
    mensajes = []
    monkeypatch.setattr(
        main,
        "llamar_groq",
        lambda recibidos, modo_json=False: mensajes.append(recibidos) or "respuesta",
    )
    trazabilidad = {
        "orquestacion_pg3": {"modulos_ejecutados": ["DIAGNOSTICO_LOTE"]},
    }
    main.llm_explicacion_unificada(trazabilidad)
    prompt_usuario = mensajes[0][1]["content"]
    assert "Solo se ejecutaron estos módulos: DIAGNOSTICO_LOTE." in prompt_usuario
