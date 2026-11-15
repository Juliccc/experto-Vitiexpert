# -*- coding: utf-8 -*-
"""
VITI-EXPERT — Orquestador Unificado FastAPI
===========================================
Patrón sándwich unificado:
  texto_usuario
    → [LLM-1 Extracción Unificada] → validación Python
    → [Neo4j Módulo 1: Diagnóstico]
    → [Neo4j + Python Módulo 2: Riesgo Bioclimático (Alejo)]
    → [Neo4j + scikit-fuzzy Módulo 3: Prescripción Mamdani (Patricio)]
    → [LLM-2 Explicación Unificada → Receta Agraria Digital]

Autores: Julián Cadenas / Alejo Carobolante / Patricio Buono — Grupo 12, Comisión 5k9, UTN FRM
"""

import json
import hmac
import logging
import math
import os
import re
import unicodedata
from contextlib import asynccontextmanager
from typing import Any, Optional

import numpy as np
import skfuzzy as fuzz
from dotenv import load_dotenv
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from groq import Groq
from neo4j import GraphDatabase
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# 0. Configuración y arranque
# ---------------------------------------------------------------------------
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("vitiexpert")

# Variables de entorno
GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL     = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_TRANSCRIPTION_MODEL = os.getenv("GROQ_TRANSCRIPTION_MODEL", "whisper-large-v3-turbo")
NEO4J_URI      = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", None)   # None → base por defecto
ADMIN_TOKEN     = os.getenv("ADMIN_TOKEN", "")

# Clientes globales (inicializados en lifespan)
groq_client: Groq = None
neo4j_driver = None
startup_error: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa y cierra conexiones al arrancar/apagar el servidor."""
    global groq_client, neo4j_driver, startup_error
    log.info("Iniciando VITI-EXPERT...")
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY es obligatoria para iniciar VITI-EXPERT.")
    if not NEO4J_PASSWORD or NEO4J_PASSWORD == "change-me":
        raise RuntimeError("NEO4J_PASSWORD debe configurarse con un valor no predeterminado.")
    groq_client = Groq(api_key=GROQ_API_KEY, timeout=30, max_retries=0)
    neo4j_driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
        connection_timeout=10,
        max_connection_lifetime=300,
    )
    try:
        neo4j_driver.verify_connectivity()
        log.info("Neo4j conectado. Modelo LLM: %s", GROQ_MODEL)
        _cargar_grafo()
        log.info("Grafo de conocimiento sincronizado.")
    except Exception as exc:
        startup_error = str(exc)
        neo4j_driver.close()
        neo4j_driver = None
        raise RuntimeError(f"No se pudo inicializar Neo4j: {exc}") from exc
    yield
    if neo4j_driver is not None:
        neo4j_driver.close()
    log.info("VITI-EXPERT apagado.")


app = FastAPI(
    title="VITI-EXPERT",
    description="Sistema Experto Vitivinícola — Orquestador Unificado",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# 1. Modelos Pydantic
# ---------------------------------------------------------------------------
class ConsultaRequest(BaseModel):
    mensaje: str = Field(
        ...,
        min_length=5,
        max_length=4000,
        description="Reporte coloquial del encargado de finca",
    )


class ConsultaResponse(BaseModel):
    receta_agraria: str
    trazabilidad: dict[str, Any]


# ---------------------------------------------------------------------------
# 2. Helpers de bajo nivel
# ---------------------------------------------------------------------------
def normalizar_texto(texto: str) -> str:
    t = unicodedata.normalize("NFD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip().lower()


def es_numero(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)


def ejecutar_cypher(consulta: str, parametros: dict | None = None) -> list[dict]:
    if neo4j_driver is None:
        raise RuntimeError("Neo4j no está inicializado.")
    registros, _, _ = neo4j_driver.execute_query(
        consulta,
        parameters_=parametros or {},
        database_=NEO4J_DATABASE,
    )
    return [r.data() for r in registros]


def llamar_groq(mensajes: list[dict], modo_json: bool = False) -> str:
    kwargs: dict = {"model": GROQ_MODEL, "messages": mensajes, "temperature": 0}
    if modo_json:
        kwargs["response_format"] = {"type": "json_object"}
    if groq_client is None:
        raise RuntimeError("El cliente Groq no está inicializado.")
    try:
        respuesta = groq_client.chat.completions.create(**kwargs)
    except Exception as first_error:
        status_code = getattr(first_error, "status_code", None)
        if not modo_json or status_code in {401, 403, 429}:
            raise RuntimeError(f"Error en Groq: {first_error}") from first_error
        kwargs.pop("response_format", None)
        try:
            respuesta = groq_client.chat.completions.create(**kwargs)
        except Exception as second_error:
            raise RuntimeError(f"Error en Groq: {second_error}") from second_error
    contenido = (respuesta.choices[0].message.content or "").strip()
    # Limpiar bloque <think>…</think> de modelos razonadores
    if "<think>" in contenido and "</think>" in contenido:
        contenido = contenido.split("</think>")[-1].strip()
    return contenido


# ---------------------------------------------------------------------------
# 3. Carga del grafo de conocimiento (idempotente — MERGE)
# ---------------------------------------------------------------------------
CYPHER_PG2_BASE = """
// 1. Patologías y Principios Activos
MERGE (p_oidio:Patologia_Fungica {nombre: "Oídio"})
SET p_oidio.requiere_agua_libre = false,
    p_oidio.etapas_susceptibles = ["Floración", "Envero", "Maduración"]

MERGE (p_pero:Patologia_Fungica {nombre: "Peronóspora"})
SET p_pero.requiere_agua_libre = true,
    p_pero.etapas_susceptibles = ["Brotación", "Floración", "Envero"]

MERGE (p_botr:Patologia_Fungica {nombre: "Botritis"})
SET p_botr.requiere_agua_libre = true,
    p_botr.etapas_susceptibles = ["Envero", "Maduración"]

MERGE (pa_miclo:Principio_Activo {nombre_quimico: "Miclobutanil"})
SET pa_miclo.dias_carencia = 14, pa_miclo.espectro = "Sistémico"

MERGE (pa_azufre:Principio_Activo {nombre_quimico: "Azufre_Mojable"})
SET pa_azufre.dias_carencia = 5, pa_azufre.espectro = "Contacto_Preventivo"

MERGE (pa_oxiclo:Principio_Activo {nombre_quimico: "Oxicloruro_de_Cobre"})
SET pa_oxiclo.dias_carencia = 21, pa_oxiclo.espectro = "Contacto_Preventivo"

// 2. Variables Difusas: Severidad_de_la_Infeccion
MERGE (v_sev:VariableDifusa {nombreVariable: "Severidad_de_la_Infeccion"})
SET v_sev.universoMin = 0.0, v_sev.universoMax = 100.0, v_sev.tipo = "Entrada"
MERGE (v_prox:VariableDifusa {nombreVariable: "Proximidad_a_Cosecha"})
SET v_prox.universoMin = 0.0, v_prox.universoMax = 120.0, v_prox.tipo = "Entrada"
MERGE (v_viab:VariableDifusa {nombreVariable: "Viabilidad_Aplicacion"})
SET v_viab.universoMin = 0.0, v_viab.universoMax = 100.0, v_viab.tipo = "Salida"

// Conjuntos difusos — Severidad
MERGE (c_sev_leve:ConjuntoDifuso {id_conjunto: "Sev_Leve"})
SET c_sev_leve.nombreEtiqueta = "Leve", c_sev_leve.variable = "Severidad_de_la_Infeccion"
MERGE (f_sev_leve:FuncionPertenencia {id_funcion: "FP_Sev_Leve"})
SET f_sev_leve.tipoFuncion = "Gaussiana", f_sev_leve.centro_c = 0.0, f_sev_leve.dispersion_sigma = 15.0
MERGE (v_sev)-[:TIENE_ETIQUETA]->(c_sev_leve)
MERGE (c_sev_leve)-[:MODELADO_POR]->(f_sev_leve)

MERGE (c_sev_mod:ConjuntoDifuso {id_conjunto: "Sev_Moderada"})
SET c_sev_mod.nombreEtiqueta = "Moderada", c_sev_mod.variable = "Severidad_de_la_Infeccion"
MERGE (f_sev_mod:FuncionPertenencia {id_funcion: "FP_Sev_Moderada"})
SET f_sev_mod.tipoFuncion = "Gaussiana", f_sev_mod.centro_c = 40.0, f_sev_mod.dispersion_sigma = 15.0
MERGE (v_sev)-[:TIENE_ETIQUETA]->(c_sev_mod)
MERGE (c_sev_mod)-[:MODELADO_POR]->(f_sev_mod)

MERGE (c_sev_sev:ConjuntoDifuso {id_conjunto: "Sev_Severa"})
SET c_sev_sev.nombreEtiqueta = "Severa", c_sev_sev.variable = "Severidad_de_la_Infeccion"
MERGE (f_sev_sev:FuncionPertenencia {id_funcion: "FP_Sev_Severa"})
SET f_sev_sev.tipoFuncion = "Gaussiana", f_sev_sev.centro_c = 100.0, f_sev_sev.dispersion_sigma = 25.0
MERGE (v_sev)-[:TIENE_ETIQUETA]->(c_sev_sev)
MERGE (c_sev_sev)-[:MODELADO_POR]->(f_sev_sev)

// Conjuntos difusos — Proximidad a Cosecha
MERGE (c_prox_inm:ConjuntoDifuso {id_conjunto: "Prox_Inminente"})
SET c_prox_inm.nombreEtiqueta = "Inminente", c_prox_inm.variable = "Proximidad_a_Cosecha"
MERGE (f_prox_inm:FuncionPertenencia {id_funcion: "FP_Prox_Inminente"})
SET f_prox_inm.tipoFuncion = "Gaussiana", f_prox_inm.centro_c = 0.0, f_prox_inm.dispersion_sigma = 12.0
MERGE (v_prox)-[:TIENE_ETIQUETA]->(c_prox_inm)
MERGE (c_prox_inm)-[:MODELADO_POR]->(f_prox_inm)

MERGE (c_prox_cer:ConjuntoDifuso {id_conjunto: "Prox_Cercana"})
SET c_prox_cer.nombreEtiqueta = "Cercana", c_prox_cer.variable = "Proximidad_a_Cosecha"
MERGE (f_prox_cer:FuncionPertenencia {id_funcion: "FP_Prox_Cercana"})
SET f_prox_cer.tipoFuncion = "Gaussiana", f_prox_cer.centro_c = 35.0, f_prox_cer.dispersion_sigma = 15.0
MERGE (v_prox)-[:TIENE_ETIQUETA]->(c_prox_cer)
MERGE (c_prox_cer)-[:MODELADO_POR]->(f_prox_cer)

MERGE (c_prox_lej:ConjuntoDifuso {id_conjunto: "Prox_Lejana"})
SET c_prox_lej.nombreEtiqueta = "Lejana", c_prox_lej.variable = "Proximidad_a_Cosecha"
MERGE (f_prox_lej:FuncionPertenencia {id_funcion: "FP_Prox_Lejana"})
SET f_prox_lej.tipoFuncion = "Gaussiana", f_prox_lej.centro_c = 100.0, f_prox_lej.dispersion_sigma = 30.0
MERGE (v_prox)-[:TIENE_ETIQUETA]->(c_prox_lej)
MERGE (c_prox_lej)-[:MODELADO_POR]->(f_prox_lej)

// Conjuntos difusos — Viabilidad
MERGE (c_viab_baja:ConjuntoDifuso {id_conjunto: "Viab_Baja"})
SET c_viab_baja.nombreEtiqueta = "Baja", c_viab_baja.variable = "Viabilidad_Aplicacion"
MERGE (f_viab_baja:FuncionPertenencia {id_funcion: "FP_Viab_Baja"})
SET f_viab_baja.tipoFuncion = "Gaussiana", f_viab_baja.centro_c = 0.0, f_viab_baja.dispersion_sigma = 15.0
MERGE (v_viab)-[:TIENE_ETIQUETA]->(c_viab_baja)
MERGE (c_viab_baja)-[:MODELADO_POR]->(f_viab_baja)

MERGE (c_viab_media:ConjuntoDifuso {id_conjunto: "Viab_Media"})
SET c_viab_media.nombreEtiqueta = "Media", c_viab_media.variable = "Viabilidad_Aplicacion"
MERGE (f_viab_media:FuncionPertenencia {id_funcion: "FP_Viab_Media"})
SET f_viab_media.tipoFuncion = "Gaussiana", f_viab_media.centro_c = 50.0, f_viab_media.dispersion_sigma = 15.0
MERGE (v_viab)-[:TIENE_ETIQUETA]->(c_viab_media)
MERGE (c_viab_media)-[:MODELADO_POR]->(f_viab_media)

MERGE (c_viab_alta:ConjuntoDifuso {id_conjunto: "Viab_Alta"})
SET c_viab_alta.nombreEtiqueta = "Alta", c_viab_alta.variable = "Viabilidad_Aplicacion"
MERGE (f_viab_alta:FuncionPertenencia {id_funcion: "FP_Viab_Alta"})
SET f_viab_alta.tipoFuncion = "Gaussiana", f_viab_alta.centro_c = 100.0, f_viab_alta.dispersion_sigma = 15.0
MERGE (v_viab)-[:TIENE_ETIQUETA]->(c_viab_alta)
MERGE (c_viab_alta)-[:MODELADO_POR]->(f_viab_alta)

// Reglas Difusas RD_01 … RD_05
MERGE (r1:ReglaDifusa {codigoRegla: "RD_01"})
SET r1.descripcion = "SI Proximidad ES Inminente OR Severidad ES Leve ENTONCES Viabilidad ES Baja",
    r1.operador = "MAX", r1.pesoRegla = 1.0
MERGE (r1)-[:EVALUA_ANTECEDENTE {operador: "OR"}]->(c_prox_inm)
MERGE (r1)-[:EVALUA_ANTECEDENTE {operador: "OR"}]->(c_sev_leve)
MERGE (r1)-[:DETERMINA_CONSECUENTE]->(c_viab_baja)

MERGE (r2:ReglaDifusa {codigoRegla: "RD_02"})
SET r2.descripcion = "SI Proximidad ES Lejana AND Severidad ES Severa ENTONCES Viabilidad ES Alta",
    r2.operador = "MIN", r2.pesoRegla = 1.0
MERGE (r2)-[:EVALUA_ANTECEDENTE {operador: "AND"}]->(c_prox_lej)
MERGE (r2)-[:EVALUA_ANTECEDENTE {operador: "AND"}]->(c_sev_sev)
MERGE (r2)-[:DETERMINA_CONSECUENTE]->(c_viab_alta)

MERGE (r3:ReglaDifusa {codigoRegla: "RD_03"})
SET r3.descripcion = "SI Proximidad ES Cercana AND Severidad ES Moderada ENTONCES Viabilidad ES Media",
    r3.operador = "MIN", r3.pesoRegla = 1.0
MERGE (r3)-[:EVALUA_ANTECEDENTE {operador: "AND"}]->(c_prox_cer)
MERGE (r3)-[:EVALUA_ANTECEDENTE {operador: "AND"}]->(c_sev_mod)
MERGE (r3)-[:DETERMINA_CONSECUENTE]->(c_viab_media)

MERGE (r4:ReglaDifusa {codigoRegla: "RD_04"})
SET r4.descripcion = "SI Proximidad ES Lejana AND Severidad ES Moderada ENTONCES Viabilidad ES Alta",
    r4.operador = "MIN", r4.pesoRegla = 1.0
MERGE (r4)-[:EVALUA_ANTECEDENTE {operador: "AND"}]->(c_prox_lej)
MERGE (r4)-[:EVALUA_ANTECEDENTE {operador: "AND"}]->(c_sev_mod)
MERGE (r4)-[:DETERMINA_CONSECUENTE]->(c_viab_alta)

MERGE (r5:ReglaDifusa {codigoRegla: "RD_05"})
SET r5.descripcion = "SI Proximidad ES Cercana AND Severidad ES Severa ENTONCES Viabilidad ES Media",
    r5.operador = "MIN", r5.pesoRegla = 1.0
MERGE (r5)-[:EVALUA_ANTECEDENTE {operador: "AND"}]->(c_prox_cer)
MERGE (r5)-[:EVALUA_ANTECEDENTE {operador: "AND"}]->(c_sev_sev)
MERGE (r5)-[:DETERMINA_CONSECUENTE]->(c_viab_media)

// Lotes de prueba
MERGE (l1:Lote_Vinedo {id_lote: "Lote_Norte_01"})
SET l1.etapa_fenologica = "Floración", l1.dias_para_cosecha = 60, l1.porcentaje_area_afectada = 50.0
MERGE (s1:Sintoma_Visual {id_sintoma: "Sintoma_01"})
SET s1.ubicacion = "Haz_y_Envés", s1.textura = "PolvilloCeniza", s1.distribucion = "UniformeIntercostal"
MERGE (e1:Evidencia_Climatica {id_clima: "Clima_01"})
SET e1.temperatura_media = 25.5, e1.humedad_relativa = 65.0,
    e1.evento_inhibitorio_reciente = false, e1.severidad_estimada = "Moderada"
MERGE (d1:Diagnostico_Presuntivo {id_diag: "Diag_01"})
SET d1.factor_certeza_ambiental = "Pendiente"
MERGE (t1a:Tratamiento {id_trat: "Trat_01"})
SET t1a.estado_evaluacion = "Pendiente", t1a.viabilidad_agronomica = 0.0
MERGE (t1b:Tratamiento {id_trat: "Trat_02"})
SET t1b.estado_evaluacion = "Pendiente", t1b.viabilidad_agronomica = 0.0
MERGE (s1)-[:GENERA_HIPOTESIS]->(d1)
MERGE (d1)-[:IDENTIFICA_CANDIDATO]->(p_oidio)
MERGE (e1)-[:CONFIRMA_O_REFUTA]->(d1)
MERGE (l1)-[:EVALUA_INOCUIDAD]->(t1a)
MERGE (t1a)-[:COMBATE]->(p_oidio)
MERGE (t1a)-[:UTILIZA_QUIMICO]->(pa_miclo)
MERGE (l1)-[:EVALUA_INOCUIDAD]->(t1b)
MERGE (t1b)-[:COMBATE]->(p_oidio)
MERGE (t1b)-[:UTILIZA_QUIMICO]->(pa_azufre)

MERGE (l2:Lote_Vinedo {id_lote: "Lote_Sur_02"})
SET l2.etapa_fenologica = "Maduración", l2.dias_para_cosecha = 10, l2.porcentaje_area_afectada = 75.0
MERGE (s2:Sintoma_Visual {id_sintoma: "Sintoma_02"})
SET s2.ubicacion = "Haz_y_Envés", s2.textura = "PolvilloCeniza", s2.distribucion = "Irregular"
MERGE (e2:Evidencia_Climatica {id_clima: "Clima_02"})
SET e2.temperatura_media = 26.0, e2.humedad_relativa = 70.0,
    e2.evento_inhibitorio_reciente = false, e2.severidad_estimada = "Critica"
MERGE (d2:Diagnostico_Presuntivo {id_diag: "Diag_02"})
SET d2.factor_certeza_ambiental = "Pendiente"
MERGE (t2a:Tratamiento {id_trat: "Trat_03"})
SET t2a.estado_evaluacion = "Pendiente", t2a.viabilidad_agronomica = 0.0
MERGE (t2b:Tratamiento {id_trat: "Trat_04"})
SET t2b.estado_evaluacion = "Pendiente", t2b.viabilidad_agronomica = 0.0
MERGE (s2)-[:GENERA_HIPOTESIS]->(d2)
MERGE (d2)-[:IDENTIFICA_CANDIDATO]->(p_oidio)
MERGE (e2)-[:CONFIRMA_O_REFUTA]->(d2)
MERGE (l2)-[:EVALUA_INOCUIDAD]->(t2a)
MERGE (t2a)-[:COMBATE]->(p_oidio)
MERGE (t2a)-[:UTILIZA_QUIMICO]->(pa_miclo)
MERGE (l2)-[:EVALUA_INOCUIDAD]->(t2b)
MERGE (t2b)-[:COMBATE]->(p_oidio)
MERGE (t2b)-[:UTILIZA_QUIMICO]->(pa_azufre)

MERGE (l3:Lote_Vinedo {id_lote: "Lote_Oeste_03"})
SET l3.etapa_fenologica = "Envero", l3.dias_para_cosecha = 45, l3.porcentaje_area_afectada = 15.0
MERGE (s3:Sintoma_Visual {id_sintoma: "Sintoma_03"})
SET s3.ubicacion = "Envés", s3.textura = "ManchaAceite", s3.distribucion = "Irregular"
MERGE (e3:Evidencia_Climatica {id_clima: "Clima_03"})
SET e3.temperatura_media = 36.0, e3.humedad_relativa = 14.0,
    e3.evento_inhibitorio_reciente = true, e3.severidad_estimada = "Nula"
MERGE (d3:Diagnostico_Presuntivo {id_diag: "Diag_03"})
SET d3.factor_certeza_ambiental = "Pendiente"
MERGE (t3:Tratamiento {id_trat: "Trat_05"})
SET t3.estado_evaluacion = "Pendiente", t3.viabilidad_agronomica = 0.0
MERGE (s3)-[:GENERA_HIPOTESIS]->(d3)
MERGE (d3)-[:IDENTIFICA_CANDIDATO]->(p_pero)
MERGE (e3)-[:CONFIRMA_O_REFUTA]->(d3)
MERGE (l3)-[:EVALUA_INOCUIDAD]->(t3)
MERGE (t3)-[:COMBATE]->(p_pero)
MERGE (t3)-[:UTILIZA_QUIMICO]->(pa_oxiclo)
"""

EXTENSION_BIOCLIMATICA = [
    # Etapas fenológicas
    """UNWIND [{n:"Brotación",o:1},{n:"Floración",o:2},{n:"Cuajado",o:3},{n:"Envero",o:4},{n:"Maduración",o:5}] AS et
       MERGE (e:EtapaFenologica {nombre: et.n}) SET e.orden = et.o""",
    """MATCH (p:Patologia_Fungica)
       UNWIND coalesce(p.etapas_susceptibles, []) AS etapa
       MATCH (e:EtapaFenologica {nombre: etapa})
       MERGE (p)-[:POSIBLE_EN]->(e)""",
    # Condiciones climáticas
    """MATCH (p:Patologia_Fungica {nombre: "Peronóspora"})
       MERGE (c:CondicionClimatica {id_condicion: "COND-PER"})
       SET c.temp_min = 10.0, c.temp_max = 30.0, c.temp_optima_min = 20.0, c.temp_optima_max = 25.0,
           c.humedad_min = 70.0, c.humedad_optima_min = 80.0, c.humedad_optima_max = 100.0,
           c.horas_mojado_min = 6, c.fuente = "Cuaderno de Conocimiento PI1 (Carobolante, 2026)"
       MERGE (p)-[:REQUIERE_CONDICION]->(c)""",
    """MATCH (p:Patologia_Fungica {nombre: "Oídio"})
       MERGE (c:CondicionClimatica {id_condicion: "COND-OID"})
       SET c.temp_min = 8.0, c.temp_max = 35.0, c.temp_optima_min = 22.0, c.temp_optima_max = 28.0,
           c.humedad_min = 40.0, c.humedad_max = 85.0, c.humedad_optima_min = 45.0, c.humedad_optima_max = 70.0,
           c.fuente = "Cuaderno de Conocimiento PI1 (Carobolante, 2026)"
       MERGE (p)-[:REQUIERE_CONDICION]->(c)""",
    """MATCH (p:Patologia_Fungica {nombre: "Botritis"})
       MERGE (c:CondicionClimatica {id_condicion: "COND-BOT"})
       SET c.temp_min = 5.0, c.temp_max = 30.0, c.temp_optima_min = 15.0, c.temp_optima_max = 25.0,
           c.humedad_min = 85.0, c.humedad_optima_min = 90.0, c.humedad_optima_max = 100.0,
           c.horas_mojado_min = 15, c.fuente = "Cuaderno de Conocimiento PI1 (Carobolante, 2026)"
       MERGE (p)-[:REQUIERE_CONDICION]->(c)""",
    # Evento inhibitorio Zonda
    """MERGE (e:EventoInhibitorio {nombre: "Viento Zonda"})
       SET e.tipo = "Desecación térmica", e.temp_disparo_min = 32.0, e.humedad_max_limite = 20.0,
           e.descripcion = "Viento cálido y seco que reduce la favorabilidad para el desarrollo fúngico"
       WITH e
       MATCH (p:Patologia_Fungica) WHERE p.nombre IN ["Peronóspora", "Oídio", "Botritis"]
       MERGE (e)-[:INHIBE]->(p)""",
    # Reglas bioclimáticas
    """MERGE (r:ReglaBioclimatica {codigo: "REG-BIO-INH-01"})
       SET r.nombre = "Inhibición por evento meteorológico", r.estrategia = "INHIBICION", r.prioridad = 1
       WITH r MATCH (p:Patologia_Fungica) WHERE p.nombre IN ["Peronóspora", "Oídio", "Botritis"]
       MERGE (r)-[:APLICA_A]->(p)""",
    """MATCH (p:Patologia_Fungica {nombre: "Peronóspora"})
       MERGE (r:ReglaBioclimatica {codigo: "REG-BIO-PER-01"})
       SET r.nombre = "Favorabilidad para Peronóspora", r.estrategia = "PERONOSPORA", r.prioridad = 2
       MERGE (r)-[:APLICA_A]->(p)""",
    """MATCH (p:Patologia_Fungica {nombre: "Oídio"})
       MERGE (r:ReglaBioclimatica {codigo: "REG-BIO-OID-01"})
       SET r.nombre = "Favorabilidad para Oídio", r.estrategia = "OIDIO", r.prioridad = 2
       MERGE (r)-[:APLICA_A]->(p)""",
    """MATCH (p:Patologia_Fungica {nombre: "Botritis"})
       MERGE (r:ReglaBioclimatica {codigo: "REG-BIO-BOT-01"})
       SET r.nombre = "Favorabilidad para Botritis", r.estrategia = "BOTRITIS", r.prioridad = 2
       MERGE (r)-[:APLICA_A]->(p)""",
]


def _cargar_grafo():
    ejecutar_cypher(CYPHER_PG2_BASE)
    for s in EXTENSION_BIOCLIMATICA:
        ejecutar_cypher(s)


# ---------------------------------------------------------------------------
# 4. Catálogos (leídos del grafo en arranque)
# ---------------------------------------------------------------------------
CATALOGO: dict[str, list[str]] = {}


def cargar_catalogo() -> dict[str, list[str]]:
    patologias = [r["nombre"] for r in ejecutar_cypher(
        "MATCH (p:Patologia_Fungica) RETURN p.nombre AS nombre ORDER BY nombre")]
    etapas = [r["nombre"] for r in ejecutar_cypher(
        "MATCH (e:EtapaFenologica) RETURN e.nombre AS nombre, e.orden AS orden ORDER BY orden")]
    quimicos = [r["nombre"] for r in ejecutar_cypher(
        "MATCH (pa:Principio_Activo) RETURN pa.nombre_quimico AS nombre ORDER BY nombre")]
    lotes = [r["id"] for r in ejecutar_cypher(
        "MATCH (l:Lote_Vinedo) RETURN l.id_lote AS id ORDER BY id")]
    return {"patologias": patologias, "etapas": etapas, "quimicos": quimicos, "lotes": lotes}


# ---------------------------------------------------------------------------
# 5. FASE 1 — Extracción Unificada (LLM)
# ---------------------------------------------------------------------------
SYSTEM_PROMPT_EXTRACCION_UNIFICADO = """Eres el módulo de extracción semántica unificado de VITI-EXPERT.
Tu ÚNICA función es convertir el reporte coloquial del encargado de finca en un único objeto JSON estructurado.
Este JSON se usará como entrada para tres motores especializados: Diagnóstico (Julián), Riesgo Bioclimático (Alejo) y Prescripción (Patricio).

REGLAS OBLIGATORIAS:
1. Responde SOLO con un objeto JSON válido. Sin saludos, sin markdown, sin texto adicional.
2. NO diagnostiques ni prescribas. Solo extrae y normaliza lo que el usuario dijo.
3. Si un dato no fue mencionado, usa null. Nunca inventes valores.

CLAVES REQUERIDAS (siempre presentes, con null si no aplica):
- "id_lote": Normaliza a "Lote_Norte_01", "Lote_Sur_02", "Lote_Oeste_03" o null.
  (lote norte/1 → Lote_Norte_01; lote sur/2 → Lote_Sur_02; lote oeste/3 → Lote_Oeste_03)
- "etapa_fenologica": uno de ["Brotación","Floración","Cuajado","Envero","Maduración"] o null.
- "sintomas_reportados": lista de objetos con claves "ubicacion", "textura", "distribucion".
  - ubicacion: "Haz"|"Envés"|"Haz_y_Envés"|"Racimo"|"Brote"|null
  - textura: "PolvilloCeniza"|"MohoGris"|"ManchaAceite"|"Ninguna"|null
  - distribucion: "UniformeIntercostal"|"Irregular"|null
  Lista vacía si no describe síntomas visuales.
- "temperatura": número en °C o null.
- "humedad_relativa": número en % (0-100) o null.
- "horas_mojado": entero de horas de mojado foliar o null. (0 solo si se afirma explícitamente follaje seco)
- "viento_zonda": true si se menciona Zonda; false si se niega; null si no se menciona.
- "dias_para_cosecha": entero (0-365) o null. ("dos meses" → 60, "una semana" → 7)
- "porcentaje_area_afectada": float (0.0-100.0) o null. ("la mitad" → 50.0, "tres cuartas partes" → 75.0)
- "patologia_mencionada": uno de ["Oídio","Peronóspora","Botritis"] o null. 
  Sinónimos: cenicilla/polvillo/quintal → Oídio; mildiu/mancha de aceite → Peronóspora; podredumbre gris → Botritis.
- "principio_activo": uno de ["Miclobutanil","Azufre_Mojable","Oxicloruro_de_Cobre"] o null.
- "intencion": "DIAGNOSTICO_LOTE"|"PRESCRIPCION"|"CONSULTA_CARENCIA"|"FUERA_DE_DOMINIO"
- "fuera_de_dominio": true si no trata de enfermedades fúngicas de la vid, false en caso contrario.
"""


LIMITES_FISICOS = {
    "temperatura":      (-10.0, 60.0),
    "humedad_relativa": (0.0, 100.0),
    "horas_mojado":     (0, 24),
    "dias_para_cosecha":        (0, 365),
    "porcentaje_area_afectada": (0.0, 100.0),
}
CLAVES_NUMERICAS = set(LIMITES_FISICOS.keys())
CLAVES_EXTRACCION_UNIF = {
    "id_lote", "etapa_fenologica", "sintomas_reportados",
    "temperatura", "humedad_relativa", "horas_mojado", "viento_zonda",
    "dias_para_cosecha", "porcentaje_area_afectada",
    "patologia_mencionada", "principio_activo",
    "intencion", "fuera_de_dominio",
}
INTENCIONES_VALIDAS = {
    "DIAGNOSTICO_LOTE",
    "PRESCRIPCION",
    "CONSULTA_CARENCIA",
    "FUERA_DE_DOMINIO",
}
CLAVES_OBLIGATORIAS_EXTRACCION = {
    "id_lote": None,
    "etapa_fenologica": None,
    "sintomas_reportados": [],
    "temperatura": None,
    "humedad_relativa": None,
    "horas_mojado": None,
    "viento_zonda": None,
    "dias_para_cosecha": None,
    "porcentaje_area_afectada": None,
    "patologia_mencionada": None,
    "principio_activo": None,
    "intencion": "DIAGNOSTICO_LOTE",
    "fuera_de_dominio": False,
}

SYSTEM_PROMPT_MAESTRO = """Eres el orquestador maestro de VITI-EXPERT, un asistente experto
vitivinícola. Debes enrutar cada consulta hacia los submódulos adecuados sin resolver por tu
cuenta ninguna regla agronómica, normativa o difusa.

Submódulos disponibles:
- DIAGNOSTICO_LOTE: hipótesis fitosanitaria y evidencia visual/contextual.
- RIESGO_BIOCLIMATICO: favorabilidad ambiental según clima, etapa y eventos inhibitorios.
- PRESCRIPCION: carencia/LMR crisp, alternativas y viabilidad Mamdani.
- CONSULTA_CARENCIA: solo verificación de carencia para un lote y principio activo.

Reglas de enrutamiento:
1. Si la consulta pide qué ocurre, identificar una patología o evaluar síntomas, usa
   DIAGNOSTICO_LOTE y RIESGO_BIOCLIMATICO.
2. Si pide recomendar, seleccionar o aplicar un tratamiento, usa DIAGNOSTICO_LOTE,
   RIESGO_BIOCLIMATICO y PRESCRIPCION.
3. Si pregunta únicamente por carencia, usa CONSULTA_CARENCIA.
4. Si no pertenece a enfermedades fúngicas de la vid, marca FUERA_DE_DOMINIO.
5. Neo4j y los motores Python son la única fuente de verdad. El LLM solo extrae datos,
   clasifica la intención y redacta una explicación grounded.
6. Nunca inventes valores faltantes, diagnósticos definitivos, dosis ni normativa vigente.
"""


def _canonico(valor: str, opciones: list[str]) -> str | None:
    """Mapeo flexible sin tildes ni mayúsculas."""
    return {normalizar_texto(o): o for o in opciones}.get(normalizar_texto(valor))


def llm_extraccion_unificada(mensaje: str, catalogo: dict) -> dict:
    """Fase 1: LLM extrae JSON unificado; Python valida y normaliza los rangos."""
    prompt = SYSTEM_PROMPT_MAESTRO + "\n\n" + SYSTEM_PROMPT_EXTRACCION_UNIFICADO
    mensajes = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Reporte del encargado:\n{mensaje}"},
    ]
    ultimo_error = None
    for _ in range(2):
        crudo = llamar_groq(mensajes, modo_json=True)
        limpio = re.sub(r"^```(?:json)?\s*|\s*```$", "", crudo.strip())
        try:
            datos = json.loads(limpio)
            if isinstance(datos, dict):
                break
        except (json.JSONDecodeError, ValueError) as e:
            ultimo_error = e
    else:
        raise RuntimeError(f"El LLM no devolvió un JSON válido: {ultimo_error}")

    # --- Normalización y validación determinística ---
    errores: list[str] = []
    for clave, valor_por_defecto in CLAVES_OBLIGATORIAS_EXTRACCION.items():
        if clave not in datos:
            datos[clave] = list(valor_por_defecto) if isinstance(valor_por_defecto, list) else valor_por_defecto
            errores.append(f"Falta la clave obligatoria '{clave}'; se aplicó null.")

    intencion = datos.get("intencion")
    if intencion not in INTENCIONES_VALIDAS:
        errores.append(f"intencion: valor no permitido {intencion!r}.")
        datos["intencion"] = "DIAGNOSTICO_LOTE"

    if not isinstance(datos.get("fuera_de_dominio"), bool):
        errores.append("fuera_de_dominio: se esperaba true/false.")
        datos["fuera_de_dominio"] = False

    sintomas = datos.get("sintomas_reportados")
    if not isinstance(sintomas, list):
        errores.append("sintomas_reportados: se esperaba una lista.")
        datos["sintomas_reportados"] = []
    else:
        datos["sintomas_reportados"] = [
            item for item in sintomas if isinstance(item, dict)
        ]

    # Campos de vocabulario controlado
    for campo, opciones_key in [
        ("patologia_mencionada", "patologias"),
        ("etapa_fenologica", "etapas"),
        ("principio_activo", "quimicos"),
        ("id_lote", "lotes"),
    ]:
        valor = datos.get(campo)
        if valor is not None and isinstance(valor, str):
            canonico = _canonico(valor, catalogo.get(opciones_key, []))
            if canonico is None:
                errores.append(f"{campo}: '{valor}' no existe en el catálogo del grafo.")
                datos[campo] = None
            else:
                datos[campo] = canonico

    # Campos numéricos con rangos físicos
    for campo, (minimo, maximo) in LIMITES_FISICOS.items():
        valor = datos.get(campo)
        if valor is None:
            continue
        if not es_numero(valor):
            errores.append(f"{campo}: se esperaba un número, llegó {valor!r}.")
            datos[campo] = None
            continue
        if campo == "horas_mojado" or campo == "dias_para_cosecha":
            if float(valor) != int(float(valor)):
                errores.append(f"{campo}: debe ser entero, llegó {valor}.")
                datos[campo] = None
                continue
            datos[campo] = int(float(valor))
        else:
            datos[campo] = float(valor)
        if not minimo <= datos[campo] <= maximo:
            errores.append(f"{campo}: {datos[campo]} fuera del rango [{minimo}, {maximo}].")
            datos[campo] = None

    # viento_zonda: solo bool o None
    zonda = datos.get("viento_zonda")
    if zonda is not None and not isinstance(zonda, bool):
        errores.append(f"viento_zonda: se esperaba true/false/null, llegó {zonda!r}.")
        datos["viento_zonda"] = None

    datos["_errores_extraccion"] = errores
    return datos


def modulos_para_intencion(intencion: str) -> list[str]:
    """Define el flujo único y auditable del asistente PG3."""
    flujos = {
        "DIAGNOSTICO_LOTE": ["DIAGNOSTICO_LOTE", "RIESGO_BIOCLIMATICO"],
        "PRESCRIPCION": [
            "DIAGNOSTICO_LOTE",
            "RIESGO_BIOCLIMATICO",
            "PRESCRIPCION",
        ],
        "CONSULTA_CARENCIA": ["PRESCRIPCION"],
        "FUERA_DE_DOMINIO": [],
    }
    return flujos.get(intencion, [])


# ---------------------------------------------------------------------------
# 6. FASE 2 — Consultas Cypher (Módulo 1 — Diagnóstico: Julián)
# ---------------------------------------------------------------------------
_JOIN_DIAG = """
MATCH (l:Lote_Vinedo)
MATCH (s:Sintoma_Visual)-[:GENERA_HIPOTESIS]->(d:Diagnostico_Presuntivo)-[:IDENTIFICA_CANDIDATO]->(p:Patologia_Fungica)
MATCH (e:Evidencia_Climatica)-[:CONFIRMA_O_REFUTA]->(d)
WHERE substring(l.id_lote, size(l.id_lote)-2) = substring(d.id_diag, 5)
  AND substring(s.id_sintoma, 8) = substring(e.id_clima, 6)
"""

_RETURN_DIAG = """
RETURN l.id_lote AS lote, l.etapa_fenologica AS etapa, l.porcentaje_area_afectada AS area_afectada_pct,
       s.ubicacion AS ubicacion, s.textura AS textura, s.distribucion AS distribucion,
       p.nombre AS patologia, p.etapas_susceptibles AS etapas_susceptibles,
       e.temperatura_media AS temperatura_c, e.humedad_relativa AS humedad_pct,
       e.evento_inhibitorio_reciente AS evento_inhibitorio,
       CASE
         WHEN e.evento_inhibitorio_reciente = true OR e.humedad_relativa < 20.0 THEN "Refutado_Inhibicion_Zonda"
         WHEN l.etapa_fenologica IN p.etapas_susceptibles AND e.temperatura_media >= 10.0 THEN "Confirmado_Clima_Propicio"
         ELSE "Atenuado_Condicion_Suboptima"
       END AS dictamen_bioclimatico
ORDER BY l.id_lote
"""

CYPHER_C1_DIAGNOSTICO_LOTE = _JOIN_DIAG + "  AND l.id_lote = $lote_id\n" + _RETURN_DIAG
CYPHER_C2_LOTES_POR_PATOLOGIA = _JOIN_DIAG + "  AND p.nombre = $patologia\n" + _RETURN_DIAG
CYPHER_C3_INFO_PATOLOGIA = """
MATCH (p:Patologia_Fungica {nombre: $patologia})
RETURN p.nombre AS patologia, p.etapas_susceptibles AS etapas_susceptibles,
       p.requiere_agua_libre AS requiere_agua_libre
"""

GLOSARIO_DICTAMEN = {
    "Confirmado_Clima_Propicio":
        "La etapa fenológica del lote está entre las etapas susceptibles y la temperatura ≥ 10 °C: el clima respalda la hipótesis visual.",
    "Refutado_Inhibicion_Zonda":
        "Se registró un evento inhibitorio (Zonda) o humedad < 20 %: el hongo pierde viabilidad; la hipótesis visual queda refutada por el ambiente.",
    "Atenuado_Condicion_Suboptima":
        "Las condiciones de etapa o temperatura no son óptimas: el clima atenúa el respaldo a la hipótesis visual.",
}


def modulo1_diagnostico(datos_ext: dict) -> dict:
    """Ejecuta C1_DIAGNOSTICO_LOTE o C2/C3 según intención."""
    intencion = datos_ext.get("intencion", "DIAGNOSTICO_LOTE")
    id_lote = datos_ext.get("id_lote")
    patologia = datos_ext.get("patologia_mencionada")

    if id_lote:
        filas = ejecutar_cypher(CYPHER_C1_DIAGNOSTICO_LOTE, {"lote_id": id_lote})
        query_name = "C1_DIAGNOSTICO_LOTE"
    elif patologia:
        filas = ejecutar_cypher(CYPHER_C2_LOTES_POR_PATOLOGIA, {"patologia": patologia})
        query_name = "C2_LOTES_POR_PATOLOGIA"
    else:
        filas = []
        query_name = "SIN_CONSULTA"

    dictamenes_usados = {f["dictamen_bioclimatico"] for f in filas if "dictamen_bioclimatico" in f}
    glosario = {k: GLOSARIO_DICTAMEN[k] for k in dictamenes_usados if k in GLOSARIO_DICTAMEN}

    patologia_identificada = filas[0]["patologia"] if filas else None

    return {
        "query_ejecutada": query_name,
        "resultados": filas,
        "patologia_candidata": patologia_identificada,
        "glosario_dictamen": glosario,
    }


def completar_datos_desde_diagnostico(datos_ext: dict, resultado_m1: dict) -> dict:
    """Completa datos ausentes con la evidencia del lote obtenida desde Neo4j."""
    datos = dict(datos_ext)
    fila = (resultado_m1.get("resultados") or [None])[0]
    if not fila:
        return datos

    equivalencias = {
        "temperatura": "temperatura_c",
        "humedad_relativa": "humedad_pct",
        "etapa_fenologica": "etapa",
        "porcentaje_area_afectada": "area_afectada_pct",
        "viento_zonda": "evento_inhibitorio",
    }
    for destino, origen in equivalencias.items():
        if datos.get(destino) is None and fila.get(origen) is not None:
            datos[destino] = fila[origen]
    if datos.get("patologia_mencionada") is None and fila.get("patologia") is not None:
        datos["patologia_mencionada"] = fila["patologia"]
    return datos


# ---------------------------------------------------------------------------
# 7. FASE 2 — Módulo 2 — Riesgo Bioclimático (Alejo / Carobolante)
# ---------------------------------------------------------------------------
CYPHER_CONDICION = """
MATCH (p:Patologia_Fungica {nombre: $patologia})-[:REQUIERE_CONDICION]->(c:CondicionClimatica)
OPTIONAL MATCH (p)-[:POSIBLE_EN]->(e:EtapaFenologica)
RETURN p.nombre AS patologia, p.requiere_agua_libre AS requiere_agua_libre,
       c.id_condicion AS id_condicion,
       c.temp_min AS temp_min, c.temp_max AS temp_max,
       c.temp_optima_min AS temp_optima_min, c.temp_optima_max AS temp_optima_max,
       c.humedad_min AS humedad_min, c.humedad_max AS humedad_max,
       c.humedad_optima_min AS humedad_optima_min, c.humedad_optima_max AS humedad_optima_max,
       c.horas_mojado_min AS horas_mojado_min, c.fuente AS fuente,
       collect(DISTINCT e.nombre) AS etapas_susceptibles
"""

CYPHER_EVENTOS_INHIBITORIOS = """
MATCH (e:EventoInhibitorio)-[:INHIBE]->(:Patologia_Fungica {nombre: $patologia})
RETURN e.nombre AS evento, e.tipo AS tipo, e.temp_disparo_min AS temp_disparo_min,
       e.humedad_max_limite AS humedad_max_limite, e.descripcion AS descripcion
ORDER BY evento
"""

CYPHER_REGLAS_BIOCLIMATICAS = """
MATCH (r:ReglaBioclimatica)-[:APLICA_A]->(:Patologia_Fungica {nombre: $patologia})
RETURN r.codigo AS codigo, r.nombre AS nombre, r.estrategia AS estrategia,
       r.prioridad AS prioridad, r.descripcion AS descripcion
ORDER BY prioridad, codigo
"""


def _num(registro: dict, clave: str) -> float | None:
    valor = registro.get(clave)
    return float(valor) if es_numero(valor) else None


def _faltan(condicion: dict, claves: list[str]) -> list[str]:
    return [c for c in claves if _num(condicion, c) is None]


def _chequeo(variable, valor, condicion, prop_min=None, prop_max=None) -> dict:
    minimo = _num(condicion, prop_min) if prop_min else None
    maximo = _num(condicion, prop_max) if prop_max else None
    cumple = (valor is not None and
              (minimo is None or valor >= minimo) and
              (maximo is None or valor <= maximo))
    return {"variable": variable, "valor": valor, "minimo_grafo": minimo, "maximo_grafo": maximo,
            "propiedades": [p for p in (prop_min, prop_max) if p], "cumple": cumple}


def _limitantes(chequeos: list[dict]) -> list[str]:
    return [f"{c['variable']} = {c['valor']} fuera de lo exigido por {', '.join(c['propiedades'])}"
            for c in chequeos if not c["cumple"]]


ALCANCE_BIO = ("Resultado de favorabilidad bioclimática. No confirma ni descarta una infección "
               "y no estima severidad clínica.")


def _resultado_bio(regla, favorabilidad, chequeos, limitantes=(), notas=()) -> dict:
    return {
        "regla_disparada": regla["codigo"],
        "nombre_regla": regla["nombre"],
        "favorabilidad_bioclimatica": favorabilidad,
        "chequeos": list(chequeos),
        "factores_limitantes": list(limitantes),
        "notas": list(notas),
        "alcance": ALCANCE_BIO,
    }


def _indeterminada(regla, faltan) -> dict:
    return _resultado_bio(regla, "Indeterminada", [], [],
                          ["Faltan propiedades en Neo4j: " + ", ".join(faltan)])


def regla_inhibicion(regla: dict, datos: dict, eventos: list[dict]):
    notas = []
    for evento in eventos:
        if _faltan(evento, ["humedad_max_limite", "temp_disparo_min"]):
            notas.append(f"Evento '{evento.get('evento')}' sin umbrales completos en Neo4j; no evaluado.")
            continue
        chequeos = [
            _chequeo("humedad_relativa", datos.get("humedad_relativa"), evento, prop_max="humedad_max_limite"),
            _chequeo("temperatura", datos.get("temperatura"), evento, prop_min="temp_disparo_min"),
        ]
        if all(c["cumple"] for c in chequeos):
            return _resultado_bio(
                regla, "Reducida por evento inhibitorio", chequeos,
                [f"Evento inhibitorio '{evento['evento']}' activo según umbrales del grafo"],
                notas + ["El evento reduce la favorabilidad; no demuestra ausencia de infección previa."]
            ), notas
        if datos.get("viento_zonda") is True and "zonda" in normalizar_texto(evento.get("evento", "")):
            notas.append(f"Se mencionó Zonda pero las mediciones no alcanzan los umbrales de '{evento['evento']}'; inhibición no aplicada.")
    return None, notas


def regla_peronospora(regla: dict, datos: dict, condicion: dict) -> dict:
    faltan = _faltan(condicion, ["temp_min", "temp_max", "temp_optima_min", "temp_optima_max",
                                  "humedad_min", "humedad_optima_min", "horas_mojado_min"])
    if faltan:
        return _indeterminada(regla, faltan)
    T, H, M = datos.get("temperatura"), datos.get("humedad_relativa"), datos.get("horas_mojado")
    chequeo_mojado = _chequeo("horas_mojado", M, condicion, prop_min="horas_mojado_min")
    permisivos = [chequeo_mojado,
                  _chequeo("temperatura", T, condicion, "temp_min", "temp_max"),
                  _chequeo("humedad_relativa", H, condicion, prop_min="humedad_min")]
    if not all(c["cumple"] for c in permisivos):
        notas = ["Peronóspora requiere agua libre: el mojado foliar es factor limitante."] if not chequeo_mojado["cumple"] else []
        return _resultado_bio(regla, "Baja", permisivos, _limitantes(permisivos), notas)
    optimos = [_chequeo("temperatura", T, condicion, "temp_optima_min", "temp_optima_max"),
               _chequeo("humedad_relativa", H, condicion, prop_min="humedad_optima_min")]
    return _resultado_bio(regla, "Alta" if all(c["cumple"] for c in optimos) else "Media", permisivos + optimos)


def regla_oidio(regla: dict, datos: dict, condicion: dict) -> dict:
    faltan = _faltan(condicion, ["temp_min", "temp_max", "temp_optima_min", "temp_optima_max",
                                  "humedad_min", "humedad_max", "humedad_optima_min", "humedad_optima_max"])
    if faltan:
        return _indeterminada(regla, faltan)
    T, H = datos.get("temperatura"), datos.get("humedad_relativa")
    notas = ["Oídio no requiere agua libre; horas de mojado no se exigen."]
    if datos.get("horas_mojado") is not None:
        notas.append(f"Mojado informado: {datos['horas_mojado']} h (dato informativo).")
    permisivos = [_chequeo("temperatura", T, condicion, "temp_min", "temp_max"),
                  _chequeo("humedad_relativa", H, condicion, "humedad_min", "humedad_max")]
    if not all(c["cumple"] for c in permisivos):
        return _resultado_bio(regla, "Baja", permisivos, _limitantes(permisivos), notas)
    optimos = [_chequeo("temperatura", T, condicion, "temp_optima_min", "temp_optima_max"),
               _chequeo("humedad_relativa", H, condicion, "humedad_optima_min", "humedad_optima_max")]
    return _resultado_bio(regla, "Alta" if all(c["cumple"] for c in optimos) else "Media",
                          permisivos + optimos, [], notas)


def regla_botritis(regla: dict, datos: dict, condicion: dict) -> dict:
    faltan = _faltan(condicion, ["temp_min", "temp_max", "temp_optima_min", "temp_optima_max",
                                  "humedad_min", "humedad_optima_min", "horas_mojado_min"])
    etapas = condicion.get("etapas_susceptibles") or []
    if not etapas:
        faltan.append("relaciones POSIBLE_EN (etapas susceptibles)")
    if faltan:
        return _indeterminada(regla, faltan)
    T, H, M = datos.get("temperatura"), datos.get("humedad_relativa"), datos.get("horas_mojado")
    etapa = datos.get("etapa_fenologica")
    notas = []
    chequeo_etapa = None
    if etapa is not None:
        chequeo_etapa = {"variable": "etapa_fenologica", "valor": etapa, "admitidos_grafo": etapas,
                         "propiedades": ["POSIBLE_EN"], "cumple": etapa in etapas}
        if not chequeo_etapa["cumple"]:
            return _resultado_bio(regla, "Baja", [chequeo_etapa],
                                  [f"Etapa {etapa} no vinculada a Botritis (susceptibles: {', '.join(etapas)})"])
    else:
        notas.append("No se informó la etapa fenológica; susceptibilidad del racimo no verificada.")
    permisivos = [_chequeo("humedad_relativa", H, condicion, prop_min="humedad_min"),
                  _chequeo("horas_mojado", M, condicion, prop_min="horas_mojado_min"),
                  _chequeo("temperatura", T, condicion, "temp_min", "temp_max")]
    previos = [chequeo_etapa] if chequeo_etapa else []
    if not all(c["cumple"] for c in permisivos):
        return _resultado_bio(regla, "Baja", previos + permisivos, _limitantes(permisivos), notas)
    optimos = [_chequeo("temperatura", T, condicion, "temp_optima_min", "temp_optima_max"),
               _chequeo("humedad_relativa", H, condicion, prop_min="humedad_optima_min")]
    if all(c["cumple"] for c in optimos):
        favorabilidad = "Alta" if chequeo_etapa else "Media"
        if not chequeo_etapa:
            notas.append("Variables climáticas en óptimo; para clasificar Alta falta confirmar etapa.")
    else:
        favorabilidad = "Media"
    return _resultado_bio(regla, favorabilidad, previos + permisivos + optimos, [], notas)


ESTRATEGIAS_BIO = {
    "PERONOSPORA": regla_peronospora,
    "OIDIO":       regla_oidio,
    "BOTRITIS":    regla_botritis,
}


def modulo2_riesgo_bioclimatico(datos_ext: dict, patologia_candidata: str | None) -> dict:
    """Motor de riesgo bioclimático de Alejo."""
    patologia = patologia_candidata or datos_ext.get("patologia_mencionada")
    if not patologia:
        return {"disponible": False, "motivo": "No se identificó patología candidata para evaluar riesgo bioclimático."}

    filas_cond = ejecutar_cypher(CYPHER_CONDICION, {"patologia": patologia})
    if not filas_cond:
        return {"disponible": False, "motivo": f"No hay CondicionClimatica para {patologia} en el grafo."}
    condicion = filas_cond[0]

    eventos = ejecutar_cypher(CYPHER_EVENTOS_INHIBITORIOS, {"patologia": patologia})
    reglas  = ejecutar_cypher(CYPHER_REGLAS_BIOCLIMATICAS, {"patologia": patologia})

    datos_bio = {
        "temperatura":      datos_ext.get("temperatura"),
        "humedad_relativa": datos_ext.get("humedad_relativa"),
        "horas_mojado":     datos_ext.get("horas_mojado"),
        "viento_zonda":     datos_ext.get("viento_zonda"),
        "etapa_fenologica": datos_ext.get("etapa_fenologica"),
        "patologia":        patologia,
    }

    notas_previas: list[str] = []
    for regla in reglas:
        if regla["estrategia"] == "INHIBICION":
            resultado, notas = regla_inhibicion(regla, datos_bio, eventos)
            notas_previas += notas
            if resultado:
                resultado["notas"] = notas_previas + resultado.get("notas", [])
                return {"disponible": True, "patologia": patologia, "evaluacion": resultado}
            continue
        funcion = ESTRATEGIAS_BIO.get(regla["estrategia"])
        if funcion is None:
            notas_previas.append(f"Estrategia '{regla['estrategia']}' no implementada.")
            continue
        resultado = funcion(regla, datos_bio, condicion)
        resultado["notas"] = notas_previas + resultado.get("notas", [])
        return {"disponible": True, "patologia": patologia, "evaluacion": resultado}

    return {
        "disponible": True,
        "patologia": patologia,
        "evaluacion": {
            "regla_disparada": None,
            "favorabilidad_bioclimatica": "Indeterminada",
            "chequeos": [], "factores_limitantes": [],
            "notas": notas_previas + ["El grafo no vincula ninguna regla específica."],
            "alcance": ALCANCE_BIO,
        },
    }


# ---------------------------------------------------------------------------
# 8. FASE 2 — Módulo 3 — Prescripción Mamdani (Patricio Buono)
# ---------------------------------------------------------------------------
CYPHER_Q0_CONSISTENCIA = """
MATCH (l:Lote_Vinedo {id_lote: $id_lote})
MATCH (s:Sintoma_Visual)-[:GENERA_HIPOTESIS]->(d:Diagnostico_Presuntivo)-[:IDENTIFICA_CANDIDATO]->(p:Patologia_Fungica)
WHERE substring(l.id_lote, size(l.id_lote)-2) = substring(d.id_diag, 5)
RETURN l.id_lote AS Lote, l.etapa_fenologica AS Etapa_Grafo, p.nombre AS Patologia_Grafo
"""

CYPHER_Q1_CRISP = """
MATCH (l:Lote_Vinedo {id_lote: $id_lote})-[:EVALUA_INOCUIDAD]->(t:Tratamiento)-[:COMBATE]->(p:Patologia_Fungica)
MATCH (t)-[:UTILIZA_QUIMICO]->(pa:Principio_Activo)
MATCH (s:Sintoma_Visual)-[:GENERA_HIPOTESIS]->(d:Diagnostico_Presuntivo)-[:IDENTIFICA_CANDIDATO]->(p)
MATCH (e:Evidencia_Climatica)-[:CONFIRMA_O_REFUTA]->(d)
WHERE substring(s.id_sintoma, 8) = substring(e.id_clima, 6)
  AND substring(l.id_lote, size(l.id_lote)-2) = substring(d.id_diag, 5)
  AND ($patologia IS NULL OR p.nombre = $patologia)
  AND ($etapa_fenologica IS NULL OR l.etapa_fenologica = $etapa_fenologica)
SET l.dias_para_cosecha = COALESCE($dias_para_cosecha, l.dias_para_cosecha),
    l.porcentaje_area_afectada = COALESCE($porcentaje_area_afectada, l.porcentaje_area_afectada)
SET d.factor_certeza_ambiental = CASE
    WHEN e.evento_inhibitorio_reciente = true OR e.humedad_relativa < 20.0 THEN "Refutado_Inhibicion_Zonda"
    WHEN l.etapa_fenologica IN p.etapas_susceptibles AND e.temperatura_media >= 10.0 THEN "Confirmado_Clima_Propicio"
    ELSE "Atenuado_Condicion_Suboptima"
END
SET t.viabilidad_agronomica = 0.0,
    t.estado_evaluacion = CASE
        WHEN d.factor_certeza_ambiental = "Refutado_Inhibicion_Zonda" THEN "Cancelado_Falso_Positivo"
        WHEN pa.dias_carencia > l.dias_para_cosecha THEN "Descartado_Por_LMR"
        ELSE "Admisible"
    END
RETURN l.id_lote AS Lote, t.id_trat AS Tratamiento, t.estado_evaluacion AS Estado_Crisp
"""

CYPHER_Q2_FUZZ = """
MATCH (l:Lote_Vinedo {id_lote: $id_lote})
WHERE EXISTS { MATCH (l)-[:EVALUA_INOCUIDAD]->(:Tratamiento {estado_evaluacion: "Admisible"}) }
UNWIND [
    {var: "Severidad_de_la_Infeccion", valor: l.porcentaje_area_afectada},
    {var: "Proximidad_a_Cosecha", valor: toFloat(l.dias_para_cosecha)}
] AS entrada
MATCH (v:VariableDifusa {nombreVariable: entrada.var})-[:TIENE_ETIQUETA]->(c:ConjuntoDifuso)-[:MODELADO_POR]->(f:FuncionPertenencia)
WITH l, v, c, f, entrada.valor AS x,
     exp(-0.5 * ((entrada.valor - f.centro_c) / f.dispersion_sigma) ^ 2) AS mu_calculado
MERGE (ls:LecturaSensor {id_lectura: l.id_lote + "_" + v.nombreVariable})
SET ls.id_lote = l.id_lote, ls.nombreVariable = v.nombreVariable, ls.valorCrisp = x
MERGE (ls)-[:ASOCIADO_A_VARIABLE]->(v)
MERGE (ls)-[ap:ACTIVACION_PARCIAL]->(c)
SET ap.mu = round(mu_calculado, 4)
RETURN count(ap) AS total_fuzzificados
"""

CYPHER_Q3_REGLAS = """
MATCH (l:Lote_Vinedo {id_lote: $id_lote})
WHERE EXISTS { MATCH (l)-[:EVALUA_INOCUIDAD]->(:Tratamiento {estado_evaluacion: "Admisible"}) }
MATCH (r:ReglaDifusa)-[:DETERMINA_CONSECUENTE]->(c_out:ConjuntoDifuso)
MATCH (r)-[:EVALUA_ANTECEDENTE]->(c_ant1:ConjuntoDifuso {variable: "Proximidad_a_Cosecha"})
MATCH (r)-[:EVALUA_ANTECEDENTE]->(c_ant2:ConjuntoDifuso {variable: "Severidad_de_la_Infeccion"})
MATCH (ls1:LecturaSensor {id_lote: l.id_lote, nombreVariable: "Proximidad_a_Cosecha"})-[ap1:ACTIVACION_PARCIAL]->(c_ant1)
MATCH (ls2:LecturaSensor {id_lote: l.id_lote, nombreVariable: "Severidad_de_la_Infeccion"})-[ap2:ACTIVACION_PARCIAL]->(c_ant2)
WITH l, r, c_out,
     CASE
         WHEN r.operador = "MIN" THEN CASE WHEN ap1.mu < ap2.mu THEN ap1.mu ELSE ap2.mu END
         WHEN r.operador = "MAX" THEN CASE WHEN ap1.mu > ap2.mu THEN ap1.mu ELSE ap2.mu END
     END AS fuerza_disparo
MERGE (l)-[act:ACTIVA_CONSECUENTE {regla: r.codigoRegla}]->(c_out)
SET act.fuerza_activacion = round(fuerza_disparo, 4)
RETURN c_out.nombreEtiqueta AS etiqueta, max(act.fuerza_activacion) AS fuerza_maxima
"""

CYPHER_Q_UPDATE_CENTROIDE = """
MATCH (l:Lote_Vinedo {id_lote: $id_lote})-[:EVALUA_INOCUIDAD]->(t:Tratamiento {estado_evaluacion: "Admisible"})
MATCH (t)-[:UTILIZA_QUIMICO]->(pa:Principio_Activo)
SET t.viabilidad_agronomica = $viabilidad,
    t.estado_evaluacion = CASE
        WHEN $viabilidad < 20.0 THEN "No_Recomendado_Baja_Viabilidad"
        WHEN $viabilidad >= 60.0 AND pa.espectro = "Sistémico" THEN "Seleccionado"
        WHEN $viabilidad >= 20.0 AND $viabilidad < 60.0 AND pa.espectro = "Contacto_Preventivo" THEN "Seleccionado"
        ELSE "Admisible_No_Seleccionado"
    END
"""

CYPHER_Q4_TRAZABILIDAD = """
MATCH (s:Sintoma_Visual)-[:GENERA_HIPOTESIS]->(d:Diagnostico_Presuntivo)-[:IDENTIFICA_CANDIDATO]->(p:Patologia_Fungica)
MATCH (e:Evidencia_Climatica)-[:CONFIRMA_O_REFUTA]->(d)
MATCH (l:Lote_Vinedo {id_lote: $id_lote})-[:EVALUA_INOCUIDAD]->(t:Tratamiento)-[:COMBATE]->(p)
MATCH (t)-[:UTILIZA_QUIMICO]->(pa:Principio_Activo)
WHERE substring(s.id_sintoma, 8) = substring(e.id_clima, 6)
  AND substring(l.id_lote, size(l.id_lote)-2) = substring(d.id_diag, 5)
OPTIONAL MATCH (l)-[act:ACTIVA_CONSECUENTE]->(c_out:ConjuntoDifuso)
WITH l, p, d, e, t, pa,
     collect(DISTINCT {regla: act.regla, consecuente: c_out.nombreEtiqueta, alpha: act.fuerza_activacion}) AS reglas_difusas
RETURN l.id_lote AS Lote,
       l.etapa_fenologica AS Etapa_Fenologica,
       l.dias_para_cosecha AS Dias_Para_Cosecha,
       l.porcentaje_area_afectada AS Severidad_Porcentaje,
       p.nombre AS Patologia_Candidata,
       d.factor_certeza_ambiental AS Validacion_Bioclimatica,
       e.severidad_estimada AS Severidad_Campo,
       t.id_trat AS Tratamiento,
       pa.nombre_quimico AS Principio_Activo,
       (pa.nombre_quimico = $principio_activo) AS Quimico_Consultado_Por_Usuario,
       pa.espectro AS Espectro_Quimico,
       pa.dias_carencia AS Carencia_Registrada_Grafo,
       toString(pa.dias_carencia) + "d carencia registrada vs " + toString(l.dias_para_cosecha) + "d cosecha" AS Control_LMR,
       t.viabilidad_agronomica AS Viabilidad_Difusa_Porc,
       t.estado_evaluacion AS Conclusion_Final,
       reglas_difusas AS Reglas_Difusas_Activadas
ORDER BY t.id_trat
"""


def desfuzzificar_mamdani(alpha_baja: float, alpha_media: float, alpha_alta: float) -> float:
    """Centroide Mamdani sobre universo 0-100 con funciones gaussianas del grafo."""
    y = np.linspace(0, 100, 1001)
    mu_baja  = np.exp(-0.5 * ((y - 0.0)   / 15.0) ** 2)
    mu_media = np.exp(-0.5 * ((y - 50.0)  / 15.0) ** 2)
    mu_alta  = np.exp(-0.5 * ((y - 100.0) / 15.0) ** 2)

    agregado = np.maximum(
        np.minimum(alpha_baja,  mu_baja),
        np.maximum(
            np.minimum(alpha_media, mu_media),
            np.minimum(alpha_alta,  mu_alta),
        ),
    )
    if np.sum(agregado) == 0:
        return 0.0
    return round(float(fuzz.defuzz(y, agregado, "centroid")), 2)


def modulo3_prescripcion(datos_ext: dict) -> dict:
    """Motor de prescripción + desfuzzificación Mamdani de Patricio."""
    id_lote = datos_ext.get("id_lote")
    if not id_lote:
        return {"disponible": False, "motivo": "No se proporcionó id_lote para el motor de prescripción."}

    patologia      = datos_ext.get("patologia_mencionada")
    etapa          = datos_ext.get("etapa_fenologica")
    dias           = datos_ext.get("dias_para_cosecha")
    area_afectada  = datos_ext.get("porcentaje_area_afectada")
    quimico        = datos_ext.get("principio_activo")

    consultas_ejecutadas: list[str] = []

    # Q0 — Consistencia lote
    estado_lote = ejecutar_cypher(CYPHER_Q0_CONSISTENCIA, {"id_lote": id_lote})
    consultas_ejecutadas.append("QUERY_0_CONSISTENCIA")
    if not estado_lote:
        return {"disponible": False, "motivo": f"El lote {id_lote} no existe en Neo4j."}

    # Q1 — Validación crisp LMR + dictamen bioclimático
    ejecutar_cypher(CYPHER_Q1_CRISP, {
        "id_lote": id_lote,
        "patologia": patologia,
        "etapa_fenologica": etapa,
        "dias_para_cosecha": dias,
        "porcentaje_area_afectada": area_afectada,
    })
    consultas_ejecutadas.append("CONSULTA_1_CRISP (LMR + dictamen bioclimático)")

    # Revisar si hay tratamientos admisibles para el motor difuso
    hay_admisibles_q = ejecutar_cypher(
        """MATCH (l:Lote_Vinedo {id_lote: $id_lote})-[:EVALUA_INOCUIDAD]->(t:Tratamiento)
           WHERE t.estado_evaluacion = "Admisible"
           RETURN count(t) AS total""",
        {"id_lote": id_lote}
    )
    hay_admisibles = (hay_admisibles_q[0]["total"] > 0) if hay_admisibles_q else False

    viabilidad_calculada: float | None = None
    if hay_admisibles:
        ejecutar_cypher(
            """MATCH (l:Lote_Vinedo {id_lote: $id_lote})-[act:ACTIVA_CONSECUENTE]->()
               DELETE act""",
            {"id_lote": id_lote},
        )
        consultas_ejecutadas.append("LIMPIEZA_ACTIVACIONES_PREVIAS")
        # Q2 — Fuzzificación en grafo
        ejecutar_cypher(CYPHER_Q2_FUZZ, {"id_lote": id_lote})
        consultas_ejecutadas.append("CONSULTA_2_FUZZIFICACION (Gaussianas en grafo)")

        # Q3 — Reglas difusas → fuerza de activación
        activaciones = ejecutar_cypher(CYPHER_Q3_REGLAS, {"id_lote": id_lote})
        consultas_ejecutadas.append("CONSULTA_3_REGLAS_DIFUSAS (MIN/MAX RD_01..RD_05)")

        if activaciones:
            mapa_alpha = {fila["etiqueta"]: fila["fuerza_maxima"] for fila in activaciones}
            viabilidad_calculada = desfuzzificar_mamdani(
                alpha_baja  = mapa_alpha.get("Baja",  0.0),
                alpha_media = mapa_alpha.get("Media", 0.0),
                alpha_alta  = mapa_alpha.get("Alta",  0.0),
            )
            ejecutar_cypher(CYPHER_Q_UPDATE_CENTROIDE, {"id_lote": id_lote, "viabilidad": viabilidad_calculada})
            consultas_ejecutadas.append(f"UPDATE_CENTROIDE_MAMDANI (viabilidad={viabilidad_calculada}%)")
    else:
        # Limpiar activaciones previas si no hay admisibles
        ejecutar_cypher(
            "MATCH (:Lote_Vinedo {id_lote: $id_lote})-[act:ACTIVA_CONSECUENTE]->() DELETE act",
            {"id_lote": id_lote}
        )
        consultas_ejecutadas.append("OMISIÓN_MOTOR_DIFUSO (sin tratamientos Admisibles)")

    # Q4 — Trazabilidad final
    registros = ejecutar_cypher(CYPHER_Q4_TRAZABILIDAD, {
        "id_lote": id_lote,
        "principio_activo": quimico,
    })
    consultas_ejecutadas.append("CONSULTA_4_TRAZABILIDAD")

    return {
        "disponible": True,
        "id_lote": id_lote,
        "viabilidad_calculada": viabilidad_calculada,
        "consultas_cypher": consultas_ejecutadas,
        "registros": registros,
    }


# ---------------------------------------------------------------------------
# 9. FASE 3 — Explicación Unificada (LLM) → Receta Agraria Digital
# ---------------------------------------------------------------------------
SYSTEM_PROMPT_EXPLICACION_UNIFICADO = """Eres el redactor de la respuesta unificada de VITI-EXPERT.
Transforma la trazabilidad de los módulos realmente ejecutados en una respuesta breve, clara y
técnicamente rigurosa para el encargado de finca.

REGLAS ESTRICTAS:
1. BASAMENTO EXCLUSIVO EN EVIDENCIA: Usa ÚNICAMENTE los datos del JSON de trazabilidad. NUNCA inventes patologías, químicos, dosis, días de carencia, umbrales ni criterios no presentes en los datos.
2. NO ALUCINES NÚMEROS: Cada número que menciones debe estar en el JSON de trazabilidad.
3. PROHIBICIÓN DE AFIRMACIONES ABSOLUTAS: Habla de "diagnóstico presuntivo" o "hipótesis"; nunca afirmes certeza absoluta sobre la infección.
4. FUENTE DE CARENCIA: Aclara que los días de carencia provienen de la Base de Conocimiento Neo4j (bibliografía de referencia), no son una verificación regulatoria vigente ante SENASA.
5. RESPETA EL ENRUTAMIENTO: No describas módulos que no figuren en
   orquestacion_pg3.modulos_ejecutados. No menciones que un módulo "no fue solicitado".
6. EXTENSIÓN: Responde en un máximo de 180 palabras, sin tablas, sin repetir datos y sin
   encabezados de informe formal. Usa solo estos encabezados, según corresponda:
   **Respuesta**, **Riesgo**, **Tratamiento** y **Siguiente paso**.

Para un diagnóstico, resume la patología candidata, el lote y el riesgo bioclimático en
lenguaje natural. Para una prescripción, agrega únicamente el tratamiento y la advertencia
regulatoria correspondiente. Si faltan datos, indícalo en una sola frase.
Responde en español. Sin inventar nada que no esté en el JSON.
"""


def llm_explicacion_unificada(trazabilidad: dict) -> str:
    """Fase 3: LLM redacta una respuesta breve a partir de la trazabilidad."""
    contexto = json.dumps(trazabilidad, ensure_ascii=False, indent=2)
    modulos = ", ".join(trazabilidad["orquestacion_pg3"]["modulos_ejecutados"])

    mensajes = [
        {"role": "system", "content": SYSTEM_PROMPT_EXPLICACION_UNIFICADO},
        {"role": "user", "content": (
            f"Solo se ejecutaron estos módulos: {modulos}. "
            f"Redacta la respuesta basándote exclusivamente en esta trazabilidad:\n{contexto}"
        )},
    ]
    return llamar_groq(mensajes, modo_json=False)


def _valores_trazabilidad(trazabilidad: dict) -> str:
    return json.dumps(trazabilidad, ensure_ascii=False)


def explicacion_grounded_valida(texto: str, trazabilidad: dict) -> bool:
    """Rechaza explicaciones con números o afirmaciones no sustentadas."""
    if not texto or len(texto) > 12000:
        return False
    evidencia = _valores_trazabilidad(trazabilidad)
    numeros = re.findall(r"(?<![\w.])-?\d+(?:[.,]\d+)?", texto)
    if any(numero.replace(",", ".") not in evidencia.replace(",", ".") for numero in numeros):
        return False
    frases_prohibidas = (
        "infección confirmada",
        "infeccion confirmada",
        "cura garantizada",
        "sin riesgo",
        "diagnóstico definitivo",
        "diagnostico definitivo",
    )
    texto_normalizado = normalizar_texto(texto)
    return not any(frase in texto_normalizado for frase in frases_prohibidas)


def explicacion_plantilla(trazabilidad: dict) -> str:
    """Fallback seguro cuando el LLM no puede producir una explicación grounded."""
    extraccion = trazabilidad.get("fase_extraccion", {}).get("datos_extraidos", {})
    diagnostico = trazabilidad.get("modulo_1_diagnostico", {})
    riesgo = trazabilidad.get("modulo_2_riesgo_bioclimatico", {})
    prescripcion = trazabilidad.get("modulo_3_prescripcion", {})
    patologia = (
        diagnostico.get("patologia_candidata")
        or extraccion.get("patologia_mencionada")
        or "no determinada"
    )
    lote = extraccion.get("id_lote") or "no informado"
    evaluacion = riesgo.get("evaluacion", {})
    favorabilidad = evaluacion.get("favorabilidad_bioclimatica", "Indeterminada")
    viabilidad = prescripcion.get("viabilidad_calculada")
    resultado = f"**Respuesta**\n{lote}: la evidencia es compatible con {patologia} (diagnóstico presuntivo)."
    resultado += f"\n\n**Riesgo**\nFavorabilidad bioclimática: {favorabilidad}."
    if viabilidad is not None:
        resultado += f"\n\n**Tratamiento**\nViabilidad agronómica calculada: {viabilidad}%."
    else:
        resultado += "\n\n**Siguiente paso**\nVerificar la hipótesis en campo con un profesional."
    return resultado


# ---------------------------------------------------------------------------
# 10. Endpoint principal POST /consultar
# ---------------------------------------------------------------------------
@app.post("/consultar", response_model=ConsultaResponse, summary="Receta Agraria Digital")
async def consultar(req: ConsultaRequest) -> ConsultaResponse:
    """
    Recibe un reporte coloquial del encargado de finca y ejecuta el flujo
    sándwich unificado de VITI-EXPERT:
    1. Extracción unificada (LLM)
    2. Inferencia secuencial en Neo4j (Diagnóstico → Riesgo → Prescripción)
    3. Explicación unificada (LLM) → Receta Agraria Digital
    """
    global CATALOGO

    # Inicializar catálogo si está vacío (primer request)
    if not CATALOGO:
        CATALOGO = cargar_catalogo()

    mensaje = req.mensaje.strip()
    log.info("Nueva consulta: %s", mensaje[:80])

    # --- FASE 1: Extracción unificada ---
    try:
        datos_ext = llm_extraccion_unificada(mensaje, CATALOGO)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=f"Error en extracción LLM: {e}")

    errores_extraccion = datos_ext.pop("_errores_extraccion", [])
    intencion = datos_ext.get("intencion", "DIAGNOSTICO_LOTE")
    modulos_ejecutar = modulos_para_intencion(intencion)

    # Verificar si el mensaje está fuera del dominio
    if datos_ext.get("fuera_de_dominio") is True:
        raise HTTPException(
            status_code=400,
            detail="La consulta no corresponde al dominio de enfermedades fúngicas de la vid (oídio, peronóspora, botritis)."
        )

    if intencion == "FUERA_DE_DOMINIO":
        raise HTTPException(
            status_code=400,
            detail="La consulta fue clasificada fuera del dominio de VITI-EXPERT.",
        )

    if intencion in {"PRESCRIPCION", "CONSULTA_CARENCIA"}:
        faltantes = [
            campo for campo in ("id_lote", "dias_para_cosecha")
            if datos_ext.get(campo) is None
        ]
        if faltantes:
            raise HTTPException(
                status_code=422,
                detail=f"Faltan datos obligatorios para {intencion}: {', '.join(faltantes)}.",
            )

    # Verificar que haya al menos un dato útil
    campos_clave = ["id_lote", "patologia_mencionada", "temperatura", "humedad_relativa",
                    "sintomas_reportados", "dias_para_cosecha", "porcentaje_area_afectada"]
    tiene_datos = any(
        datos_ext.get(c) not in (None, [], "")
        for c in campos_clave
    )
    if not tiene_datos:
        detalle = "No se pudieron extraer datos suficientes del reporte."
        if errores_extraccion:
            detalle += " Errores: " + "; ".join(errores_extraccion)
        raise HTTPException(status_code=400, detail=detalle)

    log.info("Extracción OK. Datos: %s", {k: v for k, v in datos_ext.items() if v is not None})

    # --- FASE 2: Módulo 1 — Diagnóstico (Julián) ---
    resultado_m1 = (
        modulo1_diagnostico(datos_ext)
        if "DIAGNOSTICO_LOTE" in modulos_ejecutar
        else {"disponible": False, "motivo": "No solicitado por el enrutamiento maestro."}
    )
    patologia_candidata = resultado_m1.get("patologia_candidata")
    datos_motor = completar_datos_desde_diagnostico(datos_ext, resultado_m1)
    log.info("Módulo 1 — Diagnóstico: patología=%s", patologia_candidata)

    # --- FASE 2: Módulo 2 — Riesgo Bioclimático (Alejo) ---
    resultado_m2 = (
        modulo2_riesgo_bioclimatico(datos_motor, patologia_candidata)
        if "RIESGO_BIOCLIMATICO" in modulos_ejecutar
        else {"disponible": False, "motivo": "No solicitado por el enrutamiento maestro."}
    )
    log.info("Módulo 2 — Riesgo bioclimático: favorabilidad=%s",
             resultado_m2.get("evaluacion", {}).get("favorabilidad_bioclimatica", "N/A"))

    # --- FASE 2: Módulo 3 — Prescripción Mamdani (Patricio) ---
    resultado_m3 = (
        modulo3_prescripcion(datos_motor)
        if "PRESCRIPCION" in modulos_ejecutar
        else {"disponible": False, "motivo": "No solicitado para esta intención."}
    )
    log.info("Módulo 3 — Prescripción: viabilidad=%s", resultado_m3.get("viabilidad_calculada"))

    # --- Ensamblado de trazabilidad End-to-End ---
    trazabilidad = {
        "orquestacion_pg3": {
            "prompt_maestro": "SYSTEM_PROMPT_MAESTRO",
            "intencion": intencion,
            "modulos_ejecutados": modulos_ejecutar,
            "entrada_unificada": True,
            "fuente_de_verdad": ["Neo4j", "reglas Python", "motor Mamdani"],
        },
        "fase_extraccion": {
            "datos_extraidos": datos_ext,
            "errores_validacion": errores_extraccion,
        },
        "datos_operativos": datos_motor,
        "modulo_1_diagnostico": resultado_m1,
        "modulo_2_riesgo_bioclimatico": resultado_m2,
        "modulo_3_prescripcion": resultado_m3,
    }

    # --- FASE 3: Explicación unificada (LLM) → Receta Agraria Digital ---
    try:
        receta_llm = llm_explicacion_unificada(trazabilidad)
        receta = (
            receta_llm
            if explicacion_grounded_valida(receta_llm, trazabilidad)
            else explicacion_plantilla(trazabilidad)
        )
    except RuntimeError as exc:
        log.error("Error controlado en LLM de explicación: %s", exc)
        receta = explicacion_plantilla(trazabilidad)

    log.info("Receta generada. Longitud: %d chars", len(receta))

    return ConsultaResponse(receta_agraria=receta, trazabilidad=trazabilidad)


# ---------------------------------------------------------------------------
# 11. Endpoints auxiliares
# ---------------------------------------------------------------------------
@app.get("/health", summary="Estado del sistema")
async def health():
    neo4j_ok = False
    if neo4j_driver is not None:
        try:
            neo4j_driver.verify_connectivity()
            neo4j_ok = True
        except Exception as exc:
            log.warning("Readiness de Neo4j falló: %s", exc)
    ready = bool(groq_client is not None and neo4j_ok and not startup_error)
    return {
        "status": "ok" if ready else "degraded",
        "ready": ready,
        "modelo_llm": GROQ_MODEL,
        "neo4j_connected": neo4j_ok,
    }


@app.get("/catalogo", summary="Catálogo del grafo Neo4j")
async def catalogo():
    """Devuelve patologías, etapas, químicos y lotes registrados en el grafo."""
    global CATALOGO
    if not CATALOGO:
        CATALOGO = cargar_catalogo()
    return CATALOGO


@app.post("/cargar_grafo", summary="Recarga el grafo de conocimiento")
async def cargar_grafo_endpoint(x_admin_token: str | None = Header(default=None)):
    """Recarga todos los nodos y relaciones PG2 + extensión bioclimática (idempotente)."""
    if not ADMIN_TOKEN or not x_admin_token or not hmac.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="Se requiere un token administrativo válido.")
    _cargar_grafo()
    global CATALOGO
    CATALOGO = cargar_catalogo()
    return {"status": "grafo sincronizado", "catalogo": CATALOGO}


@app.post("/transcribir", summary="Transcribe una consulta de voz")
async def transcribir_audio(audio: UploadFile = File(...)):
    """Convierte una grabación de voz en texto usando el modelo de transcripción."""
    tipos_admitidos = {
        "audio/webm",
        "audio/ogg",
        "audio/wav",
        "audio/x-wav",
        "audio/mpeg",
        "audio/mp4",
    }
    tipo_audio = (audio.content_type or "").split(";", 1)[0].lower()
    if tipo_audio not in tipos_admitidos:
        raise HTTPException(
            status_code=415,
            detail="Formato de audio no compatible. Usá WebM, OGG, WAV, MP3 o MP4.",
        )

    contenido = await audio.read()
    if not contenido:
        raise HTTPException(status_code=400, detail="El archivo de audio está vacío.")
    if len(contenido) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="El audio no puede superar los 25 MB.")

    try:
        respuesta = groq_client.audio.transcriptions.create(
            file=(audio.filename or "consulta.webm", contenido),
            model=GROQ_TRANSCRIPTION_MODEL,
            language="es",
            response_format="json",
        )
    except Exception as exc:
        log.error("Error en transcripción de audio: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="No se pudo transcribir el audio. Verificá la disponibilidad de Groq.",
        ) from exc

    texto = getattr(respuesta, "text", "") or ""
    if not texto.strip():
        raise HTTPException(status_code=422, detail="No se detectó voz en el audio.")
    return {"texto": texto.strip()}


app.mount("/", StaticFiles(directory="web", html=True), name="web")
