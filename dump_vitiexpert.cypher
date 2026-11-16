// VITI-EXPERT ? Dump de la base de conocimiento
// Generado a partir de CYPHER_PG2_BASE y EXTENSION_BIOCLIMATICA en main.py

// ============================================================
// CYPHER_PG2_BASE
// ============================================================
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

// ============================================================
// EXTENSION_BIOCLIMATICA[1]
// ============================================================
UNWIND [{n:"Brotación",o:1},{n:"Floración",o:2},{n:"Cuajado",o:3},{n:"Envero",o:4},{n:"Maduración",o:5}] AS et
       MERGE (e:EtapaFenologica {nombre: et.n}) SET e.orden = et.o

// ============================================================
// EXTENSION_BIOCLIMATICA[2]
// ============================================================
MATCH (p:Patologia_Fungica)
       UNWIND coalesce(p.etapas_susceptibles, []) AS etapa
       MATCH (e:EtapaFenologica {nombre: etapa})
       MERGE (p)-[:POSIBLE_EN]->(e)

// ============================================================
// EXTENSION_BIOCLIMATICA[3]
// ============================================================
MATCH (p:Patologia_Fungica {nombre: "Peronóspora"})
       MERGE (c:CondicionClimatica {id_condicion: "COND-PER"})
       SET c.temp_min = 10.0, c.temp_max = 30.0, c.temp_optima_min = 20.0, c.temp_optima_max = 25.0,
           c.humedad_min = 70.0, c.humedad_optima_min = 80.0, c.humedad_optima_max = 100.0,
           c.horas_mojado_min = 6, c.fuente = "Cuaderno de Conocimiento PI1 (Carobolante, 2026)"
       MERGE (p)-[:REQUIERE_CONDICION]->(c)

// ============================================================
// EXTENSION_BIOCLIMATICA[4]
// ============================================================
MATCH (p:Patologia_Fungica {nombre: "Oídio"})
       MERGE (c:CondicionClimatica {id_condicion: "COND-OID"})
       SET c.temp_min = 8.0, c.temp_max = 35.0, c.temp_optima_min = 22.0, c.temp_optima_max = 28.0,
           c.humedad_min = 40.0, c.humedad_max = 85.0, c.humedad_optima_min = 45.0, c.humedad_optima_max = 70.0,
           c.fuente = "Cuaderno de Conocimiento PI1 (Carobolante, 2026)"
       MERGE (p)-[:REQUIERE_CONDICION]->(c)

// ============================================================
// EXTENSION_BIOCLIMATICA[5]
// ============================================================
MATCH (p:Patologia_Fungica {nombre: "Botritis"})
       MERGE (c:CondicionClimatica {id_condicion: "COND-BOT"})
       SET c.temp_min = 5.0, c.temp_max = 30.0, c.temp_optima_min = 15.0, c.temp_optima_max = 25.0,
           c.humedad_min = 85.0, c.humedad_optima_min = 90.0, c.humedad_optima_max = 100.0,
           c.horas_mojado_min = 15, c.fuente = "Cuaderno de Conocimiento PI1 (Carobolante, 2026)"
       MERGE (p)-[:REQUIERE_CONDICION]->(c)

// ============================================================
// EXTENSION_BIOCLIMATICA[6]
// ============================================================
MERGE (e:EventoInhibitorio {nombre: "Viento Zonda"})
       SET e.tipo = "Desecación térmica", e.temp_disparo_min = 32.0, e.humedad_max_limite = 20.0,
           e.descripcion = "Viento cálido y seco que reduce la favorabilidad para el desarrollo fúngico"
       WITH e
       MATCH (p:Patologia_Fungica) WHERE p.nombre IN ["Peronóspora", "Oídio", "Botritis"]
       MERGE (e)-[:INHIBE]->(p)

// ============================================================
// EXTENSION_BIOCLIMATICA[7]
// ============================================================
MERGE (r:ReglaBioclimatica {codigo: "REG-BIO-INH-01"})
       SET r.nombre = "Inhibición por evento meteorológico", r.estrategia = "INHIBICION", r.prioridad = 1
       WITH r MATCH (p:Patologia_Fungica) WHERE p.nombre IN ["Peronóspora", "Oídio", "Botritis"]
       MERGE (r)-[:APLICA_A]->(p)

// ============================================================
// EXTENSION_BIOCLIMATICA[8]
// ============================================================
MATCH (p:Patologia_Fungica {nombre: "Peronóspora"})
       MERGE (r:ReglaBioclimatica {codigo: "REG-BIO-PER-01"})
       SET r.nombre = "Favorabilidad para Peronóspora", r.estrategia = "PERONOSPORA", r.prioridad = 2
       MERGE (r)-[:APLICA_A]->(p)

// ============================================================
// EXTENSION_BIOCLIMATICA[9]
// ============================================================
MATCH (p:Patologia_Fungica {nombre: "Oídio"})
       MERGE (r:ReglaBioclimatica {codigo: "REG-BIO-OID-01"})
       SET r.nombre = "Favorabilidad para Oídio", r.estrategia = "OIDIO", r.prioridad = 2
       MERGE (r)-[:APLICA_A]->(p)

// ============================================================
// EXTENSION_BIOCLIMATICA[10]
// ============================================================
MATCH (p:Patologia_Fungica {nombre: "Botritis"})
       MERGE (r:ReglaBioclimatica {codigo: "REG-BIO-BOT-01"})
       SET r.nombre = "Favorabilidad para Botritis", r.estrategia = "BOTRITIS", r.prioridad = 2
       MERGE (r)-[:APLICA_A]->(p)
